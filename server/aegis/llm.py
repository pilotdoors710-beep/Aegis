"""Provider router for free-tier LLMs (brief §3, "Hosting and LLMs").

All providers expose OpenAI-compatible endpoints, so one SDK serves them all. The router walks an
ordered chain (AGENT_MODELS), skips a provider whose local rate bucket is empty, and falls through
on 429 / timeout / connection / 5xx errors. Identical requests are served from a decision cache and
reported with cached=True so the UI can label them. Callers doing eval MUST pass use_cache=False.
"""

import asyncio
import hashlib
import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol, TypeVar

import openai
from openai import AsyncOpenAI
from pydantic import BaseModel, ValidationError

from aegis.config import Settings, settings

BASE_URLS = {
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/",
    "groq": "https://api.groq.com/openai/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "cerebras": "https://api.cerebras.ai/v1",
}
# Errors that mean "try the next provider" rather than "our request is wrong".
RETRYABLE = (
    openai.RateLimitError,
    openai.APITimeoutError,
    openai.APIConnectionError,
    openai.InternalServerError,
)
MAX_BUCKET_WAIT_S = 8.0
# The last provider has nothing to fall through to, so it waits out a 429 (TPM windows are 60 s).
LAST_PROVIDER_429_RETRIES = 3
MAX_RETRY_AFTER_S = 65.0


def _failed_generation(err: openai.BadRequestError) -> str | None:
    """Groq JSON mode: 400 json_validate_failed. Returns the bad output (or a placeholder)."""
    body = err.body if isinstance(err.body, dict) else {}
    if isinstance(body.get("error"), dict):
        body = body["error"]
    if body.get("code") != "json_validate_failed":
        return None
    text = body.get("failed_generation")
    return text if isinstance(text, str) and text.strip() else "(output was not valid JSON)"


def _retry_after(err: openai.RateLimitError) -> float:
    try:
        return min(float(err.response.headers.get("retry-after", "15")), MAX_RETRY_AFTER_S)
    except (ValueError, AttributeError):
        return 15.0


T = TypeVar("T", bound=BaseModel)
Messages = list[dict[str, str]]


class AllProvidersFailed(RuntimeError):
    """Every provider in the chain was rate-limited, down, or returned unusable output."""


@dataclass(frozen=True)
class LLMResult:
    text: str
    provider: str
    model: str
    cached: bool
    latency_ms: int


class DecisionCache(Protocol):
    async def get(self, key: str) -> LLMResult | None: ...
    async def set(self, key: str, value: LLMResult) -> None: ...


class MemoryCache:
    """Process-local cache. The Postgres-backed llm_cache replaces this once events land."""

    def __init__(self) -> None:
        self._d: dict[str, LLMResult] = {}

    async def get(self, key: str) -> LLMResult | None:
        return self._d.get(key)

    async def set(self, key: str, value: LLMResult) -> None:
        self._d[key] = value


class _Bucket:
    """Spaces requests at 60/rpm seconds. Returns False if the wait would be too long."""

    def __init__(self, rpm: int) -> None:
        self.interval = 60.0 / max(rpm, 1)
        self._next = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self, max_wait: float | None = MAX_BUCKET_WAIT_S) -> bool:
        """max_wait=None waits as long as needed (last provider: nothing to fall through to)."""
        async with self._lock:
            now = time.monotonic()
            wait = max(0.0, self._next - now)
            if max_wait is not None and wait > max_wait:
                return False
            self._next = max(now, self._next) + self.interval
        if wait:
            await asyncio.sleep(wait)
        return True


