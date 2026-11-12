"""The base agent: what it may see (build_agent_view) and how it decides (decide, A-D1-06).

build_agent_view is the ONLY place the agent view is built (brief §9 rule 13). Detector-only
fields (download, opacity, contrast_ratio, occluded_by, visible, bbox, onclick) never reach it.
"""

from pydantic import BaseModel

from aegis.schemas import Element, PageSnapshot

MAX_INTERACTIVE = 60
MAX_TEXT_BLOCKS = 40
TEXT_CAP = 160
NEARBY_CAP = 120

INTERACTIVE_TAGS = {"a", "button", "input", "select", "textarea", "summary"}
INTERACTIVE_ROLES = {
    "button", "link", "checkbox", "radio", "switch", "tab", "menuitem", "option", "combobox",
    "textbox",
}  # fmt: skip


class AgentElement(BaseModel):
    """Exactly the fields a typical DOM agent sees."""

    id: str
    tag: str
    role: str | None = None
    text: str = ""
    nearby_text: str = ""
    href: str | None = None
    checked: bool | None = None
    value: str | None = None


class AgentView(BaseModel):
    title: str
    interactive: list[AgentElement]
    text_blocks: list[AgentElement]  # page text in DOM order, including hidden text


def is_interactive(el: Element) -> bool:
    return el.tag in INTERACTIVE_TAGS or (el.role in INTERACTIVE_ROLES) or el.onclick


def _cap(s: str, n: int) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"


def _agent_element(el: Element) -> AgentElement:
    return AgentElement(
        id=el.id,
        tag=el.tag,
        role=el.role,
        text=_cap(el.text, TEXT_CAP),
        nearby_text=_cap(el.nearby_text, NEARBY_CAP),
        href=el.href,
        checked=el.checked,
        value=el.value,
    )


def build_agent_view(snap: PageSnapshot) -> AgentView:
    """Never includes the page URL (it can carry arena config) or detector-only fields."""
    interactive = [_agent_element(e) for e in snap.elements if is_interactive(e)]
    texts = [_agent_element(e) for e in snap.elements if not is_interactive(e) and e.text]
    return AgentView(
        title=snap.title,
        interactive=interactive[:MAX_INTERACTIVE],
        text_blocks=texts[:MAX_TEXT_BLOCKS],
    )


def render_agent_view(view: AgentView) -> str:
    """Compact line format for the prompt (~2K tokens budget)."""
    lines = [f"PAGE TITLE: {view.title}", "TEXT:"]
    lines += [f"  {t.text}" for t in view.text_blocks]
    lines.append("ELEMENTS:")
    for e in view.interactive:
        parts = [f"[{e.id}] <{e.tag}{' role=' + e.role if e.role else ''}>", repr(e.text)]
        if e.href:
            parts.append(f"href={e.href}")
        if e.checked is not None:
            parts.append(f"checked={str(e.checked).lower()}")
        if e.value:
            parts.append(f"value={e.value!r}")
        if e.nearby_text:
            parts.append(f"near={e.nearby_text!r}")
        lines.append("  " + " ".join(parts))
    return "\n".join(lines)
