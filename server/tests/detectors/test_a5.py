from playwright.async_api import Page

from aegis.detectors import a5_context
from tests.detectors.helpers import CLEAN_PAGES, by_text, snap_at


async def test_sponsored_checkout_flagged(page: Page, fixture_url: str) -> None:
    snap = await snap_at(page, f"{fixture_url}/disguised_ad.html")
    ad = by_text(snap, "Proceed to checkout")
    assert "Sponsored" in ad.nearby_text  # context binding: the label sits outside the box
    found = a5_context.detect(snap, None, None)
    assert [(f.element_id, f.trap_type) for f in found] == [(ad.id, "disguised_ad")]


async def test_clean_twin_silent(page: Page, fixture_url: str, arena_url: str) -> None:
    assert (
        a5_context.detect(await snap_at(page, f"{fixture_url}/disguised_clean.html"), None, None)
        == []
    )
    for path in CLEAN_PAGES:
        sep = "&" if "?" in path else "?"
        snap = await snap_at(page, f"{arena_url}/{path}{sep}traps=none")
        assert a5_context.detect(snap, None, None) == [], path
