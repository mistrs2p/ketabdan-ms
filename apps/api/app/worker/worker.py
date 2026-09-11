"""The notification background worker (Task 5.7).

Consumes notification jobs from the Redis queue and delivers them through
the existing ``NotificationDispatcher`` (built via
``build_notification_dispatcher`` — the same composition boundary as the
rest of the application; no global provider registries, no duplicated
Telegram/Bale HTTP logic).

Retry classification uses the Task 5.5/5.6 failure semantics:

    success                    → done
    NotificationRejectedError  → permanent, never retried
    ProviderUnavailableError   → retryable (bounded backoff)
    anything unexpected        → retryable (bounded backoff), and must not
                                crash the worker

The retry policy itself is bounded exponential backoff with a configurable
base and max delay (``app.worker.retry``); rate-limit hints
(``retry_after``) from the provider layer are respected up to the cap.

Delivery semantics: at-least-once. A worker shutdown mid-job means the job
returns to the queue and may run again — the notification layer does not
(yet) offer provider-side idempotency keys, so exactly-once is NOT
claimed. See docs/01 §6.5.

Running: ``python -m app.worker`` (see ``__main__.py``) or
``arq app.worker.worker.WorkerSettings``.
"""

import asyncio
import logging
import re

from arq import Retry

from app.core.config import Settings, get_settings
from app.notifications import NotificationDispatcher, NotificationResult
from app.notifications.factory import build_notification_dispatcher
from app.worker.errors import PermanentNotificationFailure
from app.worker.jobs import (
    DELIVER_FUNCTION_NAME,
    NOTIFICATION_QUEUE_NAME,
    NotificationJob,
)
from app.worker.retry import RetryPolicy
from app.worker.serialization import (
    json_job_deserializer,
    json_job_serializer,
)

logger = logging.getLogger("app.worker.delivery")

# The provider layer (Task 5.6 _botapi.py) reports rate limits as fixed
# diagnostic text "… rate limit exceeded (retry after Ns)" — the hint is
# deliberately NOT a structured field on NotificationResult (the frozen
# contract from 5.5 must not change). This parses that fixed format.
_RETRY_AFTER_PATTERN = re.compile(r"\(retry after (\d+)s\)")


def _retry_after_hint(error_message: str | None) -> float | None:
    """The provider's rate-limit wait hint, in seconds, when present."""
    if not error_message:
        return None
    match = _RETRY_AFTER_PATTERN.search(error_message)
    return float(match.group(1)) if match else None


def _retry_policy_from_settings(settings: Settings) -> RetryPolicy:
    return RetryPolicy(
        max_attempts=settings.notification_max_attempts,
        base_delay_seconds=settings.notification_retry_base_delay_seconds,
        max_delay_seconds=settings.notification_retry_max_delay_seconds,
    )


async def deliver_notification(ctx: dict, payload: dict) -> str:
    """One queued notification: reconstruct, deliver, classify, retry.

    arq job function — invoked by the worker with the serialized job
    payload. Returns a short, secret-free status string (kept in the job
    result for diagnosability).
    """
    dispatcher: NotificationDispatcher = ctx["notification_dispatcher"]
    policy: RetryPolicy = ctx["notification_retry_policy"]

    # 1. Reconstruct the generic NotificationMessage — strictly.
    try:
        job = NotificationJob.from_payload(payload)
        message = job.to_message()
    except Exception as exc:
        # Corrupt/hostile payload: permanent, and must not crash the worker.
        logger.error("notification job payload is invalid: %s", exc)
        raise PermanentNotificationFailure(
            f"invalid job payload ({exc.__class__.__name__})"
        ) from exc

    # 2. Deliver through the existing abstraction.
    result = await dispatcher.send(message)

    # 3. Classify (Task 5.5/5.6 semantics) and apply the bounded policy.
    if result.success:
        logger.info(
            "notification delivered: channel=%s category=%s external_id=%s",
            job.channel,
            job.category,
            result.external_message_id,
        )
        return "delivered"

    attempt = ctx["job_try"]
    if result.error_code == "notification_rejected" or (
        result.error_code
        and result.error_code not in ("provider_unavailable", "provider_error")
    ):
        # Rejected by the provider (invalid recipient, blocked bot,
        # oversized message, …): retrying cannot help — permanent.
        logger.warning(
            "notification permanently rejected: channel=%s category=%s "
            "error_code=%s",
            job.channel,
            job.category,
            result.error_code,
        )
        raise PermanentNotificationFailure(
            f"provider rejected the notification ({result.error_code})"
        )

    # Retryable: provider unavailable or unexpected provider error.
    final_attempt = attempt >= policy.max_attempts
    if final_attempt:
        logger.error(
            "notification delivery failed permanently after %d attempts: "
            "channel=%s category=%s error_code=%s",
            attempt,
            job.channel,
            job.category,
            result.error_code,
        )
        raise PermanentNotificationFailure(
            f"delivery failed after {attempt} attempts "
            f"({result.error_code or 'unknown error'})"
        )

    delay = policy.delay_for(
        attempt + 1, retry_after=_retry_after_hint(result.error_message)
    )
    logger.info(
        "notification attempt %d/%d failed (error_code=%s) — retrying in %.1fs",
        attempt,
        policy.max_attempts,
        result.error_code,
        delay,
    )
    raise Retry(defer=delay)


async def startup(ctx: dict) -> None:
    """Worker startup hook: compose the dispatcher via the existing factory.

    The dispatcher is created once per worker process and shared by all
    jobs through ``ctx`` — constructor injection, no globals.
    """
    settings: Settings = get_settings()
    ctx["notification_dispatcher"] = build_notification_dispatcher(settings)
    ctx["notification_retry_policy"] = _retry_policy_from_settings(settings)
    ctx["notification_settings"] = settings
    logger.info(
        "notification worker ready (retry policy: max_attempts=%d, "
        "base_delay=%.1fs, max_delay=%.1fs)",
        settings.notification_max_attempts,
        settings.notification_retry_base_delay_seconds,
        settings.notification_retry_max_delay_seconds,
    )


async def shutdown(ctx: dict) -> None:
    logger.info("notification worker shutting down")


class WorkerSettings:
    """arq worker settings — the composition root of the worker process.

    Run with: ``arq app.worker.worker.WorkerSettings``
    """

    functions = [deliver_notification]
    on_startup = startup
    on_shutdown = shutdown
    queue_name = NOTIFICATION_QUEUE_NAME
    job_serializer = json_job_serializer
    job_deserializer = json_job_deserializer

    # Bounded execution: one notification delivery is a couple of bounded
    # HTTP attempts — minutes are plenty.
    job_timeout = 120
    # Retries are driven by OUR policy (max_attempts via PermanentNotificationFailure
    # classification + Retry defer), with arq's max_tries as the outer
    # bound so a bug in the classification can never loop forever.
    max_tries = 25
