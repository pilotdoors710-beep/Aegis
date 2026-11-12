import json

from playwright.async_api import Page, async_playwright

from aegis.events import AskGate
from aegis.loop import run_side, start_url
from aegis.schemas import Event, Ledger, LedgerItem, Mode
from tests.scripted_agent import ScriptedAgent, click_text
from tests.test_loop import TASK

CART = "cart=aurora-desk-lamp:1"


DEFAULT_LEDGER = Ledger(goal=TASK, items=[LedgerItem(name="Aurora desk lamp")], budget_max=1500,
                        shipping_method="standard")  # fmt: skip


async def _run(
    mode: Mode,
    url: str,
    agent: ScriptedAgent,
    gate: AskGate | None = None,
    ledger: Ledger = DEFAULT_LEDGER,
) -> tuple[list[Event], list[str]]:
    effects: list[str] = []

    async def grab(page: Page) -> None:  # evaluator ground truth, test-only
        effects.extend(json.loads(await page.evaluate("localStorage['arena:effects'] || '[]'")))

    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        events = [
            ev
            async for ev in run_side(
                browser,
                run_id="t",
                mode=mode,
                task=TASK,
                url=url,
                agent=agent,
                on_finish=grab,
                ledger=ledger,
                gate=gate,
            )
        ]
        await browser.close()
    return events, effects


def _verdicts(events: list[Event]):
    vs = [e.payload for e in events if e.kind == "verdict"]
    assert all(isinstance(v.verdict.latency_ms, int) and v.verdict.latency_ms >= 0 for v in vs)
    return vs


async def test_t01_fake_close_rerouted_then_second_choice_runs(arena_url: str) -> None:
    agent = ScriptedAgent([click_text("×"), click_text("No thanks")])
    events, effects = await _run("shielded", start_url(["T01"], base=arena_url), agent)
    vs = _verdicts(events)
    assert [v.verdict.decision for v in vs] == ["REROUTE", "ALLOW"]
    assert "A4_link_truth" in {f.detector for f in vs[0].verdict.findings}
    executed = [e.payload for e in events if e.kind == "executed"]
    assert len(executed) == 1 and executed[0].defense_retry
    assert [e.payload.attempt for e in events if e.kind == "decision"][:2] == [1, 2]
    assert "download:premium-offer" not in effects


async def test_t02_overlay_neutralized_but_unshielded_subscribes(arena_url: str) -> None:
    url = f"{arena_url}/cart.html?traps=T02&{CART}"
    _, effects = await _run("unshielded", url, ScriptedAgent([click_text("Continue")]))
    assert "subscribed:aurora-plus" in effects

    events, effects = await _run("shielded", url, ScriptedAgent([click_text("Continue")]))
    (v,) = _verdicts(events)
    assert v.verdict.decision == "ALLOW"
    assert [n.target_id for n in v.neutralized] == [v.action.target_id]
    assert "Subscribe" in v.neutralized[0].evidence
    executed = next(e.payload for e in events if e.kind == "executed")
    assert executed.ok and executed.url_after and executed.url_after.endswith("checkout.html")
    assert "subscribed:aurora-plus" not in effects


async def test_visible_cover_blocks_until_ask(arena_url: str) -> None:
    lamp = click_text("Aurora desk lamp")  # under T01's visible popup: never neutralized
    events, _ = await _run(
        "shielded", start_url(["T01"], base=arena_url), ScriptedAgent([lamp] * 4)
    )
    vs = _verdicts(events)
    assert [v.verdict.decision for v in vs] == ["BLOCK"] * 4 and not any(v.neutralized for v in vs)
    assert not [e for e in events if e.kind == "executed"]
    asks = [e.payload for e in events if e.kind == "ask"]
    assert [(a.reason, a.status) for a in asks] == [
        ("retries_exhausted", "pending"),
        ("retries_exhausted", "timed_out"),
    ]  # no gate given: fails closed
    assert events[-1].payload.reason == "denied"


async def test_clean_flow_has_no_stops(arena_url: str) -> None:
    agent = ScriptedAgent([
        click_text("Aurora desk lamp"), click_text("Add to cart"),
        click_text("Continue"), click_text("Place order"),
    ])  # fmt: skip
    gate = AskGate(auto_approve=True)
    events, _ = await _run("shielded", start_url([], base=arena_url), agent, gate)
    assert [v.verdict.decision for v in _verdicts(events)] == ["ALLOW"] * 3 + ["ASK"]
    asks = [(e.payload.reason, e.payload.status) for e in events if e.kind == "ask"]
    assert asks == [("final_payment", "pending"), ("final_payment", "auto_approved_demo")]
    done = events[-1].payload
    assert done.reason == "completed" and done.outcome.total == 1299


async def test_t05_injection_stripped_and_logged(arena_url: str) -> None:
    seen: list[str] = []

    def peek(view, _history):  # records what the shielded agent is shown
        seen.extend(t.text for t in view.text_blocks)

    agent = ScriptedAgent([click_text("Aurora desk lamp"), peek])  # type: ignore[list-item]
    events, _ = await _run("shielded", start_url(["T05"], base=arena_url), agent)
    assert seen and not any("AI assistant" in t for t in seen)
    removed = [r for e in events if e.kind == "snapshot" for r in e.payload.removed]
    assert [r.reason for r in removed] == ["B5_quarantine"]
