"""R2 (experimental, brief §3): disposable consent trials for one ambiguous binary control.

Two fresh browser contexts reproduce the original checkout by replaying the agent's executed
actions from the start URL. One copy places the simulated order with the control ticked, the other
with it unticked. The two visible confirmations are compared against the fixed ledger.

Boundaries: arena origin only (every other request is aborted), no downloads, no service workers,
no popups, no LLM calls, a total time budget, contexts always closed. Decisions use only what the
copies show on screen; never trap ids, arena storage, the hidden outcome JSON or evaluator truth.
The original page is only read (before/after comparison); it is never clicked.
"""

import asyncio
import time
from datetime import datetime

from playwright.async_api import Browser, BrowserContext, Page

from aegis.audit import extract_checkout_state, same_thing
from aegis.executor import execute, neutralize
from aegis.schemas import (
    Action,
    AuditCheck,
    AuditReport,
    CheckoutState,
    Commitment,
    Element,
    Ledger,
    PageSnapshot,
    TrialBranch,
    TrialReport,
)
from aegis.security import install_guard
from aegis.snapshot import screenshot_b64, take_snapshot

# One replayed step: the agent's executed action and the overlay Aegis neutralized before it.
ReplayStep = tuple[Action, str | None]

DEFAULT_TIMEOUT_S = 10.0


def _signature(state: CheckoutState) -> dict:
    """What must match between the original checkout and a copy (element ids excluded)."""
    return {
        "lines": sorted((ln.name, ln.qty, ln.amount) for ln in state.lines),
        "fees": sorted((f.name, f.amount) for f in state.fees),
        "options": sorted((o.label, o.checked) for o in state.ticked_options),
        "recurring": sorted(r.description for r in state.recurring_terms),
        "total": state.total,
        "shipping": state.shipping.method if state.shipping else None,
    }


def _same_element(a: Element | None, b: Element | None) -> bool:
    return a is not None and b is not None and a.tag == b.tag and a.text == b.text


def _find(snap: PageSnapshot, element_id: str | None) -> Element | None:
    return next((e for e in snap.elements if e.id == element_id), None)


def _key(c: Commitment) -> str:
    return f"{c.kind}:{c.description}"


def _unauthorized(c: Commitment, ledger: Ledger) -> bool:
    named = any(same_thing(i.name, c.description) for i in ledger.items)
    match c.kind:
        case "data_sharing":
            return not ledger.data_allowed  # categories can't be read reliably: any sharing counts
        case "subscription":
            return not (ledger.allow_subscriptions and named)
        case "addon":
            return not (ledger.allow_addons and named)
        case "fee" | "download":
            return True
        case _:
            return False


async def _branch(
    browser: Browser,
    *,
    checked: bool,
    start_url: str,
    allowed_origin: str,
    replay: list[ReplayStep],
    original: PageSnapshot,
    control_id: str,
    commit_action: Action,
    viewport: dict,
    frozen_time: datetime,
    outcome_reader,  # noqa: ANN001  (loop.outcome_from_page; passed in to avoid an import cycle)
    blocked: list[str],
) -> TrialBranch:
    branch = TrialBranch(control_checked=checked)
    ctx: BrowserContext = await browser.new_context(
        viewport=viewport,  # type: ignore[arg-type]
        accept_downloads=False,
        service_workers="block",
    )
    try:
        await install_guard(ctx, allowed_origin, blocked.append)
        ctx.on("page", _close_extra_pages(ctx))
        page = await ctx.new_page()
        await page.clock.set_fixed_time(frozen_time)
        await page.goto(start_url, wait_until="domcontentloaded")
        for action, neutralized in replay:
            await take_snapshot(page)  # stamps the same deterministic element ids
            if neutralized:
                await neutralize(page, neutralized)
            res = await execute(page, action)
            branch.disposable_actions += 1
            if not res.ok:
                branch.error = f"replay step failed: {res.error}"
                return branch

        snap = await take_snapshot(page)
        same = _signature(extract_checkout_state(snap)) == _signature(
            extract_checkout_state(original)
        )
        control, target = _find(snap, control_id), _find(snap, commit_action.target_id)
        branch.state_matched = (
            same
            and _same_element(control, _find(original, control_id))
            and _same_element(target, _find(original, commit_action.target_id))
        )
        if not branch.state_matched or control is None:
            branch.error = "the copy did not reproduce the original checkout"
            return branch

        if bool(control.checked) != checked:
            res = await execute(page, Action(type="click", target_id=control_id,
                                             rationale="disposable trial"))  # fmt: skip
            branch.disposable_actions += 1
            snap = await take_snapshot(page)
            if not res.ok or bool((_find(snap, control_id) or control).checked) != checked:
                branch.error = "could not set the control in the copy"
                return branch

        res = await execute(page, commit_action)
        branch.disposable_actions += 1
        await take_snapshot(page)  # wait for the confirmation page to load
        branch.outcome = await outcome_reader(page)
        branch.screenshot_b64 = await screenshot_b64(page, quality=50)
        if not res.ok or not branch.outcome.task_completed:
            branch.error = "the copy did not reach a visible order confirmation"
        return branch
    finally:
        await ctx.close()


def _close_extra_pages(ctx: BrowserContext):  # noqa: ANN202
    def handler(page: Page) -> None:
        if len(ctx.pages) > 1:  # popups and new tabs are not part of a trial
            asyncio.ensure_future(page.close())

    return handler


