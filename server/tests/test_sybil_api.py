from datetime import UTC, datetime
from types import SimpleNamespace

import httpx

from aegis.config import settings
from api.main import app


async def test_sybil_is_disabled_by_default(monkeypatch):
    monkeypatch.setattr(settings, "sybil_enabled", False)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/sybil/datasets")
    assert response.status_code == 404


async def test_enabled_preview_does_not_claim_imported_data(monkeypatch):
    monkeypatch.setattr(settings, "sybil_enabled", True)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/sybil/datasets")
    assert response.status_code == 200
    dataset = response.json()[0]
    assert dataset["status"] == "unavailable"
    assert dataset["source_nodes"] == 134979706
    assert dataset["imported_nodes"] == dataset["imported_edges"] == 0
    assert dataset["observation_date"] is None


async def test_enabled_api_reports_validated_shared_artifact(monkeypatch):
    monkeypatch.setattr(settings, "sybil_enabled", True)
    monkeypatch.setattr(
        "api.main._load_sybil_dataset",
        lambda _: SimpleNamespace(
            manifest=SimpleNamespace(
                release="cc-main-2026-aug-sep-oct",
                source_counts=SimpleNamespace(nodes=134979706, arcs=1817202146),
                nodes=50000,
                edges=1000000,
                created_at=datetime(2026, 11, 15, tzinfo=UTC),
                source_url="https://index.commoncrawl.org/graphinfo.json",
                id="a" * 64,
            )
        ),
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/sybil/datasets")
    dataset = response.json()[0]
    assert dataset["status"] == "available"
    assert dataset["imported_nodes"] == 50000
    assert dataset["imported_edges"] == 1000000
