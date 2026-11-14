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
    ids = tuple(sorted(depth))
    original = {}

    def retained_edges():
        for u in ids:
            degree = 0
            # WebGraph adjacency is already unique. Do not materialize entire high-degree rows.
            for v in forward(u):
                degree += 1
                if v in depth:
                    yield u, v
            original[u] = degree

    def edge_priority(edge):
        u, v = edge
        return hashlib.sha256(f"{seed}:{u}:{v}".encode("ascii")).digest(), edge

    edges = tuple(sorted(heapq.nsmallest(edge_limit, retained_edges(), key=edge_priority)))
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
    )
