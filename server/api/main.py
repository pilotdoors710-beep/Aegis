"""FastAPI entrypoint (DEV_PLAN.md §4 C2/C3).

run_id "sample" always serves a labelled, contract-valid sample run.
"""

import asyncio
import base64
import time
import uuid
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from playwright.async_api import Browser, async_playwright
from sse_starlette.sse import EventSourceResponse

from aegis.agent import Agent, LLMAgent
from aegis.config import settings
from aegis.events import (
    SAMPLE_RUN_ID,
    AskGate,
    PgCache,
    PgStore,
    RunBus,
    make_store,
    sample_eval_stats,
    sample_run,
)
from aegis.llm import LLMRouter
from aegis.loop import run_pair, start_url
from aegis.presets import PRESETS
from aegis.schemas import (
    AskDecision,
    AskPayload,
    EvalStats,
    Event,
    HealthArena,
    HealthLLM,
    Preset,
    RunCreate,
    RunCreated,
    RunSummary,
)
from aegis.security import arena_origin, validate_url

# One shared Chromium per process (brief §3); contexts are created per run side.
_browser: Browser | None = None
SAMPLE_FRAME_DELAY_S = 0.3


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    global _browser, _bus
    pw = await async_playwright().start()
    _browser = await pw.chromium.launch(args=["--no-sandbox"])
    store = make_store(settings)
    if isinstance(store, PgStore):
        _router.cache = PgCache(store)
        await store.mark_interrupted()
    _bus = RunBus(store)
    try:
        yield
    finally:
        await store.close()
        await _browser.close()
        await pw.stop()


app = FastAPI(title="Aegis", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Health ---------------------------------------------------------------------------------


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/healthz/browser")
async def healthz_browser() -> dict[str, object]:
    """INF gate: prove headless Chromium runs on this host. Loads a data: page."""
    assert _browser is not None
    started = time.perf_counter()
    ctx = await _browser.new_context(viewport={"width": 1280, "height": 720})
    try:
        page = await ctx.new_page()
        await page.set_content("<title>Aegis OK</title><h1>Chromium is running</h1>")
        title = await page.title()
        jpeg = await page.screenshot(type="jpeg", quality=70)
    finally:
        await ctx.close()
    return {
        "title": title,
        "version": _browser.version,
        "screenshot_b64": base64.b64encode(jpeg).decode(),
        "elapsed_ms": int((time.perf_counter() - started) * 1000),
    }


_llm_health: tuple[float, HealthLLM] | None = None
LLM_HEALTH_TTL_S = 60.0  # public endpoint: never spend more than one LLM call a minute on it


@app.get("/healthz/llm")
async def healthz_llm() -> HealthLLM:
    """One minimal completion through the router; names the provider that answered."""
    global _llm_health
    if _llm_health and time.monotonic() - _llm_health[0] < LLM_HEALTH_TTL_S:
        return _llm_health[1]
    try:
        r = await LLMRouter().complete(
            [{"role": "user", "content": "Reply with the single word: pong"}],
            use_cache=False,
            max_tokens=300,
        )
    except Exception as e:  # health check: report, don't crash
        raise HTTPException(status_code=503, detail=f"{type(e).__name__}: {e}") from e
    _llm_health = (time.monotonic(), HealthLLM(provider=r.provider, model=r.model,
                                               latency_ms=r.latency_ms))  # fmt: skip
    return _llm_health[1]


@app.get("/healthz/arena")
async def healthz_arena() -> HealthArena:
    """The shared Chromium loads the arena home page from ARENA_BASE_URL."""
    assert _browser is not None
    url = settings.arena_base_url.rstrip("/") + "/index.html"
    ctx = await _browser.new_context(viewport={"width": 1280, "height": 720})
    try:
        page = await ctx.new_page()
        resp = await page.goto(url, wait_until="domcontentloaded", timeout=15_000)
        if resp is None or not resp.ok:
            status = resp.status if resp else "no response"
            raise HTTPException(status_code=503, detail=f"arena returned {status}")
        title = await page.title()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"{type(e).__name__}: {e}") from e
    finally:
        await ctx.close()
    return HealthArena(url=url, title=title)


# --- Presets and stats ----------------------------------------------------------------------


@app.get("/presets")
async def list_presets() -> list[Preset]:
    return PRESETS


@app.get("/stats")
async def stats() -> EvalStats:
    return sample_eval_stats()


# --- Runs -----------------------------------------------------------------------------------


