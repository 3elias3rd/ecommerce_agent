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
    router_timeout: int = 5
    router_temperature: float = 0.0

    # ── Auth ───────────────────────────────────────────
    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 480

    # Per-user credentials — set as flat env vars to avoid
    # JSON quote/$ mangling on deployment platforms like Koyeb.
    # Format: AUTH_USER_1=username, AUTH_PASS_1=bcrypt_hash
    # Supports up to 10 users (add more pairs if needed)
    auth_user_1: str = ""
    auth_pass_1: str = ""
    auth_user_2: str = ""
    auth_pass_2: str = ""
    auth_user_3: str = ""
    auth_pass_3: str = ""
    auth_user_4: str = ""
    auth_pass_4: str = ""
    auth_user_5: str = ""
    auth_pass_5: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Benchmarking ───────────────────────────────────────
    # Set ENABLE_TIMING=true to log per-layer response times.
    # Toggle on for benchmarking, off for normal operation.
    enable_timing: bool = False

settings = Settings()

# ── Module-level aliases ───────────────────────────────────────
REDIS_URL = settings.redis_url
STATE_TTL  = settings.state_ttl