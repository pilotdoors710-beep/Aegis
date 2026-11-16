from aegis.schemas import SybilAttackSearchRequest, SybilGenerate
from aegis.sybil_scenario import apply, assess_scenario, generate
from aegis.sybil_search import search_adversarial_attack, takeover, takeover_site


def test_search_is_bounded_and_reports_the_applied_budget(sybil_toy):
    base = sybil_toy
    request = SybilAttackSearchRequest(target="B", seed=42, max_proposals=15, max_seconds=30)
    result = search_adversarial_attack(base, request)
    assert result.proposals_evaluated == 15
    assert result.stopped_reason == "iteration_limit"
    best = apply(base, result.best_scenario)
    assert best.revision.id == result.best_revision_id
    assert result.best_proposal.credits == best.revision.budget.external_credits <= 25
    assert result.best_score == result.best_proposal.score
    assert isinstance(result.best_passed_policy, bool)
    assert result.history[-1] == result.best_proposal


def test_search_is_deterministic_for_a_seed(sybil_toy):
    base = sybil_toy
    request = SybilAttackSearchRequest(target="B", seed=7, max_proposals=10, max_seconds=30)
    first = search_adversarial_attack(base, request)
    second = search_adversarial_attack(base, request)
    assert first.best_revision_id == second.best_revision_id


def test_search_time_limit(sybil_toy):
    base = sybil_toy
    request = SybilAttackSearchRequest(target="B", seed=42, max_proposals=500, max_seconds=0.01)
    result = search_adversarial_attack(base, request)
    assert result.stopped_reason == "time_limit"


def test_a_takeover_actually_changes_the_attack(sybil_toy):
    # A takeover used to add no links: it cost 5 or 15 credits and changed nothing.
    base = sybil_toy
    raw = generate(base.dataset_id, SybilGenerate(count=10, pattern="chain", target="B"), base)
    site = takeover_site(base, "anchor", raw)
    taken = apply(base, takeover(raw, site, "B"))
    assert taken.revision.budget.external_credits == 15
    before = assess_scenario(base, apply(base, raw)).scores["B"]
    after = assess_scenario(base, taken).scores["B"]
    assert after.mass > before.mass
    assert after.count == before.count + 1
