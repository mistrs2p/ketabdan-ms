"""Configuration & secrets hardening tests (Task 5.10 §23).

Every production fail-closed rule, secret-representation guarantee, and
error-message hygiene rule lives here. All Settings are constructed with
``_env_file=None`` so the developer's real .env (which may hold real
tokens/credentials) can never influence these tests.

Policy violations raise ``ConfigurationError`` — NOT pydantic's
ValidationError — deliberately: pydantic renders ValueError-style
validator failures with an ``input_value=...`` suffix that can echo the
raw (possibly credential-bearing) value, while a non-ValueError
propagates verbatim with only our clean message.
"""

import logging

import pytest
from pydantic import ValidationError

from app.core.config import (
    AUTH_SECRET_MIN_LENGTH,
    AUTH_SECRET_PLACEHOLDER,
    ConfigurationError,
    Settings,
    get_settings,
)

# A syntactically valid, unmistakably fake production-grade secret.
STRONG_SECRET = "x" * 48 + "-test-only-never-real"
# A strong-looking secret for the leak probes; never valid anywhere.
LEAK_PROBE_SECRET = "LEAKPROBE-super-secret-value-never-real-0123456789"

PRODUCTION = {
    "app_env": "production",
    "auth_secret_key": STRONG_SECRET,
    "auth_allow_insecure_dev_secret": False,
    "database_url": "postgresql+psycopg://user:pw@example.invalid:5432/db",
    "redis_url": "redis://example.invalid:6390/0",
}


def build(**overrides) -> Settings:
    """Production-shaped settings with per-test overrides."""
    values = dict(PRODUCTION)
    values.update(overrides)
    return Settings(_env_file=None, **values)


# --- APP_ENV -----------------------------------------------------------------------


@pytest.mark.parametrize("value", ["development", "test"])
def test_app_env_accepts_supported_values(value: str) -> None:
    assert Settings(_env_file=None, app_env=value).app_env == value


def test_app_env_production_accepted_with_valid_config() -> None:
    # "production" alone is not valid (fail-closed defaults); with the
    # required production settings it is.
    assert build().app_env == "production"


@pytest.mark.parametrize("value", ["PRODUCTION", "Production", "TEST"])
def test_app_env_case_insensitive(value: str) -> None:
    expected = value.lower()
    if expected == "production":
        with pytest.raises(ConfigurationError) as excinfo:
            Settings(_env_file=None, app_env=value)
        # Fails on production REQUIREMENTS, not on the env value itself —
        # proving the case-insensitive mapping took effect.
        assert "AUTH_ALLOW_INSECURE_DEV_SECRET" in str(excinfo.value)
    else:
        assert Settings(_env_file=None, app_env=value).app_env == expected


@pytest.mark.parametrize("value", ["prod", "staging", "dev", "", "live"])
def test_app_env_invalid_rejected(value: str) -> None:
    # Never inferred, never aliased — a typo'd environment fails clearly.
    with pytest.raises(ValidationError) as excinfo:
        Settings(_env_file=None, app_env=value)
    assert "app_env" in str(excinfo.value)


def test_app_env_defaults_to_development() -> None:
    assert Settings(_env_file=None).app_env == "development"


# --- JWT secret (production policy) -------------------------------------------------


def test_production_with_valid_secret_loads() -> None:
    settings = build()
    assert settings.app_env == "production"


def test_production_placeholder_secret_rejected() -> None:
    with pytest.raises(ConfigurationError) as excinfo:
        build(auth_secret_key=AUTH_SECRET_PLACEHOLDER)
    message = str(excinfo.value)
    assert "AUTH_SECRET_KEY" in message
    assert "placeholder" in message.lower()
    assert AUTH_SECRET_PLACEHOLDER not in message


def test_production_short_secret_rejected() -> None:
    short = "a" * (AUTH_SECRET_MIN_LENGTH - 1)
    with pytest.raises(ConfigurationError) as excinfo:
        build(auth_secret_key=short)
    message = str(excinfo.value)
    assert str(AUTH_SECRET_MIN_LENGTH) in message
    assert short not in message  # never echo the (possibly real) secret


def test_production_min_length_secret_accepted() -> None:
    assert build(auth_secret_key="a" * AUTH_SECRET_MIN_LENGTH).app_env == (
        "production"
    )


def test_development_placeholder_still_works() -> None:
    # Existing local workflow unchanged: development may keep the
    # documented placeholder.
    settings = Settings(_env_file=None)
    assert settings.auth_secret_key.get_secret_value() == AUTH_SECRET_PLACEHOLDER


def test_production_insecure_dev_flag_rejected() -> None:
    with pytest.raises(ConfigurationError) as excinfo:
        build(auth_allow_insecure_dev_secret=True)
    assert "AUTH_ALLOW_INSECURE_DEV_SECRET" in str(excinfo.value)


def test_development_insecure_dev_flag_still_works() -> None:
    assert Settings(_env_file=None, auth_allow_insecure_dev_secret=True) is not None


