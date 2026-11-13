"""R2 spike gate (brief §3): state reproduction, both control meanings, original unchanged,
cleanup, containment, unsupported states and the timeout fallback."""

from urllib.parse import urlsplit

from playwright.async_api import Page

from aegis.loop import FROZEN_TIME, VIEWPORT, outcome_from_page
from aegis.schemas import Action, Ledger, LedgerItem, PageSnapshot
from aegis.snapshot import take_snapshot
from aegis.trials import describe, run_trials

LAMP = LedgerItem(name="Aurora desk lamp", qty=1)
NO_DATA = Ledger(goal="g", items=[LAMP], budget_max=1500, shipping_method="standard")
EMAIL_OK = NO_DATA.model_copy(update={"data_allowed": ["email"]})


def _id(snap: PageSnapshot, text: str) -> str:
    return next(e.id for e in snap.elements if text in e.text and e.tag in ("input", "button"))


async def _setup(page: Page, arena_url: str, query: str) -> tuple[str, PageSnapshot, str, Action]:
    url = f"{arena_url}/checkout.html?{query}&cart=aurora-desk-lamp:1"
    await page.clock.set_fixed_time(FROZEN_TIME)
    await page.goto(url)
    snap = await take_snapshot(page)
    control = _id(snap, "partner offers")
    order = Action(type="click", target_id=_id(snap, "Place order"), rationale="place the order")
    return url, snap, control, order


async def _trial(page: Page, arena_url: str, query: str, ledger: Ledger = NO_DATA, **kw):  # noqa: ANN003, ANN202
    url, snap, control, order = await _setup(page, arena_url, query)
    origin = kw.pop("allowed_origin", f"{urlsplit(url).scheme}://{urlsplit(url).netloc}")
    report = await run_trials(
        page.context.browser, original_page=page, original=snap, control_id=control,  # type: ignore[arg-type]
        commit_action=order, ledger=ledger, start_url=url, allowed_origin=origin, replay=[],
        viewport=VIEWPORT, frozen_time=FROZEN_TIME, outcome_reader=outcome_from_page, **kw,
    )  # fmt: skip
    return report, snap, control


async def test_t08_double_negative_resolves_to_untick(page: Page, arena_url: str) -> None:
    report, _, control = await _trial(page, arena_url, "traps=T08")
    assert report.current_checked is True
    assert report.status == "resolved" and report.recommended_checked is False
    on, off = report.branches
    assert on.state_matched and off.state_matched
    assert any(k.startswith("data_sharing:") for k in on.unauthorized) and not off.unauthorized
    assert report.original_unchanged is True
    assert f"untick it (element {control})" in describe(report)


async def test_reversed_meaning_resolves_to_tick(page: Page, arena_url: str) -> None:
    """Same control, opposite meaning: a fixed 'always untick' rule would fail here."""
    report, _, control = await _trial(page, arena_url, "traps=T08&consent=r")
    assert report.current_checked is False
    assert report.status == "resolved" and report.recommended_checked is True
    assert f"tick it (element {control})" in describe(report)


async def test_permitted_sharing_is_not_a_violation(page: Page, arena_url: str) -> None:
    report, _, _ = await _trial(page, arena_url, "traps=T08", ledger=EMAIL_OK)
    assert report.status == "both_ok" and report.recommended_checked is None


async def test_original_session_untouched_and_contexts_closed(page: Page, arena_url: str) -> None:
    browser = page.context.browser
    assert browser
    contexts = len(browser.contexts)
    report, snap, control = await _trial(page, arena_url, "traps=T08")
    assert report.original_unchanged is True
    assert page.url.endswith("/checkout.html") and "confirmation" not in page.url
    after = await take_snapshot(page)
    box = next(e for e in after.elements if e.id == control)
    assert box.checked is True  # trials ticked/unticked copies, never this page
    assert len(browser.contexts) == contexts


