"""FastAPI entrypoint (DEV_PLAN.md §4 C2/C3).

Unbuilt routes are declared with their final request/response models and return 501, so the web
can generate types today. run_id "sample" always serves a labelled, contract-valid sample run.
"""

import asyncio
import base64
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from playwright.async_api import Browser, async_playwright
from sse_starlette.sse import EventSourceResponse

from aegis.config import settings
from aegis.events import SAMPLE_RUN_ID, sample_eval_stats, sample_run
from aegis.llm import LLMRouter
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

# One shared Chromium per process (brief §3); contexts are created per run side.
_browser: Browser | None = None
SAMPLE_FRAME_DELAY_S = 0.3


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    global _browser
    pw = await async_playwright().start()
    _browser = await pw.chromium.launch(args=["--no-sandbox"])
    try:
        yield
    finally:
        await _browser.close()
        await pw.stop()


app = FastAPI(title="Aegis", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _not_built(what: str) -> HTTPException:
    return HTTPException(status_code=501, detail=f"{what} is not implemented yet")


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


@app.get("/healthz/llm")
async def healthz_llm() -> HealthLLM:
    """One minimal completion through the router; names the provider that answered."""
    try:
        r = await LLMRouter().complete(
            [{"role": "user", "content": "Reply with the single word: pong"}],
            use_cache=False,
            max_tokens=300,
        )
    except Exception as e:  # health check: report, don't crash
        raise HTTPException(status_code=503, detail=f"{type(e).__name__}: {e}") from e
    return HealthLLM(provider=r.provider, model=r.model, latency_ms=r.latency_ms)


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


@app.post("/runs", status_code=201)
async def create_run(body: RunCreate) -> RunCreated:
    raise _not_built("POST /runs")


@app.get("/runs")
async def list_runs(limit: int = Query(20, ge=1, le=100)) -> list[RunSummary]:
    raise _not_built("GET /runs")


@app.get("/runs/{run_id}")
async def get_run(run_id: str) -> RunSummary:
    if run_id == SAMPLE_RUN_ID:
        return sample_run()[0]
    raise _not_built("GET /runs/{run_id}")


@app.get("/runs/{run_id}/events")
async def get_run_events(run_id: str) -> list[Event]:
    if run_id == SAMPLE_RUN_ID:
        return sample_run()[1]
    raise _not_built("GET /runs/{run_id}/events")


@app.get("/runs/{run_id}/stream", response_class=EventSourceResponse)
async def stream_run(run_id: str) -> EventSourceResponse:
    """SSE (C2): `event: run` frame first, then `event: <kind>` frames; ends after both dones."""
    if run_id != SAMPLE_RUN_ID:
        raise _not_built("live run streams")
    summary, events = sample_run()

    async def gen() -> AsyncIterator[dict[str, str]]:
        yield {"event": "run", "data": summary.model_dump_json()}
        for i, ev in enumerate(events, start=1):
            await asyncio.sleep(SAMPLE_FRAME_DELAY_S)
            yield {"event": ev.kind, "id": str(i), "data": ev.model_dump_json()}

    return EventSourceResponse(gen(), ping=15)


@app.post("/runs/{run_id}/ask/{ask_id}")
async def resolve_ask(run_id: str, ask_id: str, body: AskDecision) -> AskPayload:
    raise _not_built("POST /runs/{run_id}/ask/{ask_id}")
