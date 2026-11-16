"""Run orchestration: snapshot -> decide -> (shield) -> execute, per side (brief §3).

run_side() is an async generator of Events for ONE side. What a Shielded side decides about each
Action lives in shield.StepShield; this module is its Playwright adapter (LivePage), the human
Ask, execution and the Events. It also builds the arena start URL from a preset's trap list;
nothing else in aegis/ reads it.
"""

import argparse
import asyncio
import os
import sys
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import UTC, datetime
from urllib.parse import urlencode, urlsplit

from playwright.async_api import Browser, Page, async_playwright

from aegis.agent import Agent, LLMAgent, build_agent_view
from aegis.config import settings
from aegis.events import AskGate, RunBus
from aegis.executor import execute, hit_test_veto, neutralize
from aegis.llm import AllProvidersFailed, LLMRouter
from aegis.pages import FROZEN_TIME, VIEWPORT, Checkout, ReplayStep, outcome_from_page
from aegis.schemas import (
    Action,
    AskEvent,
    AskPayload,
    AskStatus,
    DecisionEvent,
    DecisionPayload,
    DoneEvent,
    DonePayload,
    ErrorEvent,
    ErrorPayload,
    Event,
    ExecutedEvent,
    ExecutedPayload,
    Finding,
    Ledger,
    Mode,
    Outcome,
    PageSnapshot,
    SideOutcomes,
    SnapshotEvent,
    SnapshotPayload,
    SybilGraphEvidence,
    TrialReport,
    TwoViewReport,
    VerdictEvent,
    VerdictPayload,
)
from aegis.security import install_guard, origin
from aegis.shield import ShieldConfig, StepShield, side_ledger
from aegis.snapshot import screenshot_b64, take_snapshot
from aegis.trials import run_trials, run_two_view
from aegis.verdict import MAX_RETRIES, check_fast, highlights

PageHook = Callable[[Page], Awaitable[None]]


def start_url(
    traps: list[str],
    variant: str = "a",
    base: str | None = None,
    consent: str = "",
    recs: dict[str, int] | None = None,
) -> str:
    base = (base or settings.arena_base_url).rstrip("/")
    if variant == "two-shop":  # recs: the frozen revision's counts, shown on the shop cards
        counts = ",".join(f"{shop}:{n}" for shop, n in sorted((recs or {}).items()))
        return f"{base}/index.html?shops=two" + (f"&recs={counts}" if counts else "")
    q = {"traps": ",".join(traps) or "none"}
    if variant != "a":
        q["variant"] = variant
    if consent:
        q["consent"] = consent
    return f"{base}/index.html?{urlencode(q, safe=',')}"


