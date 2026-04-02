from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── Database ───────────────────────────────────────
    database_url: str = "sqlite:///./orders.db"

    # ── Redis ──────────────────────────────────────────
    redis_url: str = "redis://localhost:6379"
    state_ttl: int = 3600

    # ── OpenAI ─────────────────────────────────────────
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    router_timeout: int = 5          # seconds before LLM call is abandoned
    router_temperature: float = 0.0  # deterministic — extraction only

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()

# ── Module-level aliases (used by state.py and llm_router.py) ──
REDIS_URL = settings.redis_url
STATE_TTL = settings.state_ttl