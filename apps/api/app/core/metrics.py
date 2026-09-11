"""Application metrics (Task 5.9).

Prometheus-compatible metrics via ``prometheus-client`` (the smallest
maintainable option; no framework integration package). The default
registry is process-local: the API process exposes it at ``GET /metrics``
(``app.api.metrics_endpoint``); the worker process optionally exposes it
on its own port (``WORKER_METRICS_PORT``).

Cardinality rules (docs/01 §10) — labels are ONLY ever:

- ``method``        HTTP method (bounded: the verb set)
- ``route``         the route TEMPLATE (``/api/persons/{person_id}``),
                    never the raw path; unmatched requests collapse to
                    the literal ``unmatched``
- ``status_class``  ``2xx`` / ``3xx`` / ``4xx`` / ``5xx``
- ``function``      the arq job function name (one constant today)
- ``outcome``       a fixed vocabulary (completed / retried / failed …)
- ``channel``       a validated notification channel name, sanitized to
                    the known set, else the literal ``unknown``

NEVER user/event/person ids, recipients, tokens, texts, raw paths,
query strings, or exception text. Observability must never take the
application down: every helper swallows instrumentation errors (§18).
"""

import logging
from typing import Final

from prometheus_client import (
    REGISTRY,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

logger = logging.getLogger("app.metrics")

# --- HTTP (API process) ---------------------------------------------------------

HTTP_REQUESTS_TOTAL: Final = Counter(
    "http_requests_total",
    "HTTP requests processed",
    labelnames=["method", "route", "status_class"],
)
HTTP_REQUEST_DURATION_SECONDS: Final = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    labelnames=["method", "route"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)
HTTP_REQUESTS_IN_PROGRESS: Final = Gauge(
    "http_requests_in_progress",
    "HTTP requests currently being served",
    labelnames=["method"],
)

# --- Worker / notifications (worker process) ------------------------------------

WORKER_JOBS_TOTAL: Final = Counter(
    "worker_jobs_total",
    "Background jobs processed by outcome",
    labelnames=["function", "outcome"],
)
NOTIFICATION_DELIVERY_TOTAL: Final = Counter(
    "notification_delivery_total",
    "Notification delivery attempts by channel and outcome",
    labelnames=["channel", "outcome"],
)
NOTIFICATION_DELIVERY_DURATION_SECONDS: Final = Histogram(
    "notification_delivery_duration_seconds",
    "Notification delivery attempt duration in seconds",
    labelnames=["channel"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

# Fixed outcome vocabularies (keep these enums-of-strings in one place so
# new labels are a deliberate change, not an accident).
JOB_COMPLETED: Final = "completed"
JOB_RETRIED: Final = "retried"
JOB_FAILED: Final = "failed"

NOTIF_SUCCESS: Final = "success"
NOTIF_REJECTED: Final = "rejected"
NOTIF_RETRYABLE: Final = "retryable"
NOTIF_FAILED: Final = "failed"

# The bounded channel vocabulary for metric labels. The job payload is
# attacker-influenced; the generic layer validates channels against the
# NotificationChannel enum before delivery, but the metric layer never
# trusts that — anything outside the known set collapses to "unknown".
_KNOWN_CHANNELS: Final = frozenset({"telegram", "bale"})

# HTTP paths that are never recorded as request metrics: scraping /metrics
# or polling health endpoints would otherwise dominate every dashboard
# (self-observability loop, §14). Excluded deliberately and documented.
_UNMETERED_PATHS: Final = frozenset(
    {"/metrics", "/api/health", "/api/health/live", "/api/health/ready"}
)

_UNMATCHED: Final = "unmatched"


def _safe_channel(channel: object) -> str:
    """A bounded channel label: known names only, else ``unknown``."""
    value = str(channel) if channel is not None else ""
    return value if value in _KNOWN_CHANNELS else "unknown"


def _status_class(status_code: int) -> str:
    return f"{min(max(status_code // 100, 1), 5)}xx"


def observe_http_request(
    method: str, raw_path: str, route_template: object, status_code: int, duration_seconds: float
) -> None:
    """Record one finished HTTP request. Never raises (§18).

    ``route_template`` is the matched route's path template when routing
    resolved (FastAPI sets ``scope["route"]``), else ``None`` — the label
    then collapses to ``unmatched`` so a hostile URL can never create new
    label values. Paths in the self-observability exclusion set are not
    recorded at all.
    """
    try:
        if raw_path in _UNMETERED_PATHS:
            return
        route = (
            getattr(route_template, "path", None)
            if route_template is not None
            else None
        )
        if not isinstance(route, str) or not route:
            route = _UNMATCHED
        HTTP_REQUESTS_TOTAL.labels(
            method=method, route=route, status_class=_status_class(status_code)
        ).inc()
        HTTP_REQUEST_DURATION_SECONDS.labels(method=method, route=route).observe(
            duration_seconds
        )
    except Exception:  # noqa: BLE001 — instrumentation must never break a request
        logger.debug("http metric recording failed", exc_info=True)


def observe_http_request_start(method: str) -> None:
    try:
        HTTP_REQUESTS_IN_PROGRESS.labels(method=method).inc()
    except Exception:  # noqa: BLE001
        logger.debug("http in-progress metric failed", exc_info=True)


def observe_http_request_end(method: str) -> None:
    try:
        HTTP_REQUESTS_IN_PROGRESS.labels(method=method).dec()
    except Exception:  # noqa: BLE001
        logger.debug("http in-progress metric failed", exc_info=True)


def observe_job(function: str, outcome: str) -> None:
    """Record one background job outcome. Never raises (§18)."""
    try:
        WORKER_JOBS_TOTAL.labels(function=function, outcome=outcome).inc()
    except Exception:  # noqa: BLE001
        logger.debug("job metric recording failed", exc_info=True)


def observe_notification_attempt(
    channel: object, outcome: str, duration_seconds: float | None = None
) -> None:
    """Record one notification delivery attempt outcome. Never raises (§18)."""
    try:
        safe = _safe_channel(channel)
        NOTIFICATION_DELIVERY_TOTAL.labels(channel=safe, outcome=outcome).inc()
        if duration_seconds is not None:
            NOTIFICATION_DELIVERY_DURATION_SECONDS.labels(channel=safe).observe(
                duration_seconds
            )
    except Exception:  # noqa: BLE001
        logger.debug("notification metric recording failed", exc_info=True)


def metrics_payload() -> bytes:
    """The Prometheus text exposition of this process's registry.

    Controlled failure: any internal issue surfaces as an exception the
    endpoint turns into a plain 500 with no internals leaked.
    """
    return generate_latest(REGISTRY)
