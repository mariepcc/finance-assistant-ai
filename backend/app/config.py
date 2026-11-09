from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+asyncpg://postgres:postgres@127.0.0.1:54322/postgres"

    supabase_url: str = "http://127.0.0.1:54321"
    supabase_jwt_secret: str | None = None
    jwt_audience: str = "authenticated"

    cors_origins: list[str] = ["*"]
    default_currency: str = "PLN"

    anthropic_api_key: SecretStr | None = None
    mcp_url: str = "http://127.0.0.1:8001/mcp"
    router_model: str = "claude-haiku-5-5"
    worker_model: str = "claude-haiku-5-5"
    editor_model: str = "claude-haiku-5-5"
    router_effort: str = "low"
    worker_effort: str = "medium"
    agent_max_steps: int = 6
    agent_timeout_s: float = 60.0
    chat_history_limit: int = 6

    @property
    def jwt_issuer(self) -> str:
        return f"{self.supabase_url.rstrip('/')}/auth/v1"

    @property
    def jwks_uri(self) -> str:
        return f"{self.jwt_issuer}/.well-known/jwks.json"


@lru_cache
def get_settings() -> Settings:
    return Settings()
