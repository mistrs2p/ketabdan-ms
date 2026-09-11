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

import re
import time

from arq import Retry
from arq.connections import RedisSettings

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.core.metrics import (
    JOB_COMPLETED,
    JOB_FAILED,
    JOB_RETRIED,
    NOTIF_FAILED,
    NOTIF_REJECTED,
    NOTIF_RETRYABLE,
    NOTIF_SUCCESS,
    observe_job,
    observe_notification_attempt,
)
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

logger = get_logger("app.worker.delivery")

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
    # arq injects job_id/job_try; job_id is opaque (safe to log), job_try
    # identifies the attempt. Together with channel/category these are
    # the full diagnosable context — never text or recipient address.
    job_id = str(ctx.get("job_id", "-"))
    started = time.perf_counter()

    # 1. Reconstruct the generic NotificationMessage — strictly.
    try:
        job = NotificationJob.from_payload(payload)
        message = job.to_message()
    except Exception as exc:
        # Corrupt/hostile payload: permanent, and must not crash the worker.
        logger.error(
            "notification job payload is invalid: job_id=%s (%s)",
            job_id,
            exc.__class__.__name__,
        )
        observe_job(DELIVER_FUNCTION_NAME, JOB_FAILED)
        raise PermanentNotificationFailure(
            f"invalid job payload ({exc.__class__.__name__})"
        ) from exc

    # 2. Deliver through the existing abstraction.
    result = await dispatcher.send(message)
    duration_ms = (time.perf_counter() - started) * 1000.0

    # 3. Classify (Task 5.5/5.6 semantics) and apply the bounded policy.
    # Metrics observe the classification (bounded labels: function name,
    # channel, fixed outcome vocabulary — never job ids, recipients, or
    # error text; docs/01 §10).
    if result.success:
        logger.info(
            "notification delivered: channel=%s category=%s external_id=%s "
            "job_id=%s duration_ms=%.0f",
            job.channel,
            job.category,
            result.external_message_id,
            job_id,
            duration_ms,
        )
        observe_job(DELIVER_FUNCTION_NAME, JOB_COMPLETED)
        observe_notification_attempt(
            job.channel, NOTIF_SUCCESS, duration_seconds=duration_ms / 1000.0
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
            "error_code=%s job_id=%s duration_ms=%.0f",
            job.channel,
            job.category,
            result.error_code,
            job_id,
            duration_ms,
        )
        observe_job(DELIVER_FUNCTION_NAME, JOB_FAILED)
        observe_notification_attempt(
            job.channel, NOTIF_REJECTED, duration_seconds=duration_ms / 1000.0
        )
        raise PermanentNotificationFailure(
            f"provider rejected the notification ({result.error_code})"
        )

    # Retryable: provider unavailable or unexpected provider error.
    final_attempt = attempt >= policy.max_attempts
    if final_attempt:
        logger.error(
            "notification delivery failed permanently after %d attempts: "
            "channel=%s category=%s error_code=%s job_id=%s",
            attempt,
            job.channel,
            job.category,
            result.error_code,
            job_id,
        )
        observe_job(DELIVER_FUNCTION_NAME, JOB_FAILED)
        observe_notification_attempt(
            job.channel, NOTIF_FAILED, duration_seconds=duration_ms / 1000.0
        )
        raise PermanentNotificationFailure(
            f"delivery failed after {attempt} attempts "
            f"({result.error_code or 'unknown error'})"
        )

    delay = policy.delay_for(
        attempt + 1, retry_after=_retry_after_hint(result.error_message)
    )
    logger.info(
        "notification attempt %d/%d failed (error_code=%s) — retrying in "
        "%.1fs: channel=%s category=%s job_id=%s",
        attempt,
        policy.max_attempts,
        result.error_code,
        delay,
        job.channel,
        job.category,
        job_id,
    )
    observe_job(DELIVER_FUNCTION_NAME, JOB_RETRIED)
    observe_notification_attempt(
        job.channel, NOTIF_RETRYABLE, duration_seconds=duration_ms / 1000.0
    )
    raise Retry(defer=delay)


