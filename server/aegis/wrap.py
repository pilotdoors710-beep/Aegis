"""E6: drop-in Aegis protection for browser-use 0.13.x agents.

    from aegis.wrap import AegisTools
    agent = Agent(task, llm, tools=AegisTools(task))

Every action browser-use is about to run passes through the same checks as our own loop: fast
detectors (A1-A5, B5), the pre-commit audit against the ledger (B2), and the human gate (D2).
BLOCK/REROUTE come back to the agent as an action error carrying Aegis feedback, so it picks
again; nothing is executed that the agent did not propose.

Scope, stated plainly:
- browser-use 0.13.x only. 1.0+ has no discrete actions (the model writes Python against raw
  CDP), so there is no action boundary to gate.
- `evaluate` (arbitrary page JS) and `upload_file` are removed: both bypass any action check.
- Actions are checked; browser-use's own page view is not sanitized (our B5/C1 view filtering
  lives in agent.py and does not reach its prompt).
- browser-use 0.13.14 pins versions our server lock can't share, so run it in its own env:
    cd server && PYTHONPATH=. uv run --isolated --no-project --with browser-use==0.13.14 \\
      --with playwright==1.65.0 --with 'psycopg[binary]' python ../eval/browser_use_demo.py
  (playwright pinned to the server's version so its downloaded Chromium is found)
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from typing import Any
from urllib.parse import urlsplit

from browser_use import Tools
from browser_use.agent.views import ActionResult

from aegis.audit import is_irreversible
from aegis.intent import parse_ledger
from aegis.llm import LLMRouter
from aegis.loop import _audit, _audit_feedback, _commit_decision, _el, _keys, _new_uncertain
from aegis.schemas import Action, AskPayload, Ledger, PageSnapshot, Verdict
from aegis.snapshot import _script
from aegis.trials import diff_states
from aegis.verdict import (
    GUARD,
    MAX_RETRIES,
    agent_feedback,
    blocking_findings,
    check_fast,
    combine,
    plan_neutralization,
)

Approver = Callable[[AskPayload], Awaitable[bool]]
REMOVED = ("evaluate", "upload_file")
_ID_OF = "function () { const el = this.closest ? this.closest('[data-cs-id]') : null; " \
         "return el ? el.dataset.csId : null; }"  # fmt: skip
_NEUTRALIZE = """(id => { const el = document.querySelector(`[data-cs-id="${id}"]`);
  if (!el) return false; el.style.setProperty("pointer-events", "none", "important");
  return true; })"""


class AegisTools(Tools):
    """browser-use Tools whose act() runs Aegis before every action.

    approve: async callback for ASK verdicts (final payment, uncertain audit, broken check).
    None denies every ask (fail closed). ledger: skip the LLM parse (tests, fixed demos).
    """

    def __init__(
        self,
        task: str,
        *,
        ledger: Ledger | None = None,
        approve: Approver | None = None,
        router: LLMRouter | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        for name in REMOVED:
            self.exclude_action(name)
        self.task, self.ledger, self.approve, self.router = task, ledger, approve, router
        self.log: list[tuple[Action, Verdict]] = []  # every checked action and its verdict
        self._step = 0
        self._blocked = 0  # consecutive stopped actions (D1: max 3 retries)
        self._last_audit: tuple[int, set[str]] | None = None
        self._committed = False  # an approved commitment ran: like our loop, the run ends there

    async def act(self, action: Any, browser_session: Any, **kwargs: Any) -> ActionResult:
        name, params = next(
            (k, v) for k, v in action.model_dump(exclude_unset=True).items() if v is not None
        )
        cdp = await browser_session.get_or_create_cdp_session()
        snap = await _snapshot(cdp)
        ours = await _translate(name, params, browser_session, cdp)
        if ours is None:  # scroll, wait, extract, tabs, done...: nothing to commit to
            return await super().act(action, browser_session, **kwargs)
        if self._committed:  # an agent that keeps going after paying could pay twice
            return _end("An approved commitment already ran in this run; Aegis ends it here.")
        if (stop := await self._ensure_ledger(snap)) is not None:
            return stop
        assert self.ledger is not None
        self._step += 1

        findings, ms = await check_fast(snap, ours, self.ledger)
        fix = plan_neutralization(snap, ours)
        verdict = combine(findings, ours, ms, fix)
        report, ask_reason = None, None
        if any(f.detector == GUARD for f in blocking_findings(findings, ours)):
            ask_reason = "guard_unavailable"
            verdict = verdict.model_copy(update={"decision": "ASK"})
        elif verdict.decision == "ALLOW" and is_irreversible(_el(snap, ours.target_id), ours.type):
            report, guard = await _audit(snap, self.ledger, ours, self._last_audit)
            if guard:
                findings.append(guard)
            verdict, ask_reason, self._last_audit = _commit_decision(
                verdict, report, self._step, self._last_audit, findings
            )
        self.log.append((ours, verdict))

        if verdict.decision == "ALLOW":
            self._blocked = 0
            if fix:  # invisible click-jacking cover: make it click-through, then run the click
                await _eval(cdp, f"{_NEUTRALIZE}({fix.element_id!r})")
            return await super().act(action, browser_session, **kwargs)

        if ask_reason:
            ask = AskPayload(ask_id=f"ask-{uuid.uuid4().hex[:8]}", reason=ask_reason,
                             action=ours, findings=verdict.findings, audit=report,
                             status="pending")  # fmt: skip
            if not await self._ask(ask):
                return _end("The user denied this action. Stop without retrying.")
            if report is not None:  # consent binding: the approval covers exactly what was shown
                now = await _snapshot(cdp)
                again, guard = await _audit(now, self.ledger, ours, (self._step, set()))
                changed = diff_states(report.observed, again.observed, "when approved", "now") \
                    if again else []  # fmt: skip
                new_issue = _keys(again) - _keys(report) or _new_uncertain(again, report)
                if guard or changed or new_issue:
                    return ActionResult(error=_audit_feedback(ours, again, changed=True))
            self._blocked = 0
            result = await super().act(action, browser_session, **kwargs)
            self._committed = not result.error
            return result

        self._blocked += 1
        if self._blocked > MAX_RETRIES:
            # shortcut: ends the run instead of asking first (our loop's approved
            # retries_exhausted ask ends the side too); add an ask if a UI needs to show it.
            return _end(f"Aegis stopped {self._blocked} unsafe attempts in a row. Stop.")
        audit_reroute = report is not None and not blocking_findings(findings, ours, fix)
        feedback = _audit_feedback(ours, report) if audit_reroute else agent_feedback(verdict, ours)
        return ActionResult(error=feedback)

    async def _ensure_ledger(self, snap: PageSnapshot) -> ActionResult | None:
        """B1 once, on the first checked action: the ledger is fixed before anything commits."""
        if self.ledger is not None:
            return None
        host = urlsplit(snap.url).hostname or ""
        self.ledger, unresolved = await parse_ledger(
            self.task, self.router or LLMRouter(), allowed_domains=[host]
        )
        if unresolved and not await self._ask(
            AskPayload(ask_id="ask-ledger", reason="uncertain", status="pending")
        ):
            return _end("The request is unclear and the user did not confirm it: "
                        + "; ".join(unresolved))  # fmt: skip
        return None

    async def _ask(self, ask: AskPayload) -> bool:
        return bool(self.approve and await self.approve(ask))


def _end(text: str) -> ActionResult:
    return ActionResult(is_done=True, success=False, extracted_content=f"AEGIS: {text}")


async def _eval(cdp: Any, expression: str) -> Any:
    res = await cdp.cdp_client.send.Runtime.evaluate(
        params={"expression": expression, "returnByValue": True, "awaitPromise": True},
        session_id=cdp.session_id,
    )
    if res.get("exceptionDetails"):
        raise RuntimeError(f"Aegis page script failed: {res['exceptionDetails'].get('text')}")
    return res.get("result", {}).get("value")


async def _snapshot(cdp: Any) -> PageSnapshot:
    raw = await _eval(cdp, f"({_script()})()")
    if raw is None:
        raise RuntimeError("page still loading")  # caught by browser-use as an action error
    return PageSnapshot.model_validate(raw)


async def _cs_id(cdp: Any, backend_node_id: int) -> str | None:
    """browser-use index -> node -> nearest element our snapshot stamped."""
    obj = await cdp.cdp_client.send.DOM.resolveNode(
        params={"backendNodeId": backend_node_id}, session_id=cdp.session_id
    )
    res = await cdp.cdp_client.send.Runtime.callFunctionOn(
        params={"functionDeclaration": _ID_OF, "objectId": obj["object"]["objectId"],
                "returnByValue": True},
        session_id=cdp.session_id,
    )  # fmt: skip
    return res.get("result", {}).get("value")


async def _translate(name: str, params: dict, session: Any, cdp: Any) -> Action | None:
    """browser-use action -> our Action schema; None for actions with no page effect to check."""
    why = "browser-use action"

    async def target(index: int | None) -> str | None:
        node = await session.get_element_by_index(index) if index else None
        return await _cs_id(cdp, node.backend_node_id) if node else None

    if name == "click":
        if params.get("index"):
            tid = await target(params["index"])
        else:  # coordinate click: whatever is on top at that point
            from browser_use.tools.service import _convert_llm_coordinates_to_viewport

            x, y = _convert_llm_coordinates_to_viewport(
                params["coordinate_x"], params["coordinate_y"], session
            )
            tid = await _eval(cdp, f"(document.elementFromPoint({x},{y})?.closest('[data-cs-id]')"
                                   "?.dataset.csId) ?? null")  # fmt: skip
        return Action(type="click", target_id=tid, rationale=why)
    if name == "input":
        return Action(type="type", target_id=await target(params.get("index")),
                      text=params.get("text"), rationale=why)  # fmt: skip
    if name == "select_dropdown":
        return Action(type="select", target_id=await target(params.get("index")),
                      text=params.get("text"), rationale=why)  # fmt: skip
    if name == "navigate":
        return Action(type="navigate", url=params.get("url"), rationale=why)
    if name == "send_keys" and "enter" in str(params.get("keys", "")).lower():
        tid = await _eval(
            cdp, "document.activeElement?.closest('[data-cs-id]')?.dataset.csId ?? null"
        )
        return Action(type="submit", target_id=tid, rationale=why)
    return None
