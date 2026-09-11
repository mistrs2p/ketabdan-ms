"""Centralized application logging (Task 5.8).

The ONE place application logging is configured. Everything else in the
codebase only calls ``logging.getLogger(...)`` — never ``basicConfig``,
never hand-rolled handlers, never ``print`` on production paths.

Design:

- stdlib ``logging`` only — no logging framework, no JSON dependency, no
  observability stack (explicitly out of scope for 5.8).
- One ``StreamHandler`` on the ROOT logger with a single formatter.
  Application and library loggers (``app.*``, ``arq.worker``, …) propagate
  to root and come out in one consistent format. Idempotent: calling
  ``configure_logging`` twice never duplicates handlers.
- Format: ISO-8601 UTC timestamp (machine-parsable, non-locale-dependent,
  unambiguous), level, logger name, process id (the API and the background
  worker are separate processes — ``pid`` is the cheapest way to tell
  their interleaved output apart), then the message. Nothing else on the
  normal path.
- ``uvicorn.access`` is silenced here because ``app.api.middleware``
  logs each request exactly once (method, path, status, duration,
  request id). When uvicorn applies its own dictConfig it does so BEFORE
  the app is imported, so this runs after and wins; when the app runs
  without uvicorn (tests) the logger is inert anyway.

Who logs what (no duplicates):

- requests        → ``app.api.request`` (our middleware), once per request
- 5xx tracebacks  → ``uvicorn.error`` — Starlette's ServerErrorMiddleware
                    re-raises unhandled exceptions and the server logs the
                    stack trace exactly once; we deliberately do NOT add
                    an app-level Exception handler that would log it twice
- arq queue events→ ``arq.worker`` (propagates to root)
- everything else→ ``app.*`` loggers per module

Call sites: ``app.main`` (import time — runs once per process, after
uvicorn's own config) and ``app.worker.__main__`` (``python -m app.worker``;
note that only the ``arq`` CLI configures logging itself, ``run_worker``
does not).
"""

import logging
import sys
from datetime import datetime, timezone

# The settings validator enforces these; kept here so the logging module
# is self-contained and testable without Settings.
VALID_LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")

# Marked so tests (and future tooling) can identify OUR handler on the
# root logger regardless of what handlers libraries have installed.
_HANDLER_MARKER = "ketabdaneh_logging_handler"


class ISO8601Formatter(logging.Formatter):
    """One consistent format: UTC ISO-8601, level, name, pid, message.

    ``%(asctime)s`` is overridden with an explicit UTC ISO-8601 rendering
    (``2026-09-11T09:41:12.345+00:00``) — machine-friendly, unambiguous,
    and independent of the machine's locale/timezone.
    """

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:  # noqa: N802
        return datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(
            timespec="milliseconds"
        )


LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s pid=%(process)d %(message)s"


def get_logger(name: str) -> logging.Logger:
    """Namespace convention for application loggers (``app.*``)."""
    return logging.getLogger(name)


def _resolve_level(level: str | int | None) -> int:
    if level is None:
        return logging.INFO
    if isinstance(level, int):
        return level
    normalized = str(level).strip().upper()
    if normalized not in VALID_LOG_LEVELS:
        # Fail loudly and helpfully — never silently fall back (a mistyped
        # "IFNO" must not quietly mean "INFO" or "WARNING").
        raise ValueError(
            f"invalid log level {level!r}: expected one of "
            f"{', '.join(VALID_LOG_LEVELS)} (case-insensitive)"
        )
    return getattr(logging, normalized)


def _install_root_handler(root: logging.Logger) -> logging.Handler:
    handler = logging.StreamHandler(stream=sys.stderr)
    handler.setFormatter(ISO8601Formatter(LOG_FORMAT))
    setattr(handler, _HANDLER_MARKER, True)
    root.addHandler(handler)
    return handler


def app_log_handlers(root: logging.Logger) -> list[logging.Handler]:
    """The handlers this module installed on ``root`` (for tests)."""
    return [h for h in root.handlers if getattr(h, _HANDLER_MARKER, False)]


def configure_logging(level: str | int | None = None) -> None:
    """Configure application logging exactly once per process.

    - Installs a single stderr handler with the shared formatter on the
      root logger; a second call never adds another handler.
    - A second call MAY adjust the root level (e.g. tests), nothing else.
    - Silences ``uvicorn.access`` (our request middleware is the single
      per-request log line — see module docstring).
    """
    root = logging.getLogger()

    if not app_log_handlers(root):
        _install_root_handler(root)
        # One request log, ours: uvicorn's access log would duplicate
        # every request line our middleware already emits.
        uvicorn_access = logging.getLogger("uvicorn.access")
        uvicorn_access.handlers = []
        uvicorn_access.propagate = False

    root.setLevel(_resolve_level(level))
