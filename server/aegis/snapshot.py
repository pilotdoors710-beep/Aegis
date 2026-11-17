"""page -> PageSnapshot via one page.evaluate() of snapshot.js (brief §3)."""

import base64
from functools import cache
from pathlib import Path

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Page

from aegis.schemas import PageSnapshot, ScanScreen

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
            if raw is not None:
                return PageSnapshot.model_validate(raw)
            await page.wait_for_timeout(200)
            continue
        except PlaywrightError as e:
            if i == attempts - 1 or "context was destroyed" not in str(e):
                raise
            await page.wait_for_load_state("domcontentloaded", timeout=10_000)
    raise RuntimeError("the page never finished loading")


async def screenshot_b64(page: Page, quality: int = 60) -> str:
    """Viewport JPEG (1280x720, no scaling) for live events."""
    return base64.b64encode(await page.screenshot(type="jpeg", quality=quality)).decode()


# Boxes of the given snapshot ids as they sit in the current viewport (ids off screen or with no
# size are left out), plus every id's position in the page so the next screen can be chosen.
_MEASURE = """(ids) => {
  const round = (v) => Math.round(v * 10) / 10;
  const boxes = {}, pageY = {};
  for (const id of ids) {
    const el = document.querySelector(`[data-cs-id="${CSS.escape(id)}"]`);
    if (!el) continue;
    const r = el.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) continue;
    pageY[id] = r.top + scrollY;
    if (r.bottom > 0 && r.top < innerHeight && r.right > 0 && r.left < innerWidth)
      boxes[id] = [r.left, r.top, r.width, r.height].map(round);
  }
  return { scrollY: Math.round(scrollY), boxes, pageY };
}"""
_SCROLL_TO = """(id) => document.querySelector(`[data-cs-id="${CSS.escape(id)}"]`)
  ?.scrollIntoView({ block: "center", inline: "nearest", behavior: "instant" })"""
# Scroll-reveal effects (fade/slide in) would leave the screenshot half drawn: wait for the
# finite animations and transitions running now, at most max_ms (spinners never finish).
_SETTLE = """async (maxMs) => {
  const finite = document.getAnimations().filter((a) =>
    Number.isFinite(a.effect?.getComputedTiming().endTime));
  await Promise.race([Promise.all(finite.map((a) => a.finished.catch(() => null))),
                      new Promise((done) => setTimeout(done, maxMs))]);
}"""


async def evidence_screens(
    page: Page, ids: list[str], extra: int = 2, settle_ms: int = 150, max_anim_ms: int = 1000
) -> list[ScanScreen]:
    """Viewport screenshots that show the flagged elements: the top of the page, then up to
    `extra` screens each scrolled to the highest flagged element not yet shown. Boxes are
    measured again after every scroll."""
    m = await page.evaluate(_MEASURE, ids)
    screens = [ScanScreen(scroll_y=m["scrollY"], screenshot_b64=await screenshot_b64(page),
                          boxes=m["boxes"])]  # fmt: skip
    shown = set(m["boxes"])
    tried: set[str] = set()
    while len(screens) <= extra and len(tried) < extra + 3:  # bounded scroll attempts
        # Elements with no size (display:none, zero-size injections) have nothing to show.
        todo = sorted((y, i) for i, y in m["pageY"].items() if i not in shown | tried)
        if not todo:
            break
        target = todo[0][1]
        tried.add(target)
        await page.evaluate(_SCROLL_TO, target)
        await page.wait_for_timeout(settle_ms)  # lazy images, scroll observers start effects
        await page.evaluate(_SETTLE, max_anim_ms)
        m = await page.evaluate(_MEASURE, ids)
        new = set(m["boxes"]) - shown
        if not new:  # it never came into view (fixed off screen, clipped container): skip it
            continue
        shown |= new
        screens.append(ScanScreen(scroll_y=m["scrollY"], screenshot_b64=await screenshot_b64(page),
                                  boxes=m["boxes"]))  # fmt: skip
    return screens
