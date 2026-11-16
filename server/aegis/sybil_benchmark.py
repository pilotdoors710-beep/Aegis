"""Stage 4: Structural Benchmark Matrix (brief §14).

6 attack families x 3 sizes x 2 credit levels x 5 seeds = 180 attacks on Shop B, plus 30
controls = 210 scenarios. Each attack is judged by recommendation counts, ordinary PageRank,
seeded (anchor) support and the full sybil-v2 score (does Shop B beat Shop A?), and by the
graph policy (does Shop B pass without an ASK?), plus weight ablations of that policy.
"""

import random
from time import perf_counter

import numpy as np

from aegis.schemas import (
    SybilBenchmarkRow,
    SybilBenchmarkSummary,
    SybilGenerate,
    SybilRecommendation,
    SybilScenarioCreate,
)
from aegis.sybil import DEFAULT_CONFIG, propagate
from aegis.sybil_runtime import passes_policy
from aegis.sybil_scenario import AppliedScenario, BaseGraph, apply, assess_scenario, generate
from aegis.sybil_search import takeover, takeover_site

# "takeover": one non-anchor site compromised (5 credits), the rest of the level on bridges.
FAMILIES = ("dense", "clusters", "hub", "chain", "disconnected", "takeover")
SIZES = (10, 50, 300)
CREDITS = (12, 24)  # half and the full 25-credit Challenge budget (even: 2 per bridge)
SEEDS = (1, 2, 3, 4, 5)
CONTROL_SEEDS = tuple(range(1, 11))  # x 3 sizes = 30 controls
# Score weights (base, breadth, withdrawal, connection); the policy thresholds stay fixed.
ABLATIONS = {
    "support_only": (1.0, 0.0, 0.0, 0.0),
    "no_breadth": (0.5, 0.0, 0.25, 0.25),
    "no_withdrawal": (0.5, 0.25, 0.0, 0.25),
    "no_connection": (0.5, 0.25, 0.25, 0.0),
}
DISCLOSURE = (
    "Structural benchmark on the imported graph with generated attacks. Controls are random "
    "real websites recommending Shop B (research mode); they are not verified honest. "
    "No optimality or safety guarantee."
)


def _attack(base: BaseGraph, family: str, size: int, credits: int, seed: int):
    pattern = "dense" if family == "takeover" else family
    spend = credits - 5 if family == "takeover" else credits
    config = SybilGenerate(
        count=size,
        seed=seed,
        pattern=pattern,
        density=0.15 if pattern in ("dense", "clusters") else 0.0,
        target="B",
        bridges=spend // 2,
    )
    edits = generate(base.dataset_id, config, base)
    if family == "takeover":
        edits = takeover(edits, takeover_site(base, "site", edits), "B")
    return edits


def _control(base: BaseGraph, size: int, seed: int) -> SybilScenarioCreate:
    """Shop B recommended only by `size` random real non-anchor websites (its own removed)."""
    original = [v for v, shop in base.recommendations if shop == "B"]
    excluded = {*base.anchors, *original}
    pool = [v for v in base.ids if v not in excluded]
    chosen = random.Random(seed).sample(pool, size)
    return SybilScenarioCreate(
        dataset_id=base.dataset_id,
        mode="research",
        recommendations=tuple(SybilRecommendation(website=v, shop="B") for v in chosen),
        removed_recommendations=tuple(SybilRecommendation(website=v, shop="B") for v in original),
    )


def _ordinary_pagerank(scenario: AppliedScenario) -> dict[str, float]:
    """Uniform-restart PageRank on the same transition matrix, summed like seeded support."""
    n = scenario.graph.node_count
    restart = np.zeros(n + 1)
    restart[:n] = 1 / n
    result = propagate(scenario.graph.transition(), restart, DEFAULT_CONFIG)
    if not result.converged:
        raise ArithmeticError("Ordinary PageRank did not converge")
    totals = {"A": 0.0, "B": 0.0}
    for v, shops in scenario.recommendations:
        for shop in shops:
            totals[shop] += float(result.mass[v]) / len(shops)
    return totals