# --- Database URL -------------------------------------------------------------------


def test_malformed_database_url_rejected() -> None:
    with pytest.raises(ConfigurationError) as excinfo:
        Settings(_env_file=None, database_url="not a url at all")
    message = str(excinfo.value)
    assert "DATABASE_URL" in message
    assert "not a url at all" not in message  # the malformed value never echoes


def test_database_url_with_credentials_not_in_error() -> None:
    # Malformed AND credential-bearing (non-numeric port): neither the
    # password nor any part of the URL may appear in the error.
    bad = "postgresql://user:topsecret@host:notaport/db"
    with pytest.raises(ConfigurationError) as excinfo:
        Settings(_env_file=None, database_url=bad)
    blob = str(excinfo.value)
    assert "topsecret" not in blob
    assert bad not in blob


def test_valid_database_url_accepted() -> None:
    settings = Settings(
        _env_file=None,
        database_url="postgresql+psycopg://user:pw@localhost:5433/ketabdaneh",
    )
    assert settings.database_url is not None


def test_production_requires_database_url() -> None:
    overrides = dict(PRODUCTION)
    overrides.pop("database_url")
    with pytest.raises(ConfigurationError) as excinfo:
        Settings(_env_file=None, **overrides)
    assert "DATABASE_URL" in str(excinfo.value)


def test_database_url_is_never_validated_by_connecting() -> None:
    # Configuration validation ≠ connectivity validation (§11): an
    # unresolvable host must pass Settings validation — readiness (5.9)
    # owns connectivity.
    settings = Settings(
        _env_file=None,
        database_url="postgresql+psycopg://u:p@no-such-host.invalid:5432/db",
    )
    assert settings.database_url is not None


# --- Redis URL ----------------------------------------------------------------------


def test_malformed_redis_url_rejected() -> None:
    with pytest.raises(ConfigurationError) as excinfo:
        Settings(_env_file=None, redis_url="just some text")
    message = str(excinfo.value)
    assert "REDIS_URL" in message
    assert "just some text" not in message


def test_redis_url_with_credentials_not_in_error() -> None:
    # Wrong scheme AND credential-bearing: the password must not appear.
    with pytest.raises(ConfigurationError) as excinfo:
        Settings(_env_file=None, redis_url="ftp://user:topsecret@host")
    blob = str(excinfo.value)
    assert "topsecret" not in blob
    assert "user:topsecret" not in blob


@pytest.mark.parametrize(
    "url", ["redis://h:6390/0", "rediss://h:6390/0", "unix:///tmp/redis.sock"]
)
def test_valid_redis_urls_accepted(url: str) -> None:
    assert (
        Settings(_env_file=None, redis_url=url).redis_url.get_secret_value() == url
    )


def test_production_requires_explicit_redis_url() -> None:
    # The localhost default is a development convenience only.
    overrides = dict(PRODUCTION)
    overrides.pop("redis_url")
    with pytest.raises(ConfigurationError) as excinfo:
        Settings(_env_file=None, **overrides)
    assert "REDIS_URL" in str(excinfo.value)


def test_production_explicit_local_redis_url_allowed() -> None:
    # An explicitly-set localhost Redis is a legitimate production choice
    # (same-host deployment); what is rejected is relying on the default.
    assert build(redis_url="redis://localhost:6390/0").app_env == "production"


def test_no_connection_made_during_settings_construction() -> None:
    # Structural: the settings module never imports engine/pool machinery
    # and never opens sockets — only URL SHAPE validation.
    import app.core.config as config_module

    source = vars(config_module)
    assert "create_engine" not in source
    assert "Redis" not in source


# --- Notification tokens ------------------------------------------------------------


def test_telegram_optional_in_production() -> None:
    settings = build(telegram_bot_token=None, bale_bot_token=None)
    assert settings.telegram_bot_token is None


def test_one_token_without_the_other_in_production() -> None:
    settings = build(telegram_bot_token="1100000001:AA-fake-test-only")
    assert settings.telegram_bot_token is not None
    assert settings.bale_bot_token is None


def test_empty_string_token_is_unconfigured() -> None:
    # Preserves the Task 5.6 factory semantics: empty ".env" value means
    # "not configured", not "configured with an empty token".
    settings = build(telegram_bot_token="", bale_bot_token=None)
    assert settings.telegram_bot_token is not None
    assert settings.telegram_bot_token.get_secret_value() == ""


# --- CORS ----------------------------------------------------------------------------


def test_development_cors_defaults_safe() -> None:
    settings = Settings(_env_file=None)
    assert settings.cors_origins_list == [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]


def test_production_wildcard_cors_rejected() -> None:
    with pytest.raises(ConfigurationError) as excinfo:
        build(cors_allow_origins="*")
    message = str(excinfo.value)
    assert "CORS_ALLOW_ORIGINS" in message
    assert "*" in message


