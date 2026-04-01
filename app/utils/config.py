from pydantic_settings import BaseSettings, SettingsConfigDict
import os

class Settings(BaseSettings):
    database_url: str = "sqlite:///./orders.db"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

settings = Settings()

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
STATE_TTL  = int(os.getenv("STATE_TTL", 3600))