"""Stage 4: Bounded Max-Flow / Min-Cut Bottleneck Witness (brief §14).

Computes exact min-cut bottleneck on a declared explanation subgraph (at most 2,500 nodes),
with unit website capacities and one unit per anchor.
"""

from collections import deque
from time import perf_counter
from typing import Literal

import numpy as np
import scipy.sparse as sp
from scipy.sparse.csgraph import maximum_flow

from aegis.schemas import SybilBottleneckWitness, SybilCutEdge
from aegis.sybil_scenario import AppliedScenario, BaseGraph


def extract_explanation_subgraph(
    base: BaseGraph,
    scenario: AppliedScenario,
    shop: Literal["A", "B"],
    max_nodes: int = 2500,
) -> tuple[tuple[int, ...], tuple[tuple[int, int], ...]]:
    """Extract a bounded explanation subgraph (<= 2500 nodes) around anchors and shop supporters."""
    rec_dict = dict(scenario.recommendations)
    supporters = {v for v, shops in rec_dict.items() if shop in shops}
    anchor_set = set(scenario.anchors)

    if not supporters:
        return (), ()

    # Map scenario graph edges: forward and backward adjacency
    adj_forward: dict[int, list[int]] = {}
    adj_backward: dict[int, list[int]] = {}
    for u, v in scenario.graph.edges:
        adj_forward.setdefault(u, []).append(v)
        adj_backward.setdefault(v, []).append(u)

    # 1. Backward search from supporters up to 3 hops
    backward_reachable: set[int] = set(supporters)
    q_back = deque([(s, 0) for s in supporters])
    while q_back and len(backward_reachable) < max_nodes:
        node, dist = q_back.popleft()
        if dist >= 3:
            continue
        for pred in adj_backward.get(node, []):
            if pred not in backward_reachable:
                backward_reachable.add(pred)
                q_back.append((pred, dist + 1))
                if len(backward_reachable) >= max_nodes:
                    break

    # 2. Forward search from anchors up to 3 hops
    forward_reachable: set[int] = set(anchor_set)
    q_fwd = deque([(a, 0) for a in anchor_set])
    while q_fwd and len(forward_reachable) < max_nodes:
        node, dist = q_fwd.popleft()
        if dist >= 3:
            continue
        for succ in adj_forward.get(node, []):
            if succ not in forward_reachable:
                forward_reachable.add(succ)
                q_fwd.append((succ, dist + 1))
                if len(forward_reachable) >= max_nodes:
                    break

    # Connecting nodes: intersection first, then union prioritized by degree
    intersect = backward_reachable & forward_reachable
    selected = set(anchor_set) | set(supporters) | intersect

    if len(selected) > max_nodes:
        # Prioritize supporters, then anchors, then intersection
        priority = list(supporters) + [a for a in anchor_set if a not in supporters] + list(intersect - anchor_set - supporters)
        selected = set(priority[:max_nodes])
    elif len(selected) < max_nodes:
        # Fill with backward-reachable then forward-reachable nodes
        for node in backward_reachable:
            if len(selected) >= max_nodes:
                break
            selected.add(node)
        for node in forward_reachable:
            if len(selected) >= max_nodes:
                break
            selected.add(node)

    subgraph_nodes = tuple(sorted(selected))
    node_set = set(subgraph_nodes)
    subgraph_edges = tuple((u, v) for u, v in scenario.graph.edges if u in node_set and v in node_set)
    return subgraph_nodes, subgraph_edges


