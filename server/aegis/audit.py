"""B2: pre-commit audit. Observable checkout state vs the user's Ledger (brief §6 B2, §1 R1).

extract_checkout_state reads only what a person could read: visible labels, checkbox/radio state,
the order-summary table and fee text. It never reads test ids, trap ids or ground-truth JSON.
audit() is pure: one AuditCheck per constraint. Precedence for the caller: any violation ->
REROUTE; else any uncertain -> ASK(uncertain); else ASK(final_payment).
shortcut: tuned to table-row checkouts like the arena; other layouts give "uncertain", not "ok".
"""

import re

from aegis.schemas import (
    AuditCheck,
    AuditReport,
    CheckoutLine,
    CheckoutState,
    DataSharing,
    Element,
    Ledger,
    PageSnapshot,
    RecurringTerm,
    ShippingObservation,
    TickedOption,
)

MONEY = re.compile(r"₹\s?([\d,]+(?:\.\d+)?)")
QTY = re.compile(r"\s*[×x]\s*(\d+)\s*$")
RECURRING = re.compile(
    r"/\s?(yr|year|mo|month)\b|auto-?renew|per (year|month)|monthly|yearly", re.I
)
FEE = re.compile(r"\b(?:fee|surcharge|service charge)\b", re.I)
DATA = re.compile(r"\b(?:share|sharing|partner|third[- ]part|email|phone|data)\w*", re.I)
NEGATION = re.compile(r"\b(?:not|don'?t|no|uncheck|untick|stop|opt[- ]?out|unless)\b", re.I)
STOPWORDS = {"the", "a", "an", "and", "with", "of", "for"}


def money(text: str) -> float | None:
    m = MONEY.search(text)
    return float(m.group(1).replace(",", "")) if m else None


def _tokens(name: str) -> set[str]:
    name = re.sub(r"\(.*?\)|·.*$|₹[\d,]+|/\w+", " ", name.lower())
    return {t for t in re.findall(r"[a-z]+", name) if t not in STOPWORDS}


def same_thing(a: str, b: str) -> bool:
    """'Annual protection plan' ~ 'Annual protection plan (₹299/yr, auto-renewing)'."""
    ta, tb = _tokens(a), _tokens(b)
    return bool(ta and tb) and (ta <= tb or tb <= ta)


def _period(text: str) -> str | None:
    m = RECURRING.search(text)
    if not m:
        return None
    return "month" if re.search(r"mo|month", m.group(0), re.I) else "year"


def extract_checkout_state(snap: PageSnapshot) -> CheckoutState:
    els = [e for e in snap.elements if e.visible or e.text]
    state = CheckoutState()
    for i, e in enumerate(els[:-1]):
        nxt = els[i + 1]
        if e.tag != "th" or nxt.tag != "td" or money(nxt.text) is None:
            continue
        label, amount = e.text, money(nxt.text)
        if re.search(r"\border total\b|^total\b", label, re.I):
            state.total = amount
        elif re.search(r"shipping|delivery", label, re.I):
            method = "express" if re.search(r"express", label, re.I) else "standard"
            state.shipping = ShippingObservation(
                method=method, cost=amount, evidence=f"summary row {label!r}", element_id=e.id
            )
        elif FEE.search(label):
            state.fees.append(CheckoutLine(name=label, amount=amount, element_id=e.id))
        else:
            m = QTY.search(label)
            name = QTY.sub("", label).strip()
            state.lines.append(CheckoutLine(name=name, qty=int(m.group(1)) if m else 1,
                                            amount=amount, element_id=e.id))  # fmt: skip
            if p := _period(label):
                state.recurring_terms.append(
                    RecurringTerm(description=label, amount=amount, period=p, element_id=e.id)
                )
    # Fees mentioned outside the table (e.g. inside a "See details" disclosure).
    for e in els:
        if e.tag not in ("th", "td") and FEE.search(e.text) and money(e.text) is not None:
            if not any(same_thing(f.name, e.text) for f in state.fees):
                state.fees.append(CheckoutLine(name=e.text, amount=money(e.text), element_id=e.id))
    for e in snap.elements:
        if e.tag != "input" or e.checked is None:
            continue
        if e.role == "radio":
            if e.checked and re.search(r"shipping|delivery", e.text, re.I):
                method = "express" if re.search(r"express", e.text, re.I) else "standard"
                cost = state.shipping.cost if state.shipping else money(e.text)
                state.shipping = ShippingObservation(
                    method=method, cost=cost, evidence=f"selected option {e.text!r}",
                    element_id=e.id,
                )  # fmt: skip
            continue
        if DATA.search(e.text) and not RECURRING.search(e.text):
            cats = ["email"] if re.search(r"email", e.text, re.I) else []
            if e.checked or NEGATION.search(e.text):  # reversed wording: unticked may still share
                state.data_sharing.append(
                    DataSharing(description=e.text, categories=cats, element_id=e.id)
                )
            state.ticked_options.append(TickedOption(label=e.text, checked=bool(e.checked),
                                                     element_id=e.id))  # fmt: skip
            continue
        state.ticked_options.append(
            TickedOption(label=e.text, checked=bool(e.checked), element_id=e.id)
        )
        if e.checked and (p := _period(e.text)):
            if not any(same_thing(r.description, e.text) for r in state.recurring_terms):
                state.recurring_terms.append(RecurringTerm(
                    description=e.text, amount=money(e.text), period=p, element_id=e.id
                ))  # fmt: skip
    return state


