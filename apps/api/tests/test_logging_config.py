"""Tests for the central logging configuration (Task 5.8 §16-17).

Everything here runs offline through caplog / in-memory handlers; nothing
touches wall-clock deadlines (durations are only asserted to be present
and parseable, never to a specific value).
"""

import logging
import re

import pytest

from app.core.config import Settings
from app.core.logging import (
    LOG_FORMAT,
    app_log_handlers,
    configure_logging,
    get_logger,
)


@pytest.fixture(autouse=True)
def restore_root_logging():
    """Keep configure_logging's process-global side effects test-local."""
    root = logging.getLogger()
    saved_handlers = list(root.handlers)
    saved_level = root.level
    saved_access_handlers = list(logging.getLogger("uvicorn.access").handlers)
    saved_access_propagate = logging.getLogger("uvicorn.access").propagate
    saved_arq_level = logging.getLogger("arq.worker").level
    yield
    root.handlers = saved_handlers
    root.setLevel(saved_level)
    access = logging.getLogger("uvicorn.access")
    access.handlers = saved_access_handlers
    access.propagate = saved_access_propagate
    logging.getLogger("arq.worker").setLevel(saved_arq_level)


# --- configuration: LOG_LEVEL setting ------------------------------------------


@pytest.mark.parametrize("value", ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
def test_log_level_accepts_standard_levels(value: str) -> None:
    assert Settings(_env_file=None, log_level=value).log_level == value


@pytest.mark.parametrize("value", ["debug", "info", "warning", "error", "critical"])
def test_log_level_is_case_insensitive(value: str) -> None:
    assert Settings(_env_file=None, log_level=value).log_level == value.upper()


@pytest.mark.parametrize("value", ["IFNO", "VERBOSE", "TRACE", "2", "", "WARN "])
def test_invalid_log_level_fails_cleanly(value: str) -> None:
    # A mistyped level is a configuration error naming the problem —
    # never a silent fallback to a different level.
    with pytest.raises(Exception) as excinfo:
        Settings(_env_file=None, log_level=value)
    message = str(excinfo.value)
    assert "log_level" in message
    assert value.strip() in message or "empty" in message.lower() or value in message


def test_log_level_default_is_info() -> None:
    assert Settings(_env_file=None).log_level == "INFO"


# --- configure_logging: handler safety and idempotency -------------------------


def test_configure_logging_installs_exactly_one_handler() -> None:
    configure_logging()
    assert len(app_log_handlers(logging.getLogger())) == 1


def test_configure_logging_is_idempotent_no_duplicate_handlers() -> None:
    configure_logging()
    configure_logging()
    configure_logging()
    assert len(app_log_handlers(logging.getLogger())) == 1


def test_configure_logging_sets_root_level() -> None:
    configure_logging(level="WARNING")
    assert logging.getLogger().level == logging.WARNING


def test_configure_logging_reconfigurable_level_without_new_handler() -> None:
    # A second call may adjust the level (tests do this) — never add a
    # second handler, which would double every log line.
    configure_logging(level="INFO")
    configure_logging(level="DEBUG")
    assert len(app_log_handlers(logging.getLogger())) == 1
    assert logging.getLogger().level == logging.DEBUG


def test_configure_logging_rejects_invalid_level() -> None:
    with pytest.raises(ValueError) as excinfo:
        configure_logging(level="IFNO")
    assert "IFNO" in str(excinfo.value)


def test_configure_logging_silences_uvicorn_access_log() -> None:
    # Our request middleware logs each request exactly once; uvicorn's
    # access log would duplicate every line. Under pytest, caplog's
    # catching_logs attaches ITS capture handlers to any non-propagating
    # logger (so records still reach caplog) — so the assertion is about
    # production behavior: no handler of OURS or uvicorn's remains, and
    # nothing propagates to the root handler.
    configure_logging()
    access = logging.getLogger("uvicorn.access")
    assert access.propagate is False
    for handler in access.handlers:
        # pytest's capture handlers (_pytest.logging) are test machinery;
        # anything else would mean uvicorn's access log still emits.
        assert type(handler).__module__ == "_pytest.logging"


def test_configure_logging_leaves_library_loggers_propagating() -> None:
    # arq.worker (and friends) must flow to the root handler unchanged —
    # no per-library handlers, no disabled loggers. (arq.worker's LEVEL
    # is pinned separately, below — propagation is unaffected by that.)
    configure_logging()
    for name in ("arq.worker", "uvicorn.error", "app.worker.delivery"):
        logger = logging.getLogger(name)
        assert logger.handlers == []
        assert logger.propagate is True


def test_configure_logging_pins_arq_worker_above_info(caplog) -> None:
    # arq's job-start INFO lines embed the serialized job arguments — for
    # notification jobs that is the recipient address and the message
    # text, which §9.4 locks as never-logged content (verified live in
    # Task 5.14: the unpatched worker printed them). The logger is pinned
    # to WARNING: INFO lines are dropped at the source, while arq's
    # ERROR lines (job failed — no arguments) still propagate.
    configure_logging()
    assert logging.getLogger("arq.worker").level == logging.WARNING
    with caplog.at_level(logging.INFO):
        logging.getLogger("arq.worker").info(
            "0.21s → 7d1a0913:deliver_notification("
            "{'channel': 'telegram', 'address': 'e2e-probe-address-514', "
            "'text': 'E2E-514 pi…)"
        )
        logging.getLogger("arq.worker").error("job failed, no arguments")
    assert not any(r.levelno == logging.INFO for r in caplog.records)
    assert any(r.levelno == logging.ERROR for r in caplog.records)


def test_arq_pin_survives_a_later_root_level_raise(caplog) -> None:
    # Redaction must not depend on verbosity: a second configure_logging
    # call raising the root level to DEBUG (tests do this) must not
    # re-enable arq's argument-embedding INFO lines.
    configure_logging(level="INFO")
    configure_logging(level="DEBUG")
    assert logging.getLogger().level == logging.DEBUG
    assert logging.getLogger("arq.worker").level == logging.WARNING


# --- the shared format ----------------------------------------------------------


def test_format_contains_timestamp_level_name_pid_message(caplog) -> None:
    configure_logging()
    with caplog.at_level(logging.INFO, logger="app.test.format"):
        logging.getLogger("app.test.format").info("hello format")
    assert len(caplog.records) == 1
    record = caplog.records[0]

    # Machine-parsable, non-locale-dependent pieces.
    formatter = logging.Formatter(LOG_FORMAT)
    rendered = app_log_handlers(logging.getLogger())[0].format(record)

    # ISO-8601 UTC timestamp with millisecond precision and explicit offset.
    assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}\+00:00 ", rendered)
    assert "INFO" in rendered
    assert "app.test.format" in rendered
    assert f"pid={record.process}" in rendered
    assert rendered.endswith("hello format")