class LivePage:
    """PagePort over a Side's real Playwright page. Trials and the Two-view check only copy it."""

    def __init__(self, browser: Browser, page: Page, checkout: Checkout) -> None:
        self.browser, self.page, self.checkout = browser, page, checkout

    async def snapshot(self) -> PageSnapshot:
        return await take_snapshot(self.page)

    async def trial(
        self, snap: PageSnapshot, control_id: str, action: Action, ledger: Ledger
    ) -> TrialReport:
        return await run_trials(
            self.browser, original_page=self.page, original=snap, control_id=control_id,
            commit_action=action, ledger=ledger, checkout=self.checkout,
            timeout_s=settings.trial_timeout_s,
        )  # fmt: skip

    async def two_view(self, snap: PageSnapshot, action: Action) -> TwoViewReport:
        return await run_two_view(
            self.browser, original_page=self.page, original=snap, commit_action=action,
            checkout=self.checkout, timeout_s=settings.trial_timeout_s,
        )  # fmt: skip


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
    shield: ShieldConfig = "I",
    ledger: Ledger | None = None,
    unresolved: list[str] | None = None,
    gate: AskGate | None = None,
    executed_log: list[Action] | None = None,
    graph_evidence: SybilGraphEvidence | None = None,
) -> AsyncIterator[Event]:
    """One side of a run. mode=unshielded runs no checks at all. Shielded: F = fast detectors +
    filtering; I = F + pre-commit audit, verified recovery and the human gate; I_MINUS_AUDIT = I
    without the ledger comparison (eval ablation). Aegis only ever executes actions the agent
    proposed (executed_log records them for tests)."""
    shielded = mode == "shielded"
    replay: list[ReplayStep] = []  # R2: what a disposable copy must redo to reach this state
    host = urlsplit(allowed_origin or url).hostname or ""
    ledger = side_ledger(shield, ledger, task, host)
    decision = StepShield(ledger, shield, graph_evidence)
    gate = gate or AskGate(timeout_s=0)  # no gate given: every ask times out (fail closed)
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

    answer: list[AskStatus] = []

    async def ask(step: int, payload: AskPayload) -> AsyncIterator[Event]:
        """Pending ask event, wait for the human (or timeout), final ask event; status in answer."""
        gate.open(payload)
        yield AskEvent(**env(step), payload=payload)
        status = await gate.wait(payload.ask_id)
        answer.append(status)
        yield AskEvent(**env(step), payload=payload.model_copy(update={"status": status}))

    def approved() -> bool:
        return answer[-1] in ("approved", "auto_approved_demo")

    history: list[str] = []
    reason = "max_steps"
    step = 0
    try:
        if shielded and unresolved:  # the request itself is unclear: ask before browsing
            pre = AskPayload(ask_id=_ask_id(), reason="uncertain", status="pending",
                             findings=[], action=None)  # fmt: skip
            async for ev in ask(0, pre):
                yield ev
            if not approved():
                yield DoneEvent(**env(0), payload=DonePayload(reason="denied", outcome=Outcome()))
                return

        page = await ctx.new_page()
        live = LivePage(browser, page, Checkout(url, allowed_origin or origin(url), replay))
        downloads: list[str] = []
        page.on("download", lambda d: downloads.append(d.suggested_filename))
        await page.clock.set_fixed_time(FROZEN_TIME)
        if on_start:
            await on_start(page)
        await page.goto(url, wait_until="domcontentloaded")
        for ev in egress_events(0):
            yield ev

        for step in range(1, max_steps + 1):
            snap = await take_snapshot(page)
            page_findings = (await check_fast(snap, None, ledger))[0] if shielded else None
            view = build_agent_view(snap, sanitize=page_findings)
            if shielded and graph_evidence is not None:
                view = view.model_copy(update={"graph_evidence": graph_evidence})
            yield SnapshotEvent(
                **env(step),
                payload=SnapshotPayload(
                    url=snap.url,
                    title=snap.title,
                    screenshot_b64=await screenshot_b64(page),
                    element_count=len(snap.elements),
                    removed=view.removed,
                ),
            )
            # A visible order confirmation is an executed commitment: it cannot be undone by
            # clicking on, so the side ends here (both modes) and the outcome is read from it.
            if step > 1 and (await outcome_from_page(page)).task_completed:
                reason = "completed"
                break
            feedback: list[str] = []
            action: Action | None = None
            attempt = 0
            neutralized: str | None = None
            stopped_by: list[Finding] = []  # findings behind the latest stopped attempt
            correcting: int | None = None  # set once the audit rerouted an attempt this step
            for attempt in range(1, MAX_RETRIES + 2):
                try:
                    action, res = await agent.decide(view, task, history + feedback)
                except Exception as e:  # provider down, unparseable output: end this side cleanly
                    code = (
                        "provider_failed" if isinstance(e, AllProvidersFailed) else "agent_failed"
                    )
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
                        attempt=attempt,
                        correcting=correcting,
                    ),
                )
                if action.type == "done" or not shielded:
                    break

                c = await decision.check(snap, action, step, live)
                verdict, fix = c.verdict, c.fix
                stopped_by = verdict.findings
                allow = verdict.decision == "ALLOW"
                if allow and fix and not await neutralize(page, fix.element_id):
                    fix = None  # cover vanished during the LLM call; the hit-test re-check decides
                neutralized = fix.element_id if fix and verdict.decision == "ALLOW" else None
                yield VerdictEvent(
                    **env(step),
                    payload=VerdictPayload(
                        verdict=verdict, action=action, audit=c.report,
                        highlights=highlights(c.findings, snap),
                        neutralized=[fix] if fix and verdict.decision == "ALLOW" else [],
                        trial=c.trial, two_view=c.two_view,
                    ),
                )  # fmt: skip
                if verdict.decision == "ALLOW":
                    break
                if c.ask_reason:
                    pending = AskPayload(
                        ask_id=_ask_id(), reason=c.ask_reason, action=action,
                        findings=verdict.findings, audit=c.report, trial=c.trial,
                        two_view=c.two_view, status="pending",
                    )  # fmt: skip
                    async for ev in ask(step, pending):
                        yield ev
                    if not approved():
                        if (retry := decision.denied_feedback(c)) is not None:
                            feedback.append(retry)
                            action = None
                            continue
                        reason, action = "denied", None
                        break
                    if recheck := await decision.approved(c, step, live):
                        yield VerdictEvent(**env(step), payload=VerdictPayload(
                            verdict=recheck.verdict, action=action, audit=recheck.audit,
                        ))  # fmt: skip
                        feedback.append(recheck.feedback)
                        action = None
                        continue
                    break  # approved: execute the agent's own action
                feedback.append(decision.feedback(c))
                if c.audit_reroute:
                    correcting = step
                action = None  # stopped: never executed
            if reason in ("error", "denied"):
                break
            if action is None:  # every attempt was stopped
                pending = AskPayload(ask_id=_ask_id(), reason="retries_exhausted",
                                     findings=stopped_by, status="pending")  # fmt: skip
                async for ev in ask(step, pending):
                    yield ev
                reason = "denied" if not approved() else "aborted"
                break  # shortcut: an approved retries_exhausted ask ends the side (nothing to run)
            if action.type == "done":
                reason = "completed"
                break
            if executed_log is not None:
                executed_log.append(action)
            result = await execute(page, action, hit_test_veto(page) if shielded else None)
            if result.ok:
                replay.append((action, neutralized))
            history.append(_describe(action, result.ok, result.error))
            yield ExecutedEvent(
                **env(step),
                payload=ExecutedPayload(
                    action=action, ok=result.ok, url_after=result.url_after,
                    defense_retry=attempt > 1, correcting=correcting,
                ),
            )  # fmt: skip
            for ev in egress_events(step):
                yield ev

        outcome = await outcome_from_page(page, downloads)
        if on_finish:
            await on_finish(page)
        if reason == "completed" and not outcome.task_completed:
            reason = "aborted"  # agent said done without a visible confirmation
        yield DoneEvent(**env(step), payload=DonePayload(reason=reason, outcome=outcome))  # type: ignore[arg-type]
    finally:
        await ctx.close()


