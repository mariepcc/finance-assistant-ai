from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+asyncpg://postgres:postgres@127.0.0.1:54322/postgres"

    supabase_url: str = "http://127.0.0.1:54321"
    supabase_jwt_secret: str | None = None
    jwt_audience: str = "authenticated"

    cors_origins: list[str] = ["*"]
    default_currency: str = "PLN"


@lru_cache
def get_settings() -> Settings:
    return Settings()