def _named(ledger: Ledger, text: str) -> bool:
    return any(same_thing(i.name, text) for i in ledger.items)


def _fmt(x: float | None) -> str:
    return "unknown" if x is None else f"₹{x:,.0f}"


def audit(state: CheckoutState, ledger: Ledger) -> AuditReport:
    checks: list[AuditCheck] = []

    def add(constraint, kind, ledger_value, observed, evidence, status, element_id=None):  # noqa: ANN001
        checks.append(AuditCheck(constraint=constraint, kind=kind, ledger_value=str(ledger_value),
                                 observed_value=str(observed), evidence=evidence,
                                 element_id=element_id, status=status))  # fmt: skip

    data_ids = {d.element_id for d in state.data_sharing}
    extras = [
        o for o in state.ticked_options if o.element_id not in data_ids and not DATA.search(o.label)
    ]
    # Fulfillment: everything the user asked for is present at its quantity.
    for i, item in enumerate(ledger.items):
        line = next((ln for ln in state.lines if same_thing(item.name, ln.name)), None)
        if line is None:
            box = next((o for o in extras if same_thing(item.name, o.label)), None)
            add("requested_item_missing", "fulfillment", item.name, "not in order summary",
                f"{item.name!r} is requested but not in the order summary"
                + (f"; option {box.label!r} is unticked" if box and not box.checked else ""),
                "violation", box.element_id if box else None)  # fmt: skip
            continue
        status = "ok" if line.qty == item.qty else "violation"
        add(f"items[{i}]", "fulfillment", f"{item.name} × {item.qty}", f"{line.name} × {line.qty}",
            f"order summary row {line.name!r} × {line.qty}", status, line.element_id)  # fmt: skip
        if item.max_price is not None and line.amount is not None:
            unit = line.amount / max(line.qty, 1)
            add(f"items[{i}].max_price", "authorization", _fmt(item.max_price), _fmt(unit),
                f"{line.name!r} costs {_fmt(unit)} each",
                "ok" if unit <= item.max_price else "violation", line.element_id)  # fmt: skip

    # Authorization: nothing beyond what the user allowed.
    recurring_ids = {r.element_id for r in state.recurring_terms}
    for line in state.lines:
        is_extra = line.element_id in recurring_ids or any(
            same_thing(o.label, line.name) for o in extras
        )
        if not _named(ledger, line.name) and not is_extra:
            add("unrequested_line", "authorization", "only the requested items", line.name,
                f"order summary has {line.name!r} ({_fmt(line.amount)}), which was not requested",
                "violation", line.element_id)  # fmt: skip
    for o in (o for o in extras if o.checked):
        ok = ledger.allow_addons and _named(ledger, o.label)
        add("allow_addons", "authorization", f"allow_addons={ledger.allow_addons}", o.label,
            f"option {o.label!r} is ticked" + (" and the user asked for it" if ok else
                                               ", but the user did not ask for it"),
            "permitted" if ok else "violation", o.element_id)  # fmt: skip
    permitted_extra_amount = 0.0
    for r in state.recurring_terms:
        ok = ledger.allow_subscriptions and _named(ledger, r.description)
        if ok:
            permitted_extra_amount += r.amount or 0
        flag = f"allow_subscriptions={ledger.allow_subscriptions}"
        verdict = "was requested" if ok else "was not authorized"
        add("allow_subscriptions", "authorization", flag,
            f"{r.description} ({_fmt(r.amount)}/{r.period})",
            f"recurring charge {r.description!r} {verdict}",
            "permitted" if ok else "violation", r.element_id)  # fmt: skip
    for d in state.data_sharing:
        reversed_wording = bool(NEGATION.search(d.description))
        allowed = set(d.categories) <= set(ledger.data_allowed) and bool(d.categories)
        unknown = not d.categories and bool(ledger.data_allowed)  # can't tell what is shared
        if reversed_wording or unknown:
            status = "uncertain"
        else:
            status = "permitted" if allowed else "violation"
        add("data_allowed", "authorization", ledger.data_allowed or "none", d.description,
            ("the wording is reversed, so the effect of this box cannot be established: "
             if reversed_wording else "data sharing is switched on: ") + repr(d.description),
            status, d.element_id)  # fmt: skip

    if ledger.shipping_method:
        got = state.shipping.method if state.shipping else None
        status = (
            "uncertain" if got is None else ("ok" if got == ledger.shipping_method else "violation")
        )
        add("shipping_method", "authorization", ledger.shipping_method, got or "unknown",
            state.shipping.evidence if state.shipping else "selected shipping option not found",
            status, state.shipping.element_id if state.shipping else None)  # fmt: skip

    fee_note = "".join(f"; includes {f.name!r}" for f in state.fees)
    if ledger.budget_max is not None:
        if state.total is None:
            status = "uncertain"
        elif state.total <= ledger.budget_max:
            status = "ok"
        else:
            status = "violation"
        add("budget_max", "authorization", _fmt(ledger.budget_max), _fmt(state.total),
            f"order total {_fmt(state.total)}{fee_note}", status)  # fmt: skip

    parts = [ln.amount for ln in state.lines] + [f.amount for f in state.fees]
    parts.append(state.shipping.cost if state.shipping else 0.0)
    if state.total is None or any(p is None for p in parts):
        add("total_integrity", "fulfillment", "lines add up to the total", "unknown",
            "could not read every amount and the total", "uncertain")  # fmt: skip
    else:
        s = sum(p for p in parts if p is not None)
        add("total_integrity", "fulfillment", _fmt(state.total), _fmt(s),
            f"summary rows add up to {_fmt(s)}; displayed total {_fmt(state.total)}{fee_note}",
            "ok" if abs(s - state.total) < 0.5 else "uncertain")  # fmt: skip

    # Two user constraints conflict (an authorized extra breaks the budget): Aegis won't pick one.
    violations = [c for c in checks if c.status == "violation"]
    budget = next((c for c in checks if c.constraint == "budget_max"), None)
    if (budget and violations == [budget] and permitted_extra_amount
            and state.total is not None and ledger.budget_max is not None
            and state.total - permitted_extra_amount <= ledger.budget_max):  # fmt: skip
        budget.status = "uncertain"
        budget.evidence += "; the authorized extra is what breaks the budget"
    return AuditReport(checks=checks, observed=state)


