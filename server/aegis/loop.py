"""Run orchestration: snapshot -> decide -> (shield) -> execute, per side (brief §3).

run_side() is an async generator of Events for ONE side. Shielded mode today is configuration F
(fast detectors + filtering + reroute feedback); the intent audit lands with B2. This module (not
the defense) builds the arena start URL from a preset's trap list; nothing else in aegis/ reads it.
"""

import argparse
import asyncio
import re
import sys
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import UTC, datetime
from typing import Literal
from urllib.parse import urlencode, urlsplit

from playwright.async_api import Browser, Page, async_playwright

from aegis.agent import Agent, LLMAgent, build_agent_view
from aegis.audit import audit, correction_hint, extract_checkout_state, is_irreversible
from aegis.config import settings
from aegis.events import AskGate, RunBus
from aegis.executor import execute, hit_test_veto, neutralize
from aegis.llm import AllProvidersFailed, LLMRouter
from aegis.schemas import (
    Action,
    AskEvent,
    AskPayload,
    AskReason,
    AskStatus,
    AuditReport,
    DecisionEvent,
    DecisionPayload,
    DoneEvent,
    DonePayload,
    Element,
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
    Verdict,
    VerdictEvent,
    VerdictPayload,
)
from aegis.security import install_guard, origin
from aegis.snapshot import screenshot_b64, take_snapshot
from aegis.verdict import (
    GUARD,
    MAX_RETRIES,
    agent_feedback,
    blocking_findings,
    check_fast,
    combine,
    highlights,
    plan_neutralization,
    run_guarded,
)

VIEWPORT = {"width": 1280, "height": 720}
# Fixed clock so countdowns and dates render identically on every run (brief §3).
FROZEN_TIME = datetime(2026, 11, 18, 10, 0, tzinfo=UTC)
PageHook = Callable[[Page], Awaitable[None]]
ShieldConfig = Literal["F", "I", "I_MINUS_AUDIT"]  # U is mode="unshielded"

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
    shield: ShieldConfig = "I",
    ledger: Ledger | None = None,
    unresolved: list[str] | None = None,
    gate: AskGate | None = None,
    executed_log: list[Action] | None = None,
) -> AsyncIterator[Event]:
    """One side of a run. mode=unshielded runs no checks at all. Shielded: F = fast detectors +
    filtering; I = F + pre-commit audit, verified recovery and the human gate; I_MINUS_AUDIT = I
    without the ledger comparison (eval ablation). Aegis only ever executes actions the agent
    proposed (executed_log records them for tests)."""
    shielded = mode == "shielded"
    audits = shielded and shield == "I"
    gated = shielded and shield in ("I", "I_MINUS_AUDIT")
    host = urlsplit(allowed_origin or url).hostname or ""
    # F (and a missing parse) checks against a ledger that holds only the task and the domain.
    ledger = (
        ledger
        if ledger is not None and shield != "F"
        else Ledger(goal=task, allowed_domains=[host])
    )
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
    last_audit: tuple[int, set[str]] | None = None  # (step, violation keys) of the latest audit
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
            feedback: list[str] = []
            action: Action | None = None
            attempt = 0
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
                    ),
                )
                if action.type == "done" or not shielded:
                    break

                findings, ms = await check_fast(snap, action, ledger)
                fix = plan_neutralization(snap, action)
                verdict = combine(findings, action, ms, fix)
                report: AuditReport | None = None
                ask_reason: AskReason | None = None
                if any(f.detector == GUARD for f in blocking_findings(findings, action)):
                    ask_reason = "guard_unavailable"  # retrying cannot fix a broken check
                    verdict = verdict.model_copy(update={"decision": "ASK"})
                elif (
                    verdict.decision == "ALLOW"
                    and gated
                    and is_irreversible(_el(snap, action.target_id), action.type)
                ):
                    if audits:
                        report, guard = await _audit(snap, ledger, action, last_audit)
                        if guard:
                            findings.append(guard)
                    verdict, ask_reason, last_audit = _commit_decision(
                        verdict, report, step, last_audit, findings
                    )
                if (
                    verdict.decision == "ALLOW"
                    and fix
                    and not await neutralize(page, fix.element_id)
                ):
                    fix = None  # cover vanished during the LLM call; the hit-test re-check decides
                yield VerdictEvent(
                    **env(step),
                    payload=VerdictPayload(
                        verdict=verdict, action=action, audit=report,
                        highlights=highlights(findings, snap),
                        neutralized=[fix] if fix and verdict.decision == "ALLOW" else [],
                    ),
                )  # fmt: skip
                if verdict.decision == "ALLOW":
                    break
                if ask_reason:
                    pending = AskPayload(
                        ask_id=_ask_id(), reason=ask_reason, action=action,
                        findings=verdict.findings, audit=report, status="pending",
                    )  # fmt: skip
                    async for ev in ask(step, pending):
                        yield ev
                    if not approved():
                        reason, action = "denied", None
                        break
                    if audits and report is not None:  # the page may have changed while waiting
                        snap = await take_snapshot(page)
                        again, guard = await _audit(snap, ledger, action, (step, set()))
                        if guard or _keys(again) - _keys(report) or _new_uncertain(again, report):
                            yield VerdictEvent(**env(step), payload=VerdictPayload(
                                verdict=Verdict(decision="REROUTE", findings=findings,
                                                reroute_hint="The checkout changed while waiting "
                                                "for approval; check it again."),
                                action=action, audit=again))  # fmt: skip
                            feedback.append(_audit_feedback(action, again, changed=True))
                            action = None
                            continue
                    break  # approved: execute the agent's own action
                audit_reroute = report is not None and not blocking_findings(findings, action, fix)
                feedback.append(
                    _audit_feedback(action, report)
                    if audit_reroute
                    else agent_feedback(verdict, action)
                )
                action = None  # stopped: never executed
            if reason in ("error", "denied"):
                break
            if action is None:  # every attempt was stopped
                pending = AskPayload(ask_id=_ask_id(), reason="retries_exhausted",
                                     findings=verdict.findings, status="pending")  # fmt: skip
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
            history.append(_describe(action, result.ok, result.error))
            yield ExecutedEvent(
                **env(step),
                payload=ExecutedPayload(
                    action=action, ok=result.ok, url_after=result.url_after,
                    defense_retry=attempt > 1,
                ),
            )  # fmt: skip
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


