import pytest
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import async_playwright

from aegis.security import install_guard, is_allowed, origin, validate_url

ARENA = "https://aegis.example"


def test_allowlist() -> None:
    assert is_allowed("https://aegis.example/arena/cart.html?x=1", ARENA)
    assert is_allowed("data:text/plain,hi", ARENA)
    for bad in [
        "http://169.254.169.254/latest/meta-data/",
        "http://localhost:8000/healthz",
        "https://aegis.example.evil.com/",
        "http://aegis.example/",  # scheme change is a different origin
        "file:///etc/passwd",
    ]:
        assert not is_allowed(bad, ARENA), bad
    with pytest.raises(ValueError):
        validate_url("http://10.0.0.1/", ARENA)


async def test_guard_blocks_metadata_and_localhost(arena_url: str) -> None:
    blocked: list[str] = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        ctx = await browser.new_context()
        await install_guard(ctx, origin(arena_url), blocked.append)
        page = await ctx.new_page()
        await page.goto(f"{arena_url}/index.html")  # allowed
        for url in ["http://169.254.169.254/", "http://localhost:8000/"]:
            with pytest.raises(PlaywrightError):
                await page.goto(url, timeout=5_000)
        await browser.close()
    assert blocked == ["http://169.254.169.254/", "http://localhost:8000/"]
