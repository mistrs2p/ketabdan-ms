"""Tests for the queued notification job contract, serialization, and
background-delivery configuration (Task 5.7).

Everything is offline: Redis interactions use fakeredis, and no test
constructs anything that would call a real provider.
"""

import json

import fakeredis.aioredis
import pytest
from arq import ArqRedis

from app.core.config import Settings
from app.notifications import (
    InvalidNotificationError,
    NotificationChannel,
    NotificationMessage,
    NotificationRecipient,
)
from app.worker import (
    DELIVER_FUNCTION_NAME,
    NOTIFICATION_QUEUE_NAME,
    BackgroundNotificationService,
    NotificationJob,
    NotificationQueueError,
)
from app.worker.serialization import json_job_deserializer, json_job_serializer


def run(coro_or_factory):
    """Run a coroutine object or a zero-arg factory returning one."""
    import asyncio
    import inspect

    if inspect.iscoroutine(coro_or_factory):
        return asyncio.run(coro_or_factory)
    return asyncio.run(coro_or_factory())


# --- job model ---------------------------------------------------------------


def make_job(**overrides) -> NotificationJob:
    defaults = {
        "channel": "telegram",
        "address": "100200300",
        "text": "Event created",
        "category": "event",
    }
    defaults.update(overrides)
    return NotificationJob(**defaults)


def test_job_roundtrip_preserves_everything() -> None:
    job = make_job(metadata={"event_id": 7, "title": "تحلیل کتاب"})

    rebuilt = NotificationJob.from_payload(job.to_payload())

    assert rebuilt == job
    assert rebuilt.metadata == {"event_id": 7, "title": "تحلیل کتاب"}


def test_job_from_and_to_message_roundtrip() -> None:
    message = NotificationMessage(
        recipient=NotificationRecipient(
            channel=NotificationChannel.BALE, address="b-1"
        ),
        text="سلام",
        category="event",
        metadata={"k": "v"},
    )

    job = NotificationJob.from_message(message)
    reconstructed = job.to_message()

    assert reconstructed.recipient.channel == NotificationChannel.BALE
    assert reconstructed.recipient.address == "b-1"
    assert reconstructed.text == "سلام"
    assert reconstructed.category == "event"
    assert reconstructed.metadata == {"k": "v"}
    assert type(reconstructed) is NotificationMessage


@pytest.mark.parametrize(
    "overrides",
    [
        {"channel": ""},
        {"channel": "  "},
        {"address": ""},
        {"text": "   "},
        {"category": ""},
    ],
)
def test_invalid_job_fields_are_rejected(overrides: dict) -> None:
    with pytest.raises(InvalidNotificationError):
        make_job(**overrides)


def test_job_metadata_is_copied_not_aliased() -> None:
    meta = {"event_id": 1}
    job = make_job(metadata=meta)
    meta["event_id"] = 999
    assert job.metadata == {"event_id": 1}


# --- payload strictness (queue safety) ----------------------------------------


def test_payload_is_json_serializable_generic_data_only() -> None:
    payload = make_job().to_payload()

    encoded = json_job_serializer({"f": DELIVER_FUNCTION_NAME, "k": payload})
    decoded = json_job_deserializer(encoded)

    assert decoded["k"] == payload
    # Only generic keys — no provider fields, no credentials.
    assert set(decoded["k"]) == {"channel", "address", "text", "category", "metadata"}


def test_payload_rejects_unknown_keys() -> None:
    payload = make_job().to_payload()
    payload["bot_token"] = "should-not-exist"
    payload["endpoint"] = "https://evil.example"

    with pytest.raises(InvalidNotificationError):
        NotificationJob.from_payload(payload)


def test_payload_rejects_missing_keys() -> None:
    payload = make_job().to_payload()
    del payload["text"]

    with pytest.raises(InvalidNotificationError):
        NotificationJob.from_payload(payload)


def test_payload_metadata_is_optional() -> None:
    payload = make_job().to_payload()
    del payload["metadata"]

    job = NotificationJob.from_payload(payload)

    assert job.metadata == {}


def test_payload_rejects_non_mapping_metadata() -> None:
    payload = make_job().to_payload()
    payload["metadata"] = "not-a-mapping"

    with pytest.raises(InvalidNotificationError):
        NotificationJob.from_payload(payload)


def test_payload_rejects_non_mapping_payload() -> None:
    with pytest.raises(InvalidNotificationError):
        NotificationJob.from_payload(["not", "a", "mapping"])


def test_job_has_no_credential_fields() -> None:
    import dataclasses

    fields = {f.name for f in dataclasses.fields(NotificationJob)}
    for forbidden in ("token", "secret", "api_key", "password", "endpoint", "url"):
        assert forbidden not in fields


def test_unknown_channel_fails_at_message_reconstruction() -> None:
    # A channel no enum member exists for cannot become a message — the
    # job dataclass itself stores it (serialization must not guess), but
    # reconstruction raises a controlled error.
    job = make_job(channel="signal")
    with pytest.raises(ValueError):
        job.to_message()


# --- JSON serializer strictness -------------------------------------------------


def test_serializer_rejects_non_json_data_instead_of_stringifying() -> None:
    # Only exceptions render (arq stores them as failed-job results);
    # any other non-JSON object must fail loudly at enqueue time.
    with pytest.raises(TypeError):
        json_job_serializer({"k": {"callback": object()}})