def _ask_id() -> str:
    return uuid.uuid4().hex[:8]


def _el(snap: PageSnapshot, element_id: str | None) -> Element | None:
    return next((e for e in snap.elements if e.id == element_id), None)


def _keys(report: AuditReport | None) -> set[str]:
    if report is None:
        return set()
    return {f"{c.constraint}:{c.element_id or c.observed_value}" for c in report.checks
            if c.status == "violation"}  # fmt: skip


def _new_uncertain(new: AuditReport | None, old: AuditReport) -> bool:
    before = {c.constraint for c in old.checks if c.status == "uncertain"}
    return bool(new) and any(c.status == "uncertain" and c.constraint not in before
                             for c in new.checks)  # type: ignore[union-attr]  # fmt: skip


async def _audit(
    snap: PageSnapshot, ledger: Ledger, action: Action, last: tuple[int, set[str]] | None
) -> tuple[AuditReport | None, Finding | None]:
    report, guard = await run_guarded(
        "B2_audit", lambda: audit(extract_checkout_state(snap), ledger), action
    )
    if report is not None and last is not None:
        report = report.model_copy(update={"recheck_of": last[0]})
    return report, guard


def _commit_decision(
    verdict: Verdict,
    report: AuditReport | None,
    step: int,
    last: tuple[int, set[str]] | None,
    findings: list[Finding],
) -> tuple[Verdict, AskReason | None, tuple[int, set[str]] | None]:
    """Before an irreversible action (configuration I / I_MINUS_AUDIT): violation -> REROUTE with
    a hint; the same violation again at the recheck -> ask retries_exhausted; uncertain -> ask
    uncertain; all clear -> ask final_payment. No report (I_MINUS_AUDIT) -> final_payment."""
    if report is None:
        if any(f.detector == GUARD for f in findings):  # the audit itself failed
            return verdict.model_copy(update={"decision": "ASK"}), "guard_unavailable", last
        return verdict.model_copy(update={"decision": "ASK"}), "final_payment", last
    keys = _keys(report)
    if keys:
        if last is not None and keys & last[1]:
            return verdict.model_copy(update={"decision": "ASK"}), "retries_exhausted", (step, keys)
        hint = correction_hint(report)
        return verdict.model_copy(update={"decision": "REROUTE", "reroute_hint": hint}), None, (
            step, keys)  # fmt: skip
    if any(c.status == "uncertain" for c in report.checks):
        return verdict.model_copy(update={"decision": "ASK"}), "uncertain", (step, keys)
    return verdict.model_copy(update={"decision": "ASK"}), "final_payment", (step, keys)


def _audit_feedback(action: Action, report: AuditReport | None, changed: bool = False) -> str:
    bad = [c for c in (report.checks if report else []) if c.status == "violation"]
    issues = "; ".join(f"{c.constraint}: {c.evidence}" for c in bad) or "the checkout changed"
    hint = correction_hint(report) if report else None
    lead = "The checkout changed while the user was approving. " if changed else ""
    return (
        f"<<<AEGIS SECURITY FEEDBACK: your proposed {action.type} on {action.target_id} was "
        f"REROUTED and NOT executed. {lead}The checkout does not match what the user authorized: "
        f"{issues}. "
        + (
            f"Fix it yourself: {hint} "
            if hint
            else "This cannot be fixed by unticking anything; do not place the order. "
        )
        + "END AEGIS FEEDBACK>>>"
    )


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
