"""C1: pressure widgets (countdowns, "N people bought", "only N left", struck-through prices).

Flagged text is removed from the shielded agent view; the removal is logged for the console.
shortcut: CSS-only strike-through is not seen (Element has no style field), only s/del/strike.
"""

import re

from aegis.detectors import quote
from aegis.schemas import Action, Finding, Ledger, PageSnapshot, TrapType

NAME = "C1_persuasion"
COUNTDOWN = re.compile(
    r"(?:ends?|expires?|left|remaining|hurry|only)\b.{0,30}\b\d{1,2}:\d{2}\b"
    r"|\b\d{1,2}:\d{2}(?::\d{2})?\s*(?:left|remaining)\b",
    re.I,
)
SOCIAL = re.compile(
    r"\b\d[\d,]*\s+(?:people|others|customers|shoppers|buyers|users)\b.{0,20}"
    r"\b(?:viewing|watching|bought|purchased|looking|ordered|added)\b",
    re.I,
)
SCARCITY = re.compile(r"\bonly\s+\d+\s+(?:left|remaining|in stock)\b", re.I)
STRIKE_TAGS = {"s", "del", "strike"}


def _kind(tag: str, text: str) -> tuple[TrapType, str] | None:
    if COUNTDOWN.search(text):
        return "urgency", "countdown timer"
    if SCARCITY.search(text):
        return "urgency", "scarcity claim"
    if SOCIAL.search(text):
        return "social_proof", "social-proof counter"
    if tag in STRIKE_TAGS:
        return "urgency", "struck-through reference price"
    return None


def detect(snap: PageSnapshot, action: Action | None, ledger: Ledger | None) -> list[Finding]:
    out: list[Finding] = []
    for e in snap.elements:
        if e.text and (k := _kind(e.tag, e.text)):
            out.append(Finding(
                detector=NAME, trap_type=k[0], severity="low", element_id=e.id,
                evidence=f"Pressure text ({k[1]}) removed from the agent's view: {quote(e.text)}",
            ))  # fmt: skip
    return out
