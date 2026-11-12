from datetime import UTC, datetime

import httpx

import api.main as main
from aegis.events import MemoryStore, PgStore, RunBus, with_shot_url
from aegis.schemas import (
    DoneEvent,
    DonePayload,
    Outcome,
    RunSummary,
    SnapshotEvent,
    SnapshotPayload,
)

NOW = datetime(2026, 11, 13, tzinfo=UTC)


def _summary(run_id: str = "r1") -> RunSummary:
    return RunSummary(run_id=run_id, preset_id="clean", task="t", status="queued", created_at=NOW)


def _snap(run_id: str = "r1") -> SnapshotEvent:
    p = SnapshotPayload(url="u", title="t", screenshot_b64="AAAA", element_count=1)
    return SnapshotEvent(run_id=run_id, step=1, mode="shielded", ts=NOW, payload=p)


def _done(run_id: str = "r1") -> DoneEvent:
    p = DonePayload(reason="completed", outcome=Outcome(task_completed=True, total=1299))
    return DoneEvent(run_id=run_id, step=2, mode="shielded", ts=NOW, payload=p)


async def test_bus_persists_events_and_summary() -> None:
    store = MemoryStore()
    bus = RunBus(store)
    await bus.create(_summary())
    await bus.publish("r1", _snap())
    await bus.publish("r1", _done())
    await bus.update("r1", close=True, status="done")
    assert (await store.get_run("r1")).status == "done"  # type: ignore[union-attr]
    assert [e.kind for e in await store.get_events("r1")] == ["snapshot", "done"]


async def test_replay_routes_survive_restart() -> None:
    store = MemoryStore()
    old = RunBus(store)
    await old.create(_summary())
    await old.publish("r1", _done())
    await old.update("r1", close=True, status="done")
    main._bus = RunBus(store)  # "restart": the new process only has the store
    try:
        t = httpx.ASGITransport(app=main.app)
        async with httpx.AsyncClient(transport=t, base_url="http://t") as c:
            assert (await c.get("/runs/r1")).json()["status"] == "done"
            assert [e["kind"] for e in (await c.get("/runs/r1/events")).json()] == ["done"]
            assert [r["run_id"] for r in (await c.get("/runs")).json()] == ["r1"]
            assert (await c.get("/runs/nope/events")).status_code == 404
    finally:
        main._bus = RunBus()


def test_postgres_copy_never_holds_the_jpeg() -> None:
    stored = with_shot_url(_snap(), "https://x/storage/v1/object/public/shots/r1/00001.jpg")
    assert stored.payload.screenshot_b64 is None  # type: ignore[union-attr]
    assert stored.payload.screenshot_url.endswith(".jpg")  # type: ignore[union-attr]
    assert _snap().payload.screenshot_b64 == "AAAA"  # live event untouched


async def test_persist_failure_reported_once_and_run_continues() -> None:
    store = PgStore("postgresql://invalid", "https://x", "k")

    async def boom(*_: object) -> None:
        raise RuntimeError("db down")

    store._write = boom  # type: ignore[method-assign]
    bus = RunBus(store)  # type: ignore[arg-type]
    await bus.create(_summary())
    await bus.publish("r1", _snap())
    await store.flush()
    errors = [e for e in bus.get("r1").events if e.kind == "error"]  # type: ignore[union-attr]
    assert len(errors) == 1 and errors[0].payload.code == "persist_failed"  # type: ignore[union-attr]
    assert errors[0].payload.recoverable  # type: ignore[union-attr]
    await bus.publish("r1", _done())  # the live run carries on
    await store.flush()
    await store.close()


async def test_replay_routes_survive_a_broken_store() -> None:
    class Broken(MemoryStore):
        async def list_runs(self, limit: int):  # type: ignore[override]
            raise RuntimeError("relation runs does not exist")

        async def get_run(self, run_id: str):  # type: ignore[override]
            raise RuntimeError("db down")

    bus = RunBus(Broken())
    await bus.create(_summary("live1"))
    main._bus = bus
    try:
        t = httpx.ASGITransport(app=main.app)
        async with httpx.AsyncClient(transport=t, base_url="http://t") as c:
            assert [r["run_id"] for r in (await c.get("/runs")).json()] == ["live1"]
            assert (await c.get("/runs/other")).status_code == 404
    finally:
        main._bus = RunBus()