def _ask_id() -> str:
    return uuid.uuid4().hex[:8]


async def run_pair(
    browser: Browser,
    bus: RunBus,
    run_id: str,
    *,
    task: str,
    url: str,
    make_agent: Callable[[], Agent],
    max_steps: int | None = None,
    allowed_origin: str | None = None,
    ledger: Ledger | None = None,
    unresolved: list[str] | None = None,
    shield: ShieldConfig = "I",
    graph_evidence: SybilGraphEvidence | None = None,
) -> None:
    """Both sides concurrently from the same task and start URL, each with its own agent from the
    same factory (same model and prompt); events go to the bus."""
    outcomes: dict[str, Outcome] = {}
    live = bus.get(run_id)
    gate = live.gate if live else None

    async def side(mode: Mode) -> None:
        step = 0
        try:
            async for ev in run_side(
                browser, run_id=run_id, mode=mode, task=task, url=url, agent=make_agent(),
                max_steps=max_steps, allowed_origin=allowed_origin, shield=shield, ledger=ledger,
                unresolved=unresolved, gate=gate,
                graph_evidence=graph_evidence,
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
        # Chromium refuses to sandbox as root (the Docker image runs as root).
        browser = await pw.chromium.launch(chromium_sandbox=os.getuid() != 0)
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
