"""Application configuration loaded from environment variables.

Settings are read from the environment (and, for local development
convenience, from an `.env` file in the working directory). No credentials
are hard-coded; `apps/api/.env.example` documents the expected variables.

Task 5.10 — configuration & secrets hardening (docs/01 §11):

- **APP_ENV** (`development` | `test` | `production`, case-insensitive,
  default `development`) selects the environment; production behavior is
  NEVER inferred from heuristics.
- **Secret-aware types**: every setting whose value is (or may embed) a
  credential — the JWT signing key, the bot tokens, and the DB/Redis
  URLs (they can carry `user:password@`) — is a `pydantic.SecretStr`.
  `repr()`/`str()` of Settings shows `**********`, and pydantic masks
  them in type-validation errors. Callers unwrap via
  `get_secret_value()` at the single point of use.
- **Fail-closed production validation**: in production a missing or
  placeholder JWT secret, a weak secret (<32 chars), the insecure-dev
  flag, a missing DATABASE_URL, an unset REDIS_URL (the localhost
  default is a development convenience only), or a wildcard CORS origin
  is a configuration error at startup — never a silent insecure default.
- **Value-free error messages**: configuration errors name the setting
  and the requirement; they never echo the offending value (which may
  be a secret). Our policy checks raise ``ConfigurationError`` (NOT
  ``ValueError``) precisely so pydantic never attaches the raw input to
  the error message — a ``ValueError`` from a validator is rendered by
  pydantic with an ``input_value=...`` suffix that can contain the
  secret itself; a non-ValueError propagates verbatim, clean.
- URL validation is **shape-only** (parse, scheme check) — connectivity
  is Task 5.9's readiness concern, not Settings'; no connection is made
  here.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

# The deliberately-unsafe development placeholder for AUTH_SECRET_KEY.
# Exists ONLY so the application can start for local development;
# authentication refuses to use it unless AUTH_ALLOW_INSECURE_DEV_SECRET
# is set, and production rejects it outright (see _production_requirements).
AUTH_SECRET_PLACEHOLDER = "change-me-insecure-dev-placeholder"

# Minimum length of a production AUTH_SECRET_KEY. 32 chars of entropy is
# comfortably beyond brute-force reach for an HS256 signing key while
# staying easy to generate, e.g. secrets.token_urlsafe(48) in a REPL.
AUTH_SECRET_MIN_LENGTH = 32

Environment = Literal["development", "test", "production"]


class ConfigurationError(RuntimeError):
    """A configuration value violates policy; the message is safe to log.

    Raised instead of ``ValueError`` so pydantic does not append the raw
    input value to the rendered error (see module docstring).
    """


class Settings(BaseSettings):
    """Ketabdaneh API settings.

    `database_url` is optional so that the application can start (and serve
    `/api/health`) without a database configured — outside production.
    Code that needs a database session must treat a missing `DATABASE_URL`
    as an explicit error at the point of use, not at import/startup time.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        # Never render the raw input value in validation errors (Task
        # 5.10 §20/§21): a rejected value may itself be a secret, and
        # pydantic's default ``input_value=...`` suffix would echo it
        # into logs/console at startup.
        hide_input_in_errors=True,
    )

    # --- Environment (Task 5.10; docs/01 §11) --------------------------------
    # Explicit, typed, validated. Never inferred (not from DEBUG, not from
    # hostname, not from anything else). Development keeps every documented
    # convenience; production fails closed.
    app_env: Environment = "development"

    @field_validator("app_env", mode="before")
    @classmethod
    def _app_env_case_insensitive(cls, value: object) -> object:
        # "PRODUCTION"/"Production"/"production" all mean production —
        # predictable, and a typo'd value still fails validation below.
        if isinstance(value, str):
            return value.strip().lower()
        return value

    # Non-secret runtime configuration.
    database_url: SecretStr | None = None

    # Binding all interfaces is REQUIRED in the container runtime (the
    # API is reached through the Docker network, never exposed directly —
    # docs/01 §12): a loopback bind would make it unreachable from the
    # proxy/other containers. Exposure is controlled by Docker networking
    # (only Caddy publishes host ports, docs/12 §3), not by this bind.
    # (nosec marker: B104 is a false positive here, per the rationale above)
    api_host: str = "0.0.0.0"  # nosec B104
    api_port: int = 8000

    # --- Cross-origin browser access (Phase 5.3) ---------------------------
    # The web app's browser code calls this API directly (auth login, /me,
    # authenticated business calls), so the API must answer CORS preflights
    # from the frontend origin. Comma-separated origins; production sets its
    # real frontend origin(s) here. Empty string disables CORS entirely.
    # Wildcard ("*") is rejected in production (docs/01 §11).
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
    # start for local development. Authentication refuses the placeholder
    # unless explicitly allowed, and production Settings validation rejects
    # it (and any too-short secret) outright. SecretStr: never in repr(),
    # never in validation errors.
    auth_secret_key: SecretStr = SecretStr(AUTH_SECRET_PLACEHOLDER)
    auth_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    # Allow the obviously-unsafe placeholder secret. Default True for the
    # development workflow; production MUST NOT enable it (rejected by
    # _production_requirements whatever the value of the secret itself).
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
    # SecretStr (pydantic coerces plain strings, so callers pass strings);
    # the factory unwraps at the single point of use.
    telegram_bot_token: SecretStr | None = None
    bale_bot_token: SecretStr | None = None
    # Bounded network time for one provider request, in seconds.
    notification_timeout_seconds: float = Field(default=10.0, gt=0)

    # --- Background notification delivery (Phase 5.7; docs/01 §6.5) -------
    # Redis backs the notification job queue. Like DATABASE_URL, a missing
    # Redis must NOT break importing or starting the API application — the
    # connection is made only when the queue/worker infrastructure starts
    # (app/worker), and failures surface at that point, not at import time.
    # The localhost default is a development convenience; production must
    # set REDIS_URL explicitly (checked in _production_requirements).
    # SecretStr: the URL may embed credentials.
    redis_url: SecretStr = SecretStr("redis://localhost:6390/0")
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

    # --- URL / origin shape validation (no connections are made here) ------
    # All raise ConfigurationError (not ValueError) so pydantic never
    # attaches the raw — possibly credential-bearing — value to the
    # rendered error (see module docstring).

    @model_validator(mode="after")
    def _urls_and_origins_well_formed(self) -> "Settings":
        if self.database_url is not None:
            try:
                make_url(self.database_url.get_secret_value())
            except Exception as exc:
                raise ConfigurationError(
                    "DATABASE_URL is invalid (expected a SQLAlchemy URL "
                    "such as postgresql+psycopg://user:password@host:port/"
                    "database); the value is not repeated here"
                ) from exc

        from urllib.parse import urlsplit

        redis_parts = urlsplit(self.redis_url.get_secret_value())
        if redis_parts.scheme not in ("redis", "rediss", "unix") or not (
            redis_parts.netloc or redis_parts.path
        ):
            raise ConfigurationError(
                "REDIS_URL is invalid (expected redis://host:port/db, "
                "rediss://… or unix:///path); the value is not repeated here"
            )

        for origin in self.cors_origins_list:
            if origin == "*":
                continue  # tolerated outside production; checked below
            parts = urlsplit(origin)
            if parts.scheme not in ("http", "https") or not parts.netloc:
                raise ConfigurationError(
                    "CORS_ALLOW_ORIGINS entries must be http(s) URLs such "
                    "as http://localhost:3000; got an entry that is not "
                    "(the value is not repeated here)"
                )
        return self

    # --- Cross-field policy ---------------------------------------------------

    @model_validator(mode="after")
    def _retry_delays_make_sense(self) -> "Settings":
        # A max delay below the base delay would make the backoff cap
        # contradictory — reject the configuration cleanly at load time.
        if self.notification_retry_max_delay_seconds < self.notification_retry_base_delay_seconds:
            raise ConfigurationError(
                "notification_retry_max_delay_seconds must be greater than "
                "or equal to notification_retry_base_delay_seconds"
            )
        return self

    @model_validator(mode="after")
    def _production_requirements(self) -> "Settings":
        """Fail closed: production must never run on insecure defaults.

        Each check names the setting and the requirement — never the
        value (which may itself be a secret that must not reach logs).
        """
        if self.app_env != "production":
            return self

        if self.auth_allow_insecure_dev_secret:
            raise ConfigurationError(
                "AUTH_ALLOW_INSECURE_DEV_SECRET must not be enabled in "
                "production (it permits signing tokens with the public "
                "development placeholder secret)"
            )

        secret = self.auth_secret_key.get_secret_value()
        if secret == AUTH_SECRET_PLACEHOLDER:
            raise ConfigurationError(
                "AUTH_SECRET_KEY is the development placeholder; production "
                "requires a real secret (see apps/api/.env.example)"
            )
        if len(secret) < AUTH_SECRET_MIN_LENGTH:
            raise ConfigurationError(
                f"AUTH_SECRET_KEY must be at least {AUTH_SECRET_MIN_LENGTH} "
                "characters in production (generate one with "
                "secrets.token_urlsafe(48) in a Python REPL)"
            )

        if self.database_url is None:
            raise ConfigurationError(
                "DATABASE_URL is required in production "
                "(it is optional only in development/test)"
            )

        if "redis_url" not in self.model_fields_set:
            raise ConfigurationError(
                "REDIS_URL must be set explicitly in production "
                "(the localhost default is a development convenience only)"
            )

        if "*" in self.cors_origins_list:
            raise ConfigurationError(
                'CORS_ALLOW_ORIGINS must not contain "*" in production — '
                "list the real frontend origin(s) explicitly"
            )

        return self


@lru_cache
def get_settings() -> Settings:
    """Return the cached Settings instance (one per process)."""
    return Settings()
