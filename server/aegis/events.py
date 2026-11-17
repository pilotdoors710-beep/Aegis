"""Event bus: live SSE fan-out and Postgres/Storage persistence (E3)."""

import asyncio
import base64
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import httpx
import psycopg
from psycopg.types.json import Jsonb
from pydantic import TypeAdapter

from aegis.config import Settings, settings
from aegis.llm import LLMResult
from aegis.schemas import (
    AskPayload,
    AskStatus,
    ErrorEvent,
    ErrorPayload,
    EvalStats,
    Event,
    RunSummary,
    SnapshotEvent,
    SybilArtifactManifest,
    SybilAssessmentRecord,
    SybilScenarioRevision,
)

# Written by `eval/run.py --stats` from the stored final runs (no LLM calls).
FINAL_STATS = Path(__file__).resolve().parents[2] / "eval" / "results" / "final-stats.json"


def eval_stats(path: Path = FINAL_STATS) -> EvalStats | None:
    """The published eval results; None when the file is missing (never placeholder numbers)."""
    try:
        return EvalStats.model_validate_json(path.read_text())
    except FileNotFoundError:
        return None


# --- Persistence (E3) ----------------------------------------------------------------------

log = logging.getLogger("aegis.events")
_EVENT = TypeAdapter(Event)
PersistError = Callable[[str, str], Awaitable[None]]


class MemoryStore:
    """Same interface as PgStore; used when SUPABASE_DB_URL is unset (CI, tests, local dev)."""

    def __init__(self) -> None:
        self.runs: dict[str, RunSummary] = {}
        self.events: dict[str, list[Event]] = {}
        self.sybil_datasets: dict[str, SybilArtifactManifest] = {}
        self.sybil_scenarios: dict[str, SybilScenarioRevision] = {}
        self.sybil_assessments: dict[str, SybilAssessmentRecord] = {}
        self.on_error: PersistError | None = None

    async def save_run(self, summary: RunSummary) -> None:
        self.runs[summary.run_id] = summary

    async def save_event(self, event: Event, seq: int) -> None:
        self.events.setdefault(event.run_id, []).append(event)

    async def list_runs(self, limit: int) -> list[RunSummary]:
        return sorted(self.runs.values(), key=lambda r: r.created_at, reverse=True)[:limit]

    async def get_run(self, run_id: str) -> RunSummary | None:
        return self.runs.get(run_id)

    async def get_events(self, run_id: str) -> list[Event]:
        return list(self.events.get(run_id, []))

    async def save_sybil_dataset(self, manifest: SybilArtifactManifest) -> None:
        self.sybil_datasets[manifest.id] = manifest

    async def save_sybil_scenario(self, revision: SybilScenarioRevision) -> None:
        self.sybil_scenarios[revision.id] = revision

    async def get_sybil_scenario(self, revision_id: str) -> SybilScenarioRevision | None:
        return self.sybil_scenarios.get(revision_id)

    async def save_sybil_assessment(self, assessment: SybilAssessmentRecord) -> None:
        self.sybil_assessments[assessment.id] = assessment

    async def get_sybil_assessment(self, assessment_id: str) -> SybilAssessmentRecord | None:
        return self.sybil_assessments.get(assessment_id)

    async def flush(self) -> None:
        pass

    async def close(self) -> None:
        pass


def shot_path(event: Event, seq: int) -> str:
    return f"{event.run_id}/{seq:05d}-{event.mode}.jpg"


def with_shot_url(event: Event, url: str | None) -> Event:
    """What Postgres stores: never the inline JPEG, the Storage URL instead (when uploaded)."""
    if not isinstance(event, SnapshotEvent):
        return event
    payload = event.payload.model_copy(update={"screenshot_b64": None, "screenshot_url": url})
    return event.model_copy(update={"payload": payload})


