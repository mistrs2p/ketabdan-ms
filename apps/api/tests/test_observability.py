"""Tests for the observability foundation (Task 5.9 §22).

Health endpoints, metrics, and their integration with the request
middleware and the worker — fully offline: Redis via fakeredis (patched
at the health module's ``aioredis`` name), the DB check against the
test SQLite engine (patched at the health module's ``get_engine`` name
— exactly the seam the check calls, auto-restored by monkeypatch).
Real-PostgreSQL/Redis behavior is covered by the runtime smoke.
"""

from typing import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool

import app.api.health as health_module
import app.worker.worker as worker_module
from app.core import metrics as metrics_module
from app.core.metrics import metrics_payload


class FakeRedisState:
    """Minimal in-memory Redis state for the health checks — no event
    loop, no network, no fakeredis loop-binding pitfalls (TestClient runs
    the app on its own loop; sharing a fakeredis instance across loops
    raises). ``ping_error``, when set, is raised by every PING so tests
    can exercise the checks' real exception-swallowing path."""

    def __init__(self) -> None:
        self.keys: dict = {}
        self.ping_error: Exception | None = None

    class _Client:
        def __init__(self, state: "FakeRedisState") -> None:
            self._state = state

        async def ping(self):
            if self._state.ping_error is not None:
                raise self._state.ping_error
            return True

        async def exists(self, key):
            return 1 if key in self._state.keys else 0

        async def aclose(self) -> None:
            pass

    class _RedisModule:
        # Stands in for redis.asyncio at the health module's ``aioredis``
        # name: every from_url call (one per check, like production) gets
        # a client bound to the shared state. The real redis library
        # class is never touched.
        class Redis:
            @classmethod
            def from_url(cls, url, **kwargs):
                return FakeRedisState._Client(FakeRedisState._current)

    _current: "FakeRedisState | None" = None


@pytest.fixture()
def redis_fake(monkeypatch) -> FakeRedisState:
    state = FakeRedisState()
    FakeRedisState._current = state
    monkeypatch.setattr(health_module, "aioredis", FakeRedisState._RedisModule)
    yield state
    FakeRedisState._current = None


