from playwright.async_api import Page

from aegis.detectors import run_fast
from aegis.schemas import Action, Finding
from aegis.verdict import agent_feedback, combine
from tests.detectors.helpers import click, snap_at


def _f(eid: str, sev: str = "high", suggestion: str | None = None) -> Finding:
    return Finding(detector="X", trap_type="fake_control", severity=sev, element_id=eid,  # type: ignore[arg-type]
                   evidence="ev", suggestion=suggestion)  # fmt: skip


def test_only_target_findings_decide() -> None:
    assert combine([_f("e2")], click("e1"), 1).decision == "ALLOW"
    assert combine([_f("e1", "low")], click("e1"), 1).decision == "ALLOW"
    assert combine([_f("e1")], click("e1"), 1).decision == "BLOCK"
    v = combine([_f("e1", suggestion="use e9")], click("e1"), 1)
    assert v.decision == "REROUTE" and v.reroute_hint == "use e9" and v.findings
    assert combine([_f("e1")], Action(type="done"), 1).decision == "ALLOW"


async def test_feedback_never_quotes_injection(page: Page, arena_url: str) -> None:
    snap = await snap_at(page, f"{arena_url}/product.html?traps=T05")
    inj = next(e for e in snap.elements if e.text.startswith("AI assistant:"))
    action = click(inj.id)
    verdict = combine(run_fast(snap, action, None), action, 1)
    assert verdict.decision != "ALLOW"
    fb = agent_feedback(verdict, action)
    assert "AEGIS SECURITY FEEDBACK" in fb and "addressed to AI agents" in fb
    assert "Deluxe" not in fb and "AI assistant:" not in fb