class PgStore:
    """Supabase Postgres + Storage. Writes go through one background queue so database and
    upload latency never delay the live stream; a failure is logged and reported, never raised."""

    def __init__(self, db_url: str, supabase_url: str, service_key: str) -> None:
        self.db_url, self.base, self.key = db_url, supabase_url.rstrip("/"), service_key
        self.on_error: PersistError | None = None
        self._conn: psycopg.AsyncConnection | None = None
        self._lock = asyncio.Lock()
        self._q: asyncio.Queue[tuple[str, object, int]] = asyncio.Queue()
        self._worker: asyncio.Task | None = None
        self._http = httpx.AsyncClient(timeout=20)
        self._reported: set[str] = set()

    async def _sql(self, query: str, params: tuple = (), fetch: bool = False) -> list[tuple]:
        async with self._lock:
            for attempt in (1, 2):  # one reconnect: the pooler drops idle connections
                try:
                    if self._conn is None or self._conn.closed:
                        # prepare_threshold=None: Supabase's transaction pooler can't keep them.
                        self._conn = await psycopg.AsyncConnection.connect(
                            self.db_url, autocommit=True, prepare_threshold=None
                        )
                    cur = await self._conn.execute(query, params)  # type: ignore[arg-type]
                    return await cur.fetchall() if fetch else []
                except psycopg.OperationalError:
                    self._conn = None
                    if attempt == 2:
                        raise
        return []

    def _start(self) -> None:
        if self._worker is None or self._worker.done():
            self._worker = asyncio.create_task(self._drain())

    async def save_run(self, summary: RunSummary) -> None:
        self._start()
        self._q.put_nowait(("run", summary, 0))

    async def save_event(self, event: Event, seq: int) -> None:
        self._start()
        self._q.put_nowait(("event", event, seq))

    async def _upload(self, event: SnapshotEvent, seq: int) -> str | None:
        if not event.payload.screenshot_b64:
            return None
        path = f"shots/{shot_path(event, seq)}"
        r = await self._http.post(
            f"{self.base}/storage/v1/object/{path}",
            content=base64.b64decode(event.payload.screenshot_b64),
            headers={"Authorization": f"Bearer {self.key}", "apikey": self.key,
                     "content-type": "image/jpeg", "x-upsert": "true"},
        )  # fmt: skip
        r.raise_for_status()
        return f"{self.base}/storage/v1/object/public/{path}"  # bucket is public-read

    async def _write(self, kind: str, item: object, seq: int) -> None:
        if kind == "run":
            r = item
            assert isinstance(r, RunSummary)
            await self._sql(
                "insert into runs (run_id, created_at, status, preset_id, summary) "
                "values (%s, %s, %s, %s, %s) on conflict (run_id) do update set "
                "status = excluded.status, summary = excluded.summary",
                (r.run_id, r.created_at, r.status, r.preset_id, Jsonb(r.model_dump(mode="json"))),
            )
            return
        ev: Event = item  # type: ignore[assignment]
        url = await self._upload(ev, seq) if isinstance(ev, SnapshotEvent) else None
        stored = with_shot_url(ev, url)
        await self._sql(
            "insert into events (run_id, seq, step, mode, kind, ts, data) "
            "values (%s, %s, %s, %s, %s, %s, %s) on conflict (run_id, seq) do nothing",
            (ev.run_id, seq, ev.step, ev.mode, ev.kind, ev.ts,
             Jsonb(stored.model_dump(mode="json"))),
        )  # fmt: skip

    async def _drain(self) -> None:
        while True:
            kind, item, seq = await self._q.get()
            try:
                await self._write(kind, item, seq)
            except Exception as e:  # never stop a live run over persistence
                run_id = getattr(item, "run_id", "?")
                log.warning("persist %s for %s failed: %s", kind, run_id, e)
                if self.on_error and run_id not in self._reported:
                    self._reported.add(run_id)
                    await self.on_error(run_id, f"{type(e).__name__}: {str(e)[:200]}")
            finally:
                self._q.task_done()

    async def list_runs(self, limit: int) -> list[RunSummary]:
        rows = await self._sql(
            "select summary from runs order by created_at desc limit %s", (limit,), fetch=True
        )
        return [RunSummary.model_validate(r[0]) for r in rows]

    async def get_run(self, run_id: str) -> RunSummary | None:
        rows = await self._sql("select summary from runs where run_id = %s", (run_id,), True)
        return RunSummary.model_validate(rows[0][0]) if rows else None

    async def get_events(self, run_id: str) -> list[Event]:
        rows = await self._sql(
            "select data from events where run_id = %s order by seq", (run_id,), fetch=True
        )
        return [_EVENT.validate_python(r[0]) for r in rows]

    async def save_sybil_dataset(self, manifest: SybilArtifactManifest) -> None:
        await self._sql(
            "insert into sybil_datasets (id, manifest) values (%s, %s) "
            "on conflict (id) do update set manifest = excluded.manifest",
            (manifest.id, Jsonb(manifest.model_dump(mode="json"))),
        )

    async def save_sybil_scenario(self, revision: SybilScenarioRevision) -> None:
        await self._sql(
            "insert into sybil_scenarios (id, dataset_id, revision) values (%s, %s, %s) "
            "on conflict (id) do nothing",
            (revision.id, revision.dataset_id, Jsonb(revision.model_dump(mode="json"))),
        )

    async def get_sybil_scenario(self, revision_id: str) -> SybilScenarioRevision | None:
        rows = await self._sql(
            "select revision from sybil_scenarios where id = %s", (revision_id,), fetch=True
        )
        return SybilScenarioRevision.model_validate(rows[0][0]) if rows else None

    async def save_sybil_assessment(self, assessment: SybilAssessmentRecord) -> None:
        await self._sql(
            "insert into sybil_assessments (id, revision_id, status, assessment) "
            "values (%s, %s, %s, %s) on conflict (id) do update set "
            "status = excluded.status, assessment = excluded.assessment, updated_at = now()",
            (
                assessment.id,
                assessment.revision_id,
                assessment.status,
                Jsonb(assessment.model_dump(mode="json")),
            ),
        )

    async def get_sybil_assessment(self, assessment_id: str) -> SybilAssessmentRecord | None:
        rows = await self._sql(
            "select assessment from sybil_assessments where id = %s",
            (assessment_id,),
            fetch=True,
        )
        return SybilAssessmentRecord.model_validate(rows[0][0]) if rows else None

    async def flush(self) -> None:
        await self._q.join()

    async def mark_interrupted(self) -> None:
        """On startup: runs left queued/running by a previous process can never finish."""
        try:
            await self._sql(
                "update runs set status = 'error', summary = jsonb_set(summary, '{status}', "
                "'\"error\"') where status in ('queued', 'running')"
            )
            await self._sql(
                "update sybil_assessments set status = 'unavailable', assessment = "
                "jsonb_set(jsonb_set(assessment, '{status}', '\"unavailable\"'), "
                "'{reason}', '\"Backend restarted before this assessment finished.\"') "
                "where status in ('queued', 'running')"
            )
        except Exception as e:  # DB down or migration not applied: start anyway, live-only
            log.warning("could not mark interrupted runs: %s", e)

    async def close(self) -> None:
        if self._worker:
            await asyncio.wait_for(self.flush(), timeout=30)
            self._worker.cancel()
        await self._http.aclose()
        if self._conn:
            await self._conn.close()


