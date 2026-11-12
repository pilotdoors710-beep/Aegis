from playwright.async_api import Page

from aegis.detectors import a1_visibility
from tests.detectors.helpers import CLEAN_PAGES, by_text, click, snap_at


async def test_t05_hidden_injection_flagged(page: Page, arena_url: str) -> None:
    snap = await snap_at(page, f"{arena_url}/product.html?traps=T05")
    found = a1_visibility.detect(snap, None, None)
    assert any("AI assistant" in f.evidence and f.trap_type == "hidden_info" for f in found)


async def test_click_on_invisible_target_is_high(page: Page, arena_url: str) -> None:
    snap = await snap_at(page, f"{arena_url}/cart.html?traps=T02&cart=aurora-desk-lamp:1")
    overlay = by_text(snap, "Subscribe ₹199/mo")
    found = a1_visibility.detect(snap, click(overlay.id), None)
    assert any(f.element_id == overlay.id and f.severity == "high" for f in found)


async def test_clean_twin_silent(page: Page, arena_url: str) -> None:
    for path in CLEAN_PAGES:
        sep = "&" if "?" in path else "?"
        snap = await snap_at(page, f"{arena_url}/{path}{sep}traps=none")
        assert a1_visibility.detect(snap, None, None) == [], path
