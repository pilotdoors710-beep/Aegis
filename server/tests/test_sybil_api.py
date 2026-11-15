from datetime import UTC, datetime
from types import SimpleNamespace

import httpx

from aegis.config import settings
from aegis.schemas import SybilAssessmentRecord, SybilCounterfactualResult, SybilScoreDelta
from aegis.sybil import Graph
from aegis.sybil_runtime import (
    SybilRuntime,
    assessment_identity,
    calculate_counterfactual,
    graph_evidence,
)
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
        generated = await client.post(
            "/sybil/datasets/test/generate",
            json={"count": 10, "seed": 7, "pattern": "chain", "density": 0.1, "target": "A"},
        )
    assert fetched.json() == revision
    assert restored.json() == revision
    assert view.status_code == 200
    assert view.json()["displayed_nodes"] == 3
    assert view.json()["subset"] is True
    assert any(v["provenance"] == "simulated" for v in view.json()["nodes"])
    assert generated.status_code == 201
    assert generated.json()["budget"]["internal_links"] == 9
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


async def test_counterfactual_is_bound_to_baseline_revision(monkeypatch):
    revision_id = "b" * 64
    proposed_id = "c" * 64
    result = SybilCounterfactualResult(
        baseline_revision_id=revision_id,
        counterfactual_revision_id=proposed_id,
        status="complete",
        elapsed_ms=12,
        deltas={
            shop: SybilScoreDelta(
                trust_weighted_support=0,
                structural_support=0,
                anchor_breadth=0,
                anchor_withdrawal_resilience=0,
                tested_connection_resilience=0,
                total_robustness=1 if shop == "A" else -1,
                rank=-1 if shop == "A" else 1,
            )
            for shop in ("A", "B")
        },
    )
    baseline = SimpleNamespace(revision=SimpleNamespace(id=revision_id))
    proposed = SimpleNamespace(revision=SimpleNamespace(id=proposed_id))
    runtime = SimpleNamespace(
        get=lambda value: baseline if value == revision_id else None,
        create=lambda _dataset, _body: proposed,
        counterfactual=lambda _directory, current, next_scenario: _async_result(
            result, current, next_scenario, baseline, proposed
        ),
    )
    monkeypatch.setattr(settings, "sybil_enabled", True)
    monkeypatch.setattr(
        "api.main._load_sybil_dataset",
        lambda _: SimpleNamespace(base=SimpleNamespace(dataset_id="test")),
    )
    monkeypatch.setattr("api.main._sybil", runtime)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            f"/sybil/scenarios/{revision_id}/counterfactuals",
            json={"dataset_id": "test"},
        )
    assert response.status_code == 200
    assert response.json()["baseline_revision_id"] == revision_id
    assert response.json()["deltas"]["A"]["total_robustness"] == 1


def test_counterfactual_calculates_score_and_rank_deltas(monkeypatch):
    base = BaseGraph(
        "test",
        "a" * 64,
        ("anchor-a", "anchor-b", "site"),
        Graph(3, ((0, 2), (1, 2)), (1, 1, 0)),
        ("anchor-a", "anchor-b"),
        0.1,
    )
    monkeypatch.setattr(
        "aegis.sybil_runtime._worker_dataset", lambda _directory: SimpleNamespace(base=base)
    )
    shared = (
        '"dataset_id":"test","injected_nodes":["sim:one"],'
        '"added_links":[{"source":"anchor-a","target":"sim:one"}],'
        '"cooperating_links":[{"source":"anchor-a","target":"sim:one"}],'
    )
    before = "{" + shared + '"recommendations":[{"website":"sim:one","shop":"A"}]}'
    after = "{" + shared + '"recommendations":[{"website":"sim:one","shop":"B"}]}'
    result = calculate_counterfactual("unused", before, after)
    assert result["status"] == "complete"
    assert result["deltas"]["A"]["total_robustness"] < 0
    assert result["deltas"]["A"]["rank"] == 1
    assert result["deltas"]["B"]["total_robustness"] > 0
    assert result["deltas"]["B"]["rank"] == -1


async def _async_result(result, current, next_scenario, baseline, proposed):
    assert current is baseline
    assert next_scenario is proposed
    return result


def test_graph_evidence_applies_both_policy_thresholds() -> None:
    revision_id = "d" * 64
    scores = {
        shop: {
            "recommendation_count": 2,
            "trust_weighted_support": 0.2,
            "structural_support": support,
            "effective_anchors": 2,
            "anchor_breadth": 0.5,
            "anchor_withdrawal_resilience": 0.5,
            "tested_connection_resilience": 0.5,
            "total_robustness": total,
            "tested_edges": [],
        }
        for shop, support, total in (("A", 0.5, 60), ("B", 0.49, 80))
    }
    assessment = SybilAssessmentRecord.model_validate(
        {
            "id": assessment_identity(revision_id),
            "revision_id": revision_id,
            "status": "complete",
            "scores": scores,
        }
    )
    evidence = graph_evidence(assessment)
    assert evidence.shops["A"].policy_passed is True
    assert evidence.shops["B"].policy_passed is False


def test_bridge_inflated_score_still_fails_anchor_floor() -> None:
    # Measured chain + 6 bridges attack on the real graph: R and S pass, L does not.
    revision_id = "e" * 64
    attacked = {
        "recommendation_count": 301,
        "trust_weighted_support": 0.0018,
        "structural_support": 0.999,
        "effective_anchors": 1.2,
        "anchor_breadth": 0.03,
        "anchor_withdrawal_resilience": 0.11,
        "tested_connection_resilience": 1.0,
        "total_robustness": 62.9,
        "tested_edges": [],
    }
    assessment = SybilAssessmentRecord.model_validate(
        {
            "id": assessment_identity(revision_id),
            "revision_id": revision_id,
            "status": "complete",
            "scores": {"B": attacked},
        }
    )
    assert graph_evidence(assessment).shops["B"].policy_passed is False
