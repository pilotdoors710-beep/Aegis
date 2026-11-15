"""Analytical checks use a dense linear solve independent of the sparse iteration."""

import numpy as np
import pytest

from aegis.schemas import SybilBudget
from aegis.sybil import Config, Graph, _without_edges_transition, assess, reference_scale


def test_direction_sink_deduplication_and_dense_reference():
    graph = Graph(5, ((0, 2), (0, 2), (1, 2), (3, 0)), (2, 1, 0, 1, 0))
    matrix = graph.transition().toarray()
    assert matrix[0, 2] == matrix[0, 5] == 0.5
    assert matrix[2, 2] == matrix[5, 5] == 1
    np.testing.assert_allclose(matrix.sum(axis=1), 1)
    result = assess(graph, (0, 1), {2: ("A", "A", "B"), 3: ("A",)}, 0.1)
    seed = np.array([0.5, 0.5, 0, 0, 0, 0])
    expected = np.linalg.solve(np.eye(6) - 0.85 * matrix.T, 0.15 * seed)
    np.testing.assert_allclose(result.propagation.mass.mean(axis=1), expected, atol=1e-9)
    assert result.trust[3] == result.trust[4] == 0
    assert result.scores["A"].count == 2
    assert result.scores["A"].mass == result.scores["B"].mass
    assert sum(s.mass for s in result.scores.values()) <= result.trust.sum()


def test_disconnected_cluster_and_edge_direction():
    graph = Graph(4, ((2, 3), (3, 2), (2, 0)), (0, 0, 2, 1))
    result = assess(graph, (0, 1), {2: ("A",), 3: ("A",)}, 0.1)
    score = result.scores["A"]
    assert score.count == 2
    assert score.mass == score.total == score.support == score.breadth == 0
    connected = Graph(4, (*graph.edges, (0, 2)), (1, 0, 2, 1))
    assert assess(connected, (0, 1), {2: ("A",)}, 0.1).scores["A"].mass > 0


def test_anchor_decomposition_withdrawal_and_connection_intervention():
    graph = Graph(4, ((0, 2), (1, 2), (2, 3)), (1, 1, 1, 0))
    result = assess(graph, (0, 1), {3: ("A",)}, 0.1)
    score = result.scores["A"]
    np.testing.assert_allclose(result.anchor_trust.mean(axis=1), result.trust)
    assert score.effective_anchors == pytest.approx(2)
    assert score.breadth == pytest.approx(1)
    assert score.withdrawal == pytest.approx(1)
    assert score.connection == pytest.approx(0)
    assert score.tested_edges == ((2, 3),)
    assert graph.edges == ((0, 2), (1, 2), (2, 3))
    assert 0 <= score.total <= 100


@pytest.mark.parametrize(
    ("graph", "edge"),
    [
        (Graph(3, ((0, 1),), (1, 0, 0)), (0, 1)),
        (Graph(3, ((0, 1), (0, 2)), (3, 0, 0)), (0, 1)),
    ],
)
def test_fast_edge_removal_matches_graph_rebuild(graph, edge):
    expected = graph.without(edge).transition().toarray()
    actual = _without_edges_transition(graph.transition(), graph, [edge]).toarray()
    np.testing.assert_allclose(actual, expected)


def test_fast_multi_edge_removal_matches_graph_rebuild():
    graph = Graph(5, ((0, 1), (0, 2), (0, 3), (1, 2), (1, 4)), (5, 2, 0, 0, 0))
    edges = [(0, 1), (0, 3), (1, 2)]
    expected = graph
    for edge in edges:
        expected = expected.without(edge)
    actual = _without_edges_transition(graph.transition(), graph, edges).toarray()
    np.testing.assert_allclose(actual, expected.transition().toarray())


def _graph(node_count, edges):
    degree = [0] * node_count
    for u, _ in edges:
        degree[u] += 1
    return Graph(node_count, tuple(edges), tuple(degree))


def _bridged_cluster(bridges):
    # Anchors 0,1 vouch for 12 outside sites (2..13); the first `bridges` link into a
    # five-site simulated chain (14..18) whose members all recommend B.
    edges = [(a, s) for a in (0, 1) for s in range(2, 14)]
    edges += [(s, 14) for s in range(2, 2 + bridges)]
    edges += [(c, c + 1) for c in range(14, 18)]
    return _graph(19, edges), {c: ("B",) for c in range(14, 19)}


