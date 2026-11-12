"""URL validation and egress containment for every page the server's Chromium loads (rule 7).

Infrastructure containment, not trap defense: it applies to BOTH run modes, so the agent can never
reach private IPs, localhost services or cloud metadata from our host. Only the arena origin is
allowed. shortcut: arena-only allowlist; E5 (scan any URL) needs DNS-resolving private-IP checks.
"""

from collections.abc import Callable
from urllib.parse import urlsplit

from playwright.async_api import BrowserContext, Route

from aegis.config import settings


def origin(url: str) -> str:
    p = urlsplit(url)
    return f"{p.scheme}://{p.netloc}".lower()


def arena_origin(base: str | None = None) -> str:
    return origin(base or settings.arena_base_url)


def is_allowed(url: str, allowed_origin: str) -> bool:
    p = urlsplit(url)
    if p.scheme in ("data", "blob", "about"):  # in-page content, no network egress
        return True
    return p.scheme in ("http", "https") and origin(url) == allowed_origin


def validate_url(url: str, allowed_origin: str) -> str:
    if not is_allowed(url, allowed_origin):
        raise ValueError(f"URL outside the arena origin {allowed_origin}: {url[:200]}")
    return url


async def install_guard(
    ctx: BrowserContext, allowed_origin: str, on_block: Callable[[str], None] | None = None
) -> None:
    """Abort every request (navigation, subresource, popup) that leaves the arena origin."""

    async def handle(route: Route) -> None:
        url = route.request.url
        if is_allowed(url, allowed_origin):
            await route.continue_()
            return
        if on_block:
            on_block(url)
        await route.abort("blockedbyclient")

    await ctx.route("**/*", handle)
