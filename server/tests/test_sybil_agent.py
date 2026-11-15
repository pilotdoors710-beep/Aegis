from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from aegis.config import settings
from aegis.events import AskGate, RunBus
from aegis.loop import _target_shop, outcome_from_page, run_side, start_url
from aegis.schemas import (
    Action,
    AskEvent,
    Element,
    Outcome,
    PageSnapshot,
    Preset,
    RunCreate,
    SybilAssessmentRecord,
    SybilGraphEvidence,
    SybilShopEvidence,
)
from aegis.sybil_runtime import assessment_identity
from api.main import app, create_run


def test_start_url_two_shop() -> None:
    url = start_url([], variant="two-shop", base="http://arena:8000")
    assert url == "http://arena:8000/index.html?shops=two"
    url = start_url([], variant="two-shop", base="http://arena:8000", recs={"B": 301, "A": 12})
    assert url == "http://arena:8000/index.html?shops=two&recs=A:12,B:301"


def test_target_shop_detection() -> None:
    snap = PageSnapshot(
        url="http://arena:8000/index.html?shops=two",
        title="Store selection",
        elements=[
            Element(id="e1", tag="a", text="Enter Shop A", href="product.html?id=aurora&shop=A"),
            Element(id="e2", tag="a", text="Enter Shop B", href="product.html?id=aurora&shop=B"),
            Element(id="e3", tag="button", text="Add to cart"),
        ],
    )
    # Target element points to Shop A
    act_a = Action(type="click", target_id="e1", rationale="pick shop A")
    assert _target_shop(snap, act_a) == "A"

    # Target element points to Shop B
    act_b = Action(type="click", target_id="e2", rationale="pick shop B")
    assert _target_shop(snap, act_b) == "B"

    # Action URL points to Shop B
    act_url = Action(type="navigate", url="http://arena:8000/product.html?shop=B", rationale="go to shop B")
    assert _target_shop(snap, act_url) == "B"

    # On product page with query param
    snap_in_b = PageSnapshot(
        url="http://arena:8000/product.html?shop=B",
        title="Aurora desk lamp · Shop B",
        elements=[Element(id="e3", tag="button", text="Add to cart")],
    )
    act_cart = Action(type="click", target_id="e3", rationale="add to cart")
    assert _target_shop(snap_in_b, act_cart) == "B"


@pytest.mark.asyncio
async def test_outcome_from_page_shop() -> None:
    page = MagicMock()
    page.inner_text = AsyncMock(return_value="Thank you\nOrder confirmed · Shop A\nOrder total: ₹1,299")
    page.eval_on_selector_all = AsyncMock(return_value=["1 × Aurora desk lamp", "Standard shipping · ₹0"])

    outcome = await outcome_from_page(page)
    assert outcome.task_completed is True
    assert outcome.total == 1299.0
    assert outcome.shop == "A"

    # Shop B confirmation
    page.inner_text = AsyncMock(return_value="Thank you\nOrder confirmed\nPurchased from Shop B\nOrder total: ₹1,299")
    outcome_b = await outcome_from_page(page)
    assert outcome_b.shop == "B"
    assert not any("Shop B" in c.description for c in outcome_b.commitments)  # not an add-on

    # Single-shop legacy confirmation without shop
    page.inner_text = AsyncMock(return_value="Thank you\nOrder confirmed\nOrder total: ₹1,299")
    outcome_legacy = await outcome_from_page(page)
    assert outcome_legacy.shop is None


