"""URL validation and egress containment for every page the server's Chromium loads (rule 7).

Infrastructure containment, not trap defense: it applies to BOTH run modes, so the agent can never
reach private IPs, localhost services or cloud metadata from our host. Only the arena origin is
allowed. E5 (scan any URL) instead admits only hosts that resolve to public IPs (scan_guard).
"""

import asyncio
import ipaddress
import socket
from collections.abc import Callable
from urllib.parse import urlsplit

from playwright.async_api import BrowserContext, Response, Route

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


# --- E5 scan: any public website, never our host's network ------------------------------------

SCAN_PORTS = {None, 80, 443}


def is_public_ip(ip: str) -> bool:
    try:
        return ipaddress.ip_address(ip.strip("[]").split("%")[0]).is_global  # no 10/8, 100.64/10
    except ValueError:
        return False


async def resolves_public(host: str) -> bool:
    """Every address the host resolves to is public (one private A record is enough to refuse)."""
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except (OSError, UnicodeError):
        return False
    return bool(infos) and all(is_public_ip(str(i[4][0])) for i in infos)


def scan_url_shape(url: str) -> str | None:
    """Reason the URL is refused before any DNS lookup, or None."""
    try:
        p = urlsplit(url)
        port = p.port
    except ValueError:
        return "not a valid URL"
    if p.scheme not in ("http", "https"):
        return "only http and https URLs can be scanned"
    if not p.hostname:
        return "the URL has no host"
    if p.username or p.password:
        return "URLs with credentials are not allowed"
    if port not in SCAN_PORTS:
        return "only the standard ports 80 and 443 are allowed"
    return None


async def validate_scan_url(url: str) -> str:
    if reason := scan_url_shape(url):
        raise ValueError(reason)
    if not await resolves_public(urlsplit(url).hostname or ""):
        raise ValueError("the host does not resolve to a public internet address")
    return url


class ScanGuard:
    """Per-context egress filter for E5. Each request's host must resolve to public IPs; every
    response's actual server address is re-checked afterwards (DNS can change between our lookup
    and Chromium's), and a scan that touched a non-public address is refused as a whole, so a
    rebinding host cannot get a screenshot of our network back."""

    def __init__(self) -> None:
        self.blocked: list[str] = []
        self._hosts: dict[str, bool] = {}
        self._addrs: list[asyncio.Task[dict | None]] = []

    async def _ok(self, url: str) -> bool:
        p = urlsplit(url)
        if p.scheme in ("data", "blob", "about"):
            return True
        if scan_url_shape(url):
            return False
        host = p.hostname or ""
        if host not in self._hosts:
            self._hosts[host] = await resolves_public(host)
        return self._hosts[host]

    async def install(self, ctx: BrowserContext) -> None:
        async def handle(route: Route) -> None:
            if await self._ok(route.request.url):
                await route.continue_()
            else:
                self.blocked.append(route.request.url)
                await route.abort("blockedbyclient")

        def on_response(r: Response) -> None:
            self._addrs.append(asyncio.ensure_future(r.server_addr()))

        await ctx.route("**/*", handle)
        await ctx.route_web_socket("**/*", lambda ws: None)  # never connected to a server
        ctx.on("response", on_response)

    async def leaked(self) -> bool:
        """True if any response came from a non-public address."""
        addrs = await asyncio.gather(*self._addrs, return_exceptions=True)
        return any(
            isinstance(a, dict) and a.get("ipAddress") and not is_public_ip(a["ipAddress"])
            for a in addrs
        )
