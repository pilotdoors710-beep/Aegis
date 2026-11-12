"""Run orchestration: snapshot -> decide -> (shield) -> execute, per side (brief §3).

run_side() is an async generator of Events for ONE side. The shield hook lands in A-D2-06; today
only unshielded mode exists. This module (not the defense) builds the arena start URL from a
preset's trap list; nothing else in aegis/ reads it.
"""

import argparse
import asyncio
import re
import sys
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import UTC, datetime
from urllib.parse import urlencode

from playwright.async_api import Browser, Page, async_playwright

from aegis.agent import Agent, LLMAgent, build_agent_view
from aegis.config import settings
from aegis.events import RunBus
from aegis.executor import execute
from aegis.llm import AllProvidersFailed, LLMRouter
from aegis.schemas import (
    Action,
    DecisionEvent,
    DecisionPayload,
    DoneEvent,
    DonePayload,
    ErrorEvent,
    ErrorPayload,
    Event,
    ExecutedEvent,
    ExecutedPayload,
    Mode,
    Outcome,
    SideOutcomes,
    SnapshotEvent,
    SnapshotPayload,
)
from aegis.security import install_guard, origin
from aegis.snapshot import screenshot_b64, take_snapshot

VIEWPORT = {"width": 1280, "height": 720}
# Fixed clock so countdowns and dates render identically on every run (brief §3).
FROZEN_TIME = datetime(2026, 11, 18, 10, 0, tzinfo=UTC)
PageHook = Callable[[Page], Awaitable[None]]

_TOTAL_RE = re.compile(r"Order total[^\d₹]*₹?\s*([\d,]+(?:\.\d+)?)", re.I)


def start_url(traps: list[str], variant: str = "a", base: str | None = None) -> str:
    base = (base or settings.arena_base_url).rstrip("/")
    q = {"traps": ",".join(traps) or "none"}
    if variant != "a":
        q["variant"] = variant
    return f"{base}/index.html?{urlencode(q, safe=',')}"


async def outcome_from_page(page: Page) -> Outcome:
    """Visible confirmation text only; the evaluator scores against separate ground truth."""
    try:
        body = await page.inner_text("body", timeout=2_000)
    except Exception:
        return Outcome()
    if "order confirmed" not in body.lower():
        return Outcome(task_completed=False)
    m = _TOTAL_RE.search(body)
    total = float(m.group(1).replace(",", "")) if m else None
    return Outcome(task_completed=True, total=total)


def _describe(action: Action, ok: bool, error: str | None) -> str:
    target = f" {action.target_id}" if action.target_id else ""
    extra = f" text={action.text!r}" if action.text else ""
    extra += f" url={action.url}" if action.url else ""
    status = "ok" if ok else f"FAILED ({error})"
    return f"{action.type}{target}{extra} — {action.rationale} [{status}]"


async def run_side(
    browser: Browser,
    *,
    run_id: str,
    mode: Mode,
    task: str,
    url: str,
    agent: Agent,
    max_steps: int | None = None,
    on_start: PageHook | None = None,
    on_finish: PageHook | None = None,
    allowed_origin: str | None = None,
) -> AsyncIterator[Event]:
    if mode != "unshielded":
        raise NotImplementedError("shielded mode lands with the verdict engine (A-D2-06)")
    max_steps = max_steps or settings.max_steps
    ctx = await browser.new_context(viewport=VIEWPORT, accept_downloads=True)  # type: ignore[arg-type]
    blocked: list[str] = []
    await install_guard(ctx, allowed_origin or origin(url), blocked.append)

    def env(step: int) -> dict:
        return {"run_id": run_id, "step": step, "mode": mode, "ts": datetime.now(UTC)}

    def egress_events(step: int) -> list[Event]:
        evs: list[Event] = [
            ErrorEvent(**env(step), payload=ErrorPayload(
                code="egress_blocked", message=f"request outside the arena blocked: {u[:200]}",
                recoverable=True))
            for u in blocked
        ]  # fmt: skip
        blocked.clear()
        return evs

    history: list[str] = []
    reason = "max_steps"
    step = 0
    try:
        page = await ctx.new_page()
        await page.clock.set_fixed_time(FROZEN_TIME)
        if on_start:
            await on_start(page)
        await page.goto(url, wait_until="domcontentloaded")
        for ev in egress_events(0):
            yield ev

        for step in range(1, max_steps + 1):
            snap = await take_snapshot(page)
            yield SnapshotEvent(
                **env(step),
                payload=SnapshotPayload(
                    url=snap.url,
                    title=snap.title,
                    screenshot_b64=await screenshot_b64(page),
                    element_count=len(snap.elements),
                ),
            )
            view = build_agent_view(snap)
            try:
                action, res = await agent.decide(view, task, history)
            except Exception as e:  # provider down, unparseable output, ...: end this side cleanly
                code = "provider_failed" if isinstance(e, AllProvidersFailed) else "agent_failed"
                msg = f"{type(e).__name__}: {str(e)[:300]}"
                yield ErrorEvent(
                    **env(step), payload=ErrorPayload(code=code, message=msg, recoverable=False)
                )
                reason = "error"
                break
            yield DecisionEvent(
                **env(step),
                payload=DecisionPayload(
                    action=action,
                    provider=res.provider,
                    model=res.model,
                    cached=res.cached,
                    llm_latency_ms=res.latency_ms,
                ),
            )
            if action.type == "done":
                reason = "completed"
                break
            result = await execute(page, action)
            history.append(_describe(action, result.ok, result.error))
            yield ExecutedEvent(
                **env(step),
                payload=ExecutedPayload(action=action, ok=result.ok, url_after=result.url_after),
            )
            for ev in egress_events(step):
                yield ev

        outcome = await outcome_from_page(page)
        if on_finish:
            await on_finish(page)
        if reason == "completed" and not outcome.task_completed:
            reason = "aborted"  # agent said done without a visible confirmation
        yield DoneEvent(**env(step), payload=DonePayload(reason=reason, outcome=outcome))  # type: ignore[arg-type]
    finally:
        await ctx.close()


