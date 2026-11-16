"""How Aegis opens arena pages and reads what they show (brief §3, ADR-0008).

One fixed viewport and frozen clock for every page, the Disposable-copy recipe (fresh context,
arena-only egress, no downloads, popups or service workers, always closed), replay of the
agent's executed Actions, and the Outcome reader that only reads the visible confirmation.
"""

import asyncio
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime

from playwright.async_api import Browser, BrowserContext, Page

from aegis.audit import FEE, RECURRING, money
from aegis.executor import execute, neutralize
from aegis.schemas import Action, Commitment, Outcome
from aegis.security import install_guard
from aegis.snapshot import take_snapshot

VIEWPORT = {"width": 1280, "height": 720}
# Fixed clock so countdowns and dates render identically on every run (brief §3).
FROZEN_TIME = datetime(2026, 11, 18, 10, 0, tzinfo=UTC)

# One replayed step: the agent's executed action and the overlay Aegis neutralized before it.
ReplayStep = tuple[Action, str | None]


@dataclass(frozen=True)
class Checkout:
    """How to rebuild a Side's current page in a Disposable copy. `replay` is the Side's own
    list, so it grows as the Side executes Actions."""

    start_url: str
    allowed_origin: str
    replay: list[ReplayStep]


# Removes the automation signals a cloaking site can key on from page script. It is not proof of
# what a person sees: the engine and the network exit are the same as the agent's.
_HIDE_AUTOMATION = "Object.defineProperty(Navigator.prototype, 'webdriver', {get: () => false})"


def _ordinary_user_agent(browser: Browser) -> str:
    major = browser.version.split(".")[0]
    return (f"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
            f"Chrome/{major}.0.0.0 Safari/537.36")  # fmt: skip


def _close_extra_pages(ctx: BrowserContext):  # noqa: ANN202
    def handler(page: Page) -> None:
        if len(ctx.pages) > 1:  # popups and new tabs are not part of a disposable copy
            asyncio.ensure_future(page.close())

    return handler


@asynccontextmanager
async def disposable_copy(
    browser: Browser, url: str, allowed_origin: str, blocked: list[str], *, ordinary: bool = False
) -> AsyncIterator[Page]:
    """A contained page at `url` in a fresh context, closed on exit whatever happens.
    ordinary=True strips automation signals (Two-view check). Refused requests go to `blocked`."""
    ctx = await browser.new_context(
        viewport=VIEWPORT,  # type: ignore[arg-type]
        accept_downloads=False,
        service_workers="block",
        user_agent=_ordinary_user_agent(browser) if ordinary else None,
    )
    try:
        if ordinary:
            await ctx.add_init_script(_HIDE_AUTOMATION)
        await install_guard(ctx, allowed_origin, blocked.append)
        ctx.on("page", _close_extra_pages(ctx))
        page = await ctx.new_page()
        await page.clock.set_fixed_time(FROZEN_TIME)
        await page.goto(url, wait_until="domcontentloaded")
        yield page
    finally:
        await ctx.close()


async def replay(page: Page, steps: list[ReplayStep]) -> tuple[int, str | None]:
    """Redo the agent's executed actions in a copy. Returns (actions done, error)."""
    done = 0
    for action, neutralized in steps:
        await take_snapshot(page)  # stamps the same deterministic element ids
        if neutralized:
            await neutralize(page, neutralized)
        res = await execute(page, action)
        done += 1
        if not res.ok:
            return done, f"replay step failed: {res.error}"
    return done, None


_TOTAL_RE = re.compile(r"Order total[^\d₹]*₹?\s*([\d,]+(?:\.\d+)?)", re.I)


def commitment_from_text(text: str) -> Commitment | None:
    """One line of a visible "You agreed to" list -> an executed simulated commitment."""
    if m := re.match(r"^\s*(\d+)\s*×\s*(.+)$", text):
        return Commitment(kind="item", description=f"{m.group(2).strip()} × {m.group(1)}",
                          state="executed")  # fmt: skip
    if re.search(r"shipping", text, re.I) or re.match(r"^\s*no\b", text, re.I):
        return None  # delivery terms and explicit "no ..." lines are not commitments
    if re.match(r"^\s*purchased from shop\b", text, re.I):
        return None  # which shop sold it: recorded as Outcome.shop, not an extra purchase
    amount = money(text)
    if p := RECURRING.search(text):
        period = "month" if re.search(r"mo", p.group(0), re.I) else "year"
        return Commitment(kind="subscription", description=text, amount=amount, period=period,
                          state="executed")  # fmt: skip
    if FEE.search(text):
        return Commitment(kind="fee", description=text, amount=amount, state="executed")
    if re.search(r"\bshar(e|ing)\b|partner", text, re.I):
        return Commitment(kind="data_sharing", description=text, state="executed")
    return Commitment(kind="addon", description=text, amount=amount, state="executed")


async def outcome_from_page(page: Page, downloads: list[str] | None = None) -> Outcome:
    """Visible confirmation text only; the evaluator scores against separate ground truth."""
    got = [Commitment(kind="download", description=f"Downloaded {name}", state="executed")
           for name in downloads or []]  # fmt: skip
    try:
        body = await page.inner_text("body", timeout=2_000)
    except Exception:
        return Outcome(commitments=got)
    if "order confirmed" not in body.lower():
        return Outcome(task_completed=False, commitments=got)
    m = _TOTAL_RE.search(body)
    total = float(m.group(1).replace(",", "")) if m else None
    shop_m = re.search(r"order confirmed\s*[·-]\s*shop\s+([ab])", body, re.I) or re.search(
        r"purchased from shop\s+([ab])", body, re.I
    )
    shop = shop_m.group(1).upper() if shop_m else None
    agreed = await page.eval_on_selector_all("li", "els => els.map(e => e.innerText)")
    got += [c for t in agreed if (c := commitment_from_text(t))]
    return Outcome(task_completed=True, total=total, commitments=got, shop=shop)
