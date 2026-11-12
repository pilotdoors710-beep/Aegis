"""Fast detectors: pure functions detect(snapshot, action, ledger) -> list[Finding] (rule 1).

They look at the whole page, so the console can box every suspicious element; the verdict engine
decides which findings matter for the proposed action (element_id == action.target_id).
"""

from collections.abc import Callable

from aegis.schemas import Action, Element, Finding, Ledger, PageSnapshot

Detector = Callable[[PageSnapshot, Action | None, Ledger | None], list[Finding]]


def has_box(e: Element) -> bool:
    """Laid out (not display:none). Hidden-with-a-box is a trick; display:none is normal UI."""
    return e.bbox[2] >= 2 and e.bbox[3] >= 2


def quote(text: str, n: int = 80) -> str:
    return repr(text if len(text) <= n else text[: n - 1] + "…")


def _all() -> list[Detector]:
    from aegis.detectors import (
        a1_visibility,
        a2_hit_test,
        a3_faint_text,
        a4_link_truth,
        a5_context,
        b5_quarantine,
        c1_persuasion,
    )

    mods = (a1_visibility, a2_hit_test, a3_faint_text, a4_link_truth, a5_context)
    return [m.detect for m in (*mods, b5_quarantine, c1_persuasion)]


# Findings from these detectors remove their element's text from the shielded agent view.
SANITIZING = {"B5_quarantine", "C1_persuasion"}


def run_fast(snap: PageSnapshot, action: Action | None, ledger: Ledger | None) -> list[Finding]:
    return [f for d in _all() for f in d(snap, action, ledger)]
