"""B1: the user's task -> an immutable Ledger, once, before browsing (brief §5, §6 B1).

Only the user's own task text goes in; page content never reaches this module, so a page cannot
change what the user authorized. Permission flags stay False unless the task states them, and every
authorized extra must be named in items (a flag alone never permits an unnamed extra).
"""

from typing import Literal

from pydantic import BaseModel

from aegis.llm import LLMRouter
from aegis.schemas import Ledger, LedgerItem

SYSTEM = """You turn a shopping request into a JSON permission ledger. Output JSON only:
{"items": [{"name": str, "qty": int, "max_price": number|null}],
 "budget_max": number|null,
 "allow_addons": bool, "allow_subscriptions": bool,
 "shipping_method": "standard"|"express"|null,
 "data_allowed": [str],
 "unresolved": [str]}
Rules:
- items: the product(s) to buy AND every extra the user explicitly asks for (add-on, plan, gift
  wrap, ...), each by name. max_price only when a per-item price limit is stated.
- budget_max: the stated limit on the total ("under ₹1,500" -> 1500). null if none.
- allow_addons: true ONLY if the user explicitly asks for an extra/add-on. "No add-ons" -> false.
- allow_subscriptions: true ONLY if the user explicitly asks for something recurring (a
  subscription, membership, or a yearly/monthly plan). Otherwise false.
- shipping_method: only if the user states it; otherwise null.
- data_allowed: personal-data categories the user explicitly allows sharing (e.g. "email"). [] if
  not stated. Sharing for delivery of the order itself is not listed.
- unresolved: short notes on anything ambiguous that changes what is authorized (e.g. "maybe add
  the plan", an unclear budget). [] if the request is clear. Never guess permissions."""


class _Draft(BaseModel):
    items: list[LedgerItem] = []
    budget_max: float | None = None
    allow_addons: bool = False
    allow_subscriptions: bool = False
    shipping_method: Literal["standard", "express"] | None = None
    data_allowed: list[str] = []
    unresolved: list[str] = []


async def parse_ledger(
    task: str, router: LLMRouter, *, allowed_domains: list[str], use_cache: bool = True
) -> tuple[Ledger, list[str]]:
    msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": task}]
    draft, _ = await router.complete_json(msgs, _Draft, use_cache=use_cache)
    unresolved = list(draft.unresolved)
    allow_addons, allow_subs = draft.allow_addons, draft.allow_subscriptions
    if (allow_addons or allow_subs) and len(draft.items) < 2:
        # A permission with no named extra would be blanket authorization: refuse it, and ask.
        unresolved.append("An add-on or subscription seems allowed, but no extra is named.")
        allow_addons = allow_subs = False
    if not draft.items:
        unresolved.append("No product to buy could be identified.")
    ledger = Ledger(
        goal=task,
        items=draft.items,
        budget_max=draft.budget_max,
        allow_addons=allow_addons,
        allow_subscriptions=allow_subs,
        allowed_domains=allowed_domains,  # from server config, never from the LLM or the page
        data_allowed=draft.data_allowed,
        shipping_method=draft.shipping_method,
    )
    return ledger, unresolved
