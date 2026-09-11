"""Tests for the retry policy and the worker's delivery classification
(Task 5.7) — success, retryable, permanent, backoff, retry-after,
max-attempt, and isolation behavior. Offline: providers are fakes, never
real network calls.
"""

import asyncio
import inspect
from collections.abc import Awaitable, Callable

import pytest
from arq import Retry

from app.notifications import (
    NotificationChannel,
    NotificationDispatcher,
    NotificationMessage,
    NotificationRecipient,
    NotificationResult,
)
from app.worker.errors import PermanentNotificationFailure
from app.worker.retry import RetryPolicy
from app.worker.worker import _retry_after_hint, deliver_notification


def run(coro_or_factory):
    if inspect.iscoroutine(coro_or_factory):
        return asyncio.run(coro_or_factory)
    return asyncio.run(coro_or_factory())


# --- the exponential backoff calculation ---------------------------------------


def test_first_attempt_is_immediate() -> None:
    policy = RetryPolicy(max_attempts=5, base_delay_seconds=5, max_delay_seconds=300)
    assert policy.delay_for(1) == 0.0


def test_backoff_is_exponential() -> None:
    policy = RetryPolicy(max_attempts=8, base_delay_seconds=5, max_delay_seconds=300)

    # attempt 2 = first retry waits base * 2^0, then doubling each time.
    assert policy.delay_for(2) == 5.0
    assert policy.delay_for(3) == 10.0
    assert policy.delay_for(4) == 20.0
    assert policy.delay_for(5) == 40.0
    assert policy.delay_for(6) == 80.0


def test_backoff_is_capped_at_max_delay() -> None:
    policy = RetryPolicy(max_attempts=10, base_delay_seconds=5, max_delay_seconds=300)

    assert policy.delay_for(7) == 160.0
    assert policy.delay_for(8) == 300.0  # capped (raw: 320)
    assert policy.delay_for(9) == 300.0
    assert policy.delay_for(50) == 300.0  # always bounded


def test_retry_after_hint_extends_the_delay() -> None:
    policy = RetryPolicy(max_attempts=5, base_delay_seconds=5, max_delay_seconds=300)

    # The provider says wait 33s; the computed delay is only 5s — the
    # hint wins.
    assert policy.delay_for(2, retry_after=33) == 33.0


def test_retry_after_hint_is_respected_only_up_to_the_cap() -> None:
    policy = RetryPolicy(max_attempts=5, base_delay_seconds=5, max_delay_seconds=300)

    # A hostile/huge provider hint cannot stall the queue unbounded.
    assert policy.delay_for(2, retry_after=3600) == 300.0


def test_retry_after_hint_is_ignored_when_smaller() -> None:
    policy = RetryPolicy(max_attempts=5, base_delay_seconds=5, max_delay_seconds=300)
    assert policy.delay_for(4, retry_after=2) == 20.0


def test_zero_or_negative_retry_after_is_ignored() -> None:
    policy = RetryPolicy(max_attempts=5, base_delay_seconds=5, max_delay_seconds=300)
    assert policy.delay_for(2, retry_after=0) == 5.0
    assert policy.delay_for(2, retry_after=-5) == 5.0


@pytest.mark.parametrize(
    "kwargs",
    [
        {"max_attempts": 0},
        {"base_delay_seconds": 0},
        {"base_delay_seconds": -1},
        {"max_delay_seconds": 0},
        {"base_delay_seconds": 10, "max_delay_seconds": 5},
    ],
)
def test_invalid_policy_is_rejected(kwargs: dict) -> None:
    full = {
        "max_attempts": 5,
        "base_delay_seconds": 5,
        "max_delay_seconds": 300,
    }
    full.update(kwargs)
    with pytest.raises(ValueError):
        RetryPolicy(**full)


# --- retry-after extraction from provider error text ----------------------------


def test_retry_after_hint_is_parsed_from_rate_limit_message() -> None:
    # Pins the fixed format the provider layer emits (docs/01 §6.2); if
    # _botapi.py's message changes, this test tells us to update the
    # worker's parser.
    assert _retry_after_hint("Telegram rate limit exceeded (retry after 33s)") == 33.0
    assert _retry_after_hint("Bale rate limit exceeded (retry after 5s)") == 5.0


def test_retry_after_hint_returns_none_without_a_hint() -> None:
    assert _retry_after_hint("Telegram could not be reached") is None
    assert _retry_after_hint("Telegram rate limit exceeded") is None
    assert _retry_after_hint(None) is None
    assert _retry_after_hint("") is None


# --- the delivery job: classification --------------------------------------------


class ScriptedProvider:
    """A fake provider that plays out a scripted sequence of results.

    Outcomes per attempt: "success", "unavailable", "rate_limit",
    "rejected", "crash".
    """

    def __init__(self, channel: NotificationChannel, outcomes: list[str]) -> None:
        self._channel = channel
        self._outcomes = list(outcomes)
        self.sent: list[NotificationMessage] = []

    @property
    def channel(self) -> NotificationChannel:
        return self._channel

    async def send(self, message: NotificationMessage) -> NotificationResult:
        from app.notifications import (
            NotificationRejectedError,
            ProviderUnavailableError,
        )

        self.sent.append(message)
        outcome = self._outcomes.pop(0) if self._outcomes else "success"
        if outcome == "unavailable":
            raise ProviderUnavailableError("Telegram could not be reached")
        if outcome == "rate_limit":
            raise ProviderUnavailableError(
                "Telegram rate limit exceeded (retry after 33s)"
            )
        if outcome == "rejected":
            raise NotificationRejectedError(
                "Telegram rejected the notification: chat not found",
                error_code="recipient_invalid",
            )
        if outcome == "crash":
            raise RuntimeError("provider internal bug")
        return NotificationResult(
            success=True, channel=self._channel, external_message_id="fake-1"
        )


