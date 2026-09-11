"""Integration-style tests (Task 5.7 §18): the real architecture composes.

These tests exercise the full pipeline with REAL components and no
network and no real Redis:

    enqueue_notification (real service)
        ↓
    Redis queue (fakeredis, real arq ArqRedis + JSON serialization)
        ↓
    real arq Worker (real retry loop, real max_tries machinery)
        ↓
    generic NotificationMessage reconstructed (real job contract)
        ↓
    real build_notification_dispatcher + real NotificationDispatcher
        ↓
    real Telegram/Bale provider code over httpx2.MockTransport
        ↓
    success / retry behavior

fakeredis does not implement the INFO command that arq's startup calls
once for a cosmetic log line; the fixture neutralizes that one call. All
other worker machinery (queue polling, retries with defer, results,
health keys) is real.
"""

import asyncio
import json

import fakeredis.aioredis
import pytest
from arq import ArqRedis, Worker
from httpx2 import MockTransport, Request, Response

import app.worker.worker as worker_module
from app.core.config import Settings
from app.notifications.factory import build_notification_dispatcher
from app.worker.service import BackgroundNotificationService
from app.worker.serialization import json_job_deserializer, json_job_serializer
from app.worker.worker import WorkerSettings, deliver_notification

TELEGRAM_TOKEN = "1100000001:AA-test-telegram-token-never-real"
BALE_TOKEN = "2200000002:AA-test-bale-token-never-real"

SUCCESS_TELEGRAM = {"ok": True, "result": {"message_id": 11}}
SUCCESS_BALE = {"ok": True, "result": {"message_id": 22}}


class ScriptedTransport:
    """MockTransport whose handler plays a scripted outcome list.

    Outcomes: a Response (returned) or an Exception (raised). Serves a
    success envelope when the script is empty.
    """

    def __init__(self, outcomes: list) -> None:
        self.requests: list[Request] = []
        self._outcomes = list(outcomes)

        def handler(request: Request) -> Response:
            self.requests.append(request)
            if self._outcomes:
                outcome = self._outcomes.pop(0)
                if isinstance(outcome, Exception):
                    raise outcome
                return outcome
            url = str(request.url)
            if url.startswith("https://api.telegram.org/bot"):
                return Response(200, json=SUCCESS_TELEGRAM)
            if url.startswith("https://tapi.bale.ai/bot"):
                return Response(200, json=SUCCESS_BALE)
            raise AssertionError(f"unexpected destination: {url.split('/bot')[0]}")

        self.transport = MockTransport(handler)


def make_pool(fake) -> ArqRedis:
    return ArqRedis(
        pool_or_conn=fake.connection_pool,
        job_serializer=json_job_serializer,
        job_deserializer=json_job_deserializer,
        default_queue_name="ketabdaneh:notifications",
    )


@pytest.fixture
def no_redis_info(monkeypatch):
    """Neutralize arq's cosmetic startup INFO call (fakeredis has no INFO).

    arq's Worker.main references log_redis_info through the arq.worker
    module namespace (it imports the name from arq.connections), so that
    is what must be patched.
    """
    import arq.worker

    async def _noop(redis, log_func):
        return None

    monkeypatch.setattr(arq.worker, "log_redis_info", _noop)


def build_settings(**overrides) -> Settings:
    defaults = {
        "_env_file": None,
        "telegram_bot_token": TELEGRAM_TOKEN,
        "bale_bot_token": BALE_TOKEN,
        "notification_max_attempts": 4,
        "notification_retry_base_delay_seconds": 0.01,
        "notification_retry_max_delay_seconds": 0.05,
    }
    defaults.update(overrides)
    return Settings(**defaults)


async def run_worker(pool: ArqRedis, settings: Settings, transport, burst=True) -> Worker:
    """A real arq Worker wired like production, with a mock transport."""
    from app.worker.retry import RetryPolicy

    ctx = {
        "notification_dispatcher": build_notification_dispatcher(
            settings, transport=transport
        ),
        "notification_retry_policy": RetryPolicy(
            max_attempts=settings.notification_max_attempts,
            base_delay_seconds=settings.notification_retry_base_delay_seconds,
            max_delay_seconds=settings.notification_retry_max_delay_seconds,
        ),
    }

    return Worker(
        functions=WorkerSettings.functions,
        queue_name="ketabdaneh:notifications",
        burst=burst,
        redis_pool=pool,
        job_serializer=json_job_serializer,
        job_deserializer=json_job_deserializer,
        handle_signals=False,
        poll_delay=0.005,
        max_tries=25,
        ctx=ctx,
    )
    return worker


# --- the full pipeline: enqueue → worker → real provider code -------------------


