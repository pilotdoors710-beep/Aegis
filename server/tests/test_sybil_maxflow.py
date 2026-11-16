import random
from collections import deque

import pytest

from aegis.schemas import SybilLink, SybilRecommendation, SybilScenarioCreate
from aegis.sybil import Graph
from aegis.sybil_maxflow import compute_bottleneck_witness, extract_explanation_subgraph
from aegis.sybil_scenario import BaseGraph, apply


@pytest.fixture
def base_graph():
    # Anchors 'a' and 'b' link to 'c'. 'c' recommends Shop A. 'd' is disconnected.
    return BaseGraph(
        "test",
        "hash-v1",
        ("a", "b", "c", "d"),
        Graph(4, ((0, 2), (1, 2)), (2, 1, 0, 0)),
        ("a", "b"),
        0.1,
        (("c", "A"),),
    )


def test_bottleneck_witness_clean_shop(base_graph):
    scenario = apply(base_graph, SybilScenarioCreate(dataset_id="test"))
    witness = compute_bottleneck_witness(scenario, "A")
    assert witness.subgraph_nodes >= 3  # a, b, c
    assert witness.max_flow == 1.0  # unit capacity on 'c'
    assert witness.bottleneck_nodes == ("c",)
    assert witness.cut_size == 1


def test_anchors_are_the_cut_when_they_support_directly(base_graph):
    # Both anchors recommend A: two disjoint units. The old network capped each anchor twice,
    # so the cut sat on the source arcs and was reported as empty (cut 0 for flow 2).
    scenario = apply(
        base_graph,
        SybilScenarioCreate(
            dataset_id="test",
            mode="research",
            recommendations=(
                SybilRecommendation(website="a", shop="A"),
                SybilRecommendation(website="b", shop="A"),
            ),
        ),
    )
    witness = compute_bottleneck_witness(scenario, "A")
    assert witness.max_flow == 2.0
    assert witness.cut_size == 2
    assert set(witness.bottleneck_nodes) == {"a", "b"}


def test_bottleneck_witness_disconnected_shop(base_graph):
    scenario = apply(
        base_graph,
        SybilScenarioCreate(
            dataset_id="test",
            injected_nodes=("sim:1", "sim:2"),
            added_links=(SybilLink(source="sim:1", target="sim:2"),),
            recommendations=(SybilRecommendation(website="sim:2", shop="B"),),
        ),
    )
    witness = compute_bottleneck_witness(scenario, "B")
    assert witness.max_flow == 0.0
    assert witness.cut_size == 0
    assert witness.bottleneck_nodes == ()


def test_bottleneck_witness_with_bridge(base_graph):
    scenario = apply(
        base_graph,
        SybilScenarioCreate(
            dataset_id="test",
            injected_nodes=("sim:1", "sim:2"),
            added_links=(
                SybilLink(source="c", target="sim:1"),
                SybilLink(source="sim:1", target="sim:2"),
            ),
            cooperating_links=(SybilLink(source="c", target="sim:1"),),
            recommendations=(SybilRecommendation(website="sim:2", shop="B"),),
        ),
    )
    witness = compute_bottleneck_witness(scenario, "B")
    assert witness.max_flow == 1.0
    assert witness.bottleneck_nodes == ("c",)
    # The drawn links are the funnel into the bottleneck from the anchor side.
    assert {(e.source, e.target) for e in witness.cut_edges} == {("a", "c"), ("b", "c")}


def _connected_without(edges, sources, sinks, removed):
    adjacency = {}
    for u, v in edges:
        adjacency.setdefault(u, []).append(v)
    seen = {s for s in sources if s not in removed}
    queue = deque(seen)
    while queue:
        node = queue.popleft()
        if node in sinks:
            return True
        for nxt in adjacency.get(node, ()):
            if nxt not in seen and nxt not in removed:
                seen.add(nxt)
                queue.append(nxt)
    return False


@pytest.mark.parametrize("seed", range(25))
def test_cut_equals_flow_and_separates_on_random_graphs(seed):
    rng = random.Random(seed)
    n = rng.randint(6, 30)
    edges = sorted({(rng.randrange(n), rng.randrange(n)) for _ in range(rng.randint(n, 4 * n))})
    edges = [(u, v) for u, v in edges if u != v]
    degree = [0] * n
    for u, _ in edges:
        degree[u] += 1
    ids = tuple(str(i) for i in range(n))
    anchors = tuple(sorted(rng.sample(ids, 3)))
    recs = tuple((v, "A") for v in sorted(rng.sample(ids, rng.randint(1, 4))))
    base = BaseGraph("r", "h", ids, Graph(n, tuple(edges), tuple(degree)), anchors, 0.1, recs)
    scenario = apply(base, SybilScenarioCreate(dataset_id="r"))
    witness = compute_bottleneck_witness(scenario, "A")
    assert witness.cut_size == witness.max_flow
    assert witness.complete
    index = {v: i for i, v in enumerate(ids)}
    removed = {index[v] for v in witness.bottleneck_nodes}
    supporters = {index[v] for v, _ in recs}
    anchor_idx = {index[a] for a in anchors}
    assert not _connected_without(edges, anchor_idx, supporters, removed)


def test_extract_explanation_subgraph_cap(base_graph):
    scenario = apply(base_graph, SybilScenarioCreate(dataset_id="test"))
    nodes, _, complete = extract_explanation_subgraph(scenario, "A", max_nodes=2)
    assert len(nodes) <= 2
    assert not complete