def compute_bottleneck_witness(
    base: BaseGraph,
    scenario: AppliedScenario,
    shop: Literal["A", "B"],
    max_subgraph_nodes: int = 2500,
) -> SybilBottleneckWitness:
    """Solve unit-capacity max-flow min-cut on the bounded explanation subgraph."""
    started = perf_counter()
    nodes, edges = extract_explanation_subgraph(base, scenario, shop, max_nodes=max_subgraph_nodes)
    elapsed_ms = (perf_counter() - started) * 1000

    if not nodes:
        return SybilBottleneckWitness(
            revision_id=scenario.revision.id,
            shop=shop,
            subgraph_nodes=0,
            subgraph_edges=0,
            max_flow=0.0,
            cut_size=0,
            cut_edges=(),
            bottleneck_nodes=(),
            elapsed_ms=elapsed_ms,
        )

    node_to_idx = {nid: i for i, nid in enumerate(nodes)}
    n = len(nodes)
    # Vertex splitting for unit website capacities:
    # node i -> in-node = i, out-node = i + n
    # Supersource S = 2*n, Supersink T = 2*n + 1
    total_vertices = 2 * n + 2
    s_idx = 2 * n
    t_idx = 2 * n + 1

    row_indices = []
    col_indices = []
    capacities = []

    def add_capacity(u: int, v: int, cap: int):
        row_indices.append(u)
        col_indices.append(v)
        capacities.append(cap)

    # 1. Unit capacity for each website (u_in -> u_out)
    for i in range(n):
        add_capacity(i, i + n, 1)

    # 2. Directed edges in subgraph: u_out -> v_in with high capacity (bottlenecks on nodes)
    # Unit capacity on edges also bounds cut
    for u, v in edges:
        u_idx = node_to_idx[u]
        v_idx = node_to_idx[v]
        add_capacity(u_idx + n, v_idx, 1000)

    # 3. Supersource to anchors (one unit per anchor)
    anchor_set = set(scenario.anchors)
    for a in anchor_set:
        if a in node_to_idx:
            add_capacity(s_idx, node_to_idx[a], 1)

    # 4. Supporters to supersink
    rec_dict = dict(scenario.recommendations)
    supporters = {v for v, shops in rec_dict.items() if shop in shops}
    for w in supporters:
        if w in node_to_idx:
            add_capacity(node_to_idx[w] + n, t_idx, 1000)

    cap_matrix = sp.csr_matrix(
        (capacities, (row_indices, col_indices)),
        shape=(total_vertices, total_vertices),
        dtype=np.int32,
    )

    # Solve max-flow
    res = maximum_flow(cap_matrix, s_idx, t_idx)
    flow_value = float(res.flow_value)

    # Find reachable vertices in the residual graph: residual_cap = cap - flow
    # In scipy csgraph, res.flow contains net flow on each edge
    # Residual capacity: cap - flow > 0 (forward), or flow > 0 (reverse)
    dense_flow = res.flow.toarray()
    dense_cap = cap_matrix.toarray()
    residual = dense_cap - dense_flow

    reachable = set()
    queue = deque([s_idx])
    reachable.add(s_idx)
    while queue:
        curr = queue.popleft()
        for nxt in range(total_vertices):
            if nxt not in reachable and residual[curr, nxt] > 0:
                reachable.add(nxt)
                queue.append(nxt)

    # Identify bottleneck nodes (u_in reachable, u_out not reachable)
    bottleneck_node_ids = []
    for i, orig_idx in enumerate(nodes):
        if i in reachable and (i + n) not in reachable:
            bottleneck_node_ids.append(scenario.ids[orig_idx])

    # Identify cut edges in original graph (u_out reachable, v_in not reachable)
    cut_edges_list = []
    for u, v in edges:
        u_idx = node_to_idx[u]
        v_idx = node_to_idx[v]
        if (u_idx + n) in reachable and v_idx not in reachable:
            cut_edges_list.append(
                SybilCutEdge(
                    source=scenario.ids[u],
                    target=scenario.ids[v],
                    capacity=1.0,
                )
            )

    elapsed_ms = (perf_counter() - started) * 1000

    return SybilBottleneckWitness(
        revision_id=scenario.revision.id,
        shop=shop,
        subgraph_nodes=len(nodes),
        subgraph_edges=len(edges),
        max_flow=flow_value,
        cut_size=len(cut_edges_list) + len(bottleneck_node_ids),
        cut_edges=tuple(cut_edges_list),
        bottleneck_nodes=tuple(bottleneck_node_ids),
        elapsed_ms=elapsed_ms,
    )