def test_full_pipeline_success_telegram(no_redis_info) -> None:
    async def scenario():
        fake = fakeredis.aioredis.FakeRedis()
        pool = make_pool(fake)
        settings = build_settings()
        scripted = ScriptedTransport([])
        service = BackgroundNotificationService(settings, pool=pool)

        job = await service.enqueue_notification(
            channel="telegram",
            address="100200300",
            text="رویداد «تحلیل کتاب» — جمعه ساعت ۱۷",
            category="event",
            metadata={"event_id": 5},
        )
        worker = await run_worker(pool, settings, scripted.transport)
        completed = await worker.run_check()

        await pool.aclose()
        await fake.aclose()
        return completed, scripted

    completed, scripted = asyncio.run(scenario())

    assert completed == 1
    assert len(scripted.requests) == 1
    request = scripted.requests[0]
    assert str(request.url) == (
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    )
    body = json.loads(request.content.decode("utf-8"))
    assert body["chat_id"] == "100200300"
    assert body["text"] == "رویداد «تحلیل کتاب» — جمعه ساعت ۱۷"


def test_full_pipeline_success_bale(no_redis_info) -> None:
    async def scenario():
        fake = fakeredis.aioredis.FakeRedis()
        pool = make_pool(fake)
        settings = build_settings()
        scripted = ScriptedTransport([])
        service = BackgroundNotificationService(settings, pool=pool)

        await service.enqueue_notification(
            channel="bale", address="b-1", text="سلام", category="event"
        )
        worker = await run_worker(pool, settings, scripted.transport)
        completed = await worker.run_check()

        await pool.aclose()
        await fake.aclose()
        return completed, scripted

    completed, scripted = asyncio.run(scenario())

    assert completed == 1
    assert str(scripted.requests[0].url) == (
        f"https://tapi.bale.ai/bot{BALE_TOKEN}/sendMessage"
    )


def test_full_pipeline_retries_then_succeeds(no_redis_info) -> None:
    # Two transient failures (5xx) then success: the real worker retries
    # through the real provider code and the notification is delivered.
    async def scenario():
        fake = fakeredis.aioredis.FakeRedis()
        pool = make_pool(fake)
        settings = build_settings()
        scripted = ScriptedTransport(
            [
                Response(503, json={"ok": False, "error_code": 503}),
                Response(503, json={"ok": False, "error_code": 503}),
            ]
        )
        service = BackgroundNotificationService(settings, pool=pool)

        await service.enqueue_notification(
            channel="telegram", address="1", text="x", category="event"
        )
        worker = await run_worker(pool, settings, scripted.transport)
        completed = await worker.run_check()

        await pool.aclose()
        await fake.aclose()
        return completed, scripted, worker

    completed, scripted, worker = asyncio.run(scenario())

    assert completed == 1
    assert len(scripted.requests) == 3  # two failures + final success
    assert worker.jobs_retried == 2
    assert worker.jobs_failed == 0


def test_full_pipeline_rejected_is_never_retried(no_redis_info) -> None:
    # 400 "chat not found": permanent — exactly one attempt, job fails.
    async def scenario():
        fake = fakeredis.aioredis.FakeRedis()
        pool = make_pool(fake)
        settings = build_settings()
        scripted = ScriptedTransport(
            [Response(400, json={"ok": False, "error_code": 400,
                                 "description": "Bad Request: chat not found"})]
        )
        service = BackgroundNotificationService(settings, pool=pool)

        await service.enqueue_notification(
            channel="telegram", address="1", text="x", category="event"
        )
        worker = await run_worker(pool, settings, scripted.transport)
        try:
            await worker.run_check()
            failed = False
        except Exception:
            failed = True

        await pool.aclose()
        await fake.aclose()
        return scripted, worker, failed

    scripted, worker, failed = asyncio.run(scenario())

    assert failed is True
    assert len(scripted.requests) == 1  # one attempt only — no retry
    assert worker.jobs_retried == 0
    assert worker.jobs_failed == 1


def test_full_pipeline_exhausts_attempts_then_fails(no_redis_info) -> None:
    # Persistent 5xx: the bounded policy allows 4 attempts (the settings
    # max), then the job fails permanently — never infinite retries.
    async def scenario():
        fake = fakeredis.aioredis.FakeRedis()
        pool = make_pool(fake)
        settings = build_settings(notification_max_attempts=3)
        scripted = ScriptedTransport(
            [Response(503, json={"ok": False})] * 10
        )
        service = BackgroundNotificationService(settings, pool=pool)

        await service.enqueue_notification(
            channel="telegram", address="1", text="x", category="event"
        )
        worker = await run_worker(pool, settings, scripted.transport)
        try:
            await worker.run_check()
            failed = False
        except Exception:
            failed = True

        await pool.aclose()
        await fake.aclose()
        return scripted, worker, failed

    scripted, worker, failed = asyncio.run(scenario())

    assert failed is True
    assert len(scripted.requests) == 3  # exactly max_attempts
    assert worker.jobs_failed == 1


