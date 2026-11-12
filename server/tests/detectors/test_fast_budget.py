import statistics
import time

from playwright.async_api import Page

from aegis.detectors import run_fast
from tests.detectors.helpers import CART, by_text, click, snap_at


async def test_all_fast_detectors_under_150ms_median(page: Page, arena_url: str) -> None:
    snap = await snap_at(page, f"{arena_url}/checkout.html?traps=T03,T04&{CART}")
    action = click(by_text(snap, "Place order").id)
    times = []
    for _ in range(50):
        t = time.perf_counter()
        run_fast(snap, action, None)
        times.append((time.perf_counter() - t) * 1000)
    assert statistics.median(times) < 150
