"""A5: a control imitating a primary shop action while labelled as an ad by nearby text."""

import re

from aegis.detectors import quote
from aegis.schemas import Action, Finding, Ledger, PageSnapshot

NAME = "A5_context_binding"
AD_MARK = re.compile(r"\b(?:sponsored|advertisement|promoted|ad)\b", re.I)
PRIMARY = re.compile(
    r"\b(?:proceed|checkout|check out|continue|place order|buy|pay|add to cart|download)\b", re.I
)


def detect(snap: PageSnapshot, action: Action | None, ledger: Ledger | None) -> list[Finding]:
    return [
        Finding(
            detector=NAME,
            trap_type="disguised_ad",
            severity="high",
            element_id=e.id,
            evidence=f"{e.id} {quote(e.text)} looks like a shop action, but the text next to it "
            f"says it is an ad: {quote(e.nearby_text)}.",
            suggestion="Use the shop's own control, not the sponsored one.",
        )  # fmt: skip
        for e in snap.elements
        if e.text
        and PRIMARY.search(e.text)
        and AD_MARK.search(e.nearby_text)
        and not AD_MARK.search(e.text)
        and (e.href or e.onclick or e.tag in ("button", "a"))
    ]
