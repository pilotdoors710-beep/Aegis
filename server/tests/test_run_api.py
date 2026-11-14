import asyncio
import json
from collections.abc import AsyncIterator

import httpx
import pytest
from playwright.async_api import async_playwright

import api.main as main
from aegis.config import settings
from aegis.events import RunBus
from aegis.schemas import Ledger, LedgerItem
from tests.scripted_agent import ScriptedAgent, click_text


def _clean_purchase(_router: object = None) -> ScriptedAgent:
    return ScriptedAgent([
        click_text("Aurora desk lamp"), click_text("Add to cart"),
        click_text("Continue"), click_text("Place order"),
    ])  # fmt: skip


@pytest.fixture
async def client(
    arena_url: str, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[httpx.AsyncClient]:
    monkeypatch.setattr(settings, "arena_base_url", arena_url)
    monkeypatch.setattr(main, "agent_factory", _clean_purchase)
    monkeypatch.setattr(main, "ledger_parser", _ledger)
    monkeypatch.setattr(main, "_bus", RunBus())
    monkeypatch.setattr(main, "_run_slots", None)
    async with async_playwright() as pw:
        main._browser = await pw.chromium.launch()
        transport = httpx.ASGITransport(app=main.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
            yield c
        for t in list(main._tasks):
            t.cancel()
        await asyncio.gather(*main._tasks, return_exceptions=True)
        await main._browser.close()
        main._browser = None


async def _ledger(task: str, _router: object = None) -> tuple[Ledger, list[str]]:
    return Ledger(goal=task, items=[LedgerItem(name="Aurora desk lamp")], budget_max=1500,
                  shipping_method="standard"), []  # fmt: skip


def _frames(body: str) -> list[dict[str, str]]:
    out = []
    for block in body.replace("\r\n", "\n").split("\n\n"):
        f = dict(line.split(": ", 1) for line in block.splitlines() if ": " in line)
        if "event" in f:
            out.append(f)
    return out


async def test_paired_run_streams_and_queues(client: httpx.AsyncClient) -> None:
    first = (await client.post("/runs", json={"preset_id": "clean", "auto_approve": True})).json()
    assert first["status"] == "running" and first["queue_position"] == 0
    second = (await client.post("/runs", json={"preset_id": "clean", "auto_approve": True})).json()
    assert second["status"] == "queued" and second["queue_position"] == 1

    run_id = first["run_id"]
    frames = _frames((await client.get(f"/runs/{run_id}/stream")).text)
    assert frames[0]["event"] == "run"
    ids = [int(f["id"]) for f in frames if "id" in f]
    assert ids == sorted(ids) and len(ids) == len(set(ids))
    events = [json.loads(f["data"]) for f in frames if f["event"] not in ("run",)]
    dones = [e for e in events if e["kind"] == "done"]
    assert {d["mode"] for d in dones} == {"unshielded", "shielded"}
    uns = next(d for d in dones if d["mode"] == "unshielded")["payload"]
    assert uns["reason"] == "completed" and uns["outcome"]["total"] == 1299
    snap = next(e for e in events if e["kind"] == "snapshot")
    assert snap["payload"]["screenshot_b64"]

    summary = (await client.get(f"/runs/{run_id}")).json()
    assert summary["status"] == "done"
    assert len((await client.get(f"/runs/{run_id}/events")).json()) == len(events)
    assert run_id in [r["run_id"] for r in (await client.get("/runs")).json()]

    # Reconnect with Last-Event-ID replays only later frames (after a fresh run frame).
    resumed = _frames(
        (await client.get(f"/runs/{run_id}/stream", headers={"Last-Event-ID": "3"})).text
    )
    assert resumed[0]["event"] == "run" and int(resumed[1]["id"]) == 4


async def test_unknown_preset_and_run(client: httpx.AsyncClient) -> None:
    assert (await client.post("/runs", json={"preset_id": "nope"})).status_code == 404
    assert (await client.get("/runs/nope")).status_code == 404


SENTINEL = "sk-TEST-SENTINEL-123"
OWN = {"provider": "groq", "model": "openai/gpt-oss-20b", "api_key": SENTINEL}


def test_own_llm_providers_match_router() -> None:
    from typing import get_args

    from aegis.llm import BASE_URLS
    from aegis.schemas import OwnLLM

    assert set(get_args(OwnLLM.model_fields["provider"].annotation)) == set(BASE_URLS)


async def test_own_llm_rejects_bad_fields(client: httpx.AsyncClient) -> None:
    for bad in ({"provider": "evil", "model": "m"}, {"model": "m" * 101}, {"model": "a,groq:b"},
                {"api_key": "k" * 301}, {"base_url": "http://169.254.169.254"}):  # fmt: skip
        body = {"preset_id": "clean", "llm": {**OWN, **bad}}
        r = await client.post("/runs", json=body)
        # base_url is ignored (no such field), never used: the router only knows fixed endpoints
        assert r.status_code == (201 if "base_url" in bad else 422), bad


async def _run_own(client: httpx.AsyncClient) -> tuple[str, str]:
    """Launch with the sentinel key; return (run_id, everything the API and SSE expose)."""
    run_id = (await client.post("/runs", json={"preset_id": "clean", "auto_approve": True,
                                               "llm": OWN})).json()["run_id"]  # fmt: skip
    stream = (await client.get(f"/runs/{run_id}/stream")).text
    seen = stream + "".join(
        [(await client.get(u)).text for u in (f"/runs/{run_id}", f"/runs/{run_id}/events", "/runs")]
    )
    return run_id, seen


async def test_own_key_run_uses_its_router_and_never_leaks(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    routers: list[object] = []

    def factory(router: object) -> ScriptedAgent:
        routers.append(router)
        return _clean_purchase()

    async def parser(task: str, router: object) -> tuple[Ledger, list[str]]:
        routers.append(router)
        return await _ledger(task)

    monkeypatch.setattr(main, "agent_factory", factory)
    monkeypatch.setattr(main, "ledger_parser", parser)
    caplog.set_level("DEBUG")
    run_id, seen = await _run_own(client)

    assert len(routers) == 3 and len({id(r) for r in routers}) == 1  # ledger + both sides
    r = routers[0]
    assert isinstance(r, main.OwnKeyRouter) and r is not main._router
    assert r.chain == [("groq", "openai/gpt-oss-20b")] and r._keys("groq") == [SENTINEL]
    assert r._cfg.llm_cache_mode == "off" and not r._keys("gemini")
    summary = (await client.get(f"/runs/{run_id}")).json()
    assert summary["own_key"] is True and summary["model"] == "groq:openai/gpt-oss-20b"
    assert '"done"' in seen and SENTINEL not in seen
    store = main._bus.store
    await store.flush()
    stored = "".join(x.model_dump_json() for x in [*store.events[run_id], *store.runs.values()])
    assert '"done"' in stored and SENTINEL not in stored and SENTINEL not in caplog.text


async def test_provider_error_with_key_is_redacted(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    import openai

    from aegis.agent import LLMAgent
    from tests.test_llm import FakeClient

    def leak() -> openai.BadRequestError:
        req = httpx.Request("POST", "https://x")
        res = httpx.Response(400, request=req)
        return openai.BadRequestError(f"Invalid API key {SENTINEL}", response=res, body=None)

    def factory(router: main.OwnKeyRouter) -> LLMAgent:
        router._clients = {"groq": FakeClient([leak() for _ in range(9)])}  # type: ignore[assignment]
        return LLMAgent(router)

    monkeypatch.setattr(main, "agent_factory", factory)
    caplog.set_level("DEBUG")
    _, seen = await _run_own(client)
    assert "[redacted]" in seen and SENTINEL not in seen and SENTINEL not in caplog.text
