"""Canonical, immutable graph interventions. Ownership ends at the numerical adapter."""

import hashlib
import json
import random
import re
from collections import Counter
from dataclasses import dataclass

from aegis.schemas import (
    SybilBudget,
    SybilGenerate,
    SybilLink,
    SybilRecommendation,
    SybilScenarioCreate,
    SybilScenarioRevision,
    SybilWeights,
)
from aegis.sybil import Assessment, Config, Graph, assess


@dataclass(frozen=True)
class BaseGraph:
    dataset_id: str
    content_hash: str
    ids: tuple[str, ...]
    graph: Graph
    anchors: tuple[str, ...]
    tau: float
    recommendations: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class AppliedScenario:
    revision: SybilScenarioRevision
    ids: tuple[str, ...]
    graph: Graph
    anchors: tuple[int, ...]
    recommendations: tuple[tuple[int, tuple[str, ...]], ...]


def assess_scenario(base: BaseGraph, scenario: AppliedScenario) -> Assessment:
    """Pass only mathematical inputs, never ownership or target labels, to the engine."""
    if scenario.revision.dataset_hash != base.content_hash:
        raise ValueError("Scenario does not belong to this dataset version")
    weights = scenario.revision.edits.weights
    return assess(
        scenario.graph,
        scenario.anchors,
        dict(scenario.recommendations),
        base.tau,
        Config(
            restart=scenario.revision.edits.restart,
            weights=(weights.base, weights.breadth, weights.withdrawal, weights.connection),
        ),
        candidate_shops=("A", "B"),
    )


def _links(values):
    return {(v.source, v.target) for v in values}


def _recommendations(values):
    return {(v.website, v.shop) for v in values}


