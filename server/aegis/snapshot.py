"""page -> PageSnapshot via one page.evaluate() of snapshot.js (brief §3)."""

import base64
from functools import cache
from pathlib import Path

from playwright.async_api import Page

from aegis.schemas import PageSnapshot

_JS = Path(__file__).with_name("snapshot.js")


@cache
def _script() -> str:
    return _JS.read_text()


async def take_snapshot(page: Page) -> PageSnapshot:
    raw = await page.evaluate(_script())
    return PageSnapshot.model_validate(raw)


async def screenshot_b64(page: Page, quality: int = 60) -> str:
    """Viewport JPEG (1280x720, no scaling) for live events."""
    return base64.b64encode(await page.screenshot(type="jpeg", quality=quality)).decode()
