"""The Shielded Step decision: one proposed Action -> Verdict, Ask reason and evidence.

The order of checks lives only here: fast Detectors and Neutralization, the Sybil Shop gate,
guard_unavailable -> Ask (fail closed, ADR-0004), then before an Irreversible action the Audit,
Trials and the Two-view check. Page effects reach it through a PagePort, so the Playwright run
loop (loop.py) and the browser-use wrapper (wrap.py) are two adapters of one decision.
"""

import re
from dataclasses import dataclass
from typing import Literal, Protocol
from urllib.parse import parse_qs, urlsplit

from aegis.audit import audit, correction_hint, extract_checkout_state, is_irreversible
from aegis.schemas import (
    Action,
    AskReason,
    AuditReport,
    Element,
    Finding,
    Ledger,
    Neutralization,
    PageSnapshot,
    SybilGraphEvidence,
    TrialReport,
    TwoViewReport,
    Verdict,
)
from aegis.trials import apply_trial, diff_states
from aegis.verdict import (
    GUARD,
    agent_feedback,
    blocking_findings,
    check_fast,
    combine,
    plan_neutralization,
    run_guarded,
)

# U is mode="unshielded". I_R2 = I plus the disposable-copy checks: R2 consent trials and the
# two-view (agent vs ordinary-browser) check. Experimental; kept out of the core U/F/I comparison
# (brief §10).
ShieldConfig = Literal["F", "I", "I_MINUS_AUDIT", "I_R2"]
Shop = Literal["A", "B"]


@dataclass(frozen=True)
class Capabilities:
    audits: bool  # compare the checkout with the Ledger before an Irreversible action
    gated: bool  # Ask a human before an Irreversible action
    trials: bool  # R2 Trials and the Two-view check (experimental)
    parses_ledger: bool  # False: checks run against a goal-only Ledger (ADR-0005)


CAPABILITIES: dict[ShieldConfig, Capabilities] = {
    "F": Capabilities(audits=False, gated=False, trials=False, parses_ledger=False),
    "I": Capabilities(audits=True, gated=True, trials=False, parses_ledger=True),
    # Eval ablation: same gate, retries and Ledger as I, without the Ledger comparison.
    "I_MINUS_AUDIT": Capabilities(audits=False, gated=True, trials=False, parses_ledger=True),
    "I_R2": Capabilities(audits=True, gated=True, trials=True, parses_ledger=True),
}


def side_ledger(shield: ShieldConfig, ledger: Ledger | None, task: str, host: str) -> Ledger:
    """The Ledger a Side checks against. F (and a failed parse) gets only the task and domain."""
    if ledger is not None and CAPABILITIES[shield].parses_ledger:
        return ledger
    return Ledger(goal=task, allowed_domains=[host])


class PagePort(Protocol):
    """What the Step decision needs from the browser. Adapters: loop.LivePage (Playwright) and
    wrap's CDP port (no Trials)."""

    async def snapshot(self) -> PageSnapshot: ...

    async def trial(
        self, snap: PageSnapshot, control_id: str, action: Action, ledger: Ledger
    ) -> TrialReport: ...

    async def two_view(self, snap: PageSnapshot, action: Action) -> TwoViewReport: ...


@dataclass
class Check:
    """One checked Action. `findings` is everything found (highlighted on the screenshot);
    `verdict.findings` is what the decision and an Ask show."""

    action: Action
    verdict: Verdict
    findings: list[Finding]
    fix: Neutralization | None = None  # invisible cover to make click-through on ALLOW
    report: AuditReport | None = None
    trial: TrialReport | None = None
    two_view: TwoViewReport | None = None
    ask_reason: AskReason | None = None
    shop: Shop | None = None  # the Shop an untrusted_shop Ask is about

    @property
    def audit_reroute(self) -> bool:
        """Stopped by the Audit (not a Detector): the agent's next attempt is its correction."""
        return (
            self.verdict.decision != "ALLOW"
            and self.ask_reason is None
            and self.report is not None
            and not blocking_findings(self.findings, self.action, self.fix)
        )


@dataclass(frozen=True)
class Recheck:
    """The checkout changed while the human was approving: REROUTE instead of executing."""

    verdict: Verdict
    audit: AuditReport | None
    feedback: str