def apply(base: BaseGraph, edits: SybilScenarioCreate) -> AppliedScenario:
    if edits.dataset_id != base.dataset_id:
        raise ValueError("Dataset does not match scenario")
    background = set(base.ids)
    injected = set(edits.injected_nodes)
    if len(background) != base.graph.node_count:
        raise ValueError("Dataset IDs must be unique and match graph size")
    if any(not re.fullmatch(r"sim:[a-zA-Z0-9_-]{1,100}", v) for v in injected):
        raise ValueError("Simulated IDs must use sim: followed by letters, numbers, _ or -")
    if background & injected:
        raise ValueError("Simulated IDs cannot replace background websites")
    ids = (*base.ids, *sorted(injected))
    index = {v: i for i, v in enumerate(ids)}
    original_links = {(base.ids[u], base.ids[v]) for u, v in base.graph.edges}
    added, removed = _links(edits.added_links), _links(edits.removed_links)
    cooperation = _links(edits.cooperating_links)
    compromised = set(edits.compromised)
    recs, removed_recs = (
        _recommendations(edits.recommendations),
        _recommendations(edits.removed_recommendations),
    )
    original_recs = set(base.recommendations)
    if not compromised <= background:
        raise ValueError("Only background websites can be compromised")
    if any(v not in index for edge in added | removed | cooperation for v in edge):
        raise ValueError("Unknown link endpoint")
    if any(v not in index for v, _ in recs | removed_recs):
        raise ValueError("Unknown recommending website")
    if added & removed or recs & removed_recs:
        raise ValueError("An active edit cannot both add and remove the same relationship")
    if not removed <= original_links or not removed_recs <= original_recs:
        raise ValueError("Cannot remove a relationship absent from the base dataset")
    # Redundant additions are no-ops; they neither change weights nor consume credit.
    added -= original_links
    recs -= original_recs
    if not cooperation <= added:
        raise ValueError("Cooperation must name an active added link")
    if any(u not in background or v not in injected for u, v in cooperation):
        raise ValueError("Cooperation only permits background-to-injected links")
    if any(u in compromised for u, _ in cooperation):
        raise ValueError("A compromised source does not also need cooperation credit")
    anchors = base.anchors if edits.anchors is None else tuple(sorted(set(edits.anchors)))
    if len(set(anchors)) != len(anchors) or len(anchors) < 2 or not set(anchors) <= set(ids):
        raise ValueError("At least two distinct, existing anchors are required")
    if edits.mode == "challenge":
        if edits.anchors is not None or edits.restart != 0.15 or edits.weights != SybilWeights():
            raise ValueError("Challenge scoring settings and anchors are fixed")
        for edge in added:
            u, _ = edge
            if u in background and u not in compromised and edge not in cooperation:
                raise ValueError("Background outgoing links require cooperation or compromise")
        if any(u not in compromised for u, _ in removed):
            raise ValueError("Removing background links requires compromise")
        if any(v in background and v not in compromised for v, _ in recs | removed_recs):
            raise ValueError("Background recommendation edits require compromise")
        changed = Counter(u for u, _ in added | removed)
        changed.update(v for v, _ in recs | removed_recs)
        if any(changed[v] > 100 for v in compromised):
            raise ValueError("A compromised website permits at most 100 changed relationships")
    final_links = (original_links - removed) | added
    internal_count = sum(u in injected and v in injected for u, v in final_links)
    credits = len(cooperation) * 2 + sum(15 if v in base.anchors else 5 for v in compromised)
    budget = SybilBudget(
        injected_websites=len(injected), internal_links=internal_count, external_credits=credits
    )
    if edits.mode == "challenge" and (
        len(injected) > budget.website_limit
        or internal_count > budget.internal_link_limit
        or credits > budget.credit_limit
    ):
        raise ValueError("Challenge attack budget exceeded")
    normalized = SybilScenarioCreate(
        dataset_id=base.dataset_id,
        mode=edits.mode,
        injected_nodes=tuple(sorted(injected)),
        added_links=tuple(SybilLink(source=u, target=v) for u, v in sorted(added)),
        removed_links=tuple(SybilLink(source=u, target=v) for u, v in sorted(removed)),
        recommendations=tuple(SybilRecommendation(website=v, shop=m) for v, m in sorted(recs)),
        removed_recommendations=tuple(
            SybilRecommendation(website=v, shop=m) for v, m in sorted(removed_recs)
        ),
        compromised=tuple(sorted(compromised)),
        cooperating_links=tuple(SybilLink(source=u, target=v) for u, v in sorted(cooperation)),
        anchors=None if edits.anchors is None else anchors,
        restart=edits.restart,
        weights=edits.weights,
    )
    canonical = json.dumps(
        {
            "dataset": base.content_hash,
            "policy": "sybil-challenge-v1",
            "edits": normalized.model_dump(mode="json"),
        },
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    revision = SybilScenarioRevision(
        id=hashlib.sha256(canonical.encode()).hexdigest(),
        dataset_id=base.dataset_id,
        dataset_hash=base.content_hash,
        edits=normalized,
        budget=budget,
    )
    degrees = list(base.graph.original_outdegree) + [0] * len(injected)
    for u, _ in removed:
        degrees[index[u]] -= 1
    for u, _ in added:
        degrees[index[u]] += 1
    final_recs = (original_recs - removed_recs) | recs
    recommendations = {}
    for v, shop in sorted(final_recs):
        recommendations.setdefault(index[v], []).append(shop)
    return AppliedScenario(
        revision,
        ids,
        Graph(
            len(ids), tuple(sorted((index[u], index[v]) for u, v in final_links)), tuple(degrees)
        ),
        tuple(index[v] for v in anchors),
        tuple((v, tuple(shops)) for v, shops in sorted(recommendations.items())),
    )


def generate(dataset_id: str, config: SybilGenerate) -> SybilScenarioCreate:
    """Bounded deterministic generation; rejection never silently clips dense attacks."""
    rng = random.Random(config.seed)
    nodes = tuple(f"sim:{config.seed}-{i}" for i in range(config.count))
    links = []
    for i in range(config.count):
        for j in range(config.count):
            if i == j:
                continue
            eligible = (
                config.pattern == "dense"
                or config.pattern == "clusters"
                and i % 4 == j % 4
                or config.pattern == "hub"
                and (i == 0 or j == 0)
                or config.pattern == "chain"
                and j == i + 1
            )
            if eligible and (config.pattern in ("hub", "chain") or rng.random() < config.density):
                links.append(SybilLink(source=nodes[i], target=nodes[j]))
                if len(links) > 100000:
                    raise ValueError(
                        "Generated attack exceeds 100,000 internal links; lower density"
                    )
    return SybilScenarioCreate(
        dataset_id=dataset_id,
        injected_nodes=nodes,
        added_links=tuple(links),
        recommendations=tuple(SybilRecommendation(website=v, shop=config.target) for v in nodes),
    )