def test_serializer_renders_exception_results_sanitized() -> None:
    # arq stores a failed job's exception object as the result; it must
    # serialize (or every permanent failure logs a noisy fallback), and
    # carry only type + already-sanitized message.
    from app.worker.errors import PermanentNotificationFailure

    exc = PermanentNotificationFailure("provider rejected the notification (recipient_invalid)")
    encoded = json_job_serializer({"s": False, "r": exc})

    assert json_job_deserializer(encoded)["r"] == (
        "PermanentNotificationFailure: provider rejected the "
        "notification (recipient_invalid)"
    )


def test_serializer_preserves_unicode() -> None:
    text = "رویداد «تحلیل کتاب» جمعه ساعت ۱۷"
    encoded = json_job_serializer({"k": {"text": text}})
    assert json_job_deserializer(encoded)["k"]["text"] == text


# --- configuration ----------------------------------------------------------------


def test_default_configuration() -> None:
    settings = Settings(_env_file=None)

    assert settings.redis_url.get_secret_value() == "redis://localhost:6390/0"
    assert settings.notification_max_attempts == 5
    assert settings.notification_retry_base_delay_seconds == 5.0
    assert settings.notification_retry_max_delay_seconds == 300.0


def test_custom_redis_url() -> None:
    settings = Settings(
        _env_file=None, redis_url="redis://redis.example:6380/2"
    )

    assert settings.redis_url.get_secret_value() == "redis://redis.example:6380/2"


def test_invalid_retry_config_rejected_cleanly() -> None:
    from pydantic import ValidationError

    from app.core.config import ConfigurationError

    with pytest.raises(ValidationError):
        Settings(_env_file=None, notification_max_attempts=0)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, notification_retry_base_delay_seconds=0)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, notification_retry_max_delay_seconds=-1)
    # The cross-field cap check raises ConfigurationError (Task 5.10):
    # a policy violation, not a type error — and its message never
    # echoes raw input values.
    with pytest.raises(ConfigurationError):
        Settings(
            _env_file=None,
            notification_retry_base_delay_seconds=60.0,
            notification_retry_max_delay_seconds=30.0,  # cap below base
        )


def test_max_attempts_of_one_is_valid() -> None:
    settings = Settings(_env_file=None, notification_max_attempts=1)
    assert settings.notification_max_attempts == 1


# --- enqueue path (service) -------------------------------------------------------


def make_fake_pool() -> ArqRedis:
    fake = fakeredis.aioredis.FakeRedis()
    return ArqRedis(
        pool_or_conn=fake.connection_pool,
        job_serializer=json_job_serializer,
        job_deserializer=json_job_deserializer,
        default_queue_name=NOTIFICATION_QUEUE_NAME,
    )


def test_enqueue_stores_a_generic_json_job_in_the_queue() -> None:
    pool = make_fake_pool()
    service = BackgroundNotificationService(
        Settings(_env_file=None), pool=pool
    )

    async def scenario():
        await service.enqueue_notification(
            channel="telegram",
            address="100200300",
            text="Event created",
            category="event",
            metadata={"event_id": 5},
        )
        queued = await pool.queued_jobs()
        return queued

    queued = run(scenario)
    assert len(queued) == 1
    assert queued[0].function == DELIVER_FUNCTION_NAME
    # What is stored is exactly the generic payload — no provider fields.
    # (JSON round-trips the positional args tuple as a list.)
    assert queued[0].args == [
        {
            "channel": "telegram",
            "address": "100200300",
            "text": "Event created",
            "category": "event",
            "metadata": {"event_id": 5},
        }
    ]
    assert queued[0].kwargs == {}
    run(pool.aclose())


def test_enqueue_returns_without_performing_delivery() -> None:
    # The service returns a NotificationJob — never a NotificationResult.
    # Delivery is the worker's job.
    pool = make_fake_pool()
    service = BackgroundNotificationService(
        Settings(_env_file=None), pool=pool
    )

    job = run(
        lambda: service.enqueue_notification(
            channel="bale", address="b-1", text="hi", category="event"
        )
    )

    assert isinstance(job, NotificationJob)
    run(pool.aclose())


def test_enqueue_invalid_notification_is_rejected_before_redis() -> None:
    pool = make_fake_pool()
    service = BackgroundNotificationService(
        Settings(_env_file=None), pool=pool
    )

    async def scenario():
        with pytest.raises(InvalidNotificationError):
            await service.enqueue_notification(
                channel="telegram", address="", text="x", category="event"
            )
        queued = await pool.queued_jobs()
        return queued

    assert run(scenario) == []
    run(pool.aclose())


def test_enqueue_to_unreachable_redis_is_a_controlled_queue_error() -> None:
    # No injected pool: the service must try to connect to a Redis that
    # is not there (port with nothing listening), fail fast, and raise
    # the controlled NotificationQueueError — not hang forever, not
    # crash with an unrelated stack trace.
    settings = Settings(
        _env_file=None,
        redis_url="redis://127.0.0.1:1/0",  # nothing listens here
        notification_timeout_seconds=1.0,
    )
    service = BackgroundNotificationService(settings)

    with pytest.raises(NotificationQueueError) as excinfo:
        run(
            lambda: service.enqueue_notification(
                channel="telegram",
                address="1",
                text="x",
                category="event",
            )
        )

    # The error message must not embed the Redis URL.
    assert "redis://127.0.0.1:1" not in str(excinfo.value)


def test_service_does_not_know_any_provider_details() -> None:
    # The enqueue side stays provider-agnostic: no telegram/bale/httpx
    # symbols anywhere in the service module.
    import inspect

    import app.worker.service as service_module

    source = inspect.getsource(service_module)
    for forbidden in ("api.telegram.org", "tapi.bale.ai", "httpx", "bot_token"):
        assert forbidden not in source, forbidden