async def run_pair(
    browser: Browser,
    bus: RunBus,
    run_id: str,
    *,
    task: str,
    url: str,
    agent: Agent,
    max_steps: int | None = None,
    allowed_origin: str | None = None,
) -> None:
    """Both sides concurrently from the same task and start URL; events go to the bus."""
    outcomes: dict[str, Outcome] = {}

    async def side(mode: Mode) -> None:
        step = 0
        try:
            async for ev in run_side(
                browser, run_id=run_id, mode=mode, task=task, url=url, agent=agent,
                max_steps=max_steps, allowed_origin=allowed_origin,
            ):  # fmt: skip
                step = ev.step
                if isinstance(ev, DoneEvent):
                    outcomes[mode] = ev.payload.outcome
                await bus.publish(run_id, ev)
        except Exception as e:  # one side failing must still end with its done event
            env = {"run_id": run_id, "step": step, "mode": mode, "ts": datetime.now(UTC)}
            msg = f"{type(e).__name__}: {str(e)[:300]}"
            await bus.publish(
                run_id,
                ErrorEvent(
                    **env, payload=ErrorPayload(code="side_failed", message=msg, recoverable=False)
                ),
            )
            outcomes[mode] = Outcome()
            await bus.publish(run_id, DoneEvent(
                **env, payload=DonePayload(reason="error", outcome=outcomes[mode])))  # fmt: skip

    await bus.update(run_id, status="running")
    try:
        await asyncio.gather(side("unshielded"), side("shielded"))
    finally:
        await bus.update(run_id, close=True, status="done", outcomes=SideOutcomes(**outcomes))


async def _cli() -> None:
    ap = argparse.ArgumentParser(description="Run one side and print one Event JSON per line.")
    ap.add_argument("--task", required=True)
    ap.add_argument("--traps", default="none")
    ap.add_argument("--variant", default="a")
    ap.add_argument("--mode", default="unshielded", choices=["unshielded", "shielded"])
    ap.add_argument("--arena", default=None, help="arena base URL (default ARENA_BASE_URL)")
    ap.add_argument("--model", default=None, help="pin one provider:model (no fall-through)")
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--show-screenshots", action="store_true")
    a = ap.parse_args()

    cfg = settings.model_copy(update={"agent_models": a.model}) if a.model else settings
    agent = LLMAgent(LLMRouter(cfg), use_cache=not a.no_cache)
    url = start_url(a.traps.split(","), a.variant, a.arena)
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(args=["--no-sandbox"])
        async for ev in run_side(
            browser, run_id="cli", mode=a.mode, task=a.task, url=url, agent=agent
        ):
            if not a.show_screenshots and ev.kind == "snapshot":
                ev.payload.screenshot_b64 = None
            sys.stdout.write(ev.model_dump_json() + "\n")
            sys.stdout.flush()
        await browser.close()


if __name__ == "__main__":
    asyncio.run(_cli())
