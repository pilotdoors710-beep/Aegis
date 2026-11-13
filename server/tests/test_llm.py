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


def _router(
    clients: dict, chain: str = "gemini:m1,groq:m2", mode: str = "on", **keys: str
) -> LLMRouter:
    keys = {"groq_api_key_2": "", "groq_api_key_3": "", **keys}  # ignore real .env extras
    cfg = Settings(agent_models=chain, gemini_rpm=6000, groq_rpm=6000, llm_cache_mode=mode, **keys)  # type: ignore[arg-type]
    return LLMRouter(cfg, clients=clients)  # type: ignore[arg-type]


MSG = [{"role": "user", "content": "hi"}]


def _timeout() -> openai.APITimeoutError:
    return openai.APITimeoutError(request=httpx.Request("POST", "https://x"))


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


async def test_all_fail_raises_with_reasons(monkeypatch: pytest.MonkeyPatch) -> None:
    import aegis.llm as llm

    async def no_sleep(_: float) -> None:
        pass

    monkeypatch.setattr(llm.asyncio, "sleep", no_sleep)
    last = FakeClient([_rate_limit()] * (llm.LAST_PROVIDER_429_RETRIES + 1))
    router = _router({"gemini": FakeClient([_rate_limit()]), "groq": last})
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


async def test_last_provider_waits_instead_of_failing() -> None:
    """A pinned single-model chain waits for its rate bucket instead of failing."""
    from aegis.llm import _Bucket

    b = _Bucket(rpm=600)  # 0.1 s spacing
    assert await b.acquire()
    b._next += 20  # pretend the next slot is 20 s away
    assert not await b.acquire()  # a non-last provider gives up
    b._next -= 19.8
    assert await b.acquire(None)  # the last provider waits (~0.2 s)


async def test_last_provider_retries_after_429(monkeypatch: pytest.MonkeyPatch) -> None:
    import aegis.llm as llm

    async def no_sleep(_: float) -> None:
        pass

    monkeypatch.setattr(llm.asyncio, "sleep", no_sleep)
    only = FakeClient([_rate_limit(), _rate_limit(), "ok"])
    res = await _router({"groq": only}, chain="groq:m2").complete(MSG, use_cache=False)
    assert res.text == "ok" and only.calls == 3


async def test_groq_json_validate_failed_goes_to_repair() -> None:
    req = httpx.Request("POST", "https://x")
    bad = openai.BadRequestError(
        "400",
        response=httpx.Response(400, request=req),
        body={"error": {"code": "json_validate_failed", "failed_generation": "{n: 1"}},
    )
    c = FakeClient([bad, '{"n": 2}'])
    out, _ = await _router({"groq": c}, chain="groq:m2").complete_json(MSG, Out, use_cache=False)
    assert out.n == 2 and c.calls == 2


async def test_json_validate_failed_with_empty_generation() -> None:
    req = httpx.Request("POST", "https://x")
    bad = openai.BadRequestError(
        "400",
        response=httpx.Response(400, request=req),
        body={"code": "json_validate_failed", "failed_generation": ""},
    )
    c = FakeClient([bad, '{"n": 3}'])
    out, _ = await _router({"groq": c}, chain="groq:m2").complete_json(MSG, Out, use_cache=False)
    assert out.n == 3


async def test_groq_spurious_tool_call_goes_to_repair() -> None:
    req = httpx.Request("POST", "https://x")
    bad = openai.BadRequestError(
        "Error code: 400 - Tool choice is none, but model called a tool",
        response=httpx.Response(400, request=req),
        body={"message": "Tool choice is none, but model called a tool", "code": "tool_use_failed"},
    )
    c = FakeClient([bad, '{"n": 4}'])
    out, _ = await _router({"groq": c}, chain="groq:m2").complete_json(MSG, Out, use_cache=False)
    assert out.n == 4 and c.calls == 2


async def test_repeated_tool_calls_are_resent_then_repaired() -> None:
    """Two plain resends first; if the model keeps calling a tool, the repair prompt follows."""

    def bad() -> openai.BadRequestError:
        req = httpx.Request("POST", "https://x")
        msg = "Tool choice is none, but model called a tool"
        return openai.BadRequestError(
            msg, response=httpx.Response(400, request=req), body={"message": msg}
        )

    c = FakeClient([bad(), bad(), bad(), '{"n": 5}'])
    out, _ = await _router({"groq": c}, chain="groq:m2").complete_json(MSG, Out, use_cache=False)
    assert out.n == 5 and c.calls == 4


async def test_fallback_mode_replays_only_when_all_providers_fail() -> None:
    a = FakeClient(["fresh", "fresh again", _timeout()])
    router = _router({"gemini": a}, chain="gemini:m1", mode="fallback")
    assert not (await router.complete(MSG)).cached  # stored, not replayed
    r = await router.complete(MSG)
    assert (r.text, r.cached) == ("fresh again", False)  # a live call even though cached
    r = await router.complete(MSG)  # provider down -> labelled replay
    assert r.cached and r.text in ("fresh", "fresh again")


async def test_off_mode_never_stores() -> None:
    a = FakeClient(["one", _timeout()])
    router = _router({"gemini": a}, chain="gemini:m1", mode="off")
    await router.complete(MSG)
    with pytest.raises(AllProvidersFailed):
        await router.complete(MSG)


async def test_second_key_takes_over_same_model_on_429() -> None:
    """A tokens/day 429 on key 1 moves to key 2 of the same model before the next chain entry."""
    k1, k2, other = FakeClient([_rate_limit()]), FakeClient(["ok"]), FakeClient(["no"])
    router = _router(
        {"groq": k1, "groq#2": k2, "gemini": other},
        chain="groq:m2,gemini:m1",
        groq_api_key="a",
        groq_api_key_2="b",
    )
    assert [s for _, _, s in router.slots] == ["groq", "groq#2", "gemini"]
    res = await router.complete(MSG, use_cache=False)
    assert (res.provider, res.model, res.text) == ("groq", "m2", "ok")
    assert (k1.calls, k2.calls, other.calls) == (1, 1, 0)


async def test_empty_failed_generation_is_resent_like_a_tool_call() -> None:
    """Live 9700fbc49b94: two empty json_validate_failed 400s killed an agent. An empty generation
    gives the repair prompt nothing to fix, so it is resent first (same budget as tool calls)."""

    def empty() -> openai.BadRequestError:
        req = httpx.Request("POST", "https://x")
        body = {"error": {"code": "json_validate_failed", "failed_generation": ""}}
        return openai.BadRequestError("400", response=httpx.Response(400, request=req), body=body)

    c = FakeClient([empty(), empty(), '{"n": 6}'])
    out, _ = await _router({"groq": c}, chain="groq:m2").complete_json(MSG, Out, use_cache=False)
    assert out.n == 6 and c.calls == 3