_bus = RunBus()
_run_slots: asyncio.Semaphore | None = None
_tasks: set[asyncio.Task] = set()
_router = LLMRouter()  # one router per process so per-provider rate limits hold across runs
# Tests swap this for a ScriptedAgent factory.
agent_factory: Callable[[], Agent] = lambda: LLMAgent(_router)  # noqa: E731


async def _run(run_id: str, preset: Preset) -> None:
    global _run_slots
    assert _browser is not None
    _run_slots = _run_slots or asyncio.Semaphore(settings.max_concurrent_runs)
    async with _run_slots:
        await run_pair(
            _browser, _bus, run_id, task=preset.task, make_agent=agent_factory,
            url=validate_url(start_url(preset.traps, preset.variant), arena_origin()),
            allowed_origin=arena_origin(),
        )  # fmt: skip


@app.post("/runs", status_code=201)
async def create_run(body: RunCreate) -> RunCreated:
    preset = next((p for p in PRESETS if p.id == body.preset_id), None)
    if preset is None:
        raise HTTPException(status_code=404, detail=f"unknown preset {body.preset_id!r}")
    ahead = sum(r.status in ("queued", "running") for r in _bus.summaries())
    position = max(0, ahead - settings.max_concurrent_runs + 1)
    run_id = uuid.uuid4().hex[:12]
    auto = preset.auto_approve if body.auto_approve is None else body.auto_approve
    await _bus.create(RunSummary(
        run_id=run_id, preset_id=preset.id, task=preset.task, status="queued",
        created_at=datetime.now(UTC), model=settings.agent_models.split(",")[0] or None,
    ), AskGate(auto_approve=auto))  # fmt: skip
    task = asyncio.create_task(_run(run_id, preset))
    _tasks.add(task)  # keep a reference so the task is not garbage-collected
    task.add_done_callback(_tasks.discard)
    return RunCreated(run_id=run_id, status="queued" if position else "running",
                      queue_position=position)  # fmt: skip


@app.get("/runs")
async def list_runs(limit: int = Query(20, ge=1, le=100)) -> list[RunSummary]:
    # Live summaries in this process are fresher than the store's (writes are queued).
    runs = {r.run_id: r for r in await _bus.store.list_runs(limit)}
    runs |= {r.run_id: r for r in _bus.summaries()}
    return sorted(runs.values(), key=lambda r: r.created_at, reverse=True)[:limit]


def _live(run_id: str):  # noqa: ANN202
    run = _bus.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    return run


@app.get("/runs/{run_id}")
async def get_run(run_id: str) -> RunSummary:
    if run_id == SAMPLE_RUN_ID:
        return sample_run()[0]
    if run := _bus.get(run_id):
        return run.summary
    if summary := await _bus.store.get_run(run_id):
        return summary
    raise HTTPException(status_code=404, detail="run not found")


@app.get("/runs/{run_id}/events")
async def get_run_events(run_id: str) -> list[Event]:
    """Replay (E3). Runs still in memory include inline JPEGs; stored runs carry screenshot_url."""
    if run_id == SAMPLE_RUN_ID:
        return sample_run()[1]
    if run := _bus.get(run_id):
        return run.events
    if await _bus.store.get_run(run_id) is None:
        raise HTTPException(status_code=404, detail="run not found")
    return await _bus.store.get_events(run_id)


@app.get("/runs/{run_id}/stream", response_class=EventSourceResponse)
async def stream_run(run_id: str, request: Request) -> EventSourceResponse:
    """SSE (C2): `event: run` frame first, then `event: <kind>` frames; ends after both dones."""
    if run_id != SAMPLE_RUN_ID:
        _live(run_id)
        last = request.headers.get("last-event-id", "")  # read raw: keeps the OpenAPI contract
        return EventSourceResponse(
            _bus.subscribe(run_id, int(last) if last.isdigit() else 0), ping=15
        )
    summary, events = sample_run()

    async def gen() -> AsyncIterator[dict[str, str]]:
        yield {"event": "run", "data": summary.model_dump_json()}
        for i, ev in enumerate(events, start=1):
            await asyncio.sleep(SAMPLE_FRAME_DELAY_S)
            yield {"event": ev.kind, "id": str(i), "data": ev.model_dump_json()}

    return EventSourceResponse(gen(), ping=15)


@app.post("/runs/{run_id}/ask/{ask_id}")
async def resolve_ask(run_id: str, ask_id: str, body: AskDecision) -> AskPayload:
    run = _live(run_id)
    resolved = run.gate.resolve(ask_id, body.decision)
    if resolved is None:
        raise HTTPException(status_code=404, detail="no pending ask with that id")
    return resolved
