from playwright.async_api import Page

from aegis.schemas import Action, PageSnapshot
from aegis.snapshot import take_snapshot

CART = "cart=aurora-desk-lamp:1"
# Every clean arena page an agent visits; trap pages use the same paths.
CLEAN_PAGES = ["index.html", "product.html", f"cart.html?{CART}", f"checkout.html?{CART}"]


async def snap_at(page: Page, url: str) -> PageSnapshot:
    await page.goto(url)
    return await take_snapshot(page)


def by_text(snap: PageSnapshot, text: str):
    return next(e for e in snap.elements if e.text == text)


def click(target_id: str) -> Action:
    return Action(type="click", target_id=target_id, rationale="test")
