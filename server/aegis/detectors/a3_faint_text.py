"""A3: visible text whose WCAG contrast against its background is too low to read."""

from aegis.detectors import quote
from aegis.schemas import Action, Finding, Ledger, PageSnapshot

NAME = "A3_faint_text"
MIN_CONTRAST = 1.5


def detect(snap: PageSnapshot, action: Action | None, ledger: Ledger | None) -> list[Finding]:
    return [
        Finding(
            detector=NAME,
            trap_type="hidden_info",
            severity="medium",
            element_id=e.id,
            evidence=f"Near-invisible text (contrast {e.contrast_ratio}:1, readable needs "
            f"≥{MIN_CONTRAST}): {quote(e.text)}",
        )  # fmt: skip
        for e in snap.elements
        if e.visible and e.text and e.contrast_ratio is not None and e.contrast_ratio < MIN_CONTRAST
    ]
