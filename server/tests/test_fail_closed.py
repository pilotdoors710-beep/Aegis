import statistics
import time

from playwright.async_api import Page

from aegis.schemas import Action, Finding, PageSnapshot
from aegis.verdict import check_fast, combine
from tests.detectors.helpers import CART, by_text, click, snap_at

SNAP = PageSnapshot(url="https://x/", title="t", elements=[])


def boom(*_: object) -> list[Finding]:
    raise RuntimeError("detector bug")


def slow(*_: object) -> list[Finding]:
    time.sleep(1.0)
    return []


def fine(*_: object) -> list[Finding]:
    return []


async def test_raising_and_sleeping_detectors_fail_closed() -> None:
    for bad in (boom, slow):
        for action in (click("e1"), Action(type="navigate", url="https://x/")):
            findings, _ = await check_fast(SNAP, action, None, [fine, bad], mode="closed")
            (g,) = findings
            assert g.trap_type == "guard_unavailable" and g.severity == "high"
            assert ("timed out" if bad is slow else "detector bug") in g.evidence
            assert combine(findings, action, 1).decision == "BLOCK"


async def test_fail_open_logs_but_allows() -> None:
    findings, _ = await check_fast(SNAP, click("e1"), None, [boom], mode="open")
    assert [f.severity for f in findings] == ["low"] and "FAIL_MODE=open" in findings[0].evidence
    assert combine(findings, click("e1"), 1).decision == "ALLOW"


async def test_guarded_fast_detectors_median_under_150ms(page: Page, arena_url: str) -> None:
    snap = await snap_at(page, f"{arena_url}/checkout.html?traps=T03,T04&{CART}")
    action = click(by_text(snap, "Place order").id)
    times = [(await check_fast(snap, action, None))[1] for _ in range(30)]
    assert statistics.median(times) < 150
