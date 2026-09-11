"""Tests for the notification abstraction (Phase 5.5, docs/01 §6).

Everything runs against a deterministic in-memory fake provider — by
construction no test touches the network (the package itself is also
scanned for forbidden network/SDK imports below). The fake lives only in
this test module; production code paths never import it.
"""

import asyncio
import dataclasses
import inspect
from collections.abc import Awaitable, Callable
from pathlib import Path

import pytest

from app.notifications import (
    InvalidNotificationError,
    NotificationChannel,
    NotificationDispatcher,
    NotificationMessage,
    NotificationRecipient,
    NotificationResult,
    NotificationRejectedError,
    ProviderUnavailableError,
    UnsupportedChannelError,
)

# --- Deterministic fake provider (test-only, never registered in prod) ---


class FakeNotificationProvider:
    """Records notifications instead of delivering them.

    Configurable outcome: success (with a fixed external id), a domain
    rejection, unavailability, or an unexpected crash — so the dispatcher's
    normalization can be exercised without any external service.
    """

    def __init__(
        self,
        *,
        channel: NotificationChannel = NotificationChannel.TELEGRAM,
        external_message_id: str = "fake-msg-1",
        outcome: str = "success",
        error: Exception | None = None,
    ) -> None:
        self._channel = channel
        self._external_message_id = external_message_id
        self._outcome = outcome
        self._error = error
        self.sent: list[NotificationMessage] = []

    @property
    def channel(self) -> NotificationChannel:
        return self._channel

    async def send(self, message: NotificationMessage) -> NotificationResult:
        self.sent.append(message)
        if self._outcome == "reject":
            assert isinstance(self._error, Exception)
            raise self._error
        if self._outcome == "unavailable":
            raise ProviderUnavailableError("fake provider offline")
        if self._outcome == "crash":
            raise RuntimeError("provider internal bug")
        return NotificationResult(
            success=True,
            channel=self._channel,
            external_message_id=self._external_message_id,
        )


def run(coro: Callable[[], Awaitable[object]]) -> object:
    """Run one coroutine to completion (the suite is otherwise sync — no
    extra async test infrastructure is needed for this package)."""
    return asyncio.run(coro())


def make_message(
    channel: NotificationChannel = NotificationChannel.TELEGRAM,
    address: str = "12345",
    **overrides: object,
) -> NotificationMessage:
    recipient = NotificationRecipient(channel=channel, address=address)
    defaults: dict[str, object] = {
        "recipient": recipient,
        "text": "Event created",
        "category": "event",
    }
    defaults.update(overrides)
    return NotificationMessage(**defaults)  # type: ignore[arg-type]


# --- 1/7/8. successful send, normalized channel, preserved external id ---


def test_fake_provider_sends_successfully() -> None:
    provider = FakeNotificationProvider()
    dispatcher = NotificationDispatcher({"telegram": provider})

    result = run(lambda: dispatcher.send(make_message()))

    assert result == NotificationResult(
        success=True,
        channel=NotificationChannel.TELEGRAM,
        external_message_id="fake-msg-1",
    )


def test_result_channel_is_the_normalized_channel() -> None:
    bale = FakeNotificationProvider(channel=NotificationChannel.BALE)
    dispatcher = NotificationDispatcher({"bale": bale})

    result = run(lambda: dispatcher.send(make_message(NotificationChannel.BALE)))

    assert result.success is True
    assert result.channel == "bale"  # StrEnum compares equal to its value


def test_external_message_id_is_preserved() -> None:
    provider = FakeNotificationProvider(external_message_id="ext-42")
    dispatcher = NotificationDispatcher({"telegram": provider})

    result = run(lambda: dispatcher.send(make_message()))

    assert result.external_message_id == "ext-42"


# --- 2/9. routing and multi-provider coexistence ---------------------------


def test_dispatcher_routes_to_the_provider_of_the_channel() -> None:
    telegram = FakeNotificationProvider(channel=NotificationChannel.TELEGRAM)
    bale = FakeNotificationProvider(channel=NotificationChannel.BALE)
    dispatcher = NotificationDispatcher(
        {"telegram": telegram, "bale": bale}
    )

    run(lambda: dispatcher.send(make_message(NotificationChannel.BALE, "b-addr")))

    assert bale.sent and bale.sent[0].recipient.address == "b-addr"
    assert telegram.sent == []  # only the bale provider was touched


def test_multiple_providers_coexist_and_register_later() -> None:
    telegram = FakeNotificationProvider(channel=NotificationChannel.TELEGRAM)
    dispatcher = NotificationDispatcher()
    assert dispatcher.has_provider(NotificationChannel.TELEGRAM) is False

    dispatcher.register(telegram)
    bale = FakeNotificationProvider(channel=NotificationChannel.BALE)
    dispatcher.register(bale)

    results = run(
        lambda: dispatcher.send_many(
            [
                make_message(NotificationChannel.TELEGRAM, "t-1"),
                make_message(NotificationChannel.BALE, "b-1"),
            ]
        )
    )
    assert [r.success for r in results] == [True, True]
    assert [r.channel for r in results] == ["telegram", "bale"]
    assert [m.recipient.address for m in telegram.sent] == ["t-1"]
    assert [m.recipient.address for m in bale.sent] == ["b-1"]


def test_duplicate_channel_registration_is_rejected() -> None:
    dispatcher = NotificationDispatcher(
        {"telegram": FakeNotificationProvider()}
    )
    with pytest.raises(ValueError, match="already registered"):
        dispatcher.register(FakeNotificationProvider())