@pytest.fixture()
def db_fake(monkeypatch) -> Engine:
    """The readiness DB check runs in a worker thread, so the SQLite
    engine needs a shared, cross-thread connection."""
    engine = create_engine(
        "sqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    monkeypatch.setattr(health_module, "get_engine", lambda: engine)
    return engine


def ready(client: TestClient):
    response = client.get("/api/health/ready")
    return response.status_code, response.json()


# --- liveness --------------------------------------------------------------------


def test_liveness_live_endpoint(client: TestClient) -> None:
    response = client.get("/api/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_liveness_legacy_endpoint_contract_unchanged(client: TestClient) -> None:
    # The pre-5.9 contract the frontend depends on (apps/web health client).
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_liveness_touches_no_dependencies(client: TestClient, monkeypatch) -> None:
    # Liveness must never check DB/Redis: failing dependencies must not get
    # a healthy process killed by a restart loop.
    calls: list[str] = []

    def _fail(url, **kwargs):
        calls.append("redis")
        raise AssertionError("liveness must not open a Redis connection")

    def _db_fail():
        calls.append("db")
        raise AssertionError("liveness must not touch the database")

    monkeypatch.setattr(health_module, "aioredis", _fail)
    monkeypatch.setattr(health_module, "get_engine", _db_fail)

    response = client.get("/api/health/live")
    assert response.status_code == 200
    assert calls == []


# --- readiness -------------------------------------------------------------------


def test_readiness_ok_when_database_and_redis_ok(
    client: TestClient, redis_fake, db_fake
) -> None:
    # A worker heartbeat key exists in Redis → all three checks report ok.
    redis_fake.keys[health_module.WORKER_HEALTH_KEY] = b"1"

    status, body = ready(client)
    assert status == 200
    assert body == {
        "status": "ok",
        "checks": {"database": "ok", "redis": "ok", "worker": "ok"},
    }


def test_readiness_503_when_database_unavailable(
    client: TestClient, redis_fake, monkeypatch
) -> None:
    async def _db_down():
        return "unavailable"

    monkeypatch.setattr(health_module, "_check_database", _db_down)
    status, body = ready(client)
    assert status == 503
    assert body["status"] == "not_ready"
    assert body["checks"]["database"] == "unavailable"
    assert body["checks"]["redis"] == "ok"


def test_readiness_503_when_redis_unavailable(
    client: TestClient, monkeypatch
) -> None:
    async def _redis_down():
        return "unavailable"

    async def _db_ok():
        return "ok"

    monkeypatch.setattr(health_module, "_check_redis", _redis_down)
    monkeypatch.setattr(health_module, "_check_database", _db_ok)
    status, body = ready(client)
    assert status == 503
    assert body["checks"]["redis"] == "unavailable"
    assert body["status"] == "not_ready"


def test_worker_heartbeat_absent_is_reported_not_assumed(
    client: TestClient, redis_fake, db_fake
) -> None:
    # §10: never report "worker healthy" merely because Redis works —
    # with no heartbeat key in Redis the check must say so.
    status, body = ready(client)
    assert status == 200  # informational, not gating
    assert body["checks"]["worker"] == "no_recent_heartbeat"


def test_worker_heartbeat_is_informational_not_gating(
    client: TestClient, monkeypatch
) -> None:
    # Even an unavailable worker check must not make the API unready.
    async def _redis_ok():
        return "ok"

    async def _db_ok():
        return "ok"

    async def _no_worker():
        return "no_recent_heartbeat"

    monkeypatch.setattr(health_module, "_check_redis", _redis_ok)
    monkeypatch.setattr(health_module, "_check_database", _db_ok)
    monkeypatch.setattr(health_module, "_check_worker_heartbeat", _no_worker)
    status, body = ready(client)
    assert status == 200
    assert body["checks"]["worker"] == "no_recent_heartbeat"


def test_readiness_response_never_carries_details(
    client: TestClient, redis_fake, db_fake, monkeypatch
) -> None:
    # A dependency failing with a juicy exception: the REAL check must
    # swallow it and the response must carry only the fixed word — no
    # exception text, no URLs, no credentials.
    redis_fake.ping_error = RuntimeError(
        "Error 111 connecting to redis:6390 with password 'hunter2' "
        "via redis://admin:secret@redis.internal:6390/0"
    )

    status, body = ready(client)
    blob = str(body)
    assert status == 503
    assert "hunter2" not in blob
    assert "secret" not in blob
    assert "redis://" not in blob
    assert "Error 111" not in blob
    assert body["checks"]["redis"] == "unavailable"


def test_provider_outage_does_not_fail_readiness() -> None:
    # Readiness checks infrastructure dependencies only — never the
    # Telegram/Bale providers (§7). Structural: the health module never
    # imports the notification provider layer.
    import inspect

    source = inspect.getsource(health_module)
    for forbidden in (
        "build_notification_dispatcher",
        "telegram",
        "bale",
        "notification_timeout",
    ):
        assert forbidden not in source.lower(), forbidden


def test_readiness_checks_run_with_bounded_timeouts() -> None:
    # Structural: check timeouts are constants of sane magnitude —
    # readiness answers in bounded time even with hung dependencies.
    assert health_module.DATABASE_CHECK_TIMEOUT_SECONDS <= 5
    assert health_module.REDIS_CHECK_TIMEOUT_SECONDS <= 5


def test_database_check_uses_the_existing_engine() -> None:
    # Structural (§8): the DB check goes through the application's
    # get_engine — no second connection system anywhere in the module.
    import inspect

    source = inspect.getsource(health_module)
    assert "from app.db.session import get_engine" in source
    assert "get_engine()" in source
    assert "create_engine" not in source


# --- metrics endpoint ------------------------------------------------------------


def test_metrics_endpoint_exposes_prometheus_text(client: TestClient) -> None:
    response = client.get("/metrics")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    for name in (
        "http_requests_total",
        "http_request_duration_seconds",
        "http_requests_in_progress",
        "worker_jobs_total",
        "notification_delivery_total",
        "notification_delivery_duration_seconds",
    ):
        assert f"# TYPE {name}" in response.text


def test_request_counter_increments(client: TestClient) -> None:
    before = client.get("/metrics").text
    client.get("/api/health/live")  # unmetered path — must not count
    client.get("/api/nope")  # unmatched → the "unmatched" label
    after = client.get("/metrics").text

    def total(blob: str) -> float:
        for line in blob.splitlines():
            if line.startswith("http_requests_total{") and 'route="unmatched"' in line:
                return float(line.rsplit(" ", 1)[1])
        return 0.0

    assert total(after) == total(before) + 1  # only the unmatched request


def test_route_label_is_template_not_raw_path(client: TestClient) -> None:
    # A concrete id path must surface as the {param} template — the raw
    # id must never become a metric label value (unbounded cardinality).
    client.get("/api/events/not-a-real-uuid-but-long-id-123456")
    blob = client.get("/metrics").text
    assert "not-a-real-uuid-but-long-id-123456" not in blob
    assert 'route="/api/events/{event_id}"' in blob


def test_query_string_never_becomes_a_label(client: TestClient) -> None:
    # §12: full query strings are forbidden labels — and the middleware
    # passes only the path, so even tokens in a query must not surface.
    client.get("/api/events?token=super-secret-query-token-value")
    blob = client.get("/metrics").text
    assert "super-secret-query-token-value" not in blob
    assert "token=" not in blob


def test_health_and_metrics_paths_are_not_metered(client: TestClient) -> None:
    # Scraping /metrics must not inflate request counters (self-
    # observability loop); health polls likewise.
    before = client.get("/metrics").text
    for _ in range(3):
        client.get("/metrics")
        client.get("/api/health")
        client.get("/api/health/live")
        client.get("/api/health/ready")
    after = client.get("/metrics").text

    def totals(blob: str) -> float:
        return sum(
            float(line.rsplit(" ", 1)[1])
            for line in blob.splitlines()
            if line.startswith("http_requests_total{")
        )

    assert totals(after) == totals(before)


def test_metric_helpers_never_raise() -> None:
    # §18: broken instrumentation must not break the app.
    class _Broken:
        def labels(self, *a, **k):
            raise RuntimeError("boom")

    original = metrics_module.HTTP_REQUESTS_TOTAL
    metrics_module.HTTP_REQUESTS_TOTAL = _Broken()  # type: ignore[assignment]
    try:
        metrics_module.observe_http_request("GET", "/x", None, 200, 0.1)
        metrics_module.observe_http_request_start("GET")
        metrics_module.observe_http_request_end("GET")
        metrics_module.observe_job("f", "completed")
        metrics_module.observe_notification_attempt("telegram", "success", 0.1)
    finally:
        metrics_module.HTTP_REQUESTS_TOTAL = original  # type: ignore[assignment]


def test_channel_label_collapses_unknown_values() -> None:
    # A hostile channel in a payload must not become a metric label.
    metrics_module.observe_notification_attempt("telegram", "success")
    metrics_module.observe_notification_attempt("EVIL-CHANNEL-NAME", "success")
    blob = metrics_payload().decode("utf-8")
    assert "EVIL-CHANNEL-NAME" not in blob
    assert 'channel="unknown"' in blob


def test_no_secret_leakage_in_metrics(client: TestClient) -> None:
    # An authenticated request: the token must not surface in metrics.
    client.headers["Authorization"] = "Bearer super-secret-jwt-value"
    client.get("/api/persons")
    client.headers.pop("Authorization", None)
    blob = client.get("/metrics").text
    assert "super-secret-jwt-value" not in blob


def test_4xx_status_class_recorded(client: TestClient) -> None:
    client.get("/api/persons")  # no credentials → 401
    blob = client.get("/metrics").text
    assert 'status_class="4xx"' in blob


def test_5xx_status_class_recorded(authed_client: TestClient) -> None:
    # A route that raises mid-request must land in the 5xx bucket.
    from app.db.session import get_db
    from app.main import app

    def boom() -> Iterator[None]:
        raise RuntimeError("kaboom")
        yield  # pragma: no cover

    original = app.dependency_overrides[get_db]
    app.dependency_overrides[get_db] = boom
    try:
        raw = TestClient(app, raise_server_exceptions=False)
        response = raw.get("/api/persons")
        assert response.status_code == 500
    finally:
        app.dependency_overrides[get_db] = original

    blob = authed_client.get("/metrics").text
    assert 'status_class="5xx"' in blob


# --- worker metrics (§15/§16) -----------------------------------------------------


class RecordingObservers:
    """Patches the observer names the worker module calls, recording
    every invocation — offline, no registry dependency."""

    def __init__(self, monkeypatch) -> None:
        self.jobs: list[tuple[str, str]] = []
        self.notifications: list[tuple[object, str, float | None]] = []

        def fake_observe_job(function, outcome):
            self.jobs.append((function, outcome))

        def fake_observe_notification(channel, outcome, duration_seconds=None):
            self.notifications.append((channel, outcome, duration_seconds))

        monkeypatch.setattr(worker_module, "observe_job", fake_observe_job)
        monkeypatch.setattr(
            worker_module, "observe_notification_attempt", fake_observe_notification
        )


def _deliver_job(payload: dict, result: "NotificationResult | None", job_try: int = 1) -> str:
    """Run one deliver_notification job against a scripted dispatcher.

    Returns the job's status string, or ``raised:<ExceptionName>`` for the
    permanent-failure / retry outcomes (arq Retry and the worker's
    PermanentNotificationFailure are control flow, not errors here).
    """
    import asyncio

    from app.worker.retry import RetryPolicy

    class _ScriptedDispatcher:
        async def send(self, message):
            return result

    async def run():
        ctx = {
            "notification_dispatcher": _ScriptedDispatcher(),
            "notification_retry_policy": RetryPolicy(
                max_attempts=3, base_delay_seconds=0.01, max_delay_seconds=0.05
            ),
            "job_id": "job-1",
            "job_try": job_try,
        }
        return await worker_module.deliver_notification(ctx, payload)

    try:
        return asyncio.run(run())
    except Exception as exc:  # arq Retry / PermanentNotificationFailure
        return f"raised:{exc.__class__.__name__}"


VALID_PAYLOAD = {
    "channel": "telegram",
    "address": "100200300",
    "text": "hello",
    "category": "event",
    "metadata": {},
}


def _result(success: bool, error_code: str | None = None) -> "NotificationResult":
    from app.notifications import NotificationResult
    from app.notifications.models import NotificationChannel

    return NotificationResult(
        success=success,
        channel=NotificationChannel.TELEGRAM,
        external_message_id="42" if success else None,
        error_code=error_code,
    )


def test_worker_metrics_on_success(monkeypatch) -> None:
    observers = RecordingObservers(monkeypatch)
    assert _deliver_job(VALID_PAYLOAD, _result(success=True)) == "delivered"
    assert observers.jobs == [("deliver_notification", "completed")]
    # (channel, outcome, duration-recorded)
    assert len(observers.notifications) == 1
    channel, outcome, duration = observers.notifications[0]
    assert (channel, outcome) == ("telegram", "success")
    assert duration is not None and duration >= 0


def test_worker_metrics_on_rejection(monkeypatch) -> None:
    observers = RecordingObservers(monkeypatch)
    outcome = _deliver_job(
        VALID_PAYLOAD, _result(success=False, error_code="notification_rejected")
    )
    assert outcome.startswith("raised:PermanentNotificationFailure")
    assert observers.jobs == [("deliver_notification", "failed")]
    assert observers.notifications[0][:2] == ("telegram", "rejected")


def test_worker_metrics_on_retryable_failure(monkeypatch) -> None:
    observers = RecordingObservers(monkeypatch)
    outcome = _deliver_job(
        VALID_PAYLOAD, _result(success=False, error_code="provider_unavailable"),
        job_try=1,
    )
    assert outcome.startswith("raised:Retry")
    assert observers.jobs == [("deliver_notification", "retried")]
    assert observers.notifications[0][:2] == ("telegram", "retryable")


def test_worker_metrics_on_permanent_failure_after_exhaustion(monkeypatch) -> None:
    observers = RecordingObservers(monkeypatch)
    outcome = _deliver_job(
        VALID_PAYLOAD, _result(success=False, error_code="provider_unavailable"),
        job_try=3,  # final attempt under max_attempts=3
    )
    assert outcome.startswith("raised:PermanentNotificationFailure")
    assert observers.jobs == [("deliver_notification", "failed")]
    assert observers.notifications[0][:2] == ("telegram", "failed")


def test_worker_metrics_on_invalid_payload(monkeypatch) -> None:
    # Corrupt payload: job-level failure, but NO notification metric —
    # there is no channel to attribute it to.
    observers = RecordingObservers(monkeypatch)
    outcome = _deliver_job({"channel": "telegram"}, None)  # missing fields
    assert outcome.startswith("raised:PermanentNotificationFailure")
    assert observers.jobs == [("deliver_notification", "failed")]
    assert observers.notifications == []


def test_worker_metrics_use_no_recipient_or_text_labels(monkeypatch) -> None:
    # Structural (§12/§15): the worker never passes recipients, texts,
    # or message ids into metric calls — only bounded vocabularies.
    # (Diagnostic LOGS may carry the external message id; labels may not.)
    import inspect

    observe_lines = [
        line.strip()
        for line in inspect.getsource(worker_module).splitlines()
        if "observe_" in line
    ]
    assert observe_lines  # the worker does observe its jobs
    for line in observe_lines:
        for forbidden in ("recipient", "metadata", "external_message_id", "job_id"):
            assert forbidden not in line, (forbidden, line)
