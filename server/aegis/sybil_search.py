"""Stage 4: Automated Adversarial Attack Search (brief §8).

Capped at 500 proposals / 60 seconds, fixed seed, no LLM, same Challenge budget, no
optimality claim. Evaluates a seeded shuffle of attack configurations within 25 credits and
keeps the strongest one found against the target shop.
"""

import random
from time import perf_counter
from typing import Literal

from aegis.schemas import (
    SybilAttackSearchProposal,
    SybilAttackSearchRequest,
    SybilAttackSearchResult,
    SybilGenerate,
    SybilLink,
    SybilRecommendation,
    SybilScenarioCreate,
)
from aegis.sybil_runtime import passes_policy
from aegis.sybil_scenario import BaseGraph, apply, assess_scenario, generate

PATTERNS = ("dense", "clusters", "hub", "chain", "disconnected")
COUNTS = (10, 20, 50, 100, 200, 300)
DENSITIES = (0.05, 0.2, 0.5)
# (takeover kind, bridges): every combination fits the 25-credit Challenge budget.
SPENDS = (
    *(("none", b) for b in (0, 2, 4, 6, 8, 10, 12)),  # 2 credits per bridge
    *(("site", b) for b in (0, 4, 10)),  # 5 + 2b
    *(("anchor", b) for b in (0, 2, 5)),  # 15 + 2b
)


def takeover(raw: SybilScenarioCreate, site: str, target: Literal["A", "B"]) -> SybilScenarioCreate:
    """A compromised site links into the cluster and recommends the target itself."""
    entry = raw.injected_nodes[0]
    return raw.model_copy(
        update={
            "added_links": (*raw.added_links, SybilLink(source=site, target=entry)),
            "recommendations": (
                *raw.recommendations,
                SybilRecommendation(website=site, shop=target),
            ),
            "compromised": (site,),
        }
    )


def takeover_site(base: BaseGraph, kind: str, bridges: SybilScenarioCreate) -> str:
    """The highest trust-per-link site of the kind that is not already a bought bridge."""
    taken = {link.source for link in bridges.cooperating_links}
    anchors = set(base.anchors)
    pool = base.anchors if kind == "anchor" else base.ids
    degree = base.graph.original_outdegree
    eligible = [v for v in pool if v not in taken and (kind == "anchor" or v not in anchors)]
    if not eligible:
        raise ValueError("No website is left to take over")
    return min(
        eligible, key=lambda v: (-base.trust[base.index[v]] / (degree[base.index[v]] + 1), v)
    )


def search_adversarial_attack(
    base: BaseGraph,
    request: SybilAttackSearchRequest | None = None,
) -> SybilAttackSearchResult:
    """Bounded, deterministic heuristic search; the best found is not a proven worst case."""
    request = request or SybilAttackSearchRequest()
    target = request.target
    rng = random.Random(request.seed)
    started = perf_counter()

    grid = [
        (pattern, count, density, kind, bridges)
        for pattern in PATTERNS
        for count in COUNTS
        for density in (DENSITIES if pattern in ("dense", "clusters") else (0.0,))
        for kind, bridges in SPENDS
    ]
    rng.shuffle(grid)

    best: tuple[float, SybilAttackSearchProposal, SybilScenarioCreate, str, bool] | None = None
    history: list[SybilAttackSearchProposal] = []
    evaluated = 0
    stopped_reason: Literal["iteration_limit", "time_limit", "space_exhausted"] = "space_exhausted"
    for i, (pattern, count, density, kind, bridges) in enumerate(grid):
        if evaluated >= request.max_proposals:
            stopped_reason = "iteration_limit"
            break
        if perf_counter() - started >= request.max_seconds:
            stopped_reason = "time_limit"
            break
        config = SybilGenerate(
            count=count,
            seed=(request.seed + i) % 2**32,
            pattern=pattern,
            density=density,
            target=target,
            bridges=bridges,
        )
        label = pattern + (f"+{kind}-takeover" if kind != "none" else "")
        label += f"+{bridges}-bridges" if bridges else ""
        try:
            edits = generate(base.dataset_id, config, base)
            if kind != "none":
                edits = takeover(edits, takeover_site(base, kind, edits), target)
            scenario = apply(base, edits)
        except ValueError:  # e.g. a small graph has no site left to take over
            continue
        assessment = assess_scenario(base, scenario)
        evaluated += 1
        if assessment.scores is None:  # nonconverged: unavailable, never a score
            continue
        score = assessment.scores[target]
        proposal = SybilAttackSearchProposal(
            iteration=evaluated,
            pattern=label,
            count=count,
            credits=scenario.revision.budget.external_credits,
            score=round(score.total, 2),
            support=round(score.support, 4),
            withdrawal=round(score.withdrawal, 4),
            connection=round(score.connection, 4),
        )
        passed = passes_policy(score.total, score.support, score.withdrawal)
        # Rank by policy pass first, then score: passing the gate is what an attacker needs.
        if best is None or (passed, score.total) > (best[4], best[0]):
            best = (score.total, proposal, scenario.revision.edits, scenario.revision.id, passed)
            history.append(proposal)

    if best is None:
        raise ArithmeticError("No attack proposal produced a converged assessment")
    total, proposal, edits, revision_id, passed = best
    return SybilAttackSearchResult(
        dataset_id=base.dataset_id,
        target_shop=target,
        proposals_evaluated=evaluated,
        elapsed_s=round(perf_counter() - started, 3),
        stopped_reason=stopped_reason,
        best_score=round(total, 2),
        best_passed_policy=passed,
        best_proposal=proposal,
        best_scenario=edits,
        best_revision_id=revision_id,
        history=tuple(history[-50:]),
    )
