"""Pydantic v2 contracts (brief §5, DEV_PLAN.md §4 C1). The ONLY contract definition (rule 8).

web/lib/api-types.ts is generated from the OpenAPI these models produce; regenerate it in the same
commit as any change here.
"""

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator

# --- Enumerations ---------------------------------------------------------------------------


class SybilDatasetStatus(BaseModel):
    """Readiness is separate from the eventual validated artifact manifest."""

    release: str
    dataset_id: str | None = None
    status: Literal["available", "unavailable"] = "unavailable"
    source_nodes: int
    source_edges: int
    imported_nodes: int = 0
    imported_edges: int = 0
    observation_date: str | None = None
    reason: str
    source_url: str


class SybilLink(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source: str = Field(min_length=1, max_length=128)
    target: str = Field(min_length=1, max_length=128)


class SybilRecommendation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    website: str = Field(min_length=1, max_length=128)
    shop: Literal["A", "B"]


class SybilWeights(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    base: float = Field(default=0.4, ge=0, le=1)
    breadth: float = Field(default=0.2, ge=0, le=1)
    withdrawal: float = Field(default=0.2, ge=0, le=1)
    connection: float = Field(default=0.2, ge=0, le=1)

    @model_validator(mode="after")
    def normalized(self):
        if abs(self.base + self.breadth + self.withdrawal + self.connection - 1) > 1e-12:
            raise ValueError("Score weights must sum to one")
        return self


class SybilScenarioCreate(BaseModel):
    """Complete active edit set relative to a dataset, never an imperative edit history."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    dataset_id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,128}$")
    mode: Literal["challenge", "research"] = "challenge"
    injected_nodes: tuple[str, ...] = Field(default=(), max_length=10000)
    added_links: tuple[SybilLink, ...] = Field(default=(), max_length=150000)
    removed_links: tuple[SybilLink, ...] = Field(default=(), max_length=150000)
    recommendations: tuple[SybilRecommendation, ...] = Field(default=(), max_length=120000)
    removed_recommendations: tuple[SybilRecommendation, ...] = Field(default=(), max_length=120000)
    compromised: tuple[str, ...] = Field(default=(), max_length=10000)
    cooperating_links: tuple[SybilLink, ...] = Field(default=(), max_length=150000)
    anchors: tuple[str, ...] | None = None
    restart: float = Field(default=0.15, gt=0, lt=1)
    weights: SybilWeights = Field(default_factory=SybilWeights)


class SybilBudget(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    injected_websites: int
    internal_links: int
    external_credits: int
    website_limit: int = 1000
    internal_link_limit: int = 100000
    credit_limit: int = 25
    # Challenge prices (brief §14); the web reads these instead of hard-coding them.
    cooperating_link_cost: int = 2
    compromise_cost: int = 5
    anchor_compromise_cost: int = 15


class SybilScenarioRevision(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    id: str
    dataset_id: str
    dataset_hash: str
    edits: SybilScenarioCreate
    budget: SybilBudget
    policy_version: str = "sybil-challenge-v1"


class SybilGenerate(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    count: int = Field(default=100, ge=10, le=1000)
    seed: int = Field(default=1, ge=0, le=2**32 - 1)
    pattern: Literal["dense", "clusters", "hub", "chain", "disconnected"] = "dense"
    density: float = Field(default=0.1, ge=0, le=1)
    target: Literal["A", "B"] = "B"
    bridges: int = Field(default=0, ge=0, le=12)


class SybilExtractionParameters(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    seed: int
    fanout: int = Field(ge=1)
    maximum_depth: int = Field(ge=1)
    node_limit: int = Field(ge=8, le=50000)
    edge_limit: int = Field(ge=1, le=1000000)
    version: Literal["seeded-neighborhood-v1"]


class SybilArtifactNode(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    id: str = Field(pattern=r"^[0-9]+$")
    domain: str = Field(min_length=1, max_length=253)
    original_outdegree: int = Field(ge=0)
    retained_outdegree: int = Field(ge=0)
    depth: int = Field(ge=0)
    x: float
    y: float


class SybilSourceCounts(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    nodes: int = Field(gt=0)
    arcs: int = Field(gt=0)


class SybilArtifactManifest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    id: str = Field(pattern=r"^[a-f0-9]{64}$")
    release: Literal["cc-main-2026-aug-sep-oct"]
    source_counts: SybilSourceCounts
    source_sha256: dict[str, str]
    extraction: SybilExtractionParameters
    nodes: int = Field(ge=8, le=50000)
    edges: int = Field(ge=1, le=1000000)
    anchors: tuple[str, ...] = Field(min_length=8, max_length=8)
    tau: float = Field(gt=0)
    webgraph_commit: str = Field(pattern=r"^[a-f0-9]{40}$")
    webgraph_jar_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    created_at: datetime
    observation_crawls: tuple[str, ...]
    terms: str
    source_url: str
    artifacts: dict[str, str]
    limitations: str


class SybilGraphNode(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    id: str
    label: str
    provenance: Literal["observed", "simulated"]
    anchor: bool = False
    original_outdegree: int = Field(ge=0)
    retained_outdegree: int = Field(ge=0)
    x: float
    y: float


class SybilGraphEdge(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source: str
    target: str
    provenance: Literal["observed", "simulated"]


class SybilGraphView(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    revision_id: str
    total_nodes: int
    total_edges: int
    displayed_nodes: int
    displayed_edges: int
    nodes: tuple[SybilGraphNode, ...]
    edges: tuple[SybilGraphEdge, ...]
    recommendations: tuple[SybilRecommendation, ...]
    subset: bool


class SybilShopScore(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    recommendation_count: int = Field(ge=0)
    trust_weighted_support: float = Field(ge=0)
    structural_support: float = Field(ge=0, le=1)
    effective_anchors: float = Field(ge=0)
    anchor_breadth: float = Field(ge=0, le=1)
    anchor_withdrawal_resilience: float = Field(ge=0, le=1)
    tested_connection_resilience: float = Field(ge=0, le=1)
    total_robustness: float = Field(ge=0, le=100)
    cut_sources: tuple[str, ...] = ()  # outside websites E cut together, highest flow first

    @model_validator(mode="before")
    @classmethod
    def _drop_legacy_tested_edges(cls, data: Any) -> Any:
        # Assessments stored before 16 Nov listed sample links as tested_edges.
        if isinstance(data, dict) and "tested_edges" in data:
            data = {k: v for k, v in data.items() if k != "tested_edges"}
        return data


class SybilAssessmentRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    id: str = Field(pattern=r"^[a-f0-9]{64}$")
    revision_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    status: Literal["queued", "running", "complete", "unavailable"]
    formula_version: Literal["sybil-v1", "sybil-v2"] = "sybil-v2"  # v1 kept so stored replays load
    converged: bool | None = None
    residual: float | None = Field(default=None, ge=0)
    iterations: int | None = Field(default=None, ge=0, le=300)
    elapsed_ms: float | None = Field(default=None, ge=0)
    scores: dict[Literal["A", "B"], SybilShopScore] | None = None
    reason: str | None = None


class SybilScoreDelta(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    trust_weighted_support: float
    structural_support: float
    anchor_breadth: float
    anchor_withdrawal_resilience: float
    tested_connection_resilience: float
    total_robustness: float
    rank: int = Field(ge=-1, le=1)


class SybilCounterfactualResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    baseline_revision_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    counterfactual_revision_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    status: Literal["complete", "unavailable"]
    elapsed_ms: float = Field(ge=0)
    deltas: dict[Literal["A", "B"], SybilScoreDelta] | None = None
    reason: str | None = None


class SybilShopEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    recommendation_count: int = Field(ge=0)
    structural_support: float = Field(ge=0, le=1)
    anchor_breadth: float = Field(ge=0, le=1)
    anchor_withdrawal_resilience: float = Field(ge=0, le=1)
    tested_connection_resilience: float = Field(ge=0, le=1)
    total_robustness: float = Field(ge=0, le=100)
    policy_passed: bool


class SybilGraphEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    revision_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    assessment_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    formula_version: Literal["sybil-v1", "sybil-v2"] = "sybil-v2"  # v1 kept so stored replays load
    # The graph policy (brief §14). L: buying bridges inflates E (and so R) but cannot fake
    # many anchors. policy_passed on each shop is computed from these by passes().
    minimum_total: float = 60
    minimum_support: float = 0.5
    minimum_withdrawal: float = 0.5
    shops: dict[Literal["A", "B"], SybilShopEvidence]
    disclosure: str = (
        "A heuristic measure of structural support and tested sensitivity. "
        "Not a probability that this shop is safe."
    )

    def passes(self, total: float, support: float, withdrawal: float) -> bool:
        return (
            total >= self.minimum_total
            and support >= self.minimum_support
            and withdrawal >= self.minimum_withdrawal
        )

    def policy_text(self) -> str:
        return (
            f"needs R>={self.minimum_total:g}, S>={self.minimum_support:g}, "
            f"L>={self.minimum_withdrawal:g}"
        )


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
    "untrusted_shop",
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
    """What the user asked for. Written once before browsing and frozen: page content never
    edits it."""

    model_config = ConfigDict(frozen=True)

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
    trap_type: TrapType | Literal["guard_unavailable"]  # the latter: D4, a check itself failed
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
    fees: list[CheckoutLine] = []  # charges that are not items (e.g. a handling fee)
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
    shop: str | None = None


# --- R2: disposable consent trials (experimental; never the real session) -------------------


class TrialBranch(BaseModel):
    """One disposable copy of the checkout with the control set one way, ordered to the end."""

    control_checked: bool
    state_matched: bool = False  # the copy reproduced the original checkout before the test
    outcome: Outcome | None = None  # read from the copy's visible confirmation only
    effect: list[str] = []  # commitments present here but not in the other branch
    unauthorized: list[str] = []  # effect items the ledger does not allow
    screenshot_b64: str | None = None  # the copy's confirmation (labelled disposable in the UI)
    disposable_actions: int = 0  # replayed + test actions; not counted as task actions
    error: str | None = None


class TrialReport(BaseModel):
    control_id: str
    control_label: str
    current_checked: bool
    # resolved: exactly one state satisfies the ledger; both_ok: either does; uncertain: neither,
    # or no observable difference to judge; unavailable: reproduction failed, timeout, unsupported
    status: Literal["resolved", "both_ok", "uncertain", "unavailable"]
    recommended_checked: bool | None = None
    branches: list[TrialBranch] = []
    reason: str = ""
    elapsed_ms: int = 0
    original_unchanged: bool | None = None  # the real checkout was identical before and after
    blocked_requests: int = 0


class TwoViewReport(BaseModel):
    """The same checkout loaded in a disposable ordinary-browser context (automation signals
    removed; same engine and network) and compared with what the agent's browser was shown.
    Read-only: nothing is ticked or ordered in the copy."""

    # match: both views show the same commitments; mismatch: they differ (possible AI-targeted
    # cloaking); unavailable: the copy could not be reproduced, timed out or failed
    status: Literal["match", "mismatch", "unavailable"]
    diffs: list[str] = []  # plain sentences, one per commitment-relevant difference
    reason: str = ""
    agent_screenshot_b64: str | None = None  # the real session's checkout
    ordinary_screenshot_b64: str | None = None  # the disposable copy (labelled so in the UI)
    disposable_actions: int = 0  # replayed actions; not counted as task actions
    elapsed_ms: int = 0
    blocked_requests: int = 0


class LabRequest(BaseModel):
    """Trap Lab: a judge writes a checkbox label and secretly picks its real effect. The effect
    only configures the arena page; the trial reads nothing but the rendered copies."""

    label: str = Field(min_length=1, max_length=160)
    effect: Literal["plan", "share", "none"]
    ticked_means_on: bool = True
    starts_ticked: bool = False
    permit_plan: bool = False  # the user allows a care-plan subscription
    permit_sharing: bool = False  # the user allows sharing their email with partners


class ScanRequest(BaseModel):
    """E5: scan one public web page with the fast detectors (read-only, no agent, no clicks)."""

    url: str = Field(min_length=1, max_length=2000)


class ScanReport(BaseModel):
    url: str
    final_url: str  # after redirects
    title: str
    findings: list[Finding] = []
    # Plain hidden/faint text (A1/A3 hidden_info): everywhere on real sites (screen-reader labels,
    # carousels, closed menus), so kept apart. Hidden text that instructs an agent is a B5 finding.
    notes: list[Finding] = []
    flagged: list[Element] = []  # elements the findings point at (bbox for the red boxes)
    element_count: int = 0
    screenshot_b64: str | None = None  # JPEG, 1280x720 viewport, with no boxes drawn
    detector_ms: int = 0  # fast detectors only
    elapsed_ms: int = 0  # whole scan: load, wait, snapshot, detectors, screenshot
    blocked_requests: int = 0  # requests refused by the public-address guard


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


class Neutralization(BaseModel):
    """An INVISIBLE element covering the agent's target that Aegis made click-through before the
    agent's own click ran. Never applied to anything a person can see."""

    element_id: str  # the invisible covering element
    target_id: str  # the control it covered
    bbox: BBox
    evidence: str


class VerdictPayload(BaseModel):
    verdict: Verdict
    action: Action
    audit: AuditReport | None = None
    highlights: list[Highlight] = []
    neutralized: list[Neutralization] = []  # verdict is ALLOW; shown as "overlay neutralized"
    trial: TrialReport | None = None  # R2 evidence behind this verdict, if a trial ran
    two_view: TwoViewReport | None = None  # agent view vs ordinary-browser view, if checked


class ExecutedPayload(BaseModel):
    action: Action
    ok: bool
    url_after: str | None = None
    disposable: bool = False  # true only for R2 trial activity
    defense_retry: bool = False


AskReason = Literal[
    "final_payment",
    "uncertain",
    "retries_exhausted",
    "guard_unavailable",
    "cloaked_checkout",
    "untrusted_shop",
]
AskStatus = Literal["pending", "approved", "denied", "timed_out", "auto_approved_demo"]


class AskPayload(BaseModel):
    ask_id: str
    reason: AskReason
    action: Action | None = None
    findings: list[Finding] = []
    audit: AuditReport | None = None
    trial: TrialReport | None = None
    two_view: TwoViewReport | None = None
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
    consent: Literal["", "r", "o"] = ""  # R2 arena fixture: reversed-meaning consent wording
    shield: Literal["I", "I_R2"] = "I"  # I_R2 = experimental disposable-copy checks
    # Launches only with a frozen Sybil graph revision (from /sybil); hidden from the grid.
    requires_sybil_revision: bool = False


class OwnLLM(BaseModel):
    """A visitor's own key for one run. Provider is a fixed endpoint (no base URL: SSRF)."""

    provider: Literal["gemini", "groq", "openrouter", "cerebras"]  # = llm.BASE_URLS keys
    model: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9._:/@-]+$")
    api_key: SecretStr = Field(min_length=8, max_length=300)


class RunCreate(BaseModel):
    preset_id: str
    auto_approve: bool | None = None  # override; used by deploy/smoke.sh
    llm: OwnLLM | None = None  # in memory for this run only; never stored or echoed
    sybil_revision_id: str | None = None


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
    own_key: bool = False  # visitor's own LLM key: not an eval run
    sybil_revision_id: str | None = None
    # The frozen evidence Aegis judged shops with; replays read this, never a fresh score.
    sybil_graph_evidence: SybilGraphEvidence | None = None


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
