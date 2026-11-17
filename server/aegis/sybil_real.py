"""Stage 5: look up a real domain in the imported Common Crawl sample and score it.

The domain is scored on its own trust with the unchanged sybil-v2 formula: it is passed to
`assess` as the only supporter of a one-off target, so its mass is exactly its own anchor
trust. That is the quantity tau was frozen on (the clean 95th percentile of node trust), so
S, D, L and E mean the same thing here as for the playground shops. Treating every in-link as
a separate "recommendation" would add up their full trust and push almost every site to S~1.

No network access: the query is parsed, never fetched.
"""

from collections import deque
from dataclasses import dataclass
from time import perf_counter
from typing import Any

import numpy as np
from scipy.sparse import coo_array, csr_array

from aegis.schemas import (
    SybilAnchorPath,
    SybilGraphEvidence,
    SybilRealDomainEvidence,
    SybilShopScore,
)
from aegis.sybil import assess
from aegis.sybil_resolver import candidates, parse_host, shared_platform

POLICY = SybilGraphEvidence(revision_id="0" * 64, assessment_id="0" * 64, shops={})
MAX_PATH_HOPS = 6
TOP_LINKERS = 8
_TARGET = "site"


@dataclass(frozen=True)
class DomainIndex:
    by_domain: dict[str, int]
    domains: tuple[str, ...]
    incoming: csr_array  # row v lists the sites linking to v
    anchors: tuple[int, ...]
    trust: np.ndarray  # clean-graph trust, for ordering linkers and paths
    outdegree: np.ndarray  # original outdegree, sampled or not


_indexes: dict[str, DomainIndex] = {}


def domain_index(dataset: Any) -> DomainIndex:
    """Built once per dataset version; the API warms it at startup."""
    base = dataset.base
    index = _indexes.get(base.content_hash)
    if index is None:
        n = base.graph.node_count
        edges = base.graph.canonical_edges
        incoming = coo_array(
            (np.ones(len(edges), dtype=np.int8), (edges[:, 1], edges[:, 0])), shape=(n, n)
        ).tocsr()
        incoming.sort_indices()
        domains = tuple(v.domain for v in dataset.nodes)
        index = DomainIndex(
            by_domain={d: i for i, d in enumerate(domains)},
            domains=domains,
            incoming=incoming,
            anchors=tuple(base.index[a] for a in base.anchors),
            trust=base.trust,
            outdegree=np.asarray(base.graph.original_outdegree, dtype=np.float64),
        )
        _indexes.clear()
        _indexes[base.content_hash] = index
    return index


def _linkers(index: DomainIndex, node: int) -> np.ndarray:
    return index.incoming.indices[index.incoming.indptr[node] : index.incoming.indptr[node + 1]]


def _by_flow(index: DomainIndex, sites: np.ndarray) -> np.ndarray:
    """Sites ordered by the trust each sends along one link, highest first (ties by index)."""
    flow = index.trust[sites] / np.maximum(index.outdegree[sites], 1)
    return sites[np.lexsort((sites, -flow))]


def anchor_paths(index: DomainIndex, node: int, limit: int) -> tuple[SybilAnchorPath, ...]:
    """Shortest link chains from distinct anchors to the node (backward BFS, at most
    MAX_PATH_HOPS links, no other anchor in between). Among equally short chains, the
    higher-trust linker is preferred."""
    anchors = set(index.anchors)
    if node in anchors:
        name = index.domains[node]
        return (SybilAnchorPath(anchor=name, hops=(name,)),)
    toward = {node: node}  # site -> the next site on its chain to the node
    frontier = deque([(node, 0)])
    found: list[int] = []
    while frontier and len(found) < limit:
        site, hops = frontier.popleft()
        if hops == MAX_PATH_HOPS:
            continue
        for prev in _by_flow(index, _linkers(index, site)).tolist():
            if prev in toward:
                continue
            toward[prev] = site
            if prev in anchors:  # a chain ends at its first anchor, never passes through one
                found.append(prev)
                if len(found) == limit:
                    break
                continue
            frontier.append((prev, hops + 1))
    paths = []
    for anchor in found:
        chain = [anchor]
        while chain[-1] != node:
            chain.append(toward[chain[-1]])
        paths.append(
            SybilAnchorPath(
                anchor=index.domains[anchor], hops=tuple(index.domains[i] for i in chain)
            )
        )
    return tuple(paths)


