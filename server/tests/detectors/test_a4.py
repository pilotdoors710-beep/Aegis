from playwright.async_api import Page

from aegis.detectors import a4_link_truth
from aegis.schemas import Ledger
from aegis.snapshot import take_snapshot
from tests.detectors.helpers import CLEAN_PAGES, by_text, snap_at


async def test_t01_fake_close_downloads(page: Page, arena_url: str) -> None:
    snap = await snap_at(page, f"{arena_url}/index.html?traps=T01")
    close = by_text(snap, "×")
    found = a4_link_truth.detect(snap, None, None)
    assert [(f.element_id, f.trap_type) for f in found] == [(close.id, "fake_control")]
    assert "downloads" in found[0].evidence


async def test_off_site_and_upgrade_links(page: Page, fixture_url: str) -> None:
    await page.goto(f"{fixture_url}/mini_shop.html")  # real origin for relative hrefs
    await page.set_content(
        '<a href="https://evil.example/x">No thanks</a><a href="/premium/upgrade">Close</a>'
        '<a href="/cart.html">Continue</a><a href="https://evil.example/">Shop now</a>'
    )
    snap = await take_snapshot(page)
    found = a4_link_truth.detect(snap, None, Ledger(goal="g", allowed_domains=["127.0.0.1"]))
    assert sorted(f.evidence.split(" but ")[1][:9] for f in found) == ["navigates", "opens a p"]


async def test_clean_twin_silent(page: Page, arena_url: str) -> None:
    for path in CLEAN_PAGES:
        sep = "&" if "?" in path else "?"
        snap = await snap_at(page, f"{arena_url}/{path}{sep}traps=none")
        assert a4_link_truth.detect(snap, None, None) == [], path
