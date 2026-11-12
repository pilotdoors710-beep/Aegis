from playwright.async_api import Page

from aegis.detectors import a2_hit_test
from tests.detectors.helpers import CART, by_text, click, snap_at


async def test_t02_overlay_on_continue(page: Page, arena_url: str) -> None:
    snap = await snap_at(page, f"{arena_url}/cart.html?traps=T02&{CART}")
    cont = by_text(snap, "Continue")
    found = a2_hit_test.detect(snap, click(cont.id), None)
    assert [f.element_id for f in found] == [cont.id]
    assert found[0].trap_type == "clickjacking" and "Subscribe" in found[0].evidence


async def test_clean_twin_silent(page: Page, arena_url: str) -> None:
    snap = await snap_at(page, f"{arena_url}/cart.html?traps=none&{CART}")
    assert a2_hit_test.detect(snap, click(by_text(snap, "Continue").id), None) == []


async def test_visible_modal_only_matters_for_the_target(page: Page, arena_url: str) -> None:
    snap = await snap_at(page, f"{arena_url}/index.html?traps=T01")
    lamp = next(e for e in snap.elements if e.tag == "a" and e.text == "Aurora desk lamp")
    assert a2_hit_test.detect(snap, None, None) == []
    found = a2_hit_test.detect(snap, click(lamp.id), None)
    assert [(f.element_id, f.severity) for f in found] == [(lamp.id, "medium")]
