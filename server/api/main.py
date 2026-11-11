"""FastAPI entrypoint. INF-gate routes only; run/scan routes come later."""

import asyncio
import base64
import json
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from playwright.async_api import Browser, async_playwright
from sse_starlette.sse import EventSourceResponse

from aegis.config import settings

# One shared Chromium per process (brief §3); contexts are created per run side.
_browser: Browser | None = None


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


@app.get("/runs/demo/stream")
async def demo_stream() -> EventSourceResponse:
    """Canned SSE stream so the console can be built before the real loop exists."""

    async def gen() -> AsyncIterator[dict[str, str]]:
        for step in range(1, 4):
            yield {
                "event": "verdict",
                "data": json.dumps({"step": step, "decision": "ALLOW", "demo": True}),
            }
            await asyncio.sleep(1)
        yield {"event": "done", "data": json.dumps({"demo": True})}

    return EventSourceResponse(gen(), ping=15)