def correction_hint(report: AuditReport) -> str | None:
    """Concrete, agent-performed fixes (Aegis itself never changes the checkout)."""
    hints = []
    for c in report.checks:
        if c.status != "violation":
            continue
        where = f" (element {c.element_id})" if c.element_id else ""
        if c.constraint in ("allow_addons", "allow_subscriptions") and c.element_id:
            box = next(
                (o for o in report.observed.ticked_options if o.element_id == c.element_id), None
            )
            if box:
                hints.append(f"untick {box.label!r}{where}")
        elif c.constraint == "requested_item_missing" and c.element_id:
            hints.append(f"tick the requested option{where}")
        elif c.constraint == "shipping_method":
            hints.append(f"select {c.ledger_value} shipping")
        elif c.constraint == "unrequested_line":
            hints.append(f"remove {c.observed_value!r} from the order")
        elif c.constraint == "data_allowed" and c.element_id:
            hints.append(f"switch off data sharing{where}")
    hints = list(dict.fromkeys(hints))
    return ("; ".join(hints) + ", then place the order again.") if hints else None


def is_irreversible(el: Element | None, action_type: str) -> bool:
    if action_type == "submit":
        return True
    if action_type != "click" or el is None:
        return False
    return bool(re.search(r"\b(pay|place order|subscribe|confirm|buy|purchase|complete order)\b",
                          el.text, re.I))  # fmt: skip
