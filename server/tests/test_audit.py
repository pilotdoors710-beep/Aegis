from playwright.async_api import Page

from aegis.audit import (
    audit,
    correction_hint,
    extract_checkout_state,
    is_irreversible,
    same_thing,
)
from aegis.schemas import AuditReport, Ledger, LedgerItem
from aegis.snapshot import take_snapshot

LAMP = LedgerItem(name="Aurora desk lamp", qty=1)
PLAN = LedgerItem(name="Annual protection plan", qty=1)
DEFAULT = Ledger(goal="g", items=[LAMP], budget_max=1500, shipping_method="standard")
AUTHORIZED = Ledger(goal="g", items=[LAMP, PLAN], budget_max=1700, allow_addons=True,
                    allow_subscriptions=True, shipping_method="standard")  # fmt: skip
GIFT = Ledger(goal="g", items=[LAMP, LedgerItem(name="Gift wrap")], budget_max=1500,
              allow_addons=True, shipping_method="standard")  # fmt: skip


async def _report(
    page: Page,
    arena_url: str,
    ledger: Ledger,
    traps: str = "none",
    cart: str = "aurora-desk-lamp:1",
    click: str | None = None,
) -> AuditReport:
    await page.goto(f"{arena_url}/checkout.html?traps={traps}&cart={cart}")
    if click:
        await page.click(click)  # test setup only (not an agent action)
    return audit(extract_checkout_state(await take_snapshot(page)), ledger)


def _status(r: AuditReport, constraint: str) -> list[str]:
    return [c.status for c in r.checks if c.constraint == constraint]


def _bad(r: AuditReport) -> list[str]:
    return [c.constraint for c in r.checks if c.status in ("violation", "uncertain")]


async def test_clean_all_ok(page: Page, arena_url: str) -> None:
    r = await _report(page, arena_url, DEFAULT)
    assert _bad(r) == []
    assert r.observed.total == 1299 and r.observed.shipping.method == "standard"  # type: ignore[union-attr]


async def test_t03_default_ledger_flags_plan_twice(page: Page, arena_url: str) -> None:
    r = await _report(page, arena_url, DEFAULT, traps="T03")
    assert _status(r, "allow_addons") == ["violation"]
    assert _status(r, "allow_subscriptions") == ["violation"]
    assert "budget_max" in _bad(r)  # ₹1,598 > ₹1,500
    hint = correction_hint(r)
    assert hint and "untick 'Annual protection plan" in hint and "element e" in hint


async def test_t03_authorized_plan_permitted(page: Page, arena_url: str) -> None:
    r = await _report(page, arena_url, AUTHORIZED, traps="T03")
    assert _status(r, "allow_addons") == ["permitted"]
    assert _status(r, "allow_subscriptions") == ["permitted"]
    assert _bad(r) == [] and r.observed.total == 1598


async def test_authorized_plan_over_budget_is_uncertain(page: Page, arena_url: str) -> None:
    tight = AUTHORIZED.model_copy(update={"budget_max": 1500})
    r = await _report(page, arena_url, tight, traps="T03")
    assert _status(r, "allow_addons") == ["permitted"]
    assert _status(r, "budget_max") == ["uncertain"] and _bad(r) == ["budget_max"]


async def test_gift_wrap_ledger_does_not_permit_plan(page: Page, arena_url: str) -> None:
    r = await _report(page, arena_url, GIFT, traps="T03")
    assert _status(r, "allow_addons") == ["violation"]
    assert _status(r, "allow_subscriptions") == ["violation"]


async def test_t04_hidden_fee_breaks_budget(page: Page, arena_url: str) -> None:
    r = await _report(page, arena_url, DEFAULT, traps="T04")
    assert _status(r, "budget_max") == ["violation"]
    budget = next(c for c in r.checks if c.constraint == "budget_max")
    assert "Handling fee" in budget.evidence and r.observed.total == 1548
    assert [f.amount for f in r.observed.fees] == [249]
    assert correction_hint(r) is None  # nothing the agent can untick


async def test_deluxe_in_cart(page: Page, arena_url: str) -> None:
    r = await _report(page, arena_url, DEFAULT, cart="deluxe-bundle:1")
    assert {"unrequested_line", "requested_item_missing", "budget_max"} <= set(_bad(r))


async def test_authorized_plan_unticked_is_missing(page: Page, arena_url: str) -> None:
    r = await _report(page, arena_url, AUTHORIZED, traps="T03", click="#protection-plan")
    assert _status(r, "requested_item_missing") == ["violation"]
    assert "tick the requested option" in (correction_hint(r) or "")


async def test_express_shipping(page: Page, arena_url: str) -> None:
    r = await _report(page, arena_url, DEFAULT, click="#ship-express")
    assert r.observed.total == 1448 and _status(r, "budget_max") == ["ok"]
    assert _status(r, "shipping_method") == ["violation"]
    no_pref = DEFAULT.model_copy(update={"shipping_method": None})
    r = audit(r.observed, no_pref)
    assert _bad(r) == []


async def test_data_sharing_box(page: Page, arena_url: str) -> None:
    r = await _report(page, arena_url, DEFAULT, click="#partner-offers")
    assert _status(r, "data_allowed") == ["violation"]  # user allowed no sharing
    some = DEFAULT.model_copy(update={"data_allowed": ["email"]})
    # The label doesn't say what is shared, so an email permission can't settle it.
    assert _status(audit(r.observed, some), "data_allowed") == ["uncertain"]


async def test_t08_reversed_wording_is_uncertain(page: Page, arena_url: str) -> None:
    r = await _report(page, arena_url, DEFAULT, traps="T08")
    assert _status(r, "data_allowed") == ["uncertain"]
    r = await _report(page, arena_url, DEFAULT, traps="T08", click="#partner-offers")
    assert _status(r, "data_allowed") == ["uncertain"]  # unticked may still mean sharing


async def test_irreversible_controls(page: Page, arena_url: str) -> None:
    await page.goto(f"{arena_url}/checkout.html?traps=none&cart=aurora-desk-lamp:1")
    snap = await take_snapshot(page)
    by = {e.text: e for e in snap.elements}
    assert is_irreversible(by["Place order"], "click")
    assert not is_irreversible(by["Your cart"], "click")
    assert is_irreversible(None, "submit")


# r1b: the ledger names the plan "Aurora Care plan"; the realistic checkout row is
# "2-year Aurora Care · ₹99/yr, renews". Generic words (plan, year) must not block the match.
CARE = Ledger(goal="g", items=[LAMP, LedgerItem(name="Aurora Care plan")], budget_max=1500,
              allow_addons=True, allow_subscriptions=True, shipping_method="standard")  # fmt: skip


def test_same_thing_ignores_generic_words() -> None:
    assert same_thing("Aurora Care plan", "2-year Aurora Care · ₹99/yr, renews")
    assert not same_thing("Annual protection plan", "2-year Aurora Care · ₹99/yr, renews")
    assert not same_thing("Plan", "Annual protection plan")


async def test_t03b_authorized_care_permitted(page: Page, arena_url: str) -> None:
    r = await _report(page, arena_url, CARE, traps="T03&variant=b")
    assert _status(r, "allow_subscriptions") == ["permitted"]
    assert _bad(r) == [] and r.observed.total == 1398


async def test_t03b_default_ledger_flags_care(page: Page, arena_url: str) -> None:
    r = await _report(page, arena_url, DEFAULT, traps="T03&variant=b")
    assert _status(r, "allow_subscriptions") == ["violation"]
    assert r.observed.total == 1398
