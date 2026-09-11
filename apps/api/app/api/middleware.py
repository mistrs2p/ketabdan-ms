"""HTTP request logging + metrics at the FastAPI boundary (Tasks 5.8/5.9).

One log line per request, from a pure-ASGI middleware (no
``BaseHTTPMiddleware`` overhead):

    method path status duration_ms request_id

Rules (docs/01 §9):

- The path only — never the query string, headers, or body.
- A request/correlation id: an incoming ``X-Request-ID`` is accepted only
  when it is short and matches a safe charset (a hostile multi-kilobyte or
  header-injecting value must never be echoed into logs or responses);
  otherwise a fresh id is generated. The id is exposed on the request
  line, on ``request.state.request_id`` for handlers, and echoed back in
  the ``X-Request-ID`` response header so a client can quote it.
- Status >= 500 logs at WARNING; everything else (401/403/422 included —
  expected domain outcomes, not errors) logs at INFO. Unhandled
  exceptions are RE-RAISED here: Starlette's ServerErrorMiddleware and
  the server log the single stack trace, so this middleware never
  duplicates it — it only completes the request line.

Request metrics (Task 5.9, docs/01 §10), recorded in the same middleware
so one code path observes every request:

- ``http_requests_total{method, route, status_class}``
- ``http_request_duration_seconds{method, route}`` histogram
- ``http_requests_in_progress{method}`` gauge

``route`` is the ROUTE TEMPLATE (``/api/persons/{person_id}``) taken from
``scope["route"]`` which FastAPI sets during routing — never the raw
path, so label cardinality is bounded by the static route table.
Unmatched requests collapse to the literal ``unmatched``. Health and
metrics paths are not metered (self-observability loop). Metric helpers
never raise (docs/01 §10 error handling).
"""

import logging
import re
import time
import uuid

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.metrics import (
    observe_http_request,
    observe_http_request_end,
    observe_http_request_start,
)

logger = logging.getLogger("app.api.request")

REQUEST_ID_HEADER = "X-Request-ID"
# Bounded length + safe charset: accepted ids are echoed into logs and
# response headers, so they must never carry control characters, spaces,
# or arbitrary size.
_MAX_REQUEST_ID_LENGTH = 64
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")


def resolve_request_id(incoming: str | None) -> str:
    """A safe correlation id: the client's if acceptable, else fresh."""
    if incoming is not None:
        candidate = incoming.strip()
        if candidate and len(candidate) <= _MAX_REQUEST_ID_LENGTH and _SAFE_REQUEST_ID.match(candidate):
            return candidate
    return uuid.uuid4().hex


class RequestLoggingMiddleware:
    """Pure-ASGI middleware: request line + correlation id, nothing else."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = resolve_request_id(
            Headers(scope=scope).get("x-request-id")
        )
        # Visible to handlers via request.state.request_id (the same scope
        # object Starlette's Request wraps).
        state = scope.setdefault("state", {})
        state["request_id"] = request_id

        method = scope.get("method", "?")
        path = scope.get("path", "?")

        status_code = 500  # assumed until http.response.start says otherwise
        start = time.perf_counter()
        observe_http_request_start(method)

        async def send_with_request_id(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                MutableHeaders(scope=message).append(REQUEST_ID_HEADER, request_id)
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        except Exception:
            # Re-raised unchanged: ServerErrorMiddleware/the server logs
            # the stack trace exactly once (see module docstring).
            raise
        finally:
            duration_ms = (time.perf_counter() - start) * 1000.0
            observe_http_request_end(method)
            # scope["route"] is set by FastAPI's router (inside
            # self.app(...) above) — the route TEMPLATE, not the raw path.
            # Unmatched requests have no route: the metric layer collapses
            # them to the literal "unmatched" (bounded cardinality).
            observe_http_request(
                method=method,
                raw_path=path,
                route_template=scope.get("route"),
                status_code=status_code,
                duration_seconds=duration_ms / 1000.0,
            )
            log = logger.warning if status_code >= 500 else logger.info
            log(
                "request: %s %s -> %d %.1fms request_id=%s",
                method,
                path,
                status_code,
                duration_ms,
                request_id,
            )
