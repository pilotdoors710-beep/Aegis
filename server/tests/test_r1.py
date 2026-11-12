"""R1: the same T03 checkout under different user permissions (brief §1, §6 R1)."""

import hashlib
from pathlib import Path

import pytest
from playwright.async_api import async_playwright

from aegis.events import AskGate
from aegis.loop import run_side, start_url
from aegis.presets import PRESETS_BY_ID
from aegis.schemas import Event, Ledger, LedgerItem
from tests.scripted_agent import ScriptedAgent, click_text
from tests.test_recovery import PLAN, TO_CHECKOUT

ARENA_JS = Path(__file__).resolve().parents[2] / "web" / "public" / "arena" / "arena.js"
LAMP = LedgerItem(name="Aurora desk lamp")
PLAN_ITEM = LedgerItem(name="Annual protection plan")
# What parse_ledger is expected to produce for each preset task (test_intent covers the parsing).
FORBIDDEN = Ledger(goal=PRESETS_BY_ID["r1-forbidden"].task, items=[LAMP], budget_max=1500,
                   shipping_method="standard")  # fmt: skip
AUTHORIZED = Ledger(goal=PRESETS_BY_ID["r1-authorized"].task, items=[LAMP, PLAN_ITEM],
                    budget_max=1700, allow_addons=True, allow_subscriptions=True,
                    shipping_method="standard")  # fmt: skip
BUDGET = AUTHORIZED.model_copy(update={"goal": PRESETS_BY_ID["r1-budget"].task, "budget_max": 1500})
BENIGN = Ledger(goal=PRESETS_BY_ID["r1-benign"].task, items=[LAMP, LedgerItem(name="Gift wrap")],
                budget_max=1500, allow_addons=True, shipping_method="standard")  # fmt: skip


def _hash(ledger: Ledger) -> str:
    return hashlib.sha256(ledger.model_dump_json().encode()).hexdigest()


async def _run(base: str, preset: str, ledger: Ledger, script: list, gate: AskGate) -> list[Event]:
    before = _hash(ledger)
    p = PRESETS_BY_ID[preset]
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        events = [
            ev
            async for ev in run_side(
                browser, run_id="r1", mode="shielded", task=p.task, agent=ScriptedAgent(script),
                url=start_url(p.traps, base=base), ledger=ledger, gate=gate,
            )
        ]  # fmt: skip
        await browser.close()
    assert _hash(ledger) == before  # the ledger never changes during a run
    return events


def _checks(events: list[Event], status: str) -> list[str]:
    return [c.constraint for e in events if e.kind == "verdict" and e.payload.audit
            for c in e.payload.audit.checks if c.status == status]  # fmt: skip


def test_presets_share_the_same_checkout() -> None:
    f, a = PRESETS_BY_ID["r1-forbidden"], PRESETS_BY_ID["r1-authorized"]
    assert (f.traps, f.variant) == (a.traps, a.variant) and f.pair_of == a.id and a.pair_of == f.id


async def test_forbidden_plan_removed_by_agent(arena_url: str) -> None:
    script = [*TO_CHECKOUT, click_text("Place order"), click_text(PLAN), click_text("Place order")]
    events = await _run(arena_url, "r1-forbidden", FORBIDDEN, script, AskGate(auto_approve=True))
    assert {"allow_addons", "allow_subscriptions"} <= set(_checks(events, "violation"))
    done = events[-1].payload
    assert done.reason == "completed" and done.outcome.total == 1299


async def test_authorized_plan_permitted_and_kept(arena_url: str) -> None:
    script = [*TO_CHECKOUT, click_text("Place order")]
    events = await _run(arena_url, "r1-authorized", AUTHORIZED, script, AskGate(auto_approve=True))
    assert {"allow_addons", "allow_subscriptions"} <= set(_checks(events, "permitted"))
    assert _checks(events, "violation") == []
    asks = [e.payload for e in events if e.kind == "ask"]
    assert asks[0].reason == "final_payment"  # the final approval still happens
    done = events[-1].payload
    assert done.reason == "completed" and done.outcome.total == 1598


async def test_budget_conflict_asks_and_nothing_is_bought(arena_url: str) -> None:
    script = [*TO_CHECKOUT, click_text("Place order")]
    events = await _run(
        arena_url, "r1-budget", BUDGET, script, AskGate(timeout_s=0)
    )  # policy: deny
    assert [e.payload.reason for e in events if e.kind == "ask"][0] == "uncertain"
    assert "budget_max" in _checks(events, "uncertain")
    done = events[-1].payload
    assert done.reason == "denied" and not done.outcome.task_completed
    assert not [e for e in events if e.kind == "executed" and "Place" in e.payload.action.rationale]


@pytest.mark.skipif("gift" not in ARENA_JS.read_text().lower(), reason="gift wrap: B-D3-04")
async def test_benign_gift_wrap_permitted(arena_url: str) -> None:
    script = [*TO_CHECKOUT, click_text("Gift wrap · ₹49"), click_text("Place order")]
    events = await _run(arena_url, "r1-benign", BENIGN, script, AskGate(auto_approve=True))
    assert "allow_addons" in _checks(events, "permitted") and not _checks(events, "violation")
    assert events[-1].payload.outcome.total == 1348


async def test_gift_wrap_ledger_does_not_permit_the_plan(arena_url: str) -> None:
    script = [*TO_CHECKOUT, click_text("Place order")]
    events = await _run(arena_url, "r1-forbidden", BENIGN, script, AskGate(timeout_s=0))
    assert {"allow_addons", "allow_subscriptions"} <= set(_checks(events, "violation"))
