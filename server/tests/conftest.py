"""Shared fixtures: static servers for web/public (the arena) and tests/fixtures; a page."""

import threading
from collections.abc import AsyncIterator, Iterator
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from playwright.async_api import Page, async_playwright

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).with_name("fixtures")


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_: object) -> None:
        pass


def _serve(directory: Path) -> Iterator[str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(_QuietHandler, directory=str(directory)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()


@pytest.fixture(scope="session")
def arena_url() -> Iterator[str]:
    """Serves web/public/ so paths match production: <arena_url>/index.html."""
    for base in _serve(ROOT / "web" / "public"):
        yield f"{base}/arena"


@pytest.fixture(scope="session")
def fixture_url() -> Iterator[str]:
    yield from _serve(FIXTURES)


@pytest.fixture
async def page() -> AsyncIterator[Page]:
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        ctx = await browser.new_context(viewport={"width": 1280, "height": 720})
        try:
            yield await ctx.new_page()
        finally:
            await browser.close()
