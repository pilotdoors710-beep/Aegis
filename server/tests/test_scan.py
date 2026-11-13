"""E5 scan any URL: public-address guard and fast detectors on one read-only page load."""

from collections.abc import AsyncIterator
from urllib.parse import urlsplit

import httpx
import pytest
from playwright.async_api import async_playwright

import api.main as main
from aegis import security
from aegis.schemas import ScanReport


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    async with async_playwright() as pw:
        main._browser = await pw.chromium.launch()
        transport = httpx.ASGITransport(app=main.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://t", timeout=60) as c:
            yield c
        assert not main._browser.contexts  # the scan context is always closed
        await main._browser.close()


@pytest.fixture(autouse=True)
def arena_port(monkeypatch: pytest.MonkeyPatch, arena_url: str) -> None:
    monkeypatch.setattr(security, "SCAN_PORTS", {*security.SCAN_PORTS, urlsplit(arena_url).port})


@pytest.fixture
def local_is_public(monkeypatch: pytest.MonkeyPatch) -> None:
    """The test arena is served on 127.0.0.1; treat it as a public site for these tests only."""
    real = security.is_public_ip
    monkeypatch.setattr(
        security, "is_public_ip", lambda ip: ip.strip("[]") == "127.0.0.1" or real(ip)
    )


def test_public_ip() -> None:
    assert security.is_public_ip("8.8.8.8") and security.is_public_ip("[2606:4700::1111]")
    for ip in ["127.0.0.1", "10.1.2.3", "192.168.1.1", "100.100.1.1", "169.254.169.254",
               "[::1]", "fe80::1%eth0", "0.0.0.0", "not-an-ip"]:  # fmt: skip
        assert not security.is_public_ip(ip), ip


@pytest.mark.parametrize("url", [
    "file:///etc/passwd", "ftp://example.com/", "http://user:pw@example.com/",
    "http://example.com:8080/", "http://localhost/", "http://127.0.0.1/", "http://10.0.0.1/",
    "http://169.254.169.254/latest/meta-data/", "http://[::1]/", "javascript:alert(1)",
])  # fmt: skip
async def test_refuses_non_public(client: httpx.AsyncClient, url: str) -> None:
    r = await client.post("/scan", json={"url": url})
    assert r.status_code == 422 and "Cannot scan" in r.text, (url, r.text)


async def scan(client: httpx.AsyncClient, url: str) -> ScanReport:
    r = await client.post("/scan", json={"url": url})
    assert r.status_code == 200, r.text
    return ScanReport.model_validate(r.json())


@pytest.mark.usefixtures("local_is_public")
async def test_trap_page_and_clean_twin(client: httpx.AsyncClient, arena_url: str) -> None:
    trap = await scan(client, f"{arena_url}/product.html?traps=T05,T06")
    found = {(f.detector, f.trap_type) for f in trap.findings}
    assert ("B5_quarantine", "prompt_injection") in found
    assert ("C1_persuasion", "social_proof") in found
    assert {e.id for e in trap.flagged} == {f.element_id for f in trap.findings}
    assert trap.screenshot_b64 and trap.element_count > 0 and trap.detector_ms < 150

    clean = await scan(client, f"{arena_url}/product.html?traps=none")
    assert clean.findings == [] and clean.notes == []


async def test_rebinding_is_refused(
    client: httpx.AsyncClient, arena_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Our DNS check says public, but Chromium actually connects to 127.0.0.1: no report."""

    async def lies(host: str) -> bool:
        return True

    monkeypatch.setattr(security, "resolves_public", lies)
    r = await client.post("/scan", json={"url": f"{arena_url}/index.html"})
    assert r.status_code == 422 and "non-public address" in r.text
    assert "screenshot" not in r.text
