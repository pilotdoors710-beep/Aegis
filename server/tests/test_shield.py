"""The Shielded Step decision through its own interface: no run loop, no agent, no LLM.
Checkout snapshots come from the real arena; the PagePort is a fake."""

from playwright.async_api import Page

from aegis import shield as shield_module
from aegis.schemas import (
    Action,
    Element,
    Ledger,
    LedgerItem,
    PageSnapshot,
    SybilGraphEvidence,
    SybilShopEvidence,
)
from aegis.shield import CAPABILITIES, StepShield, side_ledger
from aegis.snapshot import take_snapshot
from aegis.verdict import check_fast

LEDGER = Ledger(goal="g", items=[LedgerItem(name="Aurora desk lamp", qty=1)], budget_max=1500,
                shipping_method="standard")  # fmt: skip


class FakePage:
    """PagePort that serves a fixed re-snapshot; Trials are never expected here."""

    def __init__(self, snap: PageSnapshot | None = None) -> None:
        self.snap = snap

    async def snapshot(self) -> PageSnapshot:
        assert self.snap is not None
        return self.snap

    async def trial(self, *_: object):  # noqa: ANN202
        raise AssertionError("configuration I runs no Trials")

    async def two_view(self, *_: object):  # noqa: ANN202
        raise AssertionError("configuration I runs no Two-view check")


async def _checkout(page: Page, arena_url: str, traps: str) -> tuple[PageSnapshot, Action]:
    await page.goto(f"{arena_url}/checkout.html?traps={traps}&cart=aurora-desk-lamp:1")
    snap = await take_snapshot(page)
    order = next(e.id for e in snap.elements if e.text.strip() == "Place order")
    return snap, Action(type="click", target_id=order, rationale="place the order")


async def test_violation_reroutes_then_repeat_asks_retries_exhausted(
    page: Page, arena_url: str
) -> None:
    snap, order = await _checkout(page, arena_url, "T03")
    decision = StepShield(LEDGER, "I")
    first = await decision.check(snap, order, 1, FakePage())
    assert first.verdict.decision == "REROUTE" and first.ask_reason is None
    assert first.audit_reroute  # the next attempt is the agent's correction
    assert "untick" in (first.verdict.reroute_hint or "")
    assert "REROUTED and NOT executed" in decision.feedback(first)
    again = await decision.check(snap, order, 2, FakePage())  # agent ignored the hint
    assert again.verdict.decision == "ASK" and again.ask_reason == "retries_exhausted"
    assert not again.audit_reroute
    assert again.report is not None and again.report.recheck_of == 1


async def test_approval_covers_exactly_the_checkout_shown(page: Page, arena_url: str) -> None:
    clean, order = await _checkout(page, arena_url, "none")
    decision = StepShield(LEDGER, "I")
    c = await decision.check(clean, order, 1, FakePage())
    assert c.verdict.decision == "ASK" and c.ask_reason == "final_payment"
    assert await decision.approved(c, 1, FakePage(clean)) is None  # unchanged: execute
    changed, _ = await _checkout(page, arena_url, "T03")  # plan appeared while waiting
    recheck = await decision.approved(c, 1, FakePage(changed))
    assert recheck is not None and recheck.verdict.decision == "REROUTE"
    assert "changed while" in recheck.feedback


async def test_i_minus_audit_asks_without_comparing(page: Page, arena_url: str) -> None:
    snap, order = await _checkout(page, arena_url, "T03")
    c = await StepShield(LEDGER, "I_MINUS_AUDIT").check(snap, order, 1, FakePage())
    assert c.report is None and c.ask_reason == "final_payment"


async def test_f_never_gates_a_commitment(page: Page, arena_url: str) -> None:
    snap, order = await _checkout(page, arena_url, "T03")
    c = await StepShield(LEDGER, "F").check(snap, order, 1, FakePage())
    assert c.verdict.decision == "ALLOW" and c.ask_reason is None


def test_only_f_checks_against_a_goal_only_ledger() -> None:
    for name, can in CAPABILITIES.items():
        got = side_ledger(name, LEDGER, "task", "arena.test")
        assert (got is LEDGER) == can.parses_ledger
    assert side_ledger("I", None, "task", "arena.test").goal == "task"  # failed parse


# --- Sybil Shop gate --------------------------------------------------------------------------

SHOPS = PageSnapshot(
    url="http://arena.test/index.html?shops=two",
    title="Store selection",
    elements=[
        Element(id="e1", tag="a", text="Enter Shop A", href="product.html?shop=A",
                bbox=(10, 10, 100, 30)),
        Element(id="e2", tag="a", text="Enter Shop B", href="product.html?shop=B",
                bbox=(10, 60, 100, 30)),
    ],
)  # fmt: skip


def _shop(passed: bool) -> SybilShopEvidence:
    return SybilShopEvidence(
        recommendation_count=1, structural_support=0.5, anchor_breadth=0.5,
        anchor_withdrawal_resilience=0.5, tested_connection_resilience=0.5,
        total_robustness=70 if passed else 30, policy_passed=passed,
    )  # fmt: skip


EVIDENCE = SybilGraphEvidence(
    revision_id="1" * 64, assessment_id="a" * 64, shops={"A": _shop(True), "B": _shop(False)}
)


async def test_untrusted_shop_asks_and_a_human_can_let_it_through() -> None:
    decision = StepShield(LEDGER, "I", EVIDENCE)
    enter_b = Action(type="click", target_id="e2", rationale="b")
    c = await decision.check(SHOPS, enter_b, 1, FakePage())
    assert c.verdict.decision == "ASK" and c.ask_reason == "untrusted_shop" and c.shop == "B"
    assert "Shop B" in (decision.denied_feedback(c) or "")
    assert await decision.approved(c, 1, FakePage()) is None
    later = await decision.check(SHOPS, enter_b, 2, FakePage())
    assert later.ask_reason is None  # approved once for this Side


async def test_passing_shop_still_fails_closed_on_a_broken_check(monkeypatch) -> None:  # noqa: ANN001
    """A Shop that passes the Graph policy must not skip guard_unavailable -> Ask."""

    def boom(*_: object) -> list:
        raise RuntimeError("detector bug")

    async def broken(snap, action, ledger):  # noqa: ANN001, ANN202
        return await check_fast(snap, action, ledger, [boom], mode="closed")

    monkeypatch.setattr(shield_module, "check_fast", broken)
    decision = StepShield(LEDGER, "I", EVIDENCE)
    c = await decision.check(SHOPS, Action(type="click", target_id="e1", rationale="a"), 1,
                             FakePage())  # fmt: skip
    assert c.verdict.decision == "ASK" and c.ask_reason == "guard_unavailable"
