"""FastAPI entrypoint (DEV_PLAN.md §4 C2/C3).

run_id "sample" always serves a labelled, contract-valid sample run.
"""

import asyncio
import base64
import json
import logging
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from urllib.parse import urlencode, urlsplit

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from playwright.async_api import Browser, async_playwright
from sse_starlette.sse import EventSourceResponse

from aegis.agent import Agent, LLMAgent
from aegis.config import settings
from aegis.detectors import run_fast
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
from aegis.intent import parse_ledger
from aegis.llm import LLMRouter
from aegis.loop import FROZEN_TIME, VIEWPORT, outcome_from_page, run_pair, start_url
from aegis.presets import PRESETS
from aegis.schemas import (
    Action,
    AskDecision,
    AskPayload,
    EvalStats,
    Event,
    Finding,
    HealthArena,
    HealthLLM,
    LabRequest,
    Ledger,
    LedgerItem,
    Preset,
    RunCreate,
    RunCreated,
    RunSummary,
    ScanReport,
    ScanRequest,
    TrialReport,
)
from aegis.security import ScanGuard, arena_origin, install_guard, validate_scan_url, validate_url
from aegis.snapshot import screenshot_b64, take_snapshot
from aegis.trials import run_trials

log = logging.getLogger("aegis.api")
# One shared Chromium per process (brief §3); contexts are created per run side.
_browser: Browser | None = None
SAMPLE_FRAME_DELAY_S = 0.3
SAMPLE_ASK_HOLD_S = 4.0  # keep the sample's pending approval dialog readable


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


# --- Trap Lab (R2 disposable trials on a judge-written checkbox) -----------------------------

LAB_BUDGET = 2_000.0  # above lamp + plan, so only the permission decides the plan
_lab_lock = asyncio.Lock()  # one lab trial at a time on the shared Chromium


def lab_ledger(body: LabRequest) -> Ledger:
    items = [LedgerItem(name="Aurora desk lamp", qty=1, max_price=LAB_BUDGET)]
    if body.permit_plan:
        items.append(LedgerItem(name="Lamp care plan", qty=1))
    return Ledger(
        goal="Buy one Aurora desk lamp for under ₹2,000, standard shipping.",
        items=items, budget_max=LAB_BUDGET, allow_addons=body.permit_plan,
        allow_subscriptions=body.permit_plan,
        data_allowed=["email"] if body.permit_sharing else [],
        allowed_domains=[urlsplit(settings.arena_base_url).hostname or ""],
        shipping_method="standard",
    )  # fmt: skip


def lab_url(body: LabRequest) -> str:
    lab = {"label": body.label, "effect": body.effect,
           "ticked_means_on": body.ticked_means_on, "ticked": body.starts_ticked}  # fmt: skip
    query = urlencode({"cart": "aurora-desk-lamp:1", "traps": "none", "lab": json.dumps(lab)})
    return validate_url(f"{settings.arena_base_url.rstrip('/')}/checkout.html?{query}",
                        arena_origin())  # fmt: skip


@app.post("/lab/trial")
async def lab_trial(body: LabRequest) -> TrialReport:
    """Opens the judge's checkout as the "original" page, then runs the R2 trial on its box. The
    secret effect only configures the arena; run_trials sees the URL and the rendered copies."""
    assert _browser is not None
    url = lab_url(body)
    async with _lab_lock:
        ctx = await _browser.new_context(viewport=VIEWPORT)  # type: ignore[arg-type]
        try:
            await install_guard(ctx, arena_origin())
            page = await ctx.new_page()
            await page.clock.set_fixed_time(FROZEN_TIME)
            await page.goto(url, wait_until="domcontentloaded")
            snap = await take_snapshot(page)
            control = await page.get_attribute("#lab-control", "data-cs-id", timeout=5_000)
            commit = await page.get_attribute('[data-testid="place-order"]', "data-cs-id")
            if not control or not commit:
                raise HTTPException(status_code=503, detail="the lab checkout did not render")
            return await run_trials(
                _browser, original_page=page, original=snap, control_id=control,
                commit_action=Action(type="click", target_id=commit, rationale="Trap Lab"),
                ledger=lab_ledger(body), start_url=url, allowed_origin=arena_origin(), replay=[],
                viewport=VIEWPORT, frozen_time=FROZEN_TIME, outcome_reader=outcome_from_page,
                timeout_s=settings.trial_timeout_s,
            )  # fmt: skip
        finally:
            await ctx.close()


# --- E5: scan any public URL -----------------------------------------------------------------

SCAN_LOAD_S = 15
SCAN_SETTLE_MS = 2_500  # late overlays, cookie banners and timers usually appear by then
_scan_lock = asyncio.Lock()  # one scan at a time on the shared Chromium


def is_note(f: Finding) -> bool:
    return f.detector in ("A1_visibility", "A3_faint_text") and f.trap_type == "hidden_info"


