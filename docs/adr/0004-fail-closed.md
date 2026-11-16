# Checks fail closed

If a Detector, the Audit or another check throws or times out, the Action is blocked with a `guard_unavailable` Finding instead of being let through (`FAIL_MODE=closed`; `open` exists only for diagnosis). An experimental module (Trials, Two-view check, Sybil) being unavailable likewise leads to an Ask, never to an ALLOW on a sensitive action.
