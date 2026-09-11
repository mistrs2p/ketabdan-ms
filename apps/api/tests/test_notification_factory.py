"""Tests for the notification factory/wiring and dispatcher integration
with the concrete Telegram/Bale providers (Task 5.6).

All HTTP goes through an in-memory ``httpx2.MockTransport`` injected via
the factory's test seam — no network, no credentials. Settings instances
are constructed with explicit values so the developer's local ``.env``
can never influence these tests.
"""

import asyncio
from collections.abc import Awaitable, Callable

import pytest
from httpx2 import MockTransport, Request, Response

from app.core.config import Settings
from app.notifications import (
    NotificationChannel,
    NotificationDispatcher,
    NotificationMessage,
    NotificationRecipient,
    NotificationResult,
    UnsupportedChannelError,
)
from app.notifications.factory import build_notification_dispatcher

TELEGRAM_TOKEN = "1100000001:AA-test-telegram-token-never-real"
BALE_TOKEN = "2200000002:AA-test-bale-token-never-real"

SUCCESS_TELEGRAM = {"ok": True, "result": {"message_id": 11}}
SUCCESS_BALE = {"ok": True, "result": {"message_id": 22}}


def run(coro: Callable[[], Awaitable[object]]) -> object:
    return asyncio.run(coro())


def make_message(channel: NotificationChannel, address: str = "100") -> NotificationMessage:
    return NotificationMessage(
        recipient=NotificationRecipient(channel=channel, address=address),
        text="سلام — event update",
        category="event",
    )


def ok_transport():
    """A mock transport answering both providers' endpoints correctly."""
    requests: list[Request] = []

    def handler(request: Request) -> Response:
        requests.append(request)
        url = str(request.url)
        if url.startswith("https://api.telegram.org/bot"):
            return Response(200, json=SUCCESS_TELEGRAM)
        if url.startswith("https://tapi.bale.ai/bot"):
            return Response(200, json=SUCCESS_BALE)
        raise AssertionError(f"unexpected request destination: {url.split('/bot')[0]}")

    return MockTransport(handler), requests


def build(settings: Settings):
    transport, requests = ok_transport()
    dispatcher = build_notification_dispatcher(settings, transport=transport)
    return dispatcher, requests


# --- application composition (task §25) -------------------------------------


def test_no_provider_configured_application_still_builds() -> None:
    dispatcher, _ = build(
        Settings(telegram_bot_token=None, bale_bot_token=None)
    )

    assert isinstance(dispatcher, NotificationDispatcher)
    # Both channels have a (token-less) provider — sends fail as
    # provider-unavailable, not as unknown-channel wiring errors.
    assert dispatcher.has_provider(NotificationChannel.TELEGRAM)
    assert dispatcher.has_provider(NotificationChannel.BALE)


def test_no_provider_configured_send_fails_with_configuration_error() -> None:
    dispatcher, _ = build(
        Settings(telegram_bot_token=None, bale_bot_token=None)
    )

    result = run(
        lambda: dispatcher.send(make_message(NotificationChannel.TELEGRAM))
    )

    assert result == NotificationResult(
        success=False,
        channel=NotificationChannel.TELEGRAM,
        error_code="provider_unavailable",
        error_message="Telegram provider is not configured: no bot token "
        "was provided (see TELEGRAM_BOT_TOKEN/BALE_BOT_TOKEN in "
        ".env.example)",
    )
    assert TELEGRAM_TOKEN not in str(result)


def test_telegram_only_telegram_works_bale_reports_unavailable() -> None:
    dispatcher, _ = build(
        Settings(telegram_bot_token=TELEGRAM_TOKEN, bale_bot_token=None)
    )

    telegram = run(
        lambda: dispatcher.send(make_message(NotificationChannel.TELEGRAM))
    )
    bale = run(lambda: dispatcher.send(make_message(NotificationChannel.BALE)))

    assert telegram.success is True
    assert telegram.external_message_id == "11"
    assert bale.success is False
    assert bale.error_code == "provider_unavailable"
    assert "not configured" in (bale.error_message or "")


def test_bale_only_bale_works_telegram_reports_unavailable() -> None:
    dispatcher, _ = build(
        Settings(telegram_bot_token=None, bale_bot_token=BALE_TOKEN)
    )

    bale = run(lambda: dispatcher.send(make_message(NotificationChannel.BALE)))
    telegram = run(
        lambda: dispatcher.send(make_message(NotificationChannel.TELEGRAM))
    )

    assert bale.success is True
    assert bale.external_message_id == "22"
    assert telegram.success is False
    assert telegram.error_code == "provider_unavailable"


def test_both_configured_both_work() -> None:
    dispatcher, requests = build(
        Settings(
            telegram_bot_token=TELEGRAM_TOKEN, bale_bot_token=BALE_TOKEN
        )
    )

    results = run(
        lambda: dispatcher.send_many(
            [
                make_message(NotificationChannel.TELEGRAM, "t-1"),
                make_message(NotificationChannel.BALE, "b-1"),
            ]
        )
    )

    assert [r.success for r in results] == [True, True]
    assert [r.external_message_id for r in results] == ["11", "22"]
    # Each provider was called on its own endpoint, authenticated with
    # its own token.
    assert str(requests[0].url) == (
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    )
    assert str(requests[1].url) == (
        f"https://tapi.bale.ai/bot{BALE_TOKEN}/sendMessage"
    )


def test_empty_string_token_counts_as_unconfigured() -> None:
    dispatcher, _ = build(
        Settings(telegram_bot_token="", bale_bot_token=BALE_TOKEN)
    )

    telegram = run(
        lambda: dispatcher.send(make_message(NotificationChannel.TELEGRAM))
    )

    assert telegram.success is False
    assert telegram.error_code == "provider_unavailable"


# --- dispatcher integration with the concrete providers (task §24) -----------


def test_dispatcher_returns_generic_results_only() -> None:
    dispatcher, _ = build(
        Settings(telegram_bot_token=TELEGRAM_TOKEN, bale_bot_token=BALE_TOKEN)
    )

    result = run(
        lambda: dispatcher.send(make_message(NotificationChannel.TELEGRAM))
    )

    # The business-facing value is exactly the Task 5.5 contract — no
    # provider type, no HTTP response, no endpoint details anywhere.
    assert type(result) is NotificationResult
    assert result.success is True
    assert result.channel == "telegram"
    assert result.external_message_id == "11"


def test_unknown_channel_is_a_wiring_error_not_a_delivery_failure() -> None:
    dispatcher, _ = build(
        Settings(telegram_bot_token=TELEGRAM_TOKEN, bale_bot_token=BALE_TOKEN)
    )

    # A channel no provider exists for is a wiring/programming error and
    # is raised (Task 5.5 semantics) — never silently normalized.
    message = NotificationMessage(
        recipient=NotificationRecipient(channel="signal", address="1"),  # type: ignore[arg-type]
        text="hello",
        category="event",
    )
    with pytest.raises(UnsupportedChannelError):
        run(lambda: dispatcher.send(message))


# --- settings validation -------------------------------------------------------


def test_notification_timeout_must_be_positive() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Settings(_env_file=None, notification_timeout_seconds=0)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, notification_timeout_seconds=-1)


def test_documented_defaults_when_no_environment_is_set() -> None:
    # _env_file=None: the developer's local .env must not influence this.
    settings = Settings(_env_file=None)
    assert settings.telegram_bot_token is None
    assert settings.bale_bot_token is None
    assert settings.notification_timeout_seconds == 10.0
