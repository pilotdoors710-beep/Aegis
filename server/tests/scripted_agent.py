"""Test double: decides from a script of (predicate on view -> Action) rules, no LLM."""

from collections.abc import Callable

from aegis.agent import AgentView
from aegis.llm import LLMResult
from aegis.schemas import Action

Rule = Callable[[AgentView, list[str]], Action | None]


def click_text(text: str, why: str = "scripted") -> Rule:
    def rule(view: AgentView, _: list[str]) -> Action | None:
        for e in view.interactive:
            if e.text.strip() == text:
                return Action(type="click", target_id=e.id, rationale=why)
        return None

    return rule


class ScriptedAgent:
    """Applies each rule once, in order; returns done when the script is exhausted."""

    def __init__(self, rules: list[Rule]) -> None:
        self.rules = list(rules)
        self.calls = 0

    async def decide(
        self, view: AgentView, task: str, history: list[str]
    ) -> tuple[Action, LLMResult]:
        self.calls += 1
        result = LLMResult("", "scripted", "scripted", False, 0)
        while self.rules:
            action = self.rules.pop(0)(view, history)
            if action:
                return action, result
        return Action(type="done", rationale="script finished"), result