class StepShield:
    """Per-Side decision state: the frozen Ledger, the Shield configuration, the frozen Graph
    evidence, Shops a human let the agent enter, and the latest Audit (for Rechecks)."""

    def __init__(
        self,
        ledger: Ledger,
        shield: ShieldConfig = "I",
        graph_evidence: SybilGraphEvidence | None = None,
    ) -> None:
        self.ledger = ledger
        self.can = CAPABILITIES[shield]
        self.graph_evidence = graph_evidence
        self.approved_shops: set[Shop] = set()
        self.last_audit: tuple[int, set[str]] | None = None  # (step, violation keys)

    async def check(self, snap: PageSnapshot, action: Action, step: int, page: PagePort) -> Check:
        """Decide one proposed Action. Never executes it; `page` is only read or copied."""
        findings, ms = await check_fast(snap, action, self.ledger)
        fix = plan_neutralization(snap, action)
        c = Check(action=action, verdict=combine(findings, action, ms, fix), findings=findings,
                  fix=fix)  # fmt: skip
        if untrusted := self._untrusted_shop(snap, action):
            findings.append(untrusted)
            c.ask_reason, c.shop = "untrusted_shop", target_shop(snap, action)
            c.verdict = c.verdict.model_copy(update={"decision": "ASK", "findings": findings})
        elif any(f.detector == GUARD for f in blocking_findings(findings, action)):
            c.ask_reason = "guard_unavailable"  # retrying cannot fix a broken check
            c.verdict = c.verdict.model_copy(update={"decision": "ASK"})
        elif (
            c.verdict.decision == "ALLOW"
            and self.can.gated
            and is_irreversible(_el(snap, action.target_id), action.type)
        ):
            await self._before_commit(c, snap, step, page)
        return c

    async def approved(self, c: Check, step: int, page: PagePort) -> Recheck | None:
        """The human approved `c`. Consent binding: the approval covers exactly the checkout
        shown, so any change (even one still within the Ledger) needs a fresh look."""
        if c.ask_reason == "untrusted_shop" and c.shop:
            self.approved_shops.add(c.shop)
        if not (self.can.audits and c.report is not None):
            return None
        snap = await page.snapshot()  # the page may have changed while waiting
        again, guard = await self._audit(snap, c.action, (step, set()))
        if c.trial is not None and again is not None:  # same control, same evidence
            again = apply_trial(again, c.trial)
        changed = diff_states(
            c.report.observed, again.observed, "when approved", "now"
        ) if again else []  # fmt: skip
        if not (guard or changed or _keys(again) - _keys(c.report)
                or _new_uncertain(again, c.report)):  # fmt: skip
            return None
        hint = "The checkout changed while waiting for approval; check it again." + (
            f" ({'; '.join(changed)})" if changed else ""
        )
        return Recheck(
            verdict=Verdict(decision="REROUTE", findings=c.findings, reroute_hint=hint),
            audit=again,
            feedback=_audit_feedback(c.action, again, changed=True),
        )

    def denied_feedback(self, c: Check) -> str | None:
        """Feedback that lets the agent choose again after a denial; None ends the Side."""
        if c.ask_reason == "untrusted_shop":
            return (
                f"Entry to Shop {c.shop} was denied due to insufficient structural trust. "
                "You must choose an alternative shop that meets trust requirements."
            )
        return None

    def feedback(self, c: Check) -> str:
        """Feedback for a BLOCK or REROUTE (the Action was not executed)."""
        if c.audit_reroute:
            return _audit_feedback(c.action, c.report)
        return agent_feedback(c.verdict, c.action)

    def _untrusted_shop(self, snap: PageSnapshot, action: Action) -> Finding | None:
        """Sybil Shop gate: entering a Shop that fails the Graph policy needs a human."""
        if self.graph_evidence is None:
            return None
        shop = target_shop(snap, action)
        if not shop or shop in self.approved_shops:
            return None
        ev = self.graph_evidence.shops.get(shop)
        if ev and ev.policy_passed:
            return None
        return Finding(
            detector="sybil", trap_type="untrusted_shop", severity="high",
            element_id=action.target_id,
            evidence=(
                f"Shop {shop} failed topological trust policy "
                f"({self.graph_evidence.policy_text()}; got R={ev.total_robustness:.1f}, "
                f"S={ev.structural_support:.3f}, L={ev.anchor_withdrawal_resilience:.2f}) "
                f"under frozen revision {self.graph_evidence.revision_id[:8]}."
                if ev
                else f"Shop {shop} has no verified graph evidence."
            ),
            suggestion="Do not enter untrusted shop; select a shop with verified structural trust.",
        )  # fmt: skip

    async def _before_commit(self, c: Check, snap: PageSnapshot, step: int, page: PagePort) -> None:
        if self.can.audits:
            c.report, guard = await self._audit(snap, c.action, self.last_audit)
            if guard:
                c.findings.append(guard)
            if self.can.trials and c.report is not None and (ctl := _ambiguous(c.report)):
                trial = c.trial = await page.trial(snap, ctl, c.action, self.ledger)
                c.report = apply_trial(c.report, trial)
        c.verdict, c.ask_reason, self.last_audit = _commit_decision(
            c.verdict, c.report, step, self.last_audit, c.findings
        )
        # Two-view check: only once the agent's own view passed the audit, so a checkout that
        # is about to be approved is also what an ordinary browser gets.
        if self.can.trials and c.report is not None and c.verdict.decision == "ASK":
            two_view = c.two_view = await page.two_view(snap, c.action)
            if two_view.status == "mismatch":
                c.findings.append(Finding(
                    detector="two_view", trap_type="hidden_info", severity="high",
                    element_id=c.action.target_id,
                    evidence="This site shows an automated browser a different "
                             "checkout: " + "; ".join(two_view.diffs),
                    suggestion="Do not pay: the agent's view cannot be trusted.",
                ))  # fmt: skip
                c.ask_reason = "cloaked_checkout"
                c.verdict = c.verdict.model_copy(update={"findings": c.findings})

    async def _audit(
        self, snap: PageSnapshot, action: Action, last: tuple[int, set[str]] | None
    ) -> tuple[AuditReport | None, Finding | None]:
        report, guard = await run_guarded(
            "B2_audit", lambda: audit(extract_checkout_state(snap), self.ledger), action
        )
        if report is not None and last is not None:
            report = report.model_copy(update={"recheck_of": last[0]})
        return report, guard


