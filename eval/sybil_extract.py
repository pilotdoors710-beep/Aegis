"""Deterministic bounded extraction, with adjacency supplied by Common Crawl WebGraph.

No crawler or synthetic fallback. This pure selection step is also tested on analytical graphs.
The source adapter must expose full forward/reverse adjacency using original dataset IDs.
"""

import hashlib
import heapq
from collections.abc import Callable, Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class Extraction:
    ids: tuple[int, ...]
    edges: tuple[tuple[int, int], ...]
    original_outdegree: tuple[int, ...]
    retained_outdegree: tuple[int, ...]
    depth: tuple[int, ...]
    seed: int
    fanout: int
    maximum_depth: int
    node_limit: int
    edge_limit: int
    version: str = "seeded-neighborhood-v1"
    # Named sites added after sampling (Stage 5), with every link between them and the sample.
    # The anchor sample and its edge selection are exactly what they would be without them.
    included: tuple[int, ...] = ()


def extract(
    forward: Callable[[int], Iterable[int]],
    reverse: Callable[[int], Iterable[int]],
    anchors: tuple[int, ...],
    *,
    node_limit: int = 50000,
    edge_limit: int = 1000000,
    fanout: int = 128,
    maximum_depth: int = 4,
    seed: int = 1,
    include: Iterable[int] = (),
) -> Extraction:
    if len(set(anchors)) != len(anchors) or not anchors:
        raise ValueError("Distinct source anchors are required")
    if node_limit < len(anchors) or edge_limit < 1 or fanout < 1 or maximum_depth < 1:
        raise ValueError("Invalid extraction limits")
    if any(v < 0 for v in anchors):
        raise ValueError("Source IDs must be nonnegative")

    def priority(v: int):
        return hashlib.sha256(f"{seed}:{v}".encode("ascii")).digest(), v

    depth = dict.fromkeys(anchors, 0)
    frontier = sorted(anchors, key=priority)
    for level in range(1, maximum_depth + 1):
        candidates = set()
        for v in frontier:
            # Equal forward/reverse sampling quotas before the global seeded-hash selection.
            for adjacency in (forward, reverse):
                candidates.update(
                    heapq.nsmallest(
                        fanout,
                        (n for n in adjacency(v) if n not in depth),
                        key=priority,
                    )
                )
        frontier = heapq.nsmallest(node_limit - len(depth), candidates, key=priority)
        depth.update(dict.fromkeys(frontier, level))
        if not frontier or len(depth) == node_limit:
            break
    sampled = set(depth)
    # A named site joins only if a sampled site links to it; its depth is one past the
    # shallowest such linker. Sites already sampled are left as they are.
    included = []
    for v in sorted(set(include) - sampled):
        linkers = [depth[u] for u in reverse(v) if u in sampled]
        if linkers:
            included.append(v)
            depth[v] = min(linkers) + 1
    extra = set(included)
    ids = tuple(sorted(depth))
    original = {}
    named_edges = []

    def retained_edges():
        for u in ids:
            degree = 0
            # WebGraph adjacency is already unique. Do not materialize entire high-degree rows.
            for v in forward(u):
                degree += 1
                if v in extra or (u in extra and v in depth):
                    named_edges.append((u, v))  # kept in full, outside the edge limit
                elif v in sampled and u in sampled:
                    yield u, v
            original[u] = degree

    def edge_priority(edge):
        u, v = edge
        return hashlib.sha256(f"{seed}:{u}:{v}".encode("ascii")).digest(), edge

    edges = heapq.nsmallest(edge_limit, retained_edges(), key=edge_priority)
    edges = tuple(sorted(edges + named_edges))
    counts = dict.fromkeys(ids, 0)
    for u, _ in edges:
        counts[u] += 1
    return Extraction(
        ids,
        edges,
        tuple(original[v] for v in ids),
        tuple(counts[v] for v in ids),
        tuple(depth[v] for v in ids),
        seed,
        fanout,
        maximum_depth,
        node_limit,
        edge_limit,
        included=tuple(included),
    )