def _row(base: BaseGraph, edits, family: str, size: int, credits: int, seed: int):
    scenario = apply(base, edits)
    assessment = assess_scenario(base, scenario)
    common = dict(
        family=family,
        size=size,
        credits=credits,
        credits_used=scenario.revision.budget.external_credits,
        seed=seed,
    )
    if assessment.scores is None:
        return SybilBenchmarkRow(**common, converged=False), {}
    a, b = assessment.scores["A"], assessment.scores["B"]
    pagerank = _ordinary_pagerank(scenario)
    ablations = {
        name: passes_policy(
            100 * b.support * float(np.dot(w, (1, b.breadth, b.withdrawal, b.connection))),
            b.support,
            b.withdrawal,
        )
        for name, w in ABLATIONS.items()
    }
    ablations["no_withdrawal_floor"] = passes_policy(b.total, b.support, 1.0)
    row = SybilBenchmarkRow(
        **common,
        converged=True,
        recommendation_count=b.count,
        ordinary_pagerank=pagerank["B"],
        trust_weighted_support=b.mass,
        support=b.support,
        breadth=b.breadth,
        withdrawal=b.withdrawal,
        connection=b.connection,
        total_robustness=b.total,
        count_beats_a=b.count > a.count,
        pagerank_beats_a=pagerank["B"] > pagerank["A"],
        support_beats_a=b.mass > a.mass,
        score_beats_a=b.total > a.total,
        passed_policy=passes_policy(b.total, b.support, b.withdrawal),
    )
    return row, ablations


def _rate(rows: list[SybilBenchmarkRow], field: str) -> float:
    done = [r for r in rows if r.converged]
    return round(sum(bool(getattr(r, field)) for r in done) / max(1, len(done)), 4)


def run_structural_benchmark(base: BaseGraph, sample_only: bool = False) -> SybilBenchmarkSummary:
    """The 210-scenario matrix; `sample_only` runs one seed (36 attacks + 6 controls)."""
    started = perf_counter()
    seeds = SEEDS[:1] if sample_only else SEEDS
    rows: list[SybilBenchmarkRow] = []
    ablation_passes = {name: 0 for name in (*ABLATIONS, "no_withdrawal_floor")}
    for family in FAMILIES:
        for size in SIZES:
            for credits in CREDITS:
                for seed in seeds:
                    edits = _attack(base, family, size, credits, seed)
                    row, ablations = _row(base, edits, family, size, credits, seed)
                    rows.append(row)
                    for name, passed in ablations.items():
                        ablation_passes[name] += passed

    reference, _ = _row(base, SybilScenarioCreate(dataset_id=base.dataset_id), "none", 0, 0, 0)
    controls: list[SybilBenchmarkRow] = []
    for size in SIZES:
        for seed in CONTROL_SEEDS[:2] if sample_only else CONTROL_SEEDS:
            row, _ = _row(base, _control(base, size, seed), "control", size, 0, seed)
            controls.append(row)

    converged = max(1, sum(r.converged for r in rows))
    return SybilBenchmarkSummary(
        total_scenarios=len(rows) + len(controls),
        attacks_tested=len(rows),
        controls_tested=len(controls),
        unavailable=sum(not r.converged for r in (*rows, *controls)),
        count_beats_a_rate=_rate(rows, "count_beats_a"),
        pagerank_beats_a_rate=_rate(rows, "pagerank_beats_a"),
        support_beats_a_rate=_rate(rows, "support_beats_a"),
        score_beats_a_rate=_rate(rows, "score_beats_a"),
        policy_pass_rate=_rate(rows, "passed_policy"),
        ablation_policy_pass_rates={
            name: round(count / converged, 4) for name, count in ablation_passes.items()
        },
        control_policy_pass_rate=_rate(controls, "passed_policy"),
        rows=tuple(rows),
        controls=tuple(controls),
        reference=reference,
        elapsed_s=round(perf_counter() - started, 2),
        disclosure=DISCLOSURE,
    )
