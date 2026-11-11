"""Router tests use fake clients: no network, no keys."""

from types import SimpleNamespace

import httpx
import openai
import pytest
from pydantic import BaseModel

from aegis.config import Settings
from aegis.llm import AllProvidersFailed, LLMRouter, parse_chain


def _resp(text: str) -> SimpleNamespace:
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])


class FakeClient:
    def __init__(self, replies: list) -> None:
        self.replies = list(replies)
        self.calls = 0
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    async def _create(self, **_: object) -> SimpleNamespace:
        self.calls += 1
        r = self.replies.pop(0)
        if isinstance(r, Exception):
            raise r
        return _resp(r)


def _rate_limit() -> openai.RateLimitError:
    req = httpx.Request("POST", "https://x")
    return openai.RateLimitError("429", response=httpx.Response(429, request=req), body=None)


def _router(clients: dict, chain: str = "gemini:m1,groq:m2") -> LLMRouter:
    cfg = Settings(agent_models=chain, gemini_rpm=6000, groq_rpm=6000)
    return LLMRouter(cfg, clients=clients)  # type: ignore[arg-type]


MSG = [{"role": "user", "content": "hi"}]


def test_parse_chain_keeps_colons_in_model_id() -> None:
    assert parse_chain("openrouter:vendor/model:free") == [("openrouter", "vendor/model:free")]
    with pytest.raises(ValueError):
        parse_chain("nope:model")


async def test_falls_through_on_429_and_reports_provider() -> None:
    a, b = FakeClient([_rate_limit()]), FakeClient(["ok"])
    r = await _router({"gemini": a, "groq": b}).complete(MSG)
    assert (r.provider, r.text, r.cached) == ("groq", "ok", False)


async def test_cache_hit_skips_network_and_is_labelled() -> None:
    a = FakeClient(["first"])
    router = _router({"gemini": a})
    await router.complete(MSG)
    r = await router.complete(MSG)
    assert r.cached and r.text == "first" and a.calls == 1


async def test_use_cache_false_always_calls_provider() -> None:
    a = FakeClient(["one", "two"])
    router = _router({"gemini": a})
    await router.complete(MSG, use_cache=False)
    r = await router.complete(MSG, use_cache=False)
    assert not r.cached and r.text == "two"


async def test_all_fail_raises_with_reasons() -> None:
    router = _router({"gemini": FakeClient([_rate_limit()]), "groq": FakeClient([_rate_limit()])})
    with pytest.raises(AllProvidersFailed, match="RateLimitError"):
        await router.complete(MSG)


class Out(BaseModel):
    n: int


async def test_json_repair_retry_and_bad_output_not_cached() -> None:
    a = FakeClient(["not json", '{"n": 3}'])
    router = _router({"gemini": a}, chain="gemini:m1")
    out, _ = await router.complete_json(MSG, Out)
    assert out.n == 3
    # The invalid first reply must never be cached (it would be replayed forever).
    assert not any("not json" in v.text for v in router.cache._d.values())  # type: ignore[attr-defined]
    assert a.calls == 2


async def test_empty_response_falls_through() -> None:
    a, b = FakeClient([""]), FakeClient(["ok"])
    r = await _router({"gemini": a, "groq": b}).complete(MSG)
    assert (r.provider, r.text) == ("groq", "ok")
