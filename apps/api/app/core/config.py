"""Application configuration loaded from environment variables.

Settings are read from the environment (and, for local development
convenience, from an `.env` file in the working directory). No credentials
are hard-coded; `apps/api/.env.example` documents the expected variables.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Ketabdaneh API settings.

    `database_url` is optional so that the application can start (and serve
    `/api/health`) without a database configured. Code that needs a database
    session must treat a missing `DATABASE_URL` as an explicit error at the
    point of use, not at import/startup time.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Example (see .env.example):
    # postgresql+psycopg://ketabdaneh:ketabdaneh_dev@localhost:5432/ketabdaneh
    database_url: str | None = None

    api_host: str = "0.0.0.0"
    api_port: int = 8000


@lru_cache
def get_settings() -> Settings:
    """Return the cached Settings instance (one per process)."""
    return Settings()
