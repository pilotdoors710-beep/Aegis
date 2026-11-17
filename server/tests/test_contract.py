"""Contract: presets, stats and declared routes."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from aegis.events import eval_stats
from aegis.schemas import EvalStats
from api.main import app

# sybil-two-shop launches from /sybil only, so it is not listed.
C5_IDS = {
    "clean", *(f"t0{i}" for i in range(1, 9)), "main-demo",
    "r1b-forbidden", "r1b-authorized",
    "r2-consent", "r2-consent-reversed", "cloaked",
}  # fmt: skip


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_rest_presets_and_stats(client: TestClient) -> None:
    assert {p["id"] for p in client.get("/presets").json()} == C5_IDS
    stats = EvalStats.model_validate(client.get("/stats").json())
    assert stats.label == "final" and {c.config for c in stats.configs} >= {"U", "F", "I"}
    assert client.get("/runs/demo/stream").status_code in (404, 501)


def test_stats_missing_file_gives_none_not_placeholder(tmp_path: Path) -> None:
    assert eval_stats(tmp_path / "missing.json") is None


def test_routes_declared(client: TestClient) -> None:
    paths = app.openapi()["paths"]
    for p in ["/runs", "/runs/{run_id}", "/runs/{run_id}/events", "/runs/{run_id}/stream",
              "/runs/{run_id}/ask/{ask_id}", "/presets", "/stats", "/healthz/llm",
              "/healthz/arena"]:  # fmt: skip
        assert p in paths, p
    assert "/runs/demo/stream" not in paths
    assert client.post("/runs/abc/ask/x", json={"decision": "approve"}).status_code == 404