def score_site(dataset: Any, index: DomainIndex, node: int) -> SybilShopScore | None:
    """sybil-v2 on the site's own trust; None when propagation did not converge."""
    base = dataset.base
    result = assess(base.graph, index.anchors, {node: (_TARGET,)}, base.tau)
    if result.scores is None:
        return None
    s = result.scores[_TARGET]
    return SybilShopScore(
        recommendation_count=len(_linkers(index, node)),
        trust_weighted_support=s.mass,
        structural_support=s.support,
        effective_anchors=s.effective_anchors,
        anchor_breadth=s.breadth,
        anchor_withdrawal_resilience=s.withdrawal,
        tested_connection_resilience=s.connection,
        total_robustness=s.total,
        cut_sources=tuple(index.domains[u] for u in s.cut_sources),
    )


def _verdict(score: SybilShopScore) -> tuple[bool, str]:
    r = score.total_robustness
    s = score.structural_support
    lw = score.anchor_withdrawal_resilience
    if POLICY.passes(r, s, lw):
        return True, "Passes every check."
    short = []
    if r < POLICY.minimum_total:
        short.append(f"score {r:.1f}, needs {POLICY.minimum_total:g}")
    if s < POLICY.minimum_support:
        short.append(f"trust {s:.0%}, needs {POLICY.minimum_support:.0%}")
    if lw < POLICY.minimum_withdrawal:
        short.append(f"without top trusted site {lw:.0%}, needs {POLICY.minimum_withdrawal:.0%}")
    return False, f"Too low: {'; '.join(short)}."


def evaluate_real_domain(dataset: Any, query: str, max_paths: int = 3) -> SybilRealDomainEvidence:
    started = perf_counter()
    host, path = parse_host(query)  # ValueError -> 422
    index = domain_index(dataset)
    matched = next((c for c in candidates(host) if c in index.by_domain), None)
    common = {
        "dataset_id": dataset.manifest.id,
        "query": query.strip(),
        "host": host,
        "policy": POLICY.policy_text(),
    }

    def done(**fields: Any) -> SybilRealDomainEvidence:
        elapsed = (perf_counter() - started) * 1000
        return SybilRealDomainEvidence(**common, **fields, elapsed_ms=round(elapsed, 2))

    platform = shared_platform(host, path, matched)
    if platform:
        return done(
            domain=None,
            status="shared_platform",
            policy_passed=False,
            reason=f"One seller on {platform}. The platform's links don't vouch for its sellers.",
        )
    if matched is None:
        return done(
            domain=None,
            status="not_in_sample",
            policy_passed=False,
            reason=f"Not among the {len(index.domains):,} sampled sites, so no link evidence.",
        )

    node = index.by_domain[matched]
    info = dataset.nodes[node]
    linkers = _linkers(index, node)
    score = score_site(dataset, index, node)
    facts = {
        "domain": matched,
        "links_in": len(linkers),
        "links_out": info.original_outdegree,
        "depth": info.depth,
        "top_linkers": tuple(index.domains[i] for i in _by_flow(index, linkers)[:TOP_LINKERS]),
        "anchor_paths": anchor_paths(index, node, max_paths),
        "scores": score,
    }
    if node in index.anchors:
        return done(
            **facts,
            status="anchor",
            policy_passed=True,
            reason="One of the eight trusted starting sites.",
        )
    if score is None:
        return done(
            **facts,
            status="unavailable",
            policy_passed=False,
            reason="The score did not settle, so it cannot pass.",
        )
    passed, reason = _verdict(score)
    return done(**facts, status="scored", policy_passed=passed, reason=reason)