async def test_egress_outside_allowed_origin_is_blocked(page: Page, arena_url: str) -> None:
    report, _, _ = await _trial(page, arena_url, "traps=T08", allowed_origin="https://example.test")
    assert report.status == "unavailable" and report.blocked_requests > 0


async def test_timeout_falls_back_and_cleans_up(page: Page, arena_url: str) -> None:
    browser = page.context.browser
    assert browser
    contexts = len(browser.contexts)
    report, _, _ = await _trial(page, arena_url, "traps=T08", timeout_s=0.05)
    assert report.status == "unavailable" and "timeout" in report.reason
    assert len(browser.contexts) == contexts


async def test_unsupported_control_is_rejected(page: Page, arena_url: str) -> None:
    url, snap, _, order = await _setup(page, arena_url, "traps=T08")
    radio = next(e.id for e in snap.elements if e.role == "radio")
    report = await run_trials(
        page.context.browser, original_page=page, original=snap, control_id=radio,  # type: ignore[arg-type]
        commit_action=order, ledger=NO_DATA, start_url=url,
        allowed_origin=f"{urlsplit(url).scheme}://{urlsplit(url).netloc}", replay=[],
        viewport=VIEWPORT, frozen_time=FROZEN_TIME, outcome_reader=outcome_from_page,
    )  # fmt: skip
    assert report.status == "unavailable" and report.reason.startswith("unsupported")
    assert report.branches == []


async def test_reproduction_mismatch_is_unavailable(page: Page, arena_url: str) -> None:
    """The original has gift wrap ticked but the replay doesn't do that: the copies differ, so
    the trial must refuse to judge instead of testing a different checkout."""
    url, _, control, order = await _setup(page, arena_url, "traps=T08")
    await page.click("#gift-wrap")  # test setup only
    snap = await take_snapshot(page)
    report = await run_trials(
        page.context.browser, original_page=page, original=snap, control_id=control,  # type: ignore[arg-type]
        commit_action=order, ledger=NO_DATA, start_url=url,
        allowed_origin=f"{urlsplit(url).scheme}://{urlsplit(url).netloc}", replay=[],
        viewport=VIEWPORT, frozen_time=FROZEN_TIME, outcome_reader=outcome_from_page,
    )  # fmt: skip
    assert report.status == "unavailable"
    assert all(not b.state_matched for b in report.branches)


async def test_replays_the_agents_path_from_the_start_url(page: Page, arena_url: str) -> None:
    """The real case: the original side clicked its way from the home page (through the
    executor, as the agent does); the copies replay those same actions, then test."""
    from aegis.executor import execute

    start = f"{arena_url}/index.html?traps=T08"
    await page.clock.set_fixed_time(FROZEN_TIME)
    await page.goto(start)
    replay = []
    for label in ("Aurora desk lamp", "Add to cart", "Continue"):
        snap = await take_snapshot(page)
        target = next(e.id for e in snap.elements if e.text.strip() == label
                      and e.tag in ("a", "button"))  # fmt: skip
        action = Action(type="click", target_id=target, rationale=label)
        assert (await execute(page, action)).ok
        replay.append((action, None))
    snap = await take_snapshot(page)
    assert page.url.endswith("/checkout.html")
    report = await run_trials(
        page.context.browser, original_page=page, original=snap,  # type: ignore[arg-type]
        control_id=_id(snap, "partner offers"),
        commit_action=Action(type="click", target_id=_id(snap, "Place order"), rationale="order"),
        ledger=NO_DATA, start_url=start,
        allowed_origin=f"{urlsplit(start).scheme}://{urlsplit(start).netloc}", replay=replay,
        viewport=VIEWPORT, frozen_time=FROZEN_TIME, outcome_reader=outcome_from_page,
    )  # fmt: skip
    assert report.status == "resolved" and report.recommended_checked is False, report.reason
    assert all(b.state_matched and b.disposable_actions >= 4 for b in report.branches)
    assert report.original_unchanged is True and report.elapsed_ms < 10_000
