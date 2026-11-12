"""A2: the click point of a control is covered by another element (click-jacking)."""

from aegis.detectors import quote
from aegis.schemas import Action, Finding, Ledger, PageSnapshot

NAME = "A2_hit_test"


def detect(snap: PageSnapshot, action: Action | None, ledger: Ledger | None) -> list[Finding]:
    by_id = {e.id: e for e in snap.elements}
    target = action.target_id if action and action.type == "click" else None
    out: list[Finding] = []
    for e in snap.elements:
        if not e.occluded_by:
            continue
        cover = by_id.get(e.occluded_by)
        hidden_cover = cover is not None and not cover.visible
        if not hidden_cover and e.id != target:
            continue  # a visible modal/backdrop over the page is normal unless we click under it
        what = f"{cover.id} {quote(cover.text)}" if cover else e.occluded_by
        how = "an invisible element" if hidden_cover else "another element"
        out.append(Finding(
            detector=NAME, trap_type="clickjacking", severity="high" if hidden_cover else "medium",
            element_id=e.id,
            evidence=f"Clicking {e.id} {quote(e.text)} would hit {how} on top of it: {what}.",
        ))  # fmt: skip
    return out
