import asyncio
import re
from pathlib import Path

from playwright.async_api import Page

from aegis.executor import execute
from aegis.schemas import Action
from aegis.snapshot import take_snapshot

EXECUTOR = Path(__file__).resolve().parents[1] / "aegis" / "executor.py"


def test_executor_never_uses_locator_click() -> None:
    src = EXECUTOR.read_text()
    assert not re.search(r"\.click\(", src.replace("page.mouse.click(", ""))
    assert "locator(" not in src


async def test_click_on_covered_button_hits_overlay(page: Page, fixture_url: str) -> None:
    """The T02 property: a coordinate click lands on whatever is on top."""
    await page.goto(f"{fixture_url}/mini_shop.html")
    snap = await take_snapshot(page)
    cont = next(e for e in snap.elements if e.text == "Continue")
    res = await execute(page, Action(type="click", target_id=cont.id, rationale="t"))
    assert res.ok
    assert await page.title() == "subscribed"


async def test_type_and_tick(page: Page, fixture_url: str) -> None:
    await page.goto(f"{fixture_url}/mini_shop.html")
    snap = await take_snapshot(page)
    email = next(e for e in snap.elements if e.text == "Email")
    plan = next(e for e in snap.elements if e.role == "checkbox")
    await execute(page, Action(type="type", target_id=email.id, text="b@example.org"))
    await execute(page, Action(type="click", target_id=plan.id))
    assert await page.input_value("#email") == "b@example.org"
    assert not await page.is_checked("#plan")


async def test_veto_hook_blocks_click(page: Page, fixture_url: str) -> None:
    await page.goto(f"{fixture_url}/mini_shop.html")
    snap = await take_snapshot(page)
    cont = next(e for e in snap.elements if e.text == "Continue")

    async def veto(target_id: str, x: float, y: float) -> str | None:
        return "occluded"

    res = await execute(page, Action(type="click", target_id=cont.id), pre_click=veto)
    assert not res.ok and res.error == "occluded"
    assert await page.title() == "Mini Shop"


async def test_slow_navigation_is_waited_for(page: Page, arena_url: str) -> None:
    """On a slow host the next document commits long after the click returns."""

    async def slow(route):  # noqa: ANN001
        await asyncio.sleep(1.5)
        await route.continue_()

    await page.route("**/product.html*", slow)
    await page.goto(f"{arena_url}/index.html?traps=none")
    snap = await take_snapshot(page)
    link = next(e for e in snap.elements if e.tag == "a" and e.text == "Aurora desk lamp")
    result = await execute(page, Action(type="click", target_id=link.id, rationale="t"))
    after = await take_snapshot(page)
    assert result.ok and "product.html" in after.url
    assert any(e.text == "Add to cart" for e in after.elements)