def make_dispatcher(provider) -> NotificationDispatcher:
    return NotificationDispatcher({str(provider.channel): provider})


def make_ctx(provider, policy: RetryPolicy, job_try: int = 1) -> dict:
    return {
        "notification_dispatcher": make_dispatcher(provider),
        "notification_retry_policy": policy,
        "job_try": job_try,
    }


PAYLOAD = {
    "channel": "telegram",
    "address": "100200300",
    "text": "Event created",
    "category": "event",
    "metadata": {"event_id": 5},
}

POLICY = RetryPolicy(max_attempts=4, base_delay_seconds=5, max_delay_seconds=300)


def test_successful_delivery() -> None:
    provider = ScriptedProvider(NotificationChannel.TELEGRAM, ["success"])

    status = run(deliver_notification(make_ctx(provider, POLICY), dict(PAYLOAD)))

    assert status == "delivered"
    assert len(provider.sent) == 1
    assert provider.sent[0].text == "Event created"
    assert provider.sent[0].recipient.address == "100200300"


def test_retryable_failure_raises_arq_retry_with_policy_delay() -> None:
    provider = ScriptedProvider(NotificationChannel.TELEGRAM, ["unavailable"])

    with pytest.raises(Retry) as excinfo:
        run(deliver_notification(make_ctx(provider, POLICY), dict(PAYLOAD)))

    # attempt 1 failed; attempt 2 waits base * 2^0 = 5s.
    assert excinfo.value.defer_score == 5000


def test_retry_after_hint_from_provider_extends_the_wait() -> None:
    provider = ScriptedProvider(NotificationChannel.TELEGRAM, ["rate_limit"])

    with pytest.raises(Retry) as excinfo:
        run(
            deliver_notification(
                make_ctx(provider, POLICY),
                dict(PAYLOAD),
            )
        )

    assert excinfo.value.defer_score == 33000  # 33s hint beats 5s backoff


def test_rejected_notification_is_permanent_on_first_attempt() -> None:
    provider = ScriptedProvider(NotificationChannel.TELEGRAM, ["rejected"])

    with pytest.raises(PermanentNotificationFailure) as excinfo:
        run(deliver_notification(make_ctx(provider, POLICY), dict(PAYLOAD)))

    assert "recipient_invalid" in str(excinfo.value)
    assert len(provider.sent) == 1  # exactly one attempt, no retry scheduled


def test_max_attempts_exceeded_is_permanent() -> None:
    provider = ScriptedProvider(NotificationChannel.TELEGRAM, ["unavailable"])

    with pytest.raises(PermanentNotificationFailure) as excinfo:
        run(
            deliver_notification(
                make_ctx(provider, POLICY, job_try=4), dict(PAYLOAD)
            )
        )

    # 4 attempts (the policy max) — the failure surfaces permanently.
    assert "4 attempts" in str(excinfo.value)


def test_max_attempts_not_yet_reached_still_retries() -> None:
    provider = ScriptedProvider(NotificationChannel.TELEGRAM, ["unavailable"])

    with pytest.raises(Retry):
        run(
            deliver_notification(
                make_ctx(provider, POLICY, job_try=3), dict(PAYLOAD)
            )
        )


def test_unexpected_provider_error_is_retryable_not_fatal() -> None:
    provider = ScriptedProvider(NotificationChannel.TELEGRAM, ["crash"])

    # A provider crash is normalized to provider_error by the dispatcher
    # and classified retryable — the worker must not see the raw
    # exception, and must not crash.
    with pytest.raises(Retry):
        run(deliver_notification(make_ctx(provider, POLICY), dict(PAYLOAD)))


def test_unexpected_provider_error_is_permanent_after_max_attempts() -> None:
    provider = ScriptedProvider(NotificationChannel.TELEGRAM, ["crash"])

    with pytest.raises(PermanentNotificationFailure):
        run(
            deliver_notification(
                make_ctx(provider, POLICY, job_try=4), dict(PAYLOAD)
            )
        )


def test_corrupt_payload_is_permanent_and_does_not_crash() -> None:
    provider = ScriptedProvider(NotificationChannel.TELEGRAM, [])

    with pytest.raises(PermanentNotificationFailure) as excinfo:
        run(
            deliver_notification(
                make_ctx(provider, POLICY), {"channel": "telegram"}  # missing keys
            )
        )

    assert "payload" in str(excinfo.value)
    assert provider.sent == []  # nothing was delivered


def test_rate_limit_result_is_retryable() -> None:
    # A 429 in the provider layer becomes ProviderUnavailableError →
    # dispatcher normalizes → error_code provider_unavailable, message
    # with the retry-after hint.
    from app.notifications import ProviderUnavailableError

    class RateLimitedProvider(ScriptedProvider):
        async def send(self, message):
            self.sent.append(message)
            raise ProviderUnavailableError(
                "Telegram rate limit exceeded (retry after 33s)"
            )

    provider = RateLimitedProvider(NotificationChannel.TELEGRAM, [])

    with pytest.raises(Retry) as excinfo:
        run(deliver_notification(make_ctx(provider, POLICY), dict(PAYLOAD)))

    assert excinfo.value.defer_score == 33000


def test_permanent_failure_message_carries_no_secrets() -> None:
    provider = ScriptedProvider(NotificationChannel.TELEGRAM, ["rejected"])
    payload = dict(PAYLOAD, metadata={"bot_token": "1100000001:AA-fake"})

    with pytest.raises(PermanentNotificationFailure) as excinfo:
        run(deliver_notification(make_ctx(provider, POLICY), payload))

    # The failure text is the stable error code — not the metadata, not
    # tokens, not raw provider responses.
    assert "1100000001" not in str(excinfo.value)
