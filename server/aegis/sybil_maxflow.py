"""Stage 4: Bounded Max-Flow / Min-Cut Bottleneck Witness (brief §14).

Computes an exact minimum website cut on a declared explanation subgraph (at most 2,500
nodes), with unit website capacities and one unit per anchor. Exact for that subgraph, and
for the whole graph when the subgraph holds every site on an anchor -> supporter path.
"""

from time import perf_counter
from typing import Literal

import numpy as np
import scipy.sparse as sp
from scipy.sparse.csgraph import breadth_first_order, maximum_flow, shortest_path

from aegis.schemas import SybilBottleneckWitness, SybilCutEdge
from aegis.sybil_scenario import AppliedScenario


def _supporters(scenario: AppliedScenario, shop: str) -> set[int]:
    return {v for v, shops in scenario.recommendations if shop in shops}


def _hops(node_count: int, links: np.ndarray, starts: list[int]) -> np.ndarray:
    """Breadth-first link distance from the nearest start (inf when unreachable)."""
    virtual = node_count  # one extra vertex linked to every start: a single BFS
    rows = np.concatenate((links[:, 0], np.full(len(starts), virtual)))
    cols = np.concatenate((links[:, 1], np.asarray(starts, dtype=np.int64)))
    adjacency = sp.csr_array(
        (np.ones(rows.size), (rows, cols)), shape=(node_count + 1, node_count + 1)
    )
    hops = shortest_path(adjacency, unweighted=True, indices=virtual)
    return hops[:node_count] - 1


def extract_explanation_subgraph(
    scenario: AppliedScenario,
    shop: Literal["A", "B"],
    max_nodes: int = 2500,
) -> tuple[tuple[int, ...], tuple[tuple[int, int], ...], bool]:
    """The anchors, the reachable supporters, then the sites on the shortest anchor ->
    supporter paths, up to max_nodes. `complete` is True when every site on any such path
    fits, so the cut is then exact for the whole scenario graph, not only the subgraph."""
    supporters = sorted(_supporters(scenario, shop))
    if not supporters:
        return (), (), True
    n = scenario.graph.node_count
    links = scenario.graph.canonical_edges
    from_anchors = _hops(n, links, list(scenario.anchors))
    to_supporters = _hops(n, links[:, ::-1], supporters)
    through = from_anchors + to_supporters  # finite only on some anchor -> supporter path
    anchors = sorted(scenario.anchors)
    required = [
        *[v for v in supporters if np.isfinite(from_anchors[v])],
        *[a for a in anchors if a not in set(supporters)],
    ]
    on_path = np.flatnonzero(np.isfinite(through))
    on_path = on_path[~np.isin(on_path, required)]
    on_path = on_path[np.lexsort((on_path, from_anchors[on_path], through[on_path]))]
    selected = [*required, *on_path.tolist()][:max_nodes]
    complete = len(required) + on_path.size <= max_nodes
    mask = np.zeros(n, dtype=bool)
    mask[selected] = True
    kept = links[mask[links[:, 0]] & mask[links[:, 1]]]
    return tuple(sorted(selected)), tuple(map(tuple, kept.tolist())), complete


def compute_bottleneck_witness(
    scenario: AppliedScenario,
    shop: Literal["A", "B"],
    max_subgraph_nodes: int = 2500,
) -> SybilBottleneckWitness:
    """Exact minimum website cut between the anchors and the shop's supporters.

    Each website is split into in -> out with capacity 1, so the cut is a set of websites and
    `cut_size == max_flow`. Links and the source/sink arcs get capacity larger than any flow
    (at most one unit per anchor), so they are never cut. `cut_edges` are the links entering a
    bottleneck website from the anchor side (the funnel into it, e.g. bought bridges into an
    attack's entry site), for drawing; they are not cut arcs.
    """
    started = perf_counter()
    nodes, edges, complete = extract_explanation_subgraph(
        scenario, shop, max_nodes=max_subgraph_nodes
    )
    if not nodes:
        return SybilBottleneckWitness(
            revision_id=scenario.revision.id,
            shop=shop,
            subgraph_nodes=0,
            subgraph_edges=0,
            complete=True,
            max_flow=0.0,
            cut_size=0,
            cut_edges=(),
            bottleneck_nodes=(),
            elapsed_ms=(perf_counter() - started) * 1000,
        )

    node_to_idx = {nid: i for i, nid in enumerate(nodes)}
    n = len(nodes)
    # node i: in-vertex i, out-vertex i + n; source 2n, sink 2n + 1
    source, sink = 2 * n, 2 * n + 1
    anchors = [node_to_idx[a] for a in scenario.anchors if a in node_to_idx]
    supporters = [node_to_idx[w] for w in _supporters(scenario, shop) if w in node_to_idx]
    big = len(anchors) + 1  # exceeds any possible flow

    rows = list(range(n))
    cols = [i + n for i in range(n)]
    caps = [1] * n
    for u, v in edges:
        rows.append(node_to_idx[u] + n)
        cols.append(node_to_idx[v])
        caps.append(big)
    rows += [source] * len(anchors) + [w + n for w in supporters]
    cols += anchors + [sink] * len(supporters)
    caps += [big] * (len(anchors) + len(supporters))
    capacity = sp.csr_array(
        (np.asarray(caps, dtype=np.int32), (rows, cols)), shape=(2 * n + 2, 2 * n + 2)
    )
    capacity.sum_duplicates()

    result = maximum_flow(capacity, source, sink)
    flow = result.flow.tocsr()  # antisymmetric: f[v, u] == -f[u, v]
    # Residual capacity: (cap - flow) on forward arcs, plus flow on reverse arcs (via -f).
    residual = (capacity - flow).tocsr()
    residual.data[residual.data < 0] = 0
    residual.eliminate_zeros()
    reachable = np.zeros(2 * n + 2, dtype=bool)
    reachable[breadth_first_order(residual, source, directed=True, return_predecessors=False)] = (
        True
    )

    bottleneck = [i for i in range(n) if reachable[i] and not reachable[i + n]]
    in_bottleneck = set(bottleneck)
    cut_edges = tuple(
        SybilCutEdge(source=scenario.ids[u], target=scenario.ids[v], capacity=1.0)
        for u, v in edges
        if node_to_idx[v] in in_bottleneck and reachable[node_to_idx[u] + n]
    )
    if len(bottleneck) != result.flow_value:
        raise ArithmeticError("Minimum cut does not match maximum flow")
    return SybilBottleneckWitness(
        revision_id=scenario.revision.id,
        shop=shop,
        subgraph_nodes=n,
        subgraph_edges=len(edges),
        complete=complete,
        max_flow=float(result.flow_value),
        cut_size=len(bottleneck),
        cut_edges=cut_edges,
        bottleneck_nodes=tuple(scenario.ids[nodes[i]] for i in bottleneck),
        elapsed_ms=(perf_counter() - started) * 1000,
    )