@app.post("/scan")
async def scan(body: ScanRequest) -> ScanReport:
    """Loads a public page read-only (no clicks, no agent, no LLM) and runs the fast detectors."""
    assert _browser is not None
    try:
        url = await validate_scan_url(body.url.strip())
    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"Cannot scan this URL: {e}") from e
    t0 = time.perf_counter()
    async with _scan_lock:
        guard = ScanGuard()
        ctx = await _browser.new_context(
            viewport=VIEWPORT, service_workers="block", accept_downloads=False,  # type: ignore[arg-type]
        )  # fmt: skip
        try:
            await guard.install(ctx)
            page = await ctx.new_page()
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=SCAN_LOAD_S * 1000)
            except Exception as e:  # noqa: BLE001 - any load failure is the user's answer
                msg = f"The page did not load: {e}"[:300]
                raise HTTPException(status_code=502, detail=msg) from e
            await page.wait_for_timeout(SCAN_SETTLE_MS)
            snap = await take_snapshot(page)
            d0 = time.perf_counter()
            findings = run_fast(snap, None, None)
            detector_ms = round((time.perf_counter() - d0) * 1000)
            shot = await screenshot_b64(page)
            if await guard.leaked():
                raise HTTPException(status_code=422, detail="Cannot scan this URL: the page was "
                                    "served from a non-public address")  # fmt: skip
            notes = [f for f in findings if is_note(f)]
            findings = [f for f in findings if not is_note(f)]
            ids = {f.element_id for f in findings}
            return ScanReport(
                url=url, final_url=page.url, title=snap.title, findings=findings, notes=notes,
                flagged=[e for e in snap.elements if e.id in ids],
                element_count=len(snap.elements), screenshot_b64=shot, detector_ms=detector_ms,
                elapsed_ms=round((time.perf_counter() - t0) * 1000),
                blocked_requests=len(guard.blocked),
            )  # fmt: skip
        finally:
            await ctx.close()


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


async def _parse(task: str) -> tuple[Ledger, list[str]]:
    host = urlsplit(settings.arena_base_url).hostname or ""
    return await parse_ledger(task, _router, allowed_domains=[host])


ledger_parser: Callable[[str], Awaitable[tuple[Ledger, list[str]]]] = _parse  # tests swap it


async def _run(run_id: str, preset: Preset) -> None:
    global _run_slots
    assert _browser is not None
    _run_slots = _run_slots or asyncio.Semaphore(settings.max_concurrent_runs)
    async with _run_slots:
        try:  # B1: the ledger is written once, before browsing, from the task text only
            ledger, unresolved = await ledger_parser(preset.task)
        except Exception as e:  # no ledger: the shielded side asks before it browses
            ledger, unresolved = None, [f"Could not read the request ({type(e).__name__})."]
        await _bus.update(run_id, ledger=ledger)
        await run_pair(
            _browser, _bus, run_id, task=preset.task, make_agent=agent_factory,
            url=validate_url(start_url(preset.traps, preset.variant, consent=preset.consent),
                             arena_origin()),
            allowed_origin=arena_origin(), ledger=ledger, unresolved=unresolved,
            shield=preset.shield,
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
    runs = {r.run_id: r for r in await _stored(_bus.store.list_runs(limit), [])}
    runs |= {r.run_id: r for r in _bus.summaries()}
    return sorted(runs.values(), key=lambda r: r.created_at, reverse=True)[:limit]


async def _stored[T](read: Awaitable[T], default: T) -> T:
    """Replay storage down (or migration missing): serve what this process has, never a 500."""
    try:
        return await read
    except Exception as e:
        log.warning("store read failed: %s", e)
        return default


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
    if summary := await _stored(_bus.store.get_run(run_id), None):
        return summary
    raise HTTPException(status_code=404, detail="run not found")


@app.get("/runs/{run_id}/events")
async def get_run_events(run_id: str) -> list[Event]:
    """Replay (E3). Runs still in memory include inline JPEGs; stored runs carry screenshot_url."""
    if run_id == SAMPLE_RUN_ID:
        return sample_run()[1]
    if run := _bus.get(run_id):
        return run.events
    if await _stored(_bus.store.get_run(run_id), None) is None:
        raise HTTPException(status_code=404, detail="run not found")
    return await _stored(_bus.store.get_events(run_id), [])


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
            if ev.kind == "ask" and ev.payload.status == "pending":
                await asyncio.sleep(SAMPLE_ASK_HOLD_S)

    return EventSourceResponse(gen(), ping=15)


@app.post("/runs/{run_id}/ask/{ask_id}")
async def resolve_ask(run_id: str, ask_id: str, body: AskDecision) -> AskPayload:
    run = _live(run_id)
    resolved = run.gate.resolve(ask_id, body.decision)
    if resolved is None:
        raise HTTPException(status_code=404, detail="no pending ask with that id")
    return resolved
