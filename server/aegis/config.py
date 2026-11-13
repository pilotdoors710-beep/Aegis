"""Environment-driven settings. Secrets come from env vars only (brief §9 rule 6)."""

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

# .env lives at the repo root (outside server/). Missing is fine: Docker injects real env vars.
ROOT_ENV = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT_ENV, extra="ignore")

    # Comma-separated origins allowed to call the API from a browser (the web app).
    cors_origins: str = "http://localhost:3000"
    # D4: what to do when a detector throws or times out.
    fail_mode: Literal["closed", "open"] = "closed"
    # Max paired runs executing at once (free-tier LLM quota + RAM).
    max_concurrent_runs: int = 1

    # LLM router (free tiers). AGENT_MODELS="gemini:<model>,groq:<model>,openrouter:<model>"
    # Model IDs are never hardcoded: verify them in each provider console (brief §3).
    agent_models: str = ""
    gemini_api_key: str = ""
    groq_api_key: str = ""
    # Extra accounts for the same provider: tried in order on a 429 before the next chain entry,
    # so a pinned model survives one key's tokens/day cap (separate quota, same model).
    groq_api_key_2: str = ""
    groq_api_key_3: str = ""
    openrouter_api_key: str = ""
    cerebras_api_key: str = ""
    # Requests/minute each provider may receive from us (stay under the free-tier cap).
    gemini_rpm: int = 4
    groq_rpm: int = 20
    openrouter_rpm: int = 15
    cerebras_rpm: int = 20

    # Where the agent's Chromium finds the Trap Arena (Vercel in production).
    arena_base_url: str = "http://localhost:3000/arena"
    # Ordinary action limit per run side.
    max_steps: int = 15
    # How long an ASK waits for a human before it times out (treated as deny).
    ask_timeout_s: int = 120
    # R2: total budget for both disposable copies of one consent trial (brief §3).
    trial_timeout_s: float = 10.0
    # Decision cache: off | fallback (only when every provider fails) | on. Eval forces off.
    # Default fallback: live runs make fresh decisions; replays only rescue a provider outage.
    llm_cache_mode: Literal["off", "fallback", "on"] = "fallback"
    # Supabase (server-side only; the web never gets these). Unset DB URL = in-memory store.
    supabase_db_url: str = ""
    supabase_url: str = ""
    supabase_service_key: str = ""
    # R2 disposable consent trials (gated research experiment, brief §3).
    r2_enabled: bool = False

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
