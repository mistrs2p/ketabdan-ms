"""Tests for worker / notification logging onto the logging foundation
(Task 5.8 §12-13, §16-17).

The worker loggers must make job lifecycle, retry, and Redis problems
diagnosable — carrying job_id/job_try/channel/category — while never
carrying notification text, recipient addresses, or any credential.
Offline: fake providers, caplog, no wall-clock assertions.
"""

import inspect
import logging
import re

import pytest

import app.worker.worker as worker_module

from tests.test_worker_retry import (
    PAYLOAD,
    POLICY,
    ScriptedProvider,
    make_ctx,
    run,
)

TELEGRAM_TOKEN = "1100000001:AA-test-telegram-token-never-real"


@pytest.fixture()
def capture(caplog):
    with caplog.at_level(logging.DEBUG, logger="app.worker.delivery"):
        yield caplog


def delivery_records(caplog):
    return [r for r in caplog.records if r.name == "app.worker.delivery"]


def texts(records) -> list[str]:
    return [r.getMessage() for r in records]


# --- lifecycle lines and their context -------------------------------------------


def test_success_line_carries_channel_category_job_id_and_duration(
    capture,
) -> None:
    provider = ScriptedProvider("telegram", ["success"])
    ctx = make_ctx(provider, POLICY)
    ctx["job_id"] = "job-abc-1"

    status = run(worker_module.deliver_notification(ctx, dict(PAYLOAD)))

    assert status == "delivered"
    lines = texts(delivery_records(capture))
    assert len(lines) == 1
    line = lines[0]
    assert "channel=telegram" in line
    assert "category=event" in line
    assert "job_id=job-abc-1" in line
    assert "external_id=fake-1" in line
    assert re.search(r"duration_ms=\d+", line)


def test_retry_line_carries_attempt_numbers_and_job_id(capture) -> None:
    from arq import Retry

    provider = ScriptedProvider("telegram", ["unavailable"])
    ctx = make_ctx(provider, POLICY, job_try=2)
    ctx["job_id"] = "job-retry-9"

    with pytest.raises(Retry):
        run(worker_module.deliver_notification(ctx, dict(PAYLOAD)))

    lines = texts(delivery_records(capture))
    assert len(lines) == 1
    line = lines[0]
    assert "attempt 2/4 failed" in line
    assert "error_code=provider_unavailable" in line
    assert "job_id=job-retry-9" in line


def test_permanent_failure_line_is_error_level(capture) -> None:
    provider = ScriptedProvider("telegram", ["rejected"])
    ctx = make_ctx(provider, POLICY)
    ctx["job_id"] = "job-rej-1"

    with pytest.raises(Exception):
        run(worker_module.deliver_notification(ctx, dict(PAYLOAD)))

    records = [r for r in delivery_records(capture) if "permanently rejected" in r.getMessage()]
    assert len(records) == 1
    assert records[0].levelno == logging.WARNING


def test_exhausted_attempts_line_is_error_level(capture) -> None:
    provider = ScriptedProvider("telegram", ["unavailable"])
    ctx = make_ctx(provider, POLICY, job_try=4)
    ctx["job_id"] = "job-max-1"

    with pytest.raises(Exception):
        run(worker_module.deliver_notification(ctx, dict(PAYLOAD)))

    records = [
        r
        for r in delivery_records(capture)
        if "failed permanently after 4 attempts" in r.getMessage()
    ]
    assert len(records) == 1
    assert records[0].levelno == logging.ERROR


def test_invalid_payload_line_is_error_level_without_payload_content(
    capture,
) -> None:
    payload = {"channel": "telegram", "text": "secret-ish text content"}

    with pytest.raises(Exception):
        run(worker_module.deliver_notification(make_ctx(ScriptedProvider("telegram", []), POLICY), payload))

    records = [
        r for r in delivery_records(capture) if "payload is invalid" in r.getMessage()
    ]
    assert len(records) == 1
    assert records[0].levelno == logging.ERROR
    assert "secret-ish text content" not in records[0].getMessage()


# --- no secrets / no notification content in worker logs ----------------------------


def test_worker_logs_never_contain_notification_text_or_address(capture) -> None:
    payload = dict(PAYLOAD, address="987654321", text="hi there secret text")
    provider = ScriptedProvider("telegram", ["unavailable"])
    ctx = make_ctx(provider, POLICY)
    ctx["job_id"] = "job-s-1"

    from arq import Retry

    with pytest.raises(Retry):
        run(worker_module.deliver_notification(ctx, payload))

    for record in capture.records:
        message = record.getMessage()
        assert "hi there secret text" not in message
        assert "987654321" not in message


def test_worker_logs_never_contain_bot_tokens(capture) -> None:
    payload = dict(PAYLOAD, metadata={"bot_token": TELEGRAM_TOKEN})
    provider = ScriptedProvider("telegram", ["unavailable"])
    ctx = make_ctx(provider, POLICY)
    ctx["job_id"] = "job-t-1"

    from arq import Retry

    with pytest.raises(Retry):
        run(worker_module.deliver_notification(ctx, payload))

    for record in capture.records:
        assert TELEGRAM_TOKEN not in record.getMessage()


# --- structural: the logging rules cannot silently regress -------------------------

def test_worker_uses_the_foundation_logger_convention() -> None:
    # app.core.logging.get_logger — the single namespace convention.
    source = inspect.getsource(worker_module)
    assert "from app.core.logging import get_logger" in source
    assert "basicConfig" not in source
    assert "addHandler" not in source
    assert "print(" not in source