def test_multiple_jobs_do_not_interfere(no_redis_info) -> None:
    # Three jobs across both channels, one transient failure in the
    # script — each job is delivered independently and in full (arbitrary
    # start order: whichever job hits the scripted failure first retries).
    async def scenario():
        fake = fakeredis.aioredis.FakeRedis()
        pool = make_pool(fake)
        settings = build_settings()
        scripted = ScriptedTransport(
            [Response(500, json={"ok": False})]  # one transient failure
        )
        service = BackgroundNotificationService(settings, pool=pool)

        await service.enqueue_notification(
            channel="telegram", address="t-1", text="one", category="event"
        )
        await service.enqueue_notification(
            channel="bale", address="b-1", text="two", category="event"
        )
        await service.enqueue_notification(
            channel="telegram", address="t-2", text="three", category="event"
        )
        worker = await run_worker(pool, settings, scripted.transport)
        completed = await worker.run_check()

        await pool.aclose()
        await fake.aclose()
        return completed, scripted

    completed, scripted = asyncio.run(scenario())

    assert completed == 3
    addresses = [
        json.loads(r.content.decode("utf-8"))["chat_id"]
        for r in scripted.requests
    ]
    # One transient failure → one job made two attempts → 4 requests,
    # and every job was delivered.
    assert len(addresses) == 4
    assert set(addresses) == {"t-1", "b-1", "t-2"}


# --- the worker composes through the real factory boundary ----------------------


def test_worker_startup_builds_dispatcher_via_factory(no_redis_info, monkeypatch) -> None:
    # The startup hook is THE composition point: it must call
    # build_notification_dispatcher with the app settings and nothing
    # else. get_settings is injected so the developer's local env cannot
    # influence the assertions.
    async def scenario():
        settings = build_settings()
        monkeypatch.setattr(worker_module, "get_settings", lambda: settings)

        from app.worker.worker import startup

        ctx = {}
        await startup(ctx)
        return ctx, settings

    ctx, settings = asyncio.run(scenario())

    from app.notifications import NotificationDispatcher

    assert isinstance(ctx["notification_dispatcher"], NotificationDispatcher)
    assert ctx["notification_dispatcher"].has_provider("telegram")
    assert ctx["notification_dispatcher"].has_provider("bale")
    assert ctx["notification_retry_policy"].max_attempts == settings.notification_max_attempts


def test_worker_uses_dispatcher_not_provider_code(no_redis_info) -> None:
    # Structural: the worker module delivers ONLY through the dispatcher
    # abstraction — it never imports providers or HTTP clients.
    import inspect

    source = inspect.getsource(worker_module)

    assert "build_notification_dispatcher" in source  # the factory boundary
    for forbidden in (
        "TelegramNotificationProvider(",   # direct construction
        "BaleNotificationProvider(",
        "httpx2",
        "api.telegram.org",
        "tapi.bale.ai",
        "/sendMessage",
    ):
        assert forbidden not in source, forbidden


def test_worker_settings_compose_the_real_job_function() -> None:
    # The arq settings class wires the real deliver_notification and the
    # shared JSON serialization — the enqueue side and worker side cannot
    # drift apart.
    assert WorkerSettings.functions == [deliver_notification]
    assert WorkerSettings.job_serializer is json_job_serializer
    assert WorkerSettings.job_deserializer is json_job_deserializer
    assert WorkerSettings.max_tries >= 10  # outer bound, policy is primary


# --- security: nothing secret crosses the queue ----------------------------------


def test_queued_payload_contains_no_credentials(no_redis_info) -> None:
    async def scenario():
        fake = fakeredis.aioredis.FakeRedis()
        pool = make_pool(fake)
        settings = build_settings()
        service = BackgroundNotificationService(settings, pool=pool)

        await service.enqueue_notification(
            channel="telegram",
            address="100200300",
            text="hello",
            category="event",
            metadata={"event_id": 9},
        )
        # Inspect the raw stored values: the job payload plus the queue's
        # sorted-set members. The tokens must not appear anywhere.
        keys = await fake.keys("*")
        values: list[str] = []
        for key in keys:
            key_type = await fake.type(key)
            if key_type == b"string" or isinstance(key_type, str) and key_type == "string":
                value = await fake.get(key)
                if value:
                    values.append(value.decode("utf-8", errors="replace"))
            elif key_type in (b"zset", "zset"):
                members = await fake.zrange(key, start=0, end=-1)
                values.extend(
                    m.decode("utf-8", errors="replace") for m in members
                )
        queued = await pool.queued_jobs()
        await pool.aclose()
        await fake.aclose()
        return values, queued

    values, queued = asyncio.run(scenario())

    assert len(queued) == 1
    for blob in values:
        assert TELEGRAM_TOKEN not in blob
        assert BALE_TOKEN not in blob
    # Explicit: the serialized job args contain no token either.
    serialized = json_job_serializer({"a": list(queued[0].args)}).decode("utf-8")
    assert TELEGRAM_TOKEN not in serialized
    assert BALE_TOKEN not in serialized


def test_redis_endpoint_never_comes_from_notification_data() -> None:
    # Structural: the Redis endpoint is derived ONLY from settings —
    # never from job payloads or notification data.
    import inspect

    import app.worker.service as service_module

    source = inspect.getsource(service_module)
    assert "RedisSettings.from_dsn" in source
    assert "self._settings.redis_url" in source