def test_get_logger_namespaces_under_app() -> None:
    assert get_logger("app.worker.delivery").name == "app.worker.delivery"


# --- no stray configuration anywhere else ---------------------------------------


def test_no_basiconfig_or_handler_outside_core_logging() -> None:
    # Structural (Task 5.8 §5): logging configuration CALLS appear only
    # in the central module — nothing else configures logging. (Matched
    # as call syntax so prose mentions in comments don't false-positive.)
    from pathlib import Path

    api_dir = Path(__file__).resolve().parents[1] / "app"
    forbidden = ("basicConfig(", ".addHandler(", "dictConfig(", "fileConfig(")
    offenders = []
    for path in api_dir.rglob("*.py"):
        if "__pycache__" in str(path):
            continue
        source = path.read_text(encoding="utf-8")
        if path.name == "logging.py" and path.parent.name == "core":
            continue  # the one allowed place
        if any(pattern in source for pattern in forbidden):
            offenders.append(str(path))
    assert offenders == []


def test_no_print_on_production_paths() -> None:
    # print() remains only in the three interactive CLI scripts, whose
    # output IS their user interface (documented in docs/01 §9).
    from pathlib import Path

    app_dir = Path(__file__).resolve().parents[1] / "app"
    allowed = {"assign_role.py", "create_user.py"}
    allowed_paths = {
        app_dir / "assign_role.py",
        app_dir / "create_user.py",
        app_dir / "db" / "check.py",
    }
    offenders = []
    for path in app_dir.rglob("*.py"):
        if "__pycache__" in str(path) or path in allowed_paths:
            continue
        if re.search(r"(?<!#)\bprint\(", path.read_text(encoding="utf-8")):
            offenders.append(str(path))
    assert offenders == []
    assert allowed  # (silence unused-var linters; the set documents intent)
