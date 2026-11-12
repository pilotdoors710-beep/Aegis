import asyncio

import httpx

import api.main as main
from aegis.events import AskGate, RunBus
from aegis.schemas import AskPayload
from tests.test_store import _summary


def _pending(ask_id: str = "a1") -> AskPayload:
    return AskPayload(ask_id=ask_id, reason="final_payment", status="pending")


async def _decide(gate: AskGate, decision: str | None) -> str:
    gate.open(_pending())
    waiter = asyncio.create_task(gate.wait("a1"))
    await asyncio.sleep(0)
    if decision:
        resolved = gate.resolve("a1", decision)  # type: ignore[arg-type]
        assert resolved is not None
        assert resolved.status == {"approve": "approved", "deny": "denied"}[decision]
    return await waiter


async def test_approve_deny_timeout() -> None:
    assert await _decide(AskGate(timeout_s=5), "approve") == "approved"
    assert await _decide(AskGate(timeout_s=5), "deny") == "denied"
    assert await _decide(AskGate(timeout_s=0.01), None) == "timed_out"


async def test_auto_approve_is_labelled_demo() -> None:
    assert await _decide(AskGate(auto_approve=True), None) == "auto_approved_demo"


async def test_resolve_twice_or_unknown_fails() -> None:
    gate = AskGate(timeout_s=5)
    gate.open(_pending())
    assert gate.resolve("a1", "approve") is not None
    assert gate.resolve("a1", "deny") is None
    assert gate.resolve("nope", "approve") is None


async def test_route_resolves_and_404s() -> None:
    bus = RunBus()
    gate = AskGate(timeout_s=5)
    await bus.create(_summary(), gate)
    gate.open(_pending())
    main._bus = bus
    try:
        t = httpx.ASGITransport(app=main.app)
        async with httpx.AsyncClient(transport=t, base_url="http://t") as c:
            r = await c.post("/runs/r1/ask/a1", json={"decision": "deny"})
            assert r.status_code == 200 and r.json()["status"] == "denied"
            assert (await c.post("/runs/r1/ask/zz", json={"decision": "deny"})).status_code == 404
            assert (await c.post("/runs/nope/ask/a1", json={"decision": "deny"})).status_code == 404
    finally:
        main._bus = RunBus()
