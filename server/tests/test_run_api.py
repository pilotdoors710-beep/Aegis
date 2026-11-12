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


def _clean_purchase() -> ScriptedAgent:
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


async def _ledger(task: str) -> tuple[Ledger, list[str]]:
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
