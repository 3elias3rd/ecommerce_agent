from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./orders.db"

    redis_url: str = "redis://localhost:6379"
    state_ttl: int = 3600

    openai_api_key: str
    openai_model: str = "gpt-4o-mini"

    secret_key: str

    # Flat auth
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

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
