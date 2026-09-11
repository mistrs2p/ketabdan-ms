"""Health endpoints (Task 5.9; docs/06 §4, docs/01 §10).

Three public endpoints, no authentication (health checks must work
before/independently of auth):

- ``GET /api/health``       liveness — the pre-5.9 contract, unchanged:
  ``{"status": "ok"}``, no dependencies. Kept as-is: the frontend health
  client (apps/web/lib/api/health.ts) and existing tests depend on it.
- ``GET /api/health/live``  liveness — same semantics, explicit name.
- ``GET /api/health/ready`` readiness — the dependencies the API needs
  to serve correctly, each checked with a bounded timeout:

      {"status": "ok", "checks": {"database": "ok", "redis": "ok",
       "worker": "ok"}}

  ``database`` and ``redis`` gate the overall status (503 when either is
  not ``ok``); ``worker`` is informational only — the notification
  worker is optional infrastructure (no business trigger depends on it
  yet), so an absent worker must NOT make the API unready.

  ``worker`` reflects arq's own Redis health key (written by the running
  worker every 30s with a 31s TTL — ``WorkerSettings.health_check_interval``):
  present → a worker process is alive; absent → "no_recent_heartbeat".
  This proves a WORKER is running, not merely that Redis is reachable.

Failure responses carry only fixed words (``ok`` / ``unavailable``) —
never URLs, credentials, or exception text (§6/§19). Failures are logged
with the exception CLASS NAME only.
"""

import asyncio

import redis.asyncio as aioredis
from fastapi import APIRouter
from fastapi.responses import JSONResponse, Response

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.metrics import metrics_payload
from app.db.session import get_engine
from app.worker.jobs import NOTIFICATION_QUEUE_NAME

router = APIRouter(prefix="/api/health", tags=["health"])

_health_log = get_logger("app.api.health")

# Bounded check timeouts: readiness must answer quickly — a hanging
# dependency check would turn "is the app ready?" into an unreadiness of
# the check itself.
DATABASE_CHECK_TIMEOUT_SECONDS = 3.0
REDIS_CHECK_TIMEOUT_SECONDS = 2.0

# arq's worker health key: the running worker refreshes it every
# health_check_interval seconds with a TTL of interval + 1s.
WORKER_HEALTH_KEY = f"{NOTIFICATION_QUEUE_NAME}:health"

_CHECK_OK = "ok"
_CHECK_UNAVAILABLE = "unavailable"
_WORKER_NO_HEARTBEAT = "no_recent_heartbeat"


async def _check_database() -> str:
    """PostgreSQL reachable — one ``SELECT 1`` on the existing engine.

    The engine/session infrastructure is the application's (Task 5.8:
    no second connection system); the sync ping runs in a thread with a
    hard timeout so a wedged database cannot hang readiness. The
    connection is returned by the context manager — nothing leaks.
    """

    def _ping() -> None:
        engine = get_engine()  # may raise DatabaseNotConfiguredError
        with engine.connect() as connection:
            connection.exec_driver_sql("SELECT 1")

    try:
        await asyncio.wait_for(
            asyncio.to_thread(_ping), timeout=DATABASE_CHECK_TIMEOUT_SECONDS
        )
        return _CHECK_OK
    except Exception as exc:  # noqa: BLE001 — any failure = not ready, classified only
        _health_log.warning(
            "readiness: database check failed (%s)", exc.__class__.__name__
        )
        return _CHECK_UNAVAILABLE


async def _check_redis() -> str:
    """Redis reachable — one PING on a short-lived client.

    The URL comes from the same ``redis_url`` setting as Task 5.7 (no
    duplicated configuration); the client is created per check with
    bounded socket timeouts and always closed. No global Redis client is
    created at import time.
    """
    settings = get_settings()
    try:
        client = aioredis.Redis.from_url(
            settings.redis_url,
            socket_connect_timeout=REDIS_CHECK_TIMEOUT_SECONDS,
            socket_timeout=REDIS_CHECK_TIMEOUT_SECONDS,
        )
        try:
            await asyncio.wait_for(client.ping(), timeout=REDIS_CHECK_TIMEOUT_SECONDS)
        finally:
            await client.aclose()
        return _CHECK_OK
    except Exception as exc:  # noqa: BLE001
        _health_log.warning(
            "readiness: redis check failed (%s)", exc.__class__.__name__
        )
        return _CHECK_UNAVAILABLE


async def _check_worker_heartbeat() -> str:
    """Informational: is a worker process alive (not just Redis up)?

    arq's Worker writes ``<queue>:health`` every 30s with a 31s TTL, so
    the key's presence proves a live worker process. Read through the
    same short-lived client pattern as the Redis check.
    """
    settings = get_settings()
    try:
        client = aioredis.Redis.from_url(
            settings.redis_url,
            socket_connect_timeout=REDIS_CHECK_TIMEOUT_SECONDS,
            socket_timeout=REDIS_CHECK_TIMEOUT_SECONDS,
        )
        try:
            heartbeat: int = await asyncio.wait_for(
                client.exists(WORKER_HEALTH_KEY), timeout=REDIS_CHECK_TIMEOUT_SECONDS
            )
        finally:
            await client.aclose()
        # exists() returns a count, not a boolean: 0 means the key has
        # expired (no worker refreshed it) — Redis being reachable says
        # nothing about the worker (§10: never report "worker healthy"
        # merely because Redis works).
        return _CHECK_OK if heartbeat else _WORKER_NO_HEARTBEAT
    except Exception as exc:  # noqa: BLE001
        _health_log.debug(
            "readiness: worker heartbeat check skipped (%s)",
            exc.__class__.__name__,
        )
        return _WORKER_NO_HEARTBEAT


@router.get("")
@router.get("/live")
async def liveness() -> dict[str, str]:
    """Process liveness: the app is up and serving. No dependencies.

    Must never touch DB/Redis — a liveness probe that fails because a
    dependency is down gets the (healthy) process killed by a restart
    loop. Both ``/api/health`` (legacy path) and ``/api/health/live``
    serve this contract; the response shape is the pre-5.9 one.
    """
    return {"status": "ok"}


@router.get("/ready")
async def readiness() -> JSONResponse:
    """Readiness: required dependencies are available (503 otherwise).

    database + redis gate the status; worker is informational.
    """
    database, redis, worker = await asyncio.gather(
        _check_database(),
        _check_redis(),
        _check_worker_heartbeat(),
    )
    checks = {"database": database, "redis": redis, "worker": worker}
    ready = database == _CHECK_OK and redis == _CHECK_OK
    return JSONResponse(
        status_code=200 if ready else 503,
        content={"status": _CHECK_OK if ready else "not_ready", "checks": checks},
    )


# --- metrics endpoint (lives here, not under /api/health — Prometheus ----------
#     convention is a bare /metrics path at the server root)

metrics_router = APIRouter(tags=["metrics"])


@metrics_router.get("/metrics")
async def prometheus_metrics() -> Response:
    """This process's Prometheus exposition (API process).

    Unauthenticated by design: it is meant for infrastructure scraping
    on an internal network/port. Protect at the infrastructure level
    (bind to an internal interface / reverse-proxy ACL) — see
    docs/01 §10. Exposes counters/histograms only: no request contents,
    no secrets, no user-identifying values; labels are bounded by
    construction (app.core.metrics).
    """
    return Response(
        content=metrics_payload(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
