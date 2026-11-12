"""Pydantic v2 contracts (brief §5, DEV_PLAN.md §4 C1). The ONLY contract definition (rule 8).

web/lib/api-types.ts is generated from the OpenAPI these models produce; regenerate it in the same
commit as any change here.
"""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field

# --- Enumerations ---------------------------------------------------------------------------

TrapType = Literal[
    "hidden_info",
    "preselection",
    "trick_wording",
    "obstruction",
    "urgency",
    "social_proof",
    "disguised_ad",
    "fake_control",
    "clickjacking",
    "prompt_injection",
    "forced_action",
]
Severity = Literal["low", "medium", "high"]
Decision = Literal["ALLOW", "BLOCK", "REROUTE", "ASK"]
Mode = Literal["shielded", "unshielded"]
EventKind = Literal["snapshot", "decision", "verdict", "executed", "ask", "error", "done"]
ActionType = Literal["click", "type", "select", "navigate", "submit", "done"]
BBox = tuple[float, float, float, float]  # x, y, w, h in viewport CSS pixels (1280x720)

# --- Brief §5 core --------------------------------------------------------------------------


class Action(BaseModel):
    type: ActionType
    target_id: str | None = None
    text: str | None = None
    url: str | None = None
    rationale: str = ""


class Element(BaseModel):
    id: str
    tag: str
    role: str | None = None
    text: str = ""
    nearby_text: str = ""
    href: str | None = None
    download: bool = False
    onclick: bool = False
    bbox: BBox = (0, 0, 0, 0)
    visible: bool = True
    opacity: float = 1.0
    contrast_ratio: float | None = None
    occluded_by: str | None = None
    checked: bool | None = None
    value: str | None = None


class PageSnapshot(BaseModel):
    url: str
    title: str
    elements: list[Element]
    viewport: tuple[int, int] = (1280, 720)


class LedgerItem(BaseModel):
    name: str
    qty: int = 1
    max_price: float | None = None


class Ledger(BaseModel):
    """What the user asked for. Written once before browsing; page content never edits it."""

    goal: str
    items: list[LedgerItem] = []
    budget_max: float | None = None
    allow_addons: bool = False
    allow_subscriptions: bool = False
    allowed_domains: list[str] = []
    data_allowed: list[str] = []
    # DEV_PLAN Q14: null = the task states no shipping preference.
    shipping_method: Literal["standard", "express"] | None = None


class Finding(BaseModel):
    detector: str
    trap_type: TrapType
    severity: Severity
    element_id: str | None = None
    evidence: str
    suggestion: str | None = None


class Verdict(BaseModel):
    decision: Decision
    findings: list[Finding] = []
    reroute_hint: str | None = None
    latency_ms: int = 0


# --- Audit (B2) -----------------------------------------------------------------------------


class AuditCheck(BaseModel):
    constraint: str  # e.g. "allow_subscriptions", "budget_max", "items[0]"
    kind: Literal["authorization", "fulfillment"]
    ledger_value: str
    observed_value: str
    evidence: str
    element_id: str | None = None
    status: Literal["ok", "permitted", "violation", "uncertain"]


class CheckoutLine(BaseModel):
    name: str
    qty: int = 1
    amount: float | None = None
    element_id: str | None = None


class TickedOption(BaseModel):
    label: str
    checked: bool
    element_id: str | None = None


class RecurringTerm(BaseModel):
    description: str
    amount: float | None = None
    period: str | None = None  # "month" | "year" | free text
    element_id: str | None = None


class DataSharing(BaseModel):
    description: str
    categories: list[str] = []
    element_id: str | None = None


class ShippingObservation(BaseModel):
    method: Literal["standard", "express"] | None = None
    cost: float | None = None
    evidence: str = ""
    element_id: str | None = None


class CheckoutState(BaseModel):
    lines: list[CheckoutLine] = []
    ticked_options: list[TickedOption] = []
    total: float | None = None
    recurring_terms: list[RecurringTerm] = []
    data_sharing: list[DataSharing] = []
    shipping: ShippingObservation | None = None


class AuditReport(BaseModel):
    checks: list[AuditCheck]
    observed: CheckoutState
    recheck_of: int | None = None  # step of the audit this one re-verifies


# --- Outcomes -------------------------------------------------------------------------------


class Commitment(BaseModel):
    kind: Literal["item", "addon", "subscription", "fee", "data_sharing", "download"]
    description: str
    amount: float | None = None
    period: str | None = None
    state: Literal["proposed", "approved", "executed"]


class Outcome(BaseModel):
    task_completed: bool | None = None
    total: float | None = None
    commitments: list[Commitment] = []


# --- Event payloads (typed per kind, behind the brief's envelope) ---------------------------


class RemovedText(BaseModel):
    reason: str  # "B5_quarantine" | "C1_persuasion" | ...
    text: str


