import json

import pytest
from pydantic import ValidationError

from aegis.intent import parse_ledger
from aegis.presets import DEFAULT_TASK, PRESETS_BY_ID
from tests.test_llm import FakeClient, _router

DOMAINS = ["arena.example"]


def _reply(**over: object) -> str:
    d = {"items": [{"name": "Aurora desk lamp", "qty": 1, "max_price": None}],
         "budget_max": 1500, "allow_addons": False, "allow_subscriptions": False,
         "shipping_method": "standard", "data_allowed": [], "unresolved": []}  # fmt: skip
    d.update(over)
    return json.dumps(d)


async def _parse(task: str, reply: str):
    router = _router({"gemini": FakeClient([reply])}, chain="gemini:m", mode="off")
    return await parse_ledger(task, router, allowed_domains=DOMAINS)


async def test_default_task() -> None:
    ledger, unresolved = await _parse(DEFAULT_TASK, _reply())
    assert [(i.name, i.qty) for i in ledger.items] == [("Aurora desk lamp", 1)]
    assert ledger.budget_max == 1500 and ledger.shipping_method == "standard"
    assert not ledger.allow_addons and not ledger.allow_subscriptions and unresolved == []
    assert ledger.allowed_domains == DOMAINS and ledger.goal == DEFAULT_TASK


async def test_authorized_plan_is_named() -> None:
    items = [{"name": "Aurora desk lamp", "qty": 1},
             {"name": "Annual protection plan", "qty": 1, "max_price": 299}]  # fmt: skip
    reply = _reply(items=items, budget_max=1700, allow_addons=True, allow_subscriptions=True)
    ledger, unresolved = await _parse(PRESETS_BY_ID["r1-authorized"].task, reply)
    assert ledger.allow_addons and ledger.allow_subscriptions and unresolved == []
    assert any("protection plan" in i.name.lower() for i in ledger.items)


async def test_gift_wrap_is_addon_not_subscription() -> None:
    items = [{"name": "Aurora desk lamp", "qty": 1}, {"name": "Gift wrap", "qty": 1}]
    ledger, _ = await _parse(
        PRESETS_BY_ID["r1-benign"].task, _reply(items=items, allow_addons=True)
    )
    assert ledger.allow_addons and not ledger.allow_subscriptions
    assert [i.name for i in ledger.items][1] == "Gift wrap"


async def test_flag_without_named_extra_is_refused() -> None:
    ledger, unresolved = await _parse("Buy a lamp, extras fine", _reply(allow_addons=True))
    assert not ledger.allow_addons and unresolved


async def test_ambiguous_task_is_unresolved() -> None:
    reply = _reply(unresolved=["'maybe the plan' is not a clear permission"])
    ledger, unresolved = await _parse("Buy the lamp, maybe the plan too?", reply)
    assert not ledger.allow_addons and not ledger.allow_subscriptions and unresolved


async def test_ledger_is_frozen() -> None:
    ledger, _ = await _parse(DEFAULT_TASK, _reply())
    with pytest.raises(ValidationError):
        ledger.allow_addons = True  # type: ignore[misc]
