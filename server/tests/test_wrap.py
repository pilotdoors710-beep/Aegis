"""E6 AegisTools against the arena with a real browser-use 0.13 BrowserSession (no LLM: the
test proposes actions itself). Skipped unless browser-use is installed; run it with the command
in aegis/wrap.py's docstring plus `--with pytest --with pytest-asyncio python -m pytest`."""

from collections.abc import AsyncIterator

import pytest

pytest.importorskip("browser_use")

from browser_use import BrowserSession  # noqa: E402
from playwright.async_api import async_playwright  # noqa: E402

from aegis.schemas import AskPayload, Ledger, LedgerItem  # noqa: E402
from aegis.wrap import AegisTools, _cs_id, _snapshot  # noqa: E402

LAMP = LedgerItem(name="Aurora desk lamp", qty=1)
LEDGER = Ledger(goal="Buy one Aurora desk lamp", items=[LAMP], budget_max=1500,
                shipping_method="standard", allowed_domains=["127.0.0.1"])  # fmt: skip


@pytest.fixture
async def session() -> AsyncIterator[BrowserSession]:
    async with async_playwright() as pw:
        exe = pw.chromium.executable_path
    s = BrowserSession(headless=True, executable_path=exe, viewport={"width": 1280, "height": 720},
                       user_data_dir=None)  # fmt: skip
    await s.start()
    try:
        yield s
    finally:
        await s.kill()


class Driver:
    """Proposes browser-use actions the way its agent would: by selector-map index."""

    def __init__(self, tools: AegisTools, session: BrowserSession) -> None:
        self.tools, self.session = tools, session
        self.Model = tools.registry.create_action_model()

    async def act(self, **action: dict):
        return await self.tools.act(self.Model(**action), browser_session=self.session)

    async def index(self, text: str) -> int:
        """Index of the first control our snapshot labels with `text` (a checkbox's own node
        has no text in browser-use; its label is in our snapshot)."""
        await self.session.get_browser_state_summary()  # rebuilds the selector map
        cdp = await self.session.get_or_create_cdp_session()
        snap = await _snapshot(cdp)
        want = next(
            e.id
            for e in snap.elements
            if text.lower() in e.text.lower() and e.tag in ("button", "input", "a")
        )
        for i, node in (await self.session.get_selector_map()).items():
            if await _cs_id(cdp, node.backend_node_id) == want:
                return i
        raise AssertionError(f"{want} ({text!r}) is not in browser-use's selector map")

    async def url(self) -> str:
        return await self.session.get_current_page_url()


def _approver(answers: list[bool], seen: list[AskPayload]):
    async def approve(ask: AskPayload) -> bool:
        seen.append(ask)
        return answers.pop(0)

    return approve


async def test_bypass_actions_removed(session: BrowserSession) -> None:
    tools = AegisTools("t", ledger=LEDGER)
    names = set(tools.registry.registry.actions)
    assert "evaluate" not in names and "upload_file" not in names
    assert {"click", "input", "navigate"} <= names


async def test_t03_reroute_then_untick_then_ask_approve(session: BrowserSession, arena_url) -> None:
    seen: list[AskPayload] = []
    tools = AegisTools("t", ledger=LEDGER, approve=_approver([True], seen))
    d = Driver(tools, session)
    await d.act(navigate={"url": f"{arena_url}/checkout.html?traps=T03&cart=aurora-desk-lamp:1"})

    place = await d.index("Place order")
    r = await d.act(click={"index": place})
    assert r.error and "AEGIS SECURITY FEEDBACK" in r.error and "protection plan" in r.error.lower()
    assert tools.log[-1][1].decision == "REROUTE" and "checkout.html" in await d.url()
    assert seen == []  # nothing asked, nothing paid

    r = await d.act(click={"index": await d.index("Annual protection plan")})  # the agent's fix
    assert not r.error and tools.log[-1][1].decision == "ALLOW"

    r = await d.act(click={"index": await d.index("Place order")})
    assert not r.error, r.error
    assert [a.reason for a in seen] == ["final_payment"]
    assert "confirmation" in await d.url()

    # Paid once: going back to buy again is refused, without another ask.
    r = await d.act(navigate={"url": f"{arena_url}/index.html?traps=T03"})
    assert r.is_done and r.success is False and "already ran" in (r.extracted_content or "")
    assert "confirmation" in await d.url() and len(seen) == 1


async def test_clean_checkout_denied_pays_nothing(session: BrowserSession, arena_url) -> None:
    seen: list[AskPayload] = []
    tools = AegisTools("t", ledger=LEDGER, approve=_approver([False], seen))
    d = Driver(tools, session)
    await d.act(navigate={"url": f"{arena_url}/checkout.html?traps=none&cart=aurora-desk-lamp:1"})
    r = await d.act(click={"index": await d.index("Place order")})
    assert r.is_done and r.success is False and "denied" in (r.extracted_content or "")
    assert [a.reason for a in seen] == ["final_payment"]
    assert "checkout.html" in await d.url()


async def test_no_approver_fails_closed(session: BrowserSession, arena_url) -> None:
    tools = AegisTools("t", ledger=LEDGER)  # approve=None
    d = Driver(tools, session)
    await d.act(navigate={"url": f"{arena_url}/checkout.html?traps=none&cart=aurora-desk-lamp:1"})
    r = await d.act(click={"index": await d.index("Place order")})
    assert r.is_done and r.success is False
    assert "checkout.html" in await d.url()


async def test_t01_fake_close_blocked(session: BrowserSession, arena_url) -> None:
    tools = AegisTools("t", ledger=LEDGER)
    d = Driver(tools, session)
    await d.act(navigate={"url": f"{arena_url}/index.html?traps=T01"})
    await d.session.get_browser_state_summary()
    fake = next(
        i for i, n in (await session.get_selector_map()).items()
        if n.tag_name == "a" and n.attributes.get("download") is not None
    )  # fmt: skip
    r = await d.act(click={"index": fake})
    assert r.error and tools.log[-1][1].decision in ("BLOCK", "REROUTE")
