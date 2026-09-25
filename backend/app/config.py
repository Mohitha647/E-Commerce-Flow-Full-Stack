from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "CommerceFlow"
    environment: str = "development"

    # Defaults to local SQLite (async, via aiosqlite) so it runs with zero setup.
    # In docker-compose / production this is overridden to Postgres via asyncpg.
    database_url: str = "sqlite+aiosqlite:///./commerceflow.db"

    # Redis is used for caching (product listings/details) and is optional --
    # the cache layer falls back to a no-op in-memory stub if Redis is unreachable,
    # so the app still runs without Redis installed.
    redis_url: str = "redis://localhost:6379/0"
    cache_ttl_seconds: int = 60

    jwt_secret: str = "dev-secret-change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = 60 * 24

    cors_origins: list[str] = ["*"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
