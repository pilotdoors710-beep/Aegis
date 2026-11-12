from playwright.async_api import Page

from aegis.detectors import a3_faint_text
from tests.detectors.helpers import CLEAN_PAGES, snap_at


async def test_faint_text_flagged(page: Page, fixture_url: str) -> None:
    snap = await snap_at(page, f"{fixture_url}/mini_shop.html")
    found = a3_faint_text.detect(snap, None, None)
    assert any("Faint fine print" in f.evidence for f in found)
    assert all("Mini Shop" not in f.evidence for f in found)


async def test_clean_twin_silent(page: Page, arena_url: str) -> None:
    for path in CLEAN_PAGES:
        sep = "&" if "?" in path else "?"
        snap = await snap_at(page, f"{arena_url}/{path}{sep}traps=none")
        assert a3_faint_text.detect(snap, None, None) == [], path


async def test_t07_faint_injection_flagged(page: Page, arena_url: str) -> None:
    snap = await snap_at(page, f"{arena_url}/product.html?traps=T07")
    found = a3_faint_text.detect(snap, None, None)
    assert any("partner.html" in f.evidence for f in found)
