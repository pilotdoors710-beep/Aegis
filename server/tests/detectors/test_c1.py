from playwright.async_api import Page

from aegis.detectors import c1_persuasion
from tests.detectors.helpers import CLEAN_PAGES, snap_at


async def test_t06_pressure_flagged(page: Page, arena_url: str) -> None:
    snap = await snap_at(page, f"{arena_url}/product.html?traps=T06")
    kinds = sorted(f.trap_type for f in c1_persuasion.detect(snap, None, None))
    assert kinds == ["social_proof", "urgency", "urgency"]  # people bought, countdown, strike


async def test_clean_twin_silent(page: Page, arena_url: str) -> None:
    for path in CLEAN_PAGES:
        sep = "&" if "?" in path else "?"
        snap = await snap_at(page, f"{arena_url}/{path}{sep}traps=none")
        assert c1_persuasion.detect(snap, None, None) == [], path
