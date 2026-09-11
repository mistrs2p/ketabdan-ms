"""The application-level background notification service (Task 5.7).

The one entry point future business services will call:

    await enqueue_notification(...)

Its responsibility is exactly: accept a generic notification request,
serialize it into the stable job contract, and hand it to Redis — then
return without waiting for provider delivery. The HTTP/API request path
never performs the real provider network call once this service is used.

It knows nothing about Telegram or Bale: no endpoints, no tokens, no
provider selection. Delivery is the worker's job (``app.worker.worker``),
which goes through the same ``NotificationDispatcher`` factory boundary as
everything else.

Redis availability: the connection is created lazily when the service is
first used, and a Redis outage becomes a controlled
``NotificationQueueError`` — never an obscure import-time crash. The API
application itself never needs Redis just to import or serve.
"""

from typing import Any

from arq import ArqRedis, create_pool
from arq.connections import RedisSettings

from app.core.config import Settings
from app.core.logging import get_logger
from app.worker.errors import NotificationQueueError
from app.worker.jobs import (
    DELIVER_FUNCTION_NAME,
    NOTIFICATION_QUEUE_NAME,
    NotificationJob,
)
from app.worker.serialization import (
    json_job_deserializer,
    json_job_serializer,
)

logger = get_logger("app.worker.service")

# A bounded, short pool: enqueueing is one small command; we do not want
# the enqueue path to hang forever when Redis is down (create_pool itself
# retries per RedisSettings.conn_retries and then raises).
POOL_CONN_TIMEOUT_SECONDS = 2
POOL_CONN_RETRIES = 1
POOL_CONN_RETRY_DELAY_SECONDS = 1


class BackgroundNotificationService:
    """Enqueues generic notifications onto the Redis-backed queue.

    Constructor-injected dependencies (no global state): settings supply
    the Redis URL; an existing pool can be injected for testing.
    """

    def __init__(self, settings: Settings, *, pool: ArqRedis | None = None) -> None:
        self._settings = settings
        self._pool: ArqRedis | None = pool

    def _redis_settings(self) -> RedisSettings:
        """Redis connection settings derived from the environment URL —
        never from notification data. Unknown DSN schemes are a
        configuration error and fail cleanly. The URL is unwrapped from
        its SecretStr here (Task 5.10) — its single point of use."""
        redis_settings = RedisSettings.from_dsn(
            self._settings.redis_url.get_secret_value()
        )
        redis_settings.conn_timeout = POOL_CONN_TIMEOUT_SECONDS
        redis_settings.conn_retries = POOL_CONN_RETRIES
        redis_settings.conn_retry_delay = POOL_CONN_RETRY_DELAY_SECONDS
        return redis_settings

    async def _get_pool(self) -> ArqRedis:
        if self._pool is None:
            try:
                self._pool = await create_pool(
                    self._redis_settings(),
                    job_serializer=json_job_serializer,
                    job_deserializer=json_job_deserializer,
                    default_queue_name=NOTIFICATION_QUEUE_NAME,
                )
            except Exception as exc:
                # Controlled failure: nothing was queued; sanitized message
                # only (no Redis URL with embedded credentials).
                logger.error(
                    "notification Redis connection failed (%s)",
                    exc.__class__.__name__,
                )
                raise NotificationQueueError(
                    f"could not connect to Redis for notification enqueueing "
                    f"({exc.__class__.__name__})"
                ) from exc
        return self._pool

    async def enqueue_notification(
        self,
        *,
        channel: str,
        address: str,
        text: str,
        category: str,
        metadata: dict[str, Any] | None = None,
    ) -> NotificationJob:
        """Queue one generic notification for background delivery.

        Returns the constructed ``NotificationJob`` (not a delivery
        result — delivery happens in the worker). Raises
        ``InvalidNotificationError`` for malformed input and
        ``NotificationQueueError`` when the queue is unreachable.
        """
        job = NotificationJob(
            channel=channel,
            address=address,
            text=text,
            category=category,
            metadata=metadata or {},
        )
        pool = await self._get_pool()
        try:
            queued = await pool.enqueue_job(
                DELIVER_FUNCTION_NAME,
                job.to_payload(),
            )
        except Exception as exc:
            # The pool is cached; a dead connection must not poison later
            # enqueues — drop it so the next attempt reconnects.
            self._pool = None
            logger.error(
                "notification enqueue failed (Redis problem): channel=%s "
                "category=%s (%s)",
                job.channel,
                job.category,
                exc.__class__.__name__,
            )
            raise NotificationQueueError(
                f"could not enqueue notification job ({exc.__class__.__name__})"
            ) from exc
        logger.info(
            "notification job enqueued: channel=%s category=%s job_id=%s "
            "(delivery happens in the background worker)",
            job.channel,
            job.category,
            getattr(queued, "job_id", "-"),
        )
        return job

    async def close(self) -> None:
        """Release the Redis pool, if this service owns one it created."""
        if self._pool is not None:
            try:
                await self._pool.aclose()
            except Exception:  # noqa: BLE001 — shutdown must never raise
                logger.warning("error closing notification Redis pool", exc_info=True)
            self._pool = None