async def run_trials(
    browser: Browser,
    *,
    original_page: Page,
    original: PageSnapshot,
    control_id: str,
    commit_action: Action,
    ledger: Ledger,
    start_url: str,
    allowed_origin: str,
    replay: list[ReplayStep],
    viewport: dict,
    frozen_time: datetime,
    outcome_reader,  # noqa: ANN001
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> TrialReport:
    """Both states of one checkbox, sequentially, in disposable copies. Never raises: any failure
    is reported as `unavailable` so the caller falls back to asking the human."""
    started = time.perf_counter()
    control = _find(original, control_id)
    report = TrialReport(
        control_id=control_id,
        control_label=control.text if control else "",
        current_checked=bool(control and control.checked),
        status="unavailable",
    )
    checkbox = control is not None and control.tag == "input" and control.checked is not None
    if not checkbox or control.role == "radio":  # type: ignore[union-attr]
        report.reason = "unsupported: only a single checkbox is supported"
        return report
    blocked: list[str] = []
    before = _signature(extract_checkout_state(original))
    try:
        async with asyncio.timeout(timeout_s):
            for checked in (True, False):
                report.branches.append(await _branch(
                    browser, checked=checked, start_url=start_url, allowed_origin=allowed_origin,
                    replay=replay, original=original, control_id=control_id,
                    commit_action=commit_action, viewport=viewport, frozen_time=frozen_time,
                    outcome_reader=outcome_reader, blocked=blocked,
                ))  # fmt: skip
    except TimeoutError:
        report.reason = f"timeout after {timeout_s:.0f} s"
    except Exception as e:  # experimental module: failure means "ask", never "allow"
        report.reason = f"trial failed: {type(e).__name__}: {str(e)[:200]}"
    report.blocked_requests = len(blocked)
    try:
        after = await take_snapshot(original_page)
        report.original_unchanged = _signature(extract_checkout_state(after)) == before
    except Exception:
        report.original_unchanged = None
    report.elapsed_ms = int((time.perf_counter() - started) * 1000)
    if report.reason:
        return report
    _judge(report, ledger)
    return report


def _judge(report: TrialReport, ledger: Ledger) -> None:
    """Compare the two observed confirmations; only differences between them are the control's
    effect, so unrelated problems elsewhere in the checkout don't decide this control."""
    bad = next((b for b in report.branches if b.error or b.outcome is None), None)
    if bad or len(report.branches) != 2:
        report.status, report.reason = "unavailable", (bad.error if bad else "missing branch") or ""
        return
    on, off = report.branches
    on_keys = {_key(c): c for c in on.outcome.commitments}  # type: ignore[union-attr]
    off_keys = {_key(c): c for c in off.outcome.commitments}  # type: ignore[union-attr]
    for b, mine, other in ((on, on_keys, off_keys), (off, off_keys, on_keys)):
        b.effect = [k for k in mine if k not in other]
        b.unauthorized = [k for k in b.effect if _unauthorized(mine[k], ledger)]
        if ledger.budget_max is not None and (b.outcome.total or 0) > ledger.budget_max:  # type: ignore[union-attr]
            b.unauthorized.append(f"total ₹{b.outcome.total:,.0f} is over the budget")  # type: ignore[union-attr]
    ok = [b for b in report.branches if not b.unauthorized]
    if not on.effect and not off.effect and (on.outcome.total == off.outcome.total):  # type: ignore[union-attr]
        report.status = "uncertain"
        report.reason = "both copies showed the same confirmation: no observable effect to judge"
    elif len(ok) == 2:
        report.status, report.reason = "both_ok", "either state matches the user's permission"
    elif len(ok) == 1:
        report.status, report.recommended_checked = "resolved", ok[0].control_checked
        wrong = report.branches[0] if ok[0] is report.branches[1] else report.branches[1]
        report.reason = (
            f"{'ticked' if wrong.control_checked else 'unticked'}, the confirmation showed "
            f"{', '.join(wrong.unauthorized)}; {'ticked' if ok[0].control_checked else 'unticked'}"
            " it did not"
        )
    else:
        report.status, report.reason = "uncertain", "neither state matches the user's permission"


def describe(report: TrialReport) -> str:
    """One line for the agent's correction hint / the ask dialog."""
    if report.status == "resolved":
        want = "ticked" if report.recommended_checked else "unticked"
        verb = "tick" if report.recommended_checked else "untick"
        action = (
            "leave it as it is"
            if report.recommended_checked == report.current_checked
            else f"{verb} it (element {report.control_id})"
        )
        return (f"Disposable trial of {report.control_label!r}: {report.reason}. The box must be "
                f"{want}: {action}.")  # fmt: skip
    return f"Disposable trial of {report.control_label!r}: {report.status} ({report.reason})."


def apply_trial(report: AuditReport, trial: TrialReport) -> AuditReport:
    """Replace the uncertain consent check with the trial's evidence. Resolved: ok if the box is
    already right, otherwise a violation the agent fixes itself. both_ok: ok. Anything else stays
    uncertain, so the human decides (never a silent allow)."""
    opts = report.observed.ticked_options
    box = next((o for o in opts if o.element_id == trial.control_id), None)
    current = box.checked if box else trial.current_checked  # this audit's view, not the trial's
    checks: list[AuditCheck] = []
    for c in report.checks:
        if c.constraint != "data_allowed" or c.element_id != trial.control_id:
            checks.append(c)
            continue
        if trial.status == "resolved":
            right = trial.recommended_checked == current
            status = "ok" if right else "violation"
        else:
            status = "ok" if trial.status == "both_ok" else "uncertain"
        want = {True: "box must be ticked", False: "box must be unticked", None: c.ledger_value}
        checks.append(c.model_copy(update={
            "constraint": "consent_trial",
            "ledger_value": want[trial.recommended_checked],
            "observed_value": f"box {'ticked' if current else 'unticked'}",
            "evidence": describe(trial),
            "status": status,
        }))  # fmt: skip
    return report.model_copy(update={"checks": checks})