@pytest.mark.parametrize("bridges", [1, 6, 12])
def test_bought_bridges_do_not_raise_connection_resilience(bridges):
    graph, recommendations = _bridged_cluster(bridges)
    score = assess(graph, (0, 1), recommendations, 1e-6).scores["B"]
    assert score.mass > 0
    assert score.connection == pytest.approx(0, abs=1e-12)


def test_one_source_with_many_links_counts_once():
    # A taken-over site may add up to 100 links; cutting it removes all of them.
    edges = [(0, 2), (1, 2), *((2, c) for c in range(3, 103))]
    score = assess(_graph(103, edges), (0, 1), {c: ("B",) for c in range(3, 103)}, 1e-6)
    assert score.scores["B"].connection == pytest.approx(0, abs=1e-12)


def test_wide_honest_support_survives_the_cut():
    # 20 independent outside sites each support one recommender; cutting 12 leaves 8.
    edges = [(a, s) for a in (0, 1) for s in range(2, 22)] + [(s, s + 20) for s in range(2, 22)]
    score = assess(_graph(42, edges), (0, 1), {r: ("A",) for r in range(22, 42)}, 1e-6)
    assert score.scores["A"].connection == pytest.approx(8 / 20)
    assert len(score.scores["A"].tested_edges) == 12


def test_cut_size_matches_what_the_credit_budget_can_buy():
    # Cheapest outside site an attacker can enlist is a 2-credit cooperating link.
    assert Config().cut_sources == SybilBudget.model_fields["credit_limit"].default // 2


def test_single_anchor_dependence_and_frozen_normalization():
    graph = Graph(3, ((0, 2),), (1, 0, 0))
    tau = reference_scale(graph, (0, 1))
    score = assess(graph, (0, 1), {2: ("A",)}, tau).scores["A"]
    assert score.effective_anchors == pytest.approx(1)
    assert score.breadth == score.withdrawal == 0
    assert score.support == pytest.approx(0.5)
    bigger = Graph(4, graph.edges, (*graph.original_outdegree, 0))
    assert assess(bigger, (0, 1), {2: ("A",), 3: ("A",)}, tau).scores["A"].total == score.total


def test_nonconvergence_is_unavailable_and_not_a_zero_score():
    graph = Graph(3, ((0, 2), (2, 0)), (1, 0, 1))
    result = assess(graph, (0, 1), {2: ("A",)}, 0.1, Config(max_iterations=1))
    assert result.scores is None
    assert not result.propagation.converged
    assert result.propagation.iterations == 1


def test_permutation_and_duplicate_edge_invariance():
    graph = Graph(3, ((0, 2), (1, 2)), (1, 1, 0))
    a = assess(graph, (0, 1), {2: ("A",)}, 0.1).scores["A"]
    renamed = Graph(3, ((2, 0), (1, 0), (1, 0)), (0, 1, 1))
    b = assess(renamed, (2, 1), {0: ("A",)}, 0.1).scores["A"]
    assert a.total == pytest.approx(b.total)


@pytest.mark.parametrize("graph", [Graph(2, ((0, 1),), (0, 0)), Graph(2, ((0, 2),), (1, 0))])
def test_invalid_graph_rejected(graph):
    with pytest.raises(ValueError):
        graph.transition()


def test_no_positive_background_rejected():
    with pytest.raises(ValueError, match="no positive"):
        reference_scale(Graph(2, (), (0, 0)), (0, 1))


def test_unrecommended_candidate_is_zero_not_missing():
    result = assess(Graph(2, (), (0, 0)), (0, 1), {}, 0.1, candidate_shops=("A", "B"))
    assert set(result.scores) == {"A", "B"}
    assert all(score.total == score.mass == score.count == 0 for score in result.scores.values())


def test_eight_anchor_withdrawal_matches_independent_dense_solutions():
    graph = Graph(10, tuple((i, 8 if i < 6 else 9) for i in range(8)), (1,) * 8 + (0, 0))
    result = assess(graph, tuple(range(8)), {8: ("A",), 9: ("B",)}, 0.1)
    matrix = graph.transition().toarray()
    for shop, supporter in [("A", 8), ("B", 9)]:
        surviving = []
        for withdrawn in range(8):
            seed = np.zeros(11)
            seed[:8] = 1 / 7
            seed[withdrawn] = 0
            mass = np.linalg.solve(np.eye(11) - 0.85 * matrix.T, 0.15 * seed)
            surviving.append(mass[supporter])
        assert result.scores[shop].withdrawal == pytest.approx(
            min(surviving) / result.scores[shop].mass
        )
