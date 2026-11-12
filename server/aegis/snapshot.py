"""page -> PageSnapshot via one page.evaluate() of snapshot.js (brief §3)."""

import base64
from functools import cache
from pathlib import Path

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Page

from aegis.schemas import PageSnapshot

_JS = Path(__file__).with_name("snapshot.js")


@cache
def _script() -> str:
    return _JS.read_text()


async def take_snapshot(page: Page, attempts: int = 4) -> PageSnapshot:
    # A click may start a navigation that lands after the executor settled: wait and retry.
    for i in range(attempts):
        try:
            # A half-loaded page reads as empty and the agent gives up: wait for the DOM first.
            await page.wait_for_load_state("domcontentloaded", timeout=10_000)
            raw = await page.evaluate(_script())
            return PageSnapshot.model_validate(raw)
        except PlaywrightError as e:
            if i == attempts - 1 or "context was destroyed" not in str(e):
                raise
            await page.wait_for_load_state("domcontentloaded", timeout=10_000)
    raise AssertionError("unreachable")


async def screenshot_b64(page: Page, quality: int = 60) -> str:
    """Viewport JPEG (1280x720, no scaling) for live events."""
    return base64.b64encode(await page.screenshot(type="jpeg", quality=quality)).decode()