# --- 3/4. unknown channel / missing provider -------------------------------


def test_missing_provider_raises_unsupported_channel() -> None:
    dispatcher = NotificationDispatcher()  # nothing registered

    with pytest.raises(UnsupportedChannelError) as excinfo:
        run(lambda: dispatcher.send(make_message()))

    assert "telegram" in str(excinfo.value)
    assert excinfo.value.channel == "telegram"


def test_send_many_reports_unsupported_channel_for_that_message() -> None:
    dispatcher = NotificationDispatcher(
        {"telegram": FakeNotificationProvider()}
    )

    with pytest.raises(UnsupportedChannelError):
        run(
            lambda: dispatcher.send_many(
                [
                    make_message(NotificationChannel.TELEGRAM),
                    make_message(NotificationChannel.BALE),  # no bale provider
                ]
            )
        )


# --- 5/6/13. provider failures are normalized, never swallowed -------------


def test_provider_rejection_is_normalized() -> None:
    provider = FakeNotificationProvider(
        outcome="reject",
        error=NotificationRejectedError(
            "address not known to provider", error_code="recipient_invalid"
        ),
    )
    dispatcher = NotificationDispatcher({"telegram": provider})

    result = run(lambda: dispatcher.send(make_message()))

    assert result == NotificationResult(
        success=False,
        channel=NotificationChannel.TELEGRAM,
        error_code="recipient_invalid",
        error_message="address not known to provider",
    )


def test_provider_unavailable_is_normalized() -> None:
    provider = FakeNotificationProvider(outcome="unavailable")
    dispatcher = NotificationDispatcher({"telegram": provider})

    result = run(lambda: dispatcher.send(make_message()))

    assert result.success is False
    assert result.error_code == "provider_unavailable"


def test_unexpected_provider_exception_is_normalized_not_swallowed() -> None:
    provider = FakeNotificationProvider(outcome="crash")
    dispatcher = NotificationDispatcher({"telegram": provider})

    result = run(lambda: dispatcher.send(make_message()))

    # The failure surfaces in the result — with the crash on record, not
    # turned into a success and not raised past the dispatcher.
    assert result.success is False
    assert result.error_code == "provider_error"
    assert "RuntimeError" in (result.error_message or "")
    assert provider.sent  # the provider *was* asked


# --- 10. no provider-specific details in the generic result contract -------


def test_result_contract_has_no_provider_specific_fields() -> None:
    fields = {f.name for f in dataclasses.fields(NotificationResult)}
    assert fields == {
        "success",
        "channel",
        "external_message_id",
        "error_code",
        "error_message",
    }
    # No raw provider payload, token, or API response can ride along.
    for forbidden in ("payload", "raw", "response", "token", "secret", "api_key"):
        assert forbidden not in fields


# --- 11. notification input validation -------------------------------------


@pytest.mark.parametrize(
    "kwargs",
    [
        {"text": "   "},  # whitespace-only text
        {"category": ""},  # empty category
    ],
)
def test_invalid_message_is_rejected_at_construction(kwargs: object) -> None:
    with pytest.raises(InvalidNotificationError):
        make_message(**kwargs)  # type: ignore[arg-type]


def test_invalid_recipient_address_is_rejected() -> None:
    with pytest.raises(InvalidNotificationError):
        NotificationRecipient(
            channel=NotificationChannel.TELEGRAM, address="  "
        )


def test_metadata_is_copied_not_aliased() -> None:
    meta = {"event_id": 7}
    message = make_message(metadata=meta)
    meta["event_id"] = 999  # caller mutates its dict afterwards

    assert message.metadata == {"event_id": 7}


# --- 12. recipient abstraction ----------------------------------------------


def test_recipient_is_channel_plus_opaque_address() -> None:
    recipient = NotificationRecipient(
        channel=NotificationChannel.BALE, address="whatever-bale-uses"
    )
    message = make_message(
        recipient=recipient,
        text="hello",
        category="event",
    )

    # The address stays opaque; the channel is the only thing the generic
    # layer interprets.
    assert message.recipient.address == "whatever-bale-uses"
    assert message.channel is NotificationChannel.BALE
    assert message.channel == "bale"


# --- 14/24. no network, no credentials, no SDKs in the abstraction ----------

# Modules the notification layer must never depend on: network stacks,
# Telegram/Bale SDKs. The abstraction is the boundary that keeps them out.
FORBIDDEN_IMPORTS = {
    "httpx",
    "requests",
    "urllib",
    "http",
    "socket",
    "aiohttp",
    "telegram",
    "bale",
}


def _package_source_files() -> list[Path]:
    package_dir = Path(inspect.getfile(NotificationDispatcher)).parent
    return sorted(package_dir.glob("*.py"))


def test_notification_package_has_no_network_or_sdk_imports() -> None:
    files = _package_source_files()
    assert files, "expected the app/notifications package sources"
    for source in files:
        for line in source.read_text(encoding="utf-8").splitlines():
            code = line.strip()
            if not (code.startswith("import ") or code.startswith("from ")):
                continue  # only actual import statements matter
            for module in FORBIDDEN_IMPORTS:
                assert module not in code, (
                    f"{source.name} imports forbidden module "
                    f"'{module}' in the notification abstraction"
                )


def test_notification_models_carry_no_credential_fields() -> None:
    model_fields = {
        name
        for model in (NotificationRecipient, NotificationMessage)
        for name in (f.name for f in dataclasses.fields(model))
    }
    for forbidden in ("token", "secret", "api_key", "password"):
        assert forbidden not in model_fields