class Highlight(BaseModel):
    element_id: str
    bbox: BBox
    label: str
    severity: Severity


class SnapshotPayload(BaseModel):
    url: str
    title: str
    screenshot_b64: str | None = None  # live only: JPEG, 1280x720
    screenshot_url: str | None = None  # set once persisted
    element_count: int
    removed: list[RemovedText] = []  # always empty on the unshielded side


class DecisionPayload(BaseModel):
    action: Action
    provider: str
    model: str
    cached: bool
    llm_latency_ms: int
    attempt: int = 1  # 2+ = retry after BLOCK/REROUTE


class VerdictPayload(BaseModel):
    verdict: Verdict
    action: Action
    audit: AuditReport | None = None
    highlights: list[Highlight] = []


class ExecutedPayload(BaseModel):
    action: Action
    ok: bool
    url_after: str | None = None
    disposable: bool = False  # true only for R2 trial activity
    defense_retry: bool = False


AskReason = Literal["final_payment", "uncertain", "retries_exhausted", "guard_unavailable"]
AskStatus = Literal["pending", "approved", "denied", "timed_out", "auto_approved_demo"]


class AskPayload(BaseModel):
    ask_id: str
    reason: AskReason
    action: Action | None = None
    findings: list[Finding] = []
    audit: AuditReport | None = None
    status: AskStatus


class ErrorPayload(BaseModel):
    code: str
    message: str
    recoverable: bool


class DonePayload(BaseModel):
    reason: Literal["completed", "max_steps", "denied", "aborted", "error"]
    outcome: Outcome


class _EventBase(BaseModel):
    run_id: str
    step: int
    mode: Mode
    ts: datetime


class SnapshotEvent(_EventBase):
    kind: Literal["snapshot"] = "snapshot"
    payload: SnapshotPayload


class DecisionEvent(_EventBase):
    kind: Literal["decision"] = "decision"
    payload: DecisionPayload


class VerdictEvent(_EventBase):
    kind: Literal["verdict"] = "verdict"
    payload: VerdictPayload


class ExecutedEvent(_EventBase):
    kind: Literal["executed"] = "executed"
    payload: ExecutedPayload


class AskEvent(_EventBase):
    kind: Literal["ask"] = "ask"
    payload: AskPayload


class ErrorEvent(_EventBase):
    kind: Literal["error"] = "error"
    payload: ErrorPayload


class DoneEvent(_EventBase):
    kind: Literal["done"] = "done"
    payload: DonePayload


_AnyEvent = (
    SnapshotEvent | DecisionEvent | VerdictEvent | ExecutedEvent | AskEvent | ErrorEvent | DoneEvent
)
Event = Annotated[_AnyEvent, Field(discriminator="kind")]

# --- REST -----------------------------------------------------------------------------------


class Preset(BaseModel):
    id: str
    title: str
    description: str
    task: str
    traps: list[str]  # ["none"] or ["T01", ...]
    variant: str = "a"
    auto_approve: bool = False  # labelled demo approval, never fresh human consent
    pair_of: str | None = None  # links an R1 authorized/forbidden pair


class RunCreate(BaseModel):
    preset_id: str
    auto_approve: bool | None = None  # override; used by deploy/smoke.sh


RunStatus = Literal["queued", "running", "done", "error"]


class RunCreated(BaseModel):
    run_id: str
    status: RunStatus
    queue_position: int = 0


class SideOutcomes(BaseModel):
    unshielded: Outcome | None = None
    shielded: Outcome | None = None


class RunSummary(BaseModel):
    """Also sent as the SSE transport frame `event: run` (not an Event)."""

    run_id: str
    preset_id: str
    task: str
    status: RunStatus
    created_at: datetime
    ledger: Ledger | None = None
    outcomes: SideOutcomes = SideOutcomes()
    model: str | None = None
    is_sample: bool = False


class AskDecision(BaseModel):
    decision: Literal["approve", "deny"]


class Count(BaseModel):
    count: int
    of: int


class ConfigStats(BaseModel):
    config: Literal["U", "F", "I", "I-minus-audit", "I+R2"]
    runs: int
    trap_success: Count
    task_success: Count
    safe_task_completion: Count
    unauthorized_commitments: Count
    clean_false_block: Count
    unnecessary_ask: Count
    authorized_option_rejection: Count
    expected_final_approvals: int
    uncertainty_escalations: int
    denials: int
    fast_detector_ms_median: float | None = None
    audit_ms_median: float | None = None
    shield_added_ms_median: float | None = None
    run_duration_s_median: float | None = None


class EvalStats(BaseModel):
    label: Literal["sample", "pilot", "final"]
    generated_at: datetime
    model: str | None
    n: int
    configs: list[ConfigStats]


class HealthLLM(BaseModel):
    provider: str
    model: str
    latency_ms: int


class HealthArena(BaseModel):
    url: str
    title: str
