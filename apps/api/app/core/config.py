"""Application configuration loaded from environment variables.

Settings are read from the environment (and, for local development
convenience, from an `.env` file in the working directory). No credentials
are hard-coded; `apps/api/.env.example` documents the expected variables.
"""

from functools import lru_cache

from pydantic import Field, field_validator, model_validator
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

    # --- Cross-origin browser access (Phase 5.3) ---------------------------
    # The web app's browser code calls this API directly (auth login, /me,
    # authenticated business calls), so the API must answer CORS preflights
    # from the frontend origin. Comma-separated origins; production sets its
    # real frontend origin(s) here. Empty string disables CORS entirely.
    cors_allow_origins: str = (
        "http://localhost:3000,http://127.0.0.1:3000"
    )

    @property
    def cors_origins_list(self) -> list[str]:
        """Parsed non-empty origins from `cors_allow_origins`."""
        return [
            origin.strip()
            for origin in self.cors_allow_origins.split(",")
            if origin.strip()
        ]

    # --- Authentication (Phase 5; see .env.example) ----------------------
    # The secret MUST come from the environment — the placeholder default
    # below is intentionally unsafe and exists only so the application can
    # start for local development. authenticate() refuses to run with it
    # unless explicitly allowed, so production can never silently run on
    # the placeholder.
    auth_secret_key: str = "change-me-insecure-dev-placeholder"
    auth_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    # Allow the obviously-unsafe placeholder secret. Default True for the
    # development workflow; production sets this to 0/false.
    auth_allow_insecure_dev_secret: bool = True

    # --- Logging (Task 5.8; docs/01 §9) -----------------------------------
    # Root log level for the API and the background worker. Standard
    # Python levels only, case-insensitive; anything else is a
    # configuration error (never a silent fallback to a different level).
    log_level: str = "INFO"

    @field_validator("log_level")
    @classmethod
    def _log_level_is_standard(cls, value: str) -> str:
        normalized = value.strip().upper()
        valid = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
        if normalized not in valid:
            raise ValueError(
                f"log_level must be one of {', '.join(valid)} "
                f"(case-insensitive), got {value!r}"
            )
        return normalized

    # --- Notifications (Phase 5.6; docs/01 §6, .env.example) --------------
    # Provider bot tokens come from the environment and are NEVER committed.
    # A missing/empty token does not break startup or the other provider:
    # the factory still registers the provider, and it reports a
    # provider-unavailable failure only when a send is actually attempted.
    telegram_bot_token: str | None = None
    bale_bot_token: str | None = None
    # Bounded network time for one provider request, in seconds.
    notification_timeout_seconds: float = Field(default=10.0, gt=0)

    # --- Background notification delivery (Phase 5.7; docs/01 §6.5) -------
    # Redis backs the notification job queue. Like DATABASE_URL, a missing
    # Redis must NOT break importing or starting the API application — the
    # connection is made only when the queue/worker infrastructure starts
    # (app/worker), and failures surface at that point, not at import time.
    redis_url: str = "redis://localhost:6390/0"
    # Bounded retry policy for background notification delivery: how many
    # times a retryable failure (provider unavailable/unexpected error) is
    # re-attempted, and the exponential backoff between attempts
    # (base * 2^(n-2) for retry n, capped at the max delay). Rejected
    # notifications are never retried.
    notification_max_attempts: int = Field(default=5, ge=1)
    notification_retry_base_delay_seconds: float = Field(default=5.0, gt=0)
    notification_retry_max_delay_seconds: float = Field(default=300.0, gt=0)

    # --- Observability (Task 5.9; docs/01 §10) ----------------------------
    # The API process always exposes GET /metrics (no flag gymnastics —
    # protect at infrastructure level). The worker process serves no
    # HTTP, so its Prometheus metrics need an explicit port; 0 disables.
    worker_metrics_port: int = Field(default=0, ge=0, le=65535)

    @model_validator(mode="after")
    def _retry_delays_make_sense(self) -> "Settings":
        # A max delay below the base delay would make the backoff cap
        # contradictory — reject the configuration cleanly at load time.
        if self.notification_retry_max_delay_seconds < self.notification_retry_base_delay_seconds:
            raise ValueError(
                "notification_retry_max_delay_seconds must be greater than or "
                "equal to notification_retry_base_delay_seconds"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    """Return the cached Settings instance (one per process)."""
    return Settings()
