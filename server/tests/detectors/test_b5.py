from playwright.async_api import Page

from aegis.detectors import b5_quarantine
from tests.detectors.helpers import CLEAN_PAGES, snap_at


async def test_t05_injection_flagged(page: Page, arena_url: str) -> None:
    snap = await snap_at(page, f"{arena_url}/product.html?traps=T05")
    found = b5_quarantine.detect(snap, None, None)
    assert [f.trap_type for f in found] == ["prompt_injection"]
    assert "AI assistant" in found[0].evidence


async def test_harmless_assistant_copy_silent(page: Page, fixture_url: str) -> None:
    await page.goto(f"{fixture_url}/mini_shop.html")
    await page.set_content(
        "<p>Works with your voice assistant and smart home.</p>"
        "<p>Our assistant manager picked this lamp for small desks.</p>"
        "<p>Questions? Ask our shopping assistant.</p><p>The user manual is included.</p>"
        "<p>Agent-free returns within 30 days.</p>"
    )
    from aegis.snapshot import take_snapshot

    assert b5_quarantine.detect(await take_snapshot(page), None, None) == []


async def test_clean_twin_silent(page: Page, arena_url: str) -> None:
    for path in CLEAN_PAGES:
        sep = "&" if "?" in path else "?"
        snap = await snap_at(page, f"{arena_url}/{path}{sep}traps=none")
        assert b5_quarantine.detect(snap, None, None) == [], path


async def test_t07_faint_injection_quarantined(page: Page, arena_url: str) -> None:
    snap = await snap_at(page, f"{arena_url}/product.html?traps=T07")
    found = b5_quarantine.detect(snap, None, None)
    assert [f.trap_type for f in found] == ["prompt_injection"]