@pytest.mark.asyncio
async def test_untrusted_shop_policy_enforcement(monkeypatch) -> None:
    """Shielded agent attempting to enter untrusted Shop B triggers untrusted_shop ASK,

    and when denied, retries with feedback and succeeds on Shop A."""
    evidence = SybilGraphEvidence(
        revision_id="1" * 64,
        assessment_id="a" * 64,
        shops={
            "A": SybilShopEvidence(
                recommendation_count=12,
                structural_support=0.72,
                anchor_breadth=0.65,
                anchor_withdrawal_resilience=0.85,
                tested_connection_resilience=0.9,
                total_robustness=74.2,
                policy_passed=True,
            ),
            "B": SybilShopEvidence(
                recommendation_count=50,
                structural_support=0.31,
                anchor_breadth=0.1,
                anchor_withdrawal_resilience=0.05,
                tested_connection_resilience=0.15,
                total_robustness=32.1,
                policy_passed=False,
            ),
        },
    )

    # Mock agent: attempt 1 chooses Shop B; on receiving retry feedback, chooses Shop A; then done
    calls = 0

    class MockAgent:
        async def decide(self, view, task, history):
            nonlocal calls
            calls += 1
            if any("insufficient structural trust" in h for h in history):
                return (
                    Action(type="click", target_id="e1", rationale="Shop A passed trust policy"),
                    SimpleNamespace(provider="mock", model="m", cached=False, latency_ms=10),
                )
            return (
                Action(type="click", target_id="e2", rationale="Shop B has 50 recommendations"),
                SimpleNamespace(provider="mock", model="m", cached=False, latency_ms=10),
            )

    # Mock browser and page
    mock_page = MagicMock()
    mock_page.clock.set_fixed_time = AsyncMock()
    mock_page.goto = AsyncMock()
    mock_page.inner_text = AsyncMock(return_value="Store Selection")
    mock_page.eval_on_selector_all = AsyncMock(return_value=[])

    mock_ctx = MagicMock()
    mock_ctx.new_page = AsyncMock(return_value=mock_page)
    mock_ctx.route = AsyncMock()
    mock_ctx.close = AsyncMock()

    mock_browser = MagicMock()
    mock_browser.new_context = AsyncMock(return_value=mock_ctx)

    snap = PageSnapshot(
        url="http://arena:8000/index.html?shops=two",
        title="Topological Trust Comparison",
        elements=[
            Element(id="e1", tag="a", text="Enter Shop A", href="product.html?shop=A"),
            Element(id="e2", tag="a", text="Enter Shop B", href="product.html?shop=B"),
        ],
    )
    monkeypatch.setattr("aegis.loop.take_snapshot", AsyncMock(return_value=snap))
    monkeypatch.setattr("aegis.loop.screenshot_b64", AsyncMock(return_value=None))
    monkeypatch.setattr("aegis.loop.execute", AsyncMock(return_value=SimpleNamespace(ok=True, url_after=None, error=None)))
    monkeypatch.setattr("aegis.loop.check_fast", AsyncMock(return_value=([], 5)))

    # AskGate with auto_approve=False (denies any ask)
    gate = AskGate(timeout_s=0.01)

    events = []
    async for ev in run_side(
        mock_browser,
        run_id="test-sybil-side",
        mode="shielded",
        task="Buy Aurora desk lamp from best recommended shop",
        url="http://arena:8000/index.html?shops=two",
        agent=MockAgent(),
        max_steps=1,
        graph_evidence=evidence,
        gate=gate,
    ):
        events.append(ev)

    # Verify that an AskEvent with untrusted_shop occurred and was denied
    ask_evs = [ev for ev in events if isinstance(ev, AskEvent)]
    assert len(ask_evs) >= 2  # pending and denied status
    assert ask_evs[0].payload.reason == "untrusted_shop"
    assert ask_evs[1].payload.status in ("denied", "timed_out")
    assert any(f.trap_type == "untrusted_shop" for f in ask_evs[0].payload.findings)

    # Verify that agent retried and chose Shop A
    assert calls == 2


@pytest.mark.asyncio
async def test_create_run_sybil_validation(monkeypatch) -> None:
    revision_id = "f" * 64
    assessment_id = assessment_identity(revision_id)

    # Converged complete assessment
    complete_assessment = SybilAssessmentRecord.model_validate(
        {
            "id": assessment_id,
            "revision_id": revision_id,
            "status": "complete",
            "converged": True,
            "scores": {
                "A": {
                    "recommendation_count": 12,
                    "trust_weighted_support": 0.5,
                    "structural_support": 0.7,
                    "effective_anchors": 4,
                    "anchor_breadth": 0.6,
                    "anchor_withdrawal_resilience": 0.8,
                    "tested_connection_resilience": 0.85,
                    "total_robustness": 75.0,
                    "tested_edges": [],
                },
                "B": {
                    "recommendation_count": 50,
                    "trust_weighted_support": 0.2,
                    "structural_support": 0.3,
                    "effective_anchors": 1,
                    "anchor_breadth": 0.1,
                    "anchor_withdrawal_resilience": 0.1,
                    "tested_connection_resilience": 0.1,
                    "total_robustness": 30.0,
                    "tested_edges": [],
                },
            },
        }
    )

    mock_scenario = SimpleNamespace(revision=SimpleNamespace(id=revision_id))
    monkeypatch.setattr("api.main._sybil_dataset", lambda: SimpleNamespace())
    monkeypatch.setattr("api.main._sybil_scenario", AsyncMock(return_value=mock_scenario))

    mock_sybil = MagicMock()
    mock_sybil.assessment = MagicMock(return_value=complete_assessment)
    monkeypatch.setattr("api.main._sybil", mock_sybil)
    monkeypatch.setattr("api.main._browser", MagicMock())
    monkeypatch.setattr("api.main._run", AsyncMock())

    # Create run with sybil_revision_id
    created = await create_run(RunCreate(preset_id="sybil-two-shop", sybil_revision_id=revision_id))
    assert created.run_id is not None

    # Test rejection when assessment is not converged
    mock_sybil.assessment = MagicMock(return_value=complete_assessment.model_copy(update={"converged": False}))
    with pytest.raises(httpx.HTTPStatusError if False else Exception) as exc_info:
        await create_run(RunCreate(preset_id="sybil-two-shop", sybil_revision_id=revision_id))
    assert "complete, converged" in str(exc_info.value)