Store = MemoryStore | PgStore


class PgCache:
    """llm_cache table as the router's DecisionCache (brief §3); eval always bypasses it."""

    def __init__(self, store: PgStore) -> None:
        self.store = store

    async def get(self, key: str) -> LLMResult | None:
        try:
            rows = await self.store._sql(
                "select text, provider, model from llm_cache where key = %s", (key,), fetch=True
            )
        except Exception as e:  # a cache outage is a miss, never an agent failure
            log.warning("llm_cache read failed: %s", e)
            return None
        return LLMResult(rows[0][0], rows[0][1], rows[0][2], True, 0) if rows else None

    async def set(self, key: str, value: LLMResult) -> None:
        try:
            await self.store._sql(
                "insert into llm_cache (key, text, provider, model) values (%s, %s, %s, %s) "
                "on conflict (key) do nothing",
                (key, value.text, value.provider, value.model),
            )
        except Exception as e:
            log.warning("llm_cache write failed: %s", e)


def make_store(cfg: Settings) -> Store:
    if cfg.supabase_db_url:
        return PgStore(cfg.supabase_db_url, cfg.supabase_url, cfg.supabase_service_key)
    return MemoryStore()


# --- Human gate (D2) ------------------------------------------------------------------------


class AskGate:
    """In-memory futures for one run's asks (brief §3). The loop opens an ask BEFORE announcing
    it, so a fast click can never miss it. No answer in time = timed_out, treated as denial."""

    def __init__(self, *, auto_approve: bool = False, timeout_s: float | None = None) -> None:
        self.auto_approve = auto_approve
        self.timeout_s = settings.ask_timeout_s if timeout_s is None else timeout_s
        self._open: dict[str, tuple[asyncio.Future[AskStatus], AskPayload]] = {}

    def open(self, payload: AskPayload) -> None:
        self._open[payload.ask_id] = (asyncio.get_running_loop().create_future(), payload)

    async def wait(self, ask_id: str) -> AskStatus:
        fut, _ = self._open[ask_id]
        try:
            if self.auto_approve:  # labelled demo approval, never reported as human consent
                return "auto_approved_demo"
            return await asyncio.wait_for(fut, self.timeout_s)
        except TimeoutError:
            return "timed_out"
        finally:
            self._open.pop(ask_id, None)

    def resolve(self, ask_id: str, decision: Literal["approve", "deny"]) -> AskPayload | None:
        entry = self._open.get(ask_id)
        if entry is None or entry[0].done():
            return None
        status: AskStatus = "approved" if decision == "approve" else "denied"
        entry[0].set_result(status)
        return entry[1].model_copy(update={"status": status})


