import pytest

from aegis.schemas import SybilAttackSearchRequest
from aegis.sybil import Graph
from aegis.sybil_scenario import BaseGraph
from aegis.sybil_search import search_adversarial_attack


@pytest.fixture
def base():
    # 4 nodes, 'a' and 'b' anchors, 'c' and 'd' background
    return BaseGraph(
        "test",
        "hash-v1",
        ("a", "b", "c", "d"),
        Graph(4, ((0, 2), (1, 2)), (2, 1, 0, 0)),
        ("a", "b"),
        0.1,
        (("c", "A"),),
    )


def test_adversarial_attack_search_bounded(base):
    # Test with small max_proposals
    req = SybilAttackSearchRequest(target="B", seed=42, max_proposals=15, max_seconds=10.0)
    result = search_adversarial_attack(base, req)

    assert result.dataset_id == "test"
    assert result.target_shop == "B"
    assert result.proposals_evaluated >= 1
    assert result.proposals_evaluated <= 15
    assert result.best_proposal is not None
    assert result.best_proposal.credits <= 25
    assert len(result.history) >= 1
    assert result.best_score >= 0.0


def test_adversarial_attack_search_timeout(base):
    # Test very short timeout
    req = SybilAttackSearchRequest(target="B", seed=42, max_proposals=500, max_seconds=0.01)
    result = search_adversarial_attack(base, req)
    assert result.stopped_reason in ("time_limit", "iteration_limit")
