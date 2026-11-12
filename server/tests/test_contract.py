"""Contract PR #1 (DEV_PLAN.md A-D1-02): schemas, sample run, REST stubs, SSE framing."""

import json

import pytest
from fastapi.testclient import TestClient
from pydantic import TypeAdapter

from aegis.events import sample_run
from aegis.schemas import Event, RunSummary
from api import main
from api.main import app

C5_IDS = {
    "clean", *(f"t0{i}" for i in range(1, 9)), "main-demo",
    "r1-forbidden", "r1-authorized", "r1-budget", "r1-benign",
}  # fmt: skip
KINDS = {"snapshot", "decision", "verdict", "executed", "ask", "error", "done"}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_sample_events_validate_and_cover_contract() -> None:
    summary, events = sample_run()
    assert summary.is_sample
    raw = TypeAdapter(list[Event]).dump_python(events, mode="json")
    again = TypeAdapter(list[Event]).validate_python(raw)
    assert {e.kind for e in again} == KINDS
    assert {e.mode for e in again} == {"shielded", "unshielded"}
    assert not any(e.kind in ("verdict", "ask") for e in again if e.mode == "unshielded")
    audits = [e.payload.audit for e in again if e.kind == "verdict" and e.payload.audit]
    assert any(c.status == "violation" for a in audits for c in a.checks)
    rechecks = [a for a in audits if a.recheck_of is not None]
    assert rechecks and all(c.status != "violation" for c in rechecks[0].checks)
    assert any(c.status == "permitted" for a in audits for c in a.checks)
    statuses = [e.payload.status for e in again if e.kind == "ask"]
    assert statuses == ["pending", "approved"]
    assert sum(e.kind == "done" for e in again) == 2
    o = summary.outcomes
    assert o.shielded and o.unshielded and o.shielded.total != o.unshielded.total


def test_rest_sample_and_presets(client: TestClient) -> None:
    assert {p["id"] for p in client.get("/presets").json()} == C5_IDS
    RunSummary.model_validate(client.get("/runs/sample").json())
    TypeAdapter(list[Event]).validate_python(client.get("/runs/sample/events").json())
    assert client.get("/stats").json()["label"] == "sample"
    assert client.get("/runs/demo/stream").status_code in (404, 501)


def test_unbuilt_routes_are_declared_and_501(client: TestClient) -> None:
    paths = app.openapi()["paths"]
    for p in ["/runs", "/runs/{run_id}", "/runs/{run_id}/events", "/runs/{run_id}/stream",
              "/runs/{run_id}/ask/{ask_id}", "/presets", "/stats", "/healthz/llm",
              "/healthz/arena"]:  # fmt: skip
        assert p in paths, p
    assert "/runs/demo/stream" not in paths
    assert client.post("/runs", json={"preset_id": "clean"}).status_code == 501
    assert client.get("/runs").status_code == 501
    assert client.get("/runs/abc/events").status_code == 501
    assert client.post("/runs/abc/ask/x", json={"decision": "approve"}).status_code == 501


def test_sample_stream_framing(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main, "SAMPLE_FRAME_DELAY_S", 0)
    names: list[str] = []
    with client.stream("GET", "/runs/sample/stream") as r:
        for line in r.iter_lines():
            if line.startswith("event:"):
                names.append(line.split(":", 1)[1].strip())
            elif line.startswith("data:") and names[-1] != "run":
                ev = TypeAdapter(Event).validate_python(json.loads(line[5:]))
                assert ev.kind == names[-1]
    assert names[0] == "run"
    assert names.count("done") == 2 and names[-1] == "done"