def target_shop(snap: PageSnapshot, action: Action) -> Shop | None:
    """Identify which shop (A or B) an action targets, if any."""
    candidates: list[str | None] = []
    if action.target_id:
        el = _el(snap, action.target_id)
        if el:
            candidates.extend([el.id, el.text, el.href, el.nearby_text])
    if action.text:
        candidates.append(action.text)
    if action.url:
        candidates.append(action.url)

    for c in candidates:
        if not c:
            continue
        if re.search(r"\bshop[ =_-]?b\b", c, re.I):
            return "B"
        if re.search(r"\bshop[ =_-]?a\b", c, re.I):
            return "A"

    u = urlsplit(snap.url)
    qs = parse_qs(u.query)
    if "shop" in qs:
        val = qs["shop"][0].upper()
        if val == "A" or val == "B":
            return val
    if re.search(r"\bshop\s+b\b", snap.title, re.I):
        return "B"
    if re.search(r"\bshop\s+a\b", snap.title, re.I):
        return "A"
    return None


def _el(snap: PageSnapshot, element_id: str | None) -> Element | None:
    return next((e for e in snap.elements if e.id == element_id), None)


def _ambiguous(report: AuditReport) -> str | None:
    """R2 scope: one consent box whose wording leaves its effect uncertain."""
    return next((c.element_id for c in report.checks
                 if c.constraint == "data_allowed" and c.status == "uncertain" and c.element_id),
                None)  # fmt: skip


def _keys(report: AuditReport | None) -> set[str]:
    if report is None:
        return set()
    return {f"{c.constraint}:{c.element_id or c.observed_value}" for c in report.checks
            if c.status == "violation"}  # fmt: skip


def _new_uncertain(new: AuditReport | None, old: AuditReport) -> bool:
    before = {c.constraint for c in old.checks if c.status == "uncertain"}
    return bool(new) and any(c.status == "uncertain" and c.constraint not in before
                             for c in new.checks)  # type: ignore[union-attr]  # fmt: skip


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
