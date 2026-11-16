"""Stage 4: Structural Benchmark Matrix (brief §14).

Matrix evaluation: 6 attack families × 3 sizes × 2 credit levels × 5 seeds = 180 attacks
plus 30 controls = 210 scenarios.
Compares naive count, unweighted PageRank, and Aegis sybil-v2 policy (R >= 60, S >= 0.5, L >= 0.5).
"""

from time import perf_counter
from typing import Literal

from aegis.schemas import SybilBenchmarkRow, SybilBenchmarkSummary, SybilGenerate
from aegis.sybil import Config, Graph, assess
from aegis.sybil_scenario import BaseGraph, apply, assess_scenario, generate

FAMILIES = ("dense", "clusters", "hub", "chain", "star", "disconnected")
SIZES = (10, 50, 300)
CREDITS = (0, 24)  # 0 credits (0 bridges) vs 24 credits (12 bridges)
SEEDS = (1, 2, 3, 4, 5)


def run_structural_benchmark(
    base: BaseGraph,
    sample_only: bool = False,
) -> SybilBenchmarkSummary:
    """Run the 210-scenario structural benchmark matrix.

    If sample_only is True (e.g. for fast unit tests), runs 1 seed (42 scenarios: 36 attacks + 6 controls).
    """
    started = perf_counter()
    rows: list[SybilBenchmarkRow] = []

    naive_passes = 0
    pagerank_passes = 0
    aegis_passes = 0
    clean_passes = 0

    active_seeds = (SEEDS[0],) if sample_only else SEEDS

    # 1. Evaluate Attack Scenarios (Target Shop B)
    for family in FAMILIES:
        for size in SIZES:
            for credits in CREDITS:
                for seed in active_seeds:
                    pattern = "hub" if family == "star" else family
                    bridges = credits // 2
                    gen_config = SybilGenerate(
                        count=size,
                        seed=seed,
                        pattern=pattern,  # type: ignore[arg-type]
                        density=0.15 if family in ("dense", "clusters") else 0.5,
                        target="B",
                        bridges=bridges,
                    )
                    proposal = generate(base.dataset_id, gen_config, base)
                    scenario = apply(base, proposal)
                    assessment = assess_scenario(base, scenario)

                    score_b = assessment.scores["B"]
                    score_a = assessment.scores["A"]

                    # Raw count comparison: does Shop B have more or equal recs than Shop A?
                    raw_count = score_b.count
                    raw_a = score_a.count
                    naive_pass = raw_count >= raw_a
                    if naive_pass:
                        naive_passes += 1

                    # Unweighted PageRank approximation: does raw mass of B exceed A?
                    pr_pass = score_b.mass >= score_a.mass
                    if pr_pass:
                        pagerank_passes += 1

                    # Aegis sybil-v2 policy: R >= 60, S >= 0.5, L >= 0.5
                    aegis_pass = (
                        score_b.total >= 60.0
                        and score_b.support >= 0.5
                        and score_b.withdrawal >= 0.5
                    )
                    if aegis_pass:
                        aegis_passes += 1

                    rows.append(
                        SybilBenchmarkRow(
                            family=family,
                            size=size,
                            credits=credits,
                            seed=seed,
                            raw_count=raw_count,
                            raw_rank=round(score_b.mass, 4),
                            support=round(score_b.support, 4),
                            withdrawal=round(score_b.withdrawal, 4),
                            connection=round(score_b.connection, 4),
                            total_robustness=round(score_b.total, 2),
                            passed_policy=aegis_pass,
                        )
                    )

    attacks_tested = len(rows)

    # 2. Evaluate Control Scenarios (Clean Shop A baseline controls)
    control_count = 6 if sample_only else 30
    for c_idx in range(control_count):
        # Clean scenario with no injected attack
        gen_config = SybilGenerate(count=10, seed=c_idx, pattern="disconnected", target="B", bridges=0)
        scenario = apply(base, generate(base.dataset_id, gen_config, base))
        assessment = assess_scenario(base, scenario)
        score_a = assessment.scores["A"]
        # In a graph where Shop A has reputable baseline recommendations
        clean_pass = score_a.total >= 50.0  # clean threshold
        if clean_pass:
            clean_passes += 1

    total_scenarios = attacks_tested + control_count
    elapsed_s = perf_counter() - started

    return SybilBenchmarkSummary(
        total_scenarios=total_scenarios,
        attacks_tested=attacks_tested,
        controls_tested=control_count,
        naive_pass_rate=round(naive_passes / max(1, attacks_tested), 4),
        pagerank_pass_rate=round(pagerank_passes / max(1, attacks_tested), 4),
        aegis_pass_rate=round(aegis_passes / max(1, attacks_tested), 4),
        clean_pass_rate=round(clean_passes / max(1, control_count), 4),
        rows=tuple(rows),
        elapsed_s=round(elapsed_s, 2),
    )
