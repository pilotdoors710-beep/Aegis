from datetime import UTC, datetime
from types import SimpleNamespace

import httpx

from aegis.config import settings
from aegis.schemas import SybilAssessmentRecord
from aegis.sybil import Graph
from aegis.sybil_runtime import SybilRuntime, assessment_identity
from aegis.sybil_scenario import BaseGraph
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
    assert dataset["dataset_id"] == "a" * 64
    assert dataset["imported_nodes"] == 50000
    assert dataset["imported_edges"] == 1000000


async def test_scenario_revision_and_bounded_view(monkeypatch):
    runtime = SybilRuntime()
    nodes = tuple(
        SimpleNamespace(
            id=str(i),
            domain=f"site-{i}.invalid",
            original_outdegree=int(i < 2),
            retained_outdegree=int(i < 2),
            x=float(i),
            y=0.0,
        )
        for i in range(3)
    )
    dataset = SimpleNamespace(
        manifest=SimpleNamespace(id="test"),
        nodes=nodes,
        base=BaseGraph(
            "test",
            "a" * 64,
            tuple(v.id for v in nodes),
            Graph(3, ((0, 2), (1, 2)), (1, 1, 0)),
            ("0", "1"),
            0.1,
        ),
    )
    monkeypatch.setattr(settings, "sybil_enabled", True)
    monkeypatch.setattr("api.main._load_sybil_dataset", lambda _: dataset)
    monkeypatch.setattr("api.main._sybil", runtime)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        created = await client.post(
            "/sybil/scenarios",
            json={
                "dataset_id": "test",
                "injected_nodes": ["sim:one"],
                "recommendations": [{"website": "sim:one", "shop": "B"}],
            },
        )
        assert created.status_code == 201
        revision = created.json()
        fetched = await client.get(f"/sybil/scenarios/{revision['id']}")
        view = await client.get(f"/sybil/scenarios/{revision['id']}/view?limit=3")
        replacement = SybilRuntime()
        monkeypatch.setattr("api.main._sybil", replacement)
        restored = await client.get(f"/sybil/scenarios/{revision['id']}")
    assert fetched.json() == revision
    assert restored.json() == revision
    assert view.status_code == 200
    assert view.json()["displayed_nodes"] == 3
    assert view.json()["subset"] is True
    assert any(v["provenance"] == "simulated" for v in view.json()["nodes"])
    runtime.shutdown()
    replacement.shutdown()


async def test_assessment_endpoints_reuse_revision_identity(monkeypatch):
    revision_id = "b" * 64
    assessment = SybilAssessmentRecord(
        id=assessment_identity(revision_id), revision_id=revision_id, status="queued"
    )
    runtime = SimpleNamespace(
        get=lambda value: SimpleNamespace(revision=SimpleNamespace(id=value)),
        submit=lambda _directory, _scenario: assessment,
        assessment=lambda value: assessment if value == assessment.id else None,
    )
    monkeypatch.setattr(settings, "sybil_enabled", True)
    monkeypatch.setattr("api.main._load_sybil_dataset", lambda _: SimpleNamespace())
    monkeypatch.setattr("api.main._sybil", runtime)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        started = await client.post(f"/sybil/scenarios/{revision_id}/assessments")
        fetched = await client.get(f"/sybil/assessments/{assessment.id}")
    assert started.status_code == 202
    assert fetched.json() == started.json()
