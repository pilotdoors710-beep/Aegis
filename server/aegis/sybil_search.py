"""Stage 4: Automated Adversarial Attack Search (brief §14).

Capped at 500 proposals / 60 seconds, fixed seed, no LLM, same Challenge budget,
no optimality claim. Explores topological configurations within 25 credits to
find the strongest attack on a target shop.
"""

import random
from time import perf_counter
from typing import Literal

from aegis.schemas import (
    SybilAttackSearchProposal,
    SybilAttackSearchRequest,
    SybilAttackSearchResult,
    SybilGenerate,
    SybilScenarioCreate,
)
from aegis.sybil_scenario import BaseGraph, apply, assess_scenario, generate


def search_adversarial_attack(
    base: BaseGraph,
    request: SybilAttackSearchRequest | None = None,
) -> SybilAttackSearchResult:
    """Bounded, deterministic heuristic search for worst-case attack topology."""
    if request is None:
        request = SybilAttackSearchRequest()

    target = request.target
    seed = request.seed
    max_proposals = min(500, max(1, request.max_proposals))
    max_seconds = min(60.0, max(0.001, request.max_seconds))

    rng = random.Random(seed)
    started = perf_counter()

    # Pre-identify reputable candidate bridge sources from the base graph
    anchors = set(base.anchors)
    has_incoming = {v for _, v in base.graph.edges}
    bridge_candidates = [
        base.ids[i]
        for i in range(len(base.ids))
        if base.ids[i] not in anchors and i in has_incoming
    ]
    bridge_candidates.sort(key=lambda nid: (-base.graph.original_outdegree[base.index[nid]], nid))
    if len(bridge_candidates) < 12:
        extra = [
            base.ids[i]
            for i in range(len(base.ids))
            if base.ids[i] not in anchors and base.ids[i] not in bridge_candidates
        ]
        bridge_candidates.extend(extra)

    patterns = ("dense", "clusters", "hub", "chain", "disconnected")
    counts = (20, 50, 100, 200, 300)
    densities = (0.05, 0.1, 0.25, 0.5, 0.8)
    bridge_options = (0, 1, 2, 4, 6, 8, 10, 12)

    # Initialize baseline attack configuration
    gen_config_base = SybilGenerate(
        count=100, seed=seed, pattern="dense", density=0.1, target=target, bridges=0
    )
    best_scenario = generate(base.dataset_id, gen_config_base, base)
    scenario_base = apply(base, best_scenario)
    assess_base = assess_scenario(base, scenario_base)
    score_base = assess_base.scores[target]
    best_score = score_base.total
    best_revision_id = scenario_base.revision.id

    best_proposal = SybilAttackSearchProposal(
        iteration=0,
        pattern="dense",
        count=100,
        credits=0,
        score=round(score_base.total, 2),
        support=round(score_base.support, 4),
        withdrawal=round(score_base.withdrawal, 4),
        connection=round(score_base.connection, 4),
    )
    history: list[SybilAttackSearchProposal] = [best_proposal]

    proposals_evaluated = 1
    stopped_reason: Literal["iteration_limit", "time_limit", "budget_exhausted"] = "iteration_limit"

    for i in range(1, max_proposals):
        if perf_counter() - started >= max_seconds:
            stopped_reason = "time_limit"
            break

        # Generate proposal: structured parameter variation
        if i < 40:
            # Systematic sweep over patterns and bridges
            pat = patterns[i % len(patterns)]
            b_cnt = bridge_options[(i // len(patterns)) % len(bridge_options)]
            c_cnt = counts[(i // (len(patterns) * len(bridge_options))) % len(counts)]
            gen_config = SybilGenerate(
                count=c_cnt, seed=seed + i, pattern=pat, density=0.2, target=target, bridges=b_cnt
            )
            proposal_edits = generate(base.dataset_id, gen_config, base)
            pattern_label = pat
            credit_cost = b_cnt * 2
        elif i < 70 and len(bridge_candidates) >= 2:
            # Takeover variations: 1 non-anchor takeover (5 credits) + up to 10 bridges (20 credits)
            b_cnt = min(10, (25 - 5) // 2)
            c_cnt = counts[i % len(counts)]
            pat = patterns[i % len(patterns)]
            compromised_node = bridge_candidates[0]
            gen_config = SybilGenerate(
                count=c_cnt, seed=seed + i, pattern=pat, density=0.25, target=target, bridges=b_cnt
            )
            raw = generate(base.dataset_id, gen_config, base)
            proposal_edits = SybilScenarioCreate(
                dataset_id=base.dataset_id,
                injected_nodes=raw.injected_nodes,
                added_links=raw.added_links,
                recommendations=raw.recommendations,
                cooperating_links=raw.cooperating_links,
                compromised=(compromised_node,),
            )
            pattern_label = f"{pat}+takeover(1)"
            credit_cost = 5 + b_cnt * 2
        elif i < 100 and base.anchors:
            # Anchor takeover: 1 anchor takeover (15 credits) + up to 5 bridges (10 credits)
            b_cnt = min(5, (25 - 15) // 2)
            c_cnt = counts[i % len(counts)]
            pat = patterns[i % len(patterns)]
            anchor_node = base.anchors[0]
            gen_config = SybilGenerate(
                count=c_cnt, seed=seed + i, pattern=pat, density=0.2, target=target, bridges=b_cnt
            )
            raw = generate(base.dataset_id, gen_config, base)
            proposal_edits = SybilScenarioCreate(
                dataset_id=base.dataset_id,
                injected_nodes=raw.injected_nodes,
                added_links=raw.added_links,
                recommendations=raw.recommendations,
                cooperating_links=raw.cooperating_links,
                compromised=(anchor_node,),
            )
            pattern_label = f"{pat}+anchor_takeover"
            credit_cost = 15 + b_cnt * 2
        else:
            # Local perturbations: random mutation
            pat = rng.choice(patterns)
            b_cnt = rng.choice(bridge_options)
            c_cnt = rng.choice(counts)
            dens = rng.choice(densities)
            gen_config = SybilGenerate(
                count=c_cnt, seed=seed + i, pattern=pat, density=dens, target=target, bridges=b_cnt
            )
            proposal_edits = generate(base.dataset_id, gen_config, base)
            pattern_label = pat
            credit_cost = b_cnt * 2

        try:
            scenario = apply(base, proposal_edits)
            assessment = assess_scenario(base, scenario)
            score_obj = assessment.scores[target]
            total = score_obj.total
            supp = score_obj.support
            withdr = score_obj.withdrawal
            conn = score_obj.connection
        except Exception:
            continue

        proposals_evaluated += 1

        proposal = SybilAttackSearchProposal(
            iteration=proposals_evaluated,
            pattern=pattern_label,
            count=len(proposal_edits.injected_nodes),
            credits=credit_cost,
            score=round(total, 2),
            support=round(supp, 4),
            withdrawal=round(withdr, 4),
            connection=round(conn, 4),
        )

        is_improvement = total > best_score
        if is_improvement:
            best_score = total
            best_proposal = proposal
            best_scenario = proposal_edits
            best_revision_id = scenario.revision.id
            history.append(proposal)
        elif len(history) < 25 and proposals_evaluated % 10 == 0:
            history.append(proposal)

    elapsed_s = perf_counter() - started

    assert best_proposal is not None and best_scenario is not None

    return SybilAttackSearchResult(
        dataset_id=base.dataset_id,
        target_shop=target,
        proposals_evaluated=proposals_evaluated,
        elapsed_s=round(elapsed_s, 3),
        stopped_reason=stopped_reason,
        best_score=round(best_score, 2),
        best_proposal=best_proposal,
        best_scenario=best_scenario,
        best_revision_id=best_revision_id,
        history=tuple(history[:50]),
    )