def cache_key(model_id: str, messages: Messages) -> str:
    blob = json.dumps([model_id, messages], sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()


def parse_chain(spec: str) -> list[tuple[str, str]]:
    """'gemini:foo,groq:bar' -> [('gemini','foo'), ('groq','bar')]; model ids may contain ':'."""
    chain = []
    for item in filter(None, (x.strip() for x in spec.split(","))):
        provider, _, model = item.partition(":")
        if provider not in BASE_URLS or not model:
            raise ValueError(f"bad AGENT_MODELS entry {item!r}; expected provider:model")
        chain.append((provider, model))
    return chain


class LLMRouter:
    def __init__(
        self,
        cfg: Settings = settings,
        cache: DecisionCache | None = None,
        clients: dict[str, AsyncOpenAI] | None = None,
    ) -> None:
        self.chain = parse_chain(cfg.agent_models)
        self.cache = cache or MemoryCache()
        self._clients = clients or {}
        self._cfg = cfg
        self._buckets = {p: _Bucket(getattr(cfg, f"{p}_rpm")) for p, _ in self.chain}

    def _client(self, provider: str) -> AsyncOpenAI:
        if provider not in self._clients:
            key = getattr(self._cfg, f"{provider}_api_key")
            if not key:
                raise AllProvidersFailed(f"{provider.upper()}_API_KEY is not set")
            self._clients[provider] = AsyncOpenAI(
                api_key=key, base_url=BASE_URLS[provider], timeout=30.0, max_retries=0
            )
        return self._clients[provider]

    async def complete(
        self,
        messages: Messages,
        *,
        json_mode: bool = False,
        use_cache: bool = True,
        max_tokens: int = 600,
        validator: Callable[[str], object] | None = None,
    ) -> LLMResult:
        if not self.chain:
            raise AllProvidersFailed("AGENT_MODELS is empty")
        errors: list[str] = []
        for i, (provider, model) in enumerate(self.chain):
            last = i == len(self.chain) - 1
            key = cache_key(f"{provider}:{model}:{json_mode}", messages)
            if use_cache and (hit := await self.cache.get(key)):
                return LLMResult(hit.text, hit.provider, hit.model, True, 0)
            try:
                client = self._client(provider)
            except AllProvidersFailed as e:
                errors.append(str(e))
                continue
            if not await self._buckets[provider].acquire(None if last else MAX_BUCKET_WAIT_S):
                errors.append(f"{provider}: local rate bucket empty")
                continue
            started = time.perf_counter()
            resp = None
            for attempt in range(LAST_PROVIDER_429_RETRIES + 1):
                try:
                    resp = await client.chat.completions.create(
                        model=model,
                        messages=messages,  # type: ignore[arg-type]
                        max_tokens=max_tokens,
                        temperature=0,
                        response_format={"type": "json_object"} if json_mode else openai.omit,
                    )
                    break
                except openai.RateLimitError as e:
                    if not last or attempt == LAST_PROVIDER_429_RETRIES:
                        errors.append(f"{provider}: RateLimitError")
                        break
                    await asyncio.sleep(_retry_after(e))
                except RETRYABLE as e:
                    errors.append(f"{provider}: {type(e).__name__}")
                    break
                except openai.BadRequestError as e:
                    # Groq rejects JSON-mode output that isn't valid JSON (400 json_validate_failed)
                    # and returns it as failed_generation: hand it to the caller's repair path.
                    failed = _failed_generation(e) if json_mode else None
                    if failed is None:
                        raise
                    ms = int((time.perf_counter() - started) * 1000)
                    return LLMResult(failed, provider, model, False, ms)
            if resp is None:
                continue
            text = resp.choices[0].message.content or ""
            if not text.strip():  # reasoning models can burn max_tokens and return nothing
                errors.append(f"{provider}: empty response")
                continue
            result = LLMResult(
                text, provider, model, False, int((time.perf_counter() - started) * 1000)
            )
            cacheable = use_cache
            if validator:  # never cache output the caller can't parse
                try:
                    validator(text)
                except ValidationError:
                    cacheable = False
            if cacheable:
                await self.cache.set(key, result)
            return result
        raise AllProvidersFailed("; ".join(errors))

    async def complete_json(
        self, messages: Messages, schema: type[T], *, use_cache: bool = True
    ) -> tuple[T, LLMResult]:
        """JSON-mode call validated against `schema`, with one repair retry (never cached)."""
        res = await self.complete(
            messages, json_mode=True, use_cache=use_cache, validator=schema.model_validate_json
        )
        try:
            return schema.model_validate_json(res.text), res
        except ValidationError as err:
            repair = [
                *messages,
                {"role": "assistant", "content": res.text},
                {
                    "role": "user",
                    "content": f"That was invalid: {err.errors()[:3]}. "
                    "Reply again with only valid JSON matching the schema.",
                },
            ]
            res = await self.complete(repair, json_mode=True, use_cache=False)
            return schema.model_validate_json(res.text), res  # still invalid -> caller fails closed


async def _smoke() -> None:
    """`python -m aegis.llm`: one call per configured provider (INF gate)."""
    for provider, model in parse_chain(settings.agent_models):
        router = LLMRouter(Settings(agent_models=f"{provider}:{model}"))
        try:
            r = await router.complete(
                [{"role": "user", "content": "Reply with the single word: pong"}], max_tokens=300
            )
            print(f"OK   {provider}:{model} {r.latency_ms}ms -> {r.text.strip()[:40]!r}")
        except Exception as e:  # smoke script: report everything
            print(f"FAIL {provider}:{model} {type(e).__name__}: {e}")


if __name__ == "__main__":
    asyncio.run(_smoke())