async def startup(ctx: dict) -> None:
    """Worker startup hook: compose the dispatcher via the existing factory.

    The dispatcher is created once per worker process and shared by all
    jobs through ``ctx`` — constructor injection, no globals.

    Task 5.9: optionally exposes this process's Prometheus metrics on
    ``WORKER_METRICS_PORT`` (default 0 = disabled) using the library's
    built-in single-purpose HTTP server. The worker metrics are
    process-local counters — without this port there is no way to scrape
    them (the worker serves no HTTP otherwise).
    """
    settings: Settings = get_settings()
    ctx["notification_dispatcher"] = build_notification_dispatcher(settings)
    ctx["notification_retry_policy"] = _retry_policy_from_settings(settings)
    ctx["notification_settings"] = settings
    if settings.worker_metrics_port:
        from prometheus_client import start_http_server

        server, thread = start_http_server(settings.worker_metrics_port)
        ctx["_metrics_server"] = (server, thread)
        logger.info(
            "worker metrics exposed on port %d", settings.worker_metrics_port
        )
    logger.info(
        "notification worker ready (retry policy: max_attempts=%d, "
        "base_delay=%.1fs, max_delay=%.1fs)",
        settings.notification_max_attempts,
        settings.notification_retry_base_delay_seconds,
        settings.notification_retry_max_delay_seconds,
    )


async def shutdown(ctx: dict) -> None:
    server_info = ctx.pop("_metrics_server", None)
    if server_info is not None:
        server, _thread = server_info
        try:
            server.shutdown()
        except Exception:  # noqa: BLE001 — shutdown must never raise
            logger.warning("worker metrics server shutdown failed", exc_info=True)
    logger.info("notification worker shutting down")


def _worker_redis_settings() -> "RedisSettings":
    """The worker's Redis connection, from the same REDIS_URL setting as
    the rest of the application.

    Task 5.11 bug fix (found by the containerized worker): arq reads
    ``redis_settings`` from ``WorkerSettings.__dict__`` and otherwise
    falls back to its own localhost:6379 default — the enqueue side
    (service.py) honored REDIS_URL all along, but the worker silently
    ignored it and could never reach any other Redis. arq's own connect
    retry behavior is kept (startup stays resilient to dependency
    races); only the target comes from configuration.
    """
    redis_settings = RedisSettings.from_dsn(
        get_settings().redis_url.get_secret_value()
    )
    return redis_settings


class WorkerSettings:
    """arq worker settings — the composition root of the worker process.

    Run with: ``arq app.worker.worker.WorkerSettings`` or
    ``python -m app.worker`` (see ``__main__.py``).
    """

    functions = [deliver_notification]
    on_startup = startup
    on_shutdown = shutdown
    queue_name = NOTIFICATION_QUEUE_NAME
    job_serializer = json_job_serializer
    job_deserializer = json_job_deserializer
    # Must be a plain class attribute: arq's create_worker reads
    # WorkerSettings.__dict__ (not getattr/inheritance), so this is the
    # only form both `arq`-CLI and `python -m app.worker` paths honor.
    # Evaluated at import time — like every arq settings class — which
    # reads the worker process's environment, exactly when it should.
    redis_settings = _worker_redis_settings()

    # Bounded execution: one notification delivery is a couple of bounded
    # HTTP attempts — minutes are plenty.
    job_timeout = 120
    # Retries are driven by OUR policy (max_attempts via PermanentNotificationFailure
    # classification + Retry defer), with arq's max_tries as the outer
    # bound so a bug in the classification can never loop forever.
    max_tries = 25
    # Worker liveness signal (Task 5.9): arq refreshes <queue>:health-check
    # Redis every 30s with a 31s TTL — the readiness endpoint reads it to
    # distinguish "Redis reachable" from "a worker process is actually
    # alive". The default (3600s) would make the heartbeat useless.
    health_check_interval = 30
