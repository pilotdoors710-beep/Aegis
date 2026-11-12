"""B5: page text that addresses an AI agent or tries to override instructions (prompt injection).

Flagged text is removed from the shielded agent view by build_agent_view(sanitize=...).
shortcut: phrase patterns only; paraphrased injections slip through (A7/vision is the upgrade).
"""

import re

from aegis.detectors import quote
from aegis.schemas import Action, Finding, Ledger, PageSnapshot

NAME = "B5_quarantine"
_WHO = r"(?:ai|a\.i\.|llm|language model|agent|assistant|bot|chatbot|model)"
INJECTION = re.compile(
    rf"""
    ^\W*(?:dear\s|hey\s|attention,?\s|note\sto\s(?:the\s)?)?(?:the\s)?{_WHO}\s*[:,!]  # "AI:"
    | \b(?:attention|dear|hey|note\sto|message\sfor|instructions?\sfor)\s+
      (?:the\s+|any\s+|all\s+)?(?:\w+\s+)?{_WHO}s?\b
    | \b(?:ignore|disregard|forget|override)\s+(?:all\s+|any\s+|the\s+|your\s+)*
      (?:previous|prior|above|earlier|original|user'?s?)?\s*
      (?:instructions|prompts?|rules|task|guidelines)
    | \bthe\suser\s(?:also\s|actually\s|really\s)?
      (?:wants|asked|requires|instructed|prefers|has\sauthori[sz]ed)\b
    | \b(?:system\sprompt|new\sinstructions|you\smust\snow|you\sare\snow)\b
    """,
    re.I | re.X,
)


def detect(snap: PageSnapshot, action: Action | None, ledger: Ledger | None) -> list[Finding]:
    return [
        Finding(
            detector=NAME,
            trap_type="prompt_injection",
            severity="high",
            element_id=e.id,
            evidence=f"Text addressed to an AI agent, removed from the agent's view: "
            f"{quote(e.text)}",
        )  # fmt: skip
        for e in snap.elements
        if e.text and INJECTION.search(e.text)
    ]
