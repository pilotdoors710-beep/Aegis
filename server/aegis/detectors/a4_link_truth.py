"""A4: a control labelled close/cancel/no-thanks/continue that really downloads, leaves the site,
or goes to a purchase/upgrade page."""

import re
from urllib.parse import urlsplit

from aegis.detectors import quote
from aegis.schemas import Action, Element, Finding, Ledger, PageSnapshot

NAME = "A4_link_truth"
BENIGN_LABEL = re.compile(
    r"^\s*(?:[×✕✖]|x\s*$|(?:close|cancel|dismiss|no,? thanks?|not now|maybe later|skip|continue"
    r"|back)\b)",
    re.I,
)
X_NETWORK = {"x.com", "twitter.com"}  # a link labelled "X" to the X network is its brand name
COMMIT_PATH = re.compile(r"(?:checkout|subscribe|premium|upgrade|pay|purchase|order)", re.I)


def _host(url: str) -> str:
    return (urlsplit(url).hostname or "").lower()


def _domain_ok(host: str, allowed: list[str]) -> bool:
    return any(host == d or host.endswith("." + d) for d in allowed)


def _lie(e: Element, allowed: list[str], page_url: str) -> str | None:
    if e.download:
        return f"downloads a file ({e.href})"
    if not e.href or urlsplit(e.href).scheme not in ("http", "https"):
        return None
    host = _host(e.href)
    if not _domain_ok(host, allowed):
        return f"navigates off-site to {host}"
    here, there = urlsplit(page_url), urlsplit(e.href)
    if (there.hostname, there.path) == (here.hostname, here.path):
        return None  # "#" or same-page anchor: not a navigation
    if COMMIT_PATH.search(there.path):
        return f"opens a purchase/upgrade page ({urlsplit(e.href).path})"
    return None


def _dist(a: Element, b: Element) -> float:
    (ax, ay, aw, ah), (bx, by, bw, bh) = a.bbox, b.bbox
    return abs(ax + aw / 2 - bx - bw / 2) + abs(ay + ah / 2 - by - bh / 2)


def detect(snap: PageSnapshot, action: Action | None, ledger: Ledger | None) -> list[Finding]:
    allowed = [d.lower() for d in (ledger.allowed_domains if ledger else [])] or [_host(snap.url)]
    benign = [
        e for e in snap.elements
        if BENIGN_LABEL.match(e.text)
        and not (
            e.text.strip().lower() == "x"
            and _host(e.href or "").removeprefix("www.") in X_NETWORK
        )
    ]  # fmt: skip
    liars = {e.id: lie for e in benign if e.href and (lie := _lie(e, allowed, snap.url))}
    honest = [
        e for e in benign if e.visible and e.id not in liars and (e.tag == "button" or e.href)
    ]
    out: list[Finding] = []
    for e in snap.elements:
        if e.id not in liars:
            continue
        alt = min(honest, key=lambda h: _dist(h, e), default=None)
        out.append(Finding(
            detector=NAME, trap_type="fake_control", severity="high", element_id=e.id,
            evidence=f"{e.id} is labelled {quote(e.text)} but {liars[e.id]}.",
            suggestion=f"Click {alt.id} {quote(alt.text)} instead." if alt else None,
        ))  # fmt: skip
    return out
