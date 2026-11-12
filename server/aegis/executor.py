"""Executes agent Actions on the live page (brief §3, §9 rule 12).

Clicks are ALWAYS page.mouse.click(x, y) at the target's bbox centre. Playwright's actionability
checks would refuse a click intercepted by an overlay and silently protect the unshielded agent.
"""

import asyncio
import contextlib
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Page, Request

from aegis.schemas import Action

SETTLE_TIMEOUT_MS = 5_000
# Shielded mode passes a pre-click hook that re-runs the hit-test at (x, y) and may veto.
PreClick = Callable[[str, float, float], Awaitable[str | None]]

_CENTER_JS = """(id) => {
  const el = document.querySelector(`[data-cs-id="${id}"]`);
  if (!el) return null;
  el.scrollIntoView({block: "center", inline: "center"});
  const r = el.getBoundingClientRect();
  return [r.left + r.width / 2, r.top + r.height / 2];
}"""


@dataclass
class ExecResult:
    ok: bool
    url_after: str | None
    error: str | None = None


async def _center(page: Page, target_id: str) -> tuple[float, float] | None:
    xy = await page.evaluate(_CENTER_JS, target_id)
    return (xy[0], xy[1]) if xy else None


class _NavWatch:
    """Listens BEFORE the action, so a navigation it causes is never missed: on a slow host the
    new document can commit long after the click returns, and a snapshot of the old or a
    half-parsed page made the agent give up."""

    def __init__(self, page: Page) -> None:
        self.page, self.started, self.loaded = page, False, asyncio.Event()
        page.on("request", self._request)
        page.on("domcontentloaded", self._dom)

    def _request(self, request: Request) -> None:
        if request.is_navigation_request() and request.frame == self.page.main_frame:
            self.started = True
            self.loaded.clear()

    def _dom(self, _: Page) -> None:
        self.loaded.set()

    async def settle(self) -> None:
        await asyncio.sleep(0.15)  # handlers that set location.href start just after the click
        if self.started:
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self.loaded.wait(), SETTLE_TIMEOUT_MS / 1000)

    def close(self) -> None:
        self.page.remove_listener("request", self._request)
        self.page.remove_listener("domcontentloaded", self._dom)


async def execute(page: Page, action: Action, pre_click: PreClick | None = None) -> ExecResult:
    watch = _NavWatch(page)
    try:
        match action.type:
            case "click" | "submit" | "type":
                if not action.target_id:
                    if action.type == "submit":
                        await page.keyboard.press("Enter")
                        await watch.settle()
                        return ExecResult(True, page.url)
                    return ExecResult(False, page.url, "missing target_id")
                xy = await _center(page, action.target_id)
                if xy is None:
                    return ExecResult(False, page.url, f"element {action.target_id} not found")
                if pre_click and (veto := await pre_click(action.target_id, *xy)):
                    return ExecResult(False, page.url, veto)
                await page.mouse.click(*xy)
                if action.type == "type":
                    await page.keyboard.press("ControlOrMeta+A")
                    await page.keyboard.type(action.text or "")
            case "select":
                if not action.target_id:
                    return ExecResult(False, page.url, "missing target_id")
                sel = f'[data-cs-id="{action.target_id}"]'
                await page.select_option(sel, label=action.text or "", timeout=SETTLE_TIMEOUT_MS)
            case "navigate":
                if not action.url:
                    return ExecResult(False, page.url, "missing url")
                await page.goto(action.url, wait_until="domcontentloaded")
            case "done":
                return ExecResult(True, page.url)
        await watch.settle()
        return ExecResult(True, page.url)
    except PlaywrightError as e:
        return ExecResult(False, page.url, f"{type(e).__name__}: {str(e).splitlines()[0]}")
    finally:
        watch.close()


_HIT_JS = """([id, x, y]) => {
  const t = document.querySelector(`[data-cs-id="${id}"]`);
  const hit = document.elementFromPoint(x, y);
  if (!t || !hit) return "nothing to click at the target's position";
  if (t === hit || t.contains(hit) || (t.labels && [...t.labels].includes(hit))) return null;
  const host = hit.closest("[data-cs-id]");
  return `click point is covered by ${host ? host.dataset.csId : hit.tagName.toLowerCase()}`;
}"""


async def neutralize(page: Page, element_id: str) -> bool:
    """Make one (invisible) element click-through. Logged by the caller as a Neutralization."""
    return await page.evaluate(
        """(id) => { const el = document.querySelector(`[data-cs-id="${id}"]`);
        if (!el) return false; el.style.setProperty("pointer-events", "none", "important");
        return true; }""",
        element_id,
    )


def hit_test_veto(page: Page) -> PreClick:
    """Shielded only: re-run A2 at the real click point right before clicking (the page may have
    changed during the LLM call)."""

    async def check(target_id: str, x: float, y: float) -> str | None:
        reason = await page.evaluate(_HIT_JS, [target_id, x, y])
        return f"Aegis pre-click hit-test: {reason}" if reason else None

    return check
