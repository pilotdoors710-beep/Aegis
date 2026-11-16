import pytest

from aegis.schemas import SybilLink, SybilRecommendation, SybilScenarioCreate
from aegis.sybil import Graph
from aegis.sybil_maxflow import compute_bottleneck_witness, extract_explanation_subgraph
from aegis.sybil_scenario import BaseGraph, apply


@pytest.fixture
def base_graph():
    # Anchors 'a' and 'b' link to 'c'. 'c' recommends Shop A.
    # 'd' is disconnected.
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
    # Base scenario has 'c' recommending Shop A.
    scenario = apply(base_graph, SybilScenarioCreate(dataset_id="test"))
    witness = compute_bottleneck_witness(base_graph, scenario, "A")
    assert witness.shop == "A"
    assert witness.subgraph_nodes >= 3  # a, b, c
    assert witness.max_flow == 1.0  # Unit capacity on node 'c' limits flow to 1
    assert "c" in witness.bottleneck_nodes or len(witness.cut_edges) > 0


def test_bottleneck_witness_disconnected_shop(base_graph):
    # Simulated nodes recommend B, with no bridges to anchors
    scenario = apply(
        base_graph,
        SybilScenarioCreate(
            dataset_id="test",
            injected_nodes=("sim:1", "sim:2"),
            added_links=(SybilLink(source="sim:1", target="sim:2"),),
            recommendations=(SybilRecommendation(website="sim:2", shop="B"),),
        ),
    )
    witness = compute_bottleneck_witness(base_graph, scenario, "B")
    assert witness.shop == "B"
    assert witness.max_flow == 0.0
    assert witness.cut_size == 0


def test_bottleneck_witness_with_bridge(base_graph):
    # Bridge from 'c' to 'sim:1' with cooperating link
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
    witness = compute_bottleneck_witness(base_graph, scenario, "B")
    assert witness.shop == "B"
    assert witness.max_flow == 1.0
    assert witness.cut_size >= 1


def test_extract_explanation_subgraph_cap(base_graph):
    scenario = apply(base_graph, SybilScenarioCreate(dataset_id="test"))
    nodes, edges = extract_explanation_subgraph(base_graph, scenario, "A", max_nodes=2)
    assert len(nodes) <= 2