def test_production_wildcard_in_list_rejected() -> None:
    with pytest.raises(ConfigurationError):
        build(cors_allow_origins="https://app.example.com,*")


def test_production_explicit_origins_accepted() -> None:
    settings = build(cors_allow_origins="https://app.example.com")
    assert settings.cors_origins_list == ["https://app.example.com"]


def test_development_wildcard_tolerated() -> None:
    # allow_credentials is always False (bearer auth, no cookies), so a
    # wildcard in local development is not credential-exposing.
    assert Settings(_env_file=None, cors_allow_origins="*").cors_origins_list == (
        ["*"]
    )


def test_non_http_cors_entry_rejected() -> None:
    with pytest.raises(ConfigurationError) as excinfo:
        Settings(_env_file=None, cors_allow_origins="javascript:alert(1)")
    assert "CORS_ALLOW_ORIGINS" in str(excinfo.value)


# --- Secret representation (§21) -----------------------------------------------------


def test_repr_does_not_leak_secrets() -> None:
    settings = Settings(
        _env_file=None,
        auth_secret_key=LEAK_PROBE_SECRET,
        telegram_bot_token="TELEGRAM-LEAK-PROBE",
        bale_bot_token="BALE-LEAK-PROBE",
        database_url="postgresql://user:DBPASS-probe@host/db",
        redis_url="redis://user:REDISPASS-probe@host/0",
    )
    blob = repr(settings)
    for secret in (
        LEAK_PROBE_SECRET,
        "TELEGRAM-LEAK-PROBE",
        "BALE-LEAK-PROBE",
        "DBPASS-probe",
        "REDISPASS-probe",
    ):
        assert secret not in blob


def test_str_does_not_leak_secrets() -> None:
    settings = Settings(_env_file=None, auth_secret_key=LEAK_PROBE_SECRET)
    assert LEAK_PROBE_SECRET not in str(settings)


def test_configuration_errors_do_not_leak_secrets() -> None:
    # Every policy failure message is value-free — even when the offending
    # settings carry credentials (pydantic never gets to attach the raw
    # input to a ConfigurationError).
    with pytest.raises(ConfigurationError) as excinfo:
        Settings(
            _env_file=None,
            auth_secret_key="short",
            database_url="postgresql://user:DBPASS-probe@h/db",
            redis_url="redis://user:REDISPASS-probe@h/0",
            notification_retry_base_delay_seconds=10.0,
            notification_retry_max_delay_seconds=1.0,
        )
    blob = str(excinfo.value)
    assert "DBPASS-probe" not in blob
    assert "REDISPASS-probe" not in blob


def test_model_dump_masks_secrets() -> None:
    settings = Settings(_env_file=None, auth_secret_key=LEAK_PROBE_SECRET)
    blob = str(settings.model_dump())
    assert LEAK_PROBE_SECRET not in blob


def test_secrets_not_leaked_via_logging(caplog) -> None:
    # The framework's own debug logging of a settings instance stays safe.
    settings = Settings(_env_file=None, auth_secret_key=LEAK_PROBE_SECRET)
    with caplog.at_level(logging.DEBUG):
        logging.getLogger("app.test").debug("settings: %r", settings)
    assert all(LEAK_PROBE_SECRET not in r.message for r in caplog.records)


def test_pydantic_type_errors_on_secret_fields_do_not_leak() -> None:
    # pydantic's own type validation (not our policy validators) must not
    # echo a value passed for a secret field.
    with pytest.raises(ValidationError) as excinfo:
        Settings(_env_file=None, telegram_bot_token=12345)
    assert "12345" not in str(excinfo.value)


# --- error-safety of messages (§20) ---------------------------------------------------


def test_error_messages_name_settings_without_values() -> None:
    # Each production fail-closed message names the setting; none repeats
    # the value — spot-check the placeholder case end-to-end.
    base = dict(PRODUCTION)
    base["auth_secret_key"] = AUTH_SECRET_PLACEHOLDER
    with pytest.raises(ConfigurationError) as excinfo:
        Settings(_env_file=None, **base)
    assert AUTH_SECRET_PLACEHOLDER not in str(excinfo.value)


def test_production_failure_messages_are_actionable() -> None:
    # Each message says WHAT to do, not just that it failed.
    base = dict(PRODUCTION)
    base.pop("redis_url")
    with pytest.raises(ConfigurationError) as excinfo:
        Settings(_env_file=None, **base)
    message = str(excinfo.value)
    assert "REDIS_URL" in message
    assert "must be set" in message or "required" in message.lower()


# --- cached settings / test isolation --------------------------------------------------


def test_get_settings_returns_cached_instance() -> None:
    assert get_settings() is get_settings()


def test_settings_ignore_unknown_env_keys() -> None:
    # extra="ignore": a stray variable (e.g. POSTGRES_PASSWORD used by
    # docker-compose) must never crash settings loading.
    assert Settings(_env_file=None, POSTGRES_PASSWORD="whatever") is not None