# --- Live run bus (C2) ----------------------------------------------------------------------
# Live frames stay in memory for streaming; every Event and summary change is also persisted.

MAX_RUNS_KEPT = 50


class _Run:
    def __init__(self, summary: RunSummary, gate: AskGate) -> None:
        self.summary = summary
        self.gate = gate
        self.frames: list[tuple[str, str]] = []  # (sse event name, json); SSE id = index + 1
        self.events: list[Event] = []
        self.closed = False
        self.changed = asyncio.Condition()


class RunBus:
    """Per-run frame buffer + fan-out. Late subscribers and Last-Event-ID reconnects replay."""

    def __init__(self, store: Store | None = None) -> None:
        self._runs: dict[str, _Run] = {}
        self.store: Store = store or MemoryStore()
        self.store.on_error = self._persist_failed

    async def create(self, summary: RunSummary, gate: AskGate | None = None) -> None:
        self._runs[summary.run_id] = _Run(summary, gate or AskGate())
        await self.store.save_run(summary)
        while len(self._runs) > MAX_RUNS_KEPT:
            oldest = next(iter(self._runs))
            if not self._runs[oldest].closed:
                break
            del self._runs[oldest]

    def get(self, run_id: str) -> _Run | None:
        return self._runs.get(run_id)

    def summaries(self) -> list[RunSummary]:
        return [r.summary for r in self._runs.values()]

    async def _append(self, run: _Run, name: str, data: str, *, close: bool = False) -> int:
        async with run.changed:
            run.frames.append((name, data))
            run.closed = run.closed or close
            run.changed.notify_all()
            return len(run.frames)

    async def publish(self, run_id: str, event: Event, *, persist: bool = True) -> None:
        run = self._runs[run_id]
        run.events.append(event)
        seq = await self._append(run, event.kind, event.model_dump_json())
        if persist:
            await self.store.save_event(event, seq)

    async def _persist_failed(self, run_id: str, message: str) -> None:
        if (run := self._runs.get(run_id)) is None or run.closed:
            return
        # Not tied to one side; reported on the shielded pane, live only (it is about the DB).
        msg = f"Replay storage failed; the live run continues. {message}"
        ev = ErrorEvent(
            run_id=run_id, step=0, mode="shielded", ts=datetime.now(UTC),
            payload=ErrorPayload(code="persist_failed", message=msg, recoverable=True),
        )  # fmt: skip
        await self.publish(run_id, ev, persist=False)

    async def update(self, run_id: str, *, close: bool = False, **changes: object) -> None:
        """Change the RunSummary and send a `run` frame (C2)."""
        run = self._runs[run_id]
        run.summary = run.summary.model_copy(update=changes)
        await self._append(run, "run", run.summary.model_dump_json(), close=close)
        await self.store.save_run(run.summary)

    async def subscribe(self, run_id: str, last_id: int = 0) -> AsyncIterator[dict[str, str]]:
        run = self._runs[run_id]
        yield {"event": "run", "data": run.summary.model_dump_json()}
        i = last_id
        while True:
            async with run.changed:
                await run.changed.wait_for(lambda n=i: len(run.frames) > n or run.closed)
                pending, closed = run.frames[i:], run.closed
            for name, data in pending:
                i += 1
                yield {"event": name, "id": str(i), "data": data}
            if closed and i >= len(run.frames):
                return
