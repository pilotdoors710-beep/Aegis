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
