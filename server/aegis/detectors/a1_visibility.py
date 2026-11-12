"""A1: content an agent can read or click but a human cannot see (opacity, clip, off-screen)."""

from aegis.detectors import has_box, quote
from aegis.schemas import Action, Finding, Ledger, PageSnapshot

NAME = "A1_visibility"


def detect(snap: PageSnapshot, action: Action | None, ledger: Ledger | None) -> list[Finding]:
    out: list[Finding] = []
    for e in snap.elements:
        if e.visible:
            continue
        is_target = action is not None and action.target_id == e.id
        if is_target:
            out.append(Finding(
                detector=NAME, trap_type="fake_control", severity="high", element_id=e.id,
                evidence=f"The agent wants to act on {e.id} {quote(e.text)}, which a person "
                f"cannot see (opacity {e.opacity}, box {e.bbox[2]:.0f}x{e.bbox[3]:.0f}).",
            ))  # fmt: skip
        elif has_box(e) and e.text:
            out.append(Finding(
                detector=NAME, trap_type="hidden_info", severity="medium", element_id=e.id,
                evidence=f"Text invisible to people but readable by agents (opacity "
                f"{e.opacity}): {quote(e.text)}",
            ))  # fmt: skip
    return out
