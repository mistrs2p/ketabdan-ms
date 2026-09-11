"""Runtime smoke for Task 5.8 (not a pytest file — run directly).

Exercises logging exactly as production entry points see it, in fresh
processes: uvicorn-style app import, the middleware request line, the
worker entry point, and idempotency. ASCII-only output (cp1252 console).
"""

import logging
import re
import subprocess
import sys

PY = [sys.executable, "-X", "utf8"]
FAILURES = []


def run_smoke(code: str, timeout: int = 60) -> subprocess.CompletedProcess:
    """Run a smoke snippet in a fresh process, decoding as UTF-8 (the
    console codepage is cp1252 and log lines are UTF-8)."""
    return subprocess.run(
        PY + ["-c", code],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )


def check(name: str, ok: bool, detail: str = "") -> None:
    status = "OK  " if ok else "FAIL"
    print(f"{status} {name}" + (f"  [{detail}]" if detail and not ok else ""))
    if not ok:
        FAILURES.append(name)


# --- 1. app import: logging configured once, correct level, no dupes ----------

APP_IMPORT = r"""
import logging
from app.main import app
from app.core.logging import app_log_handlers

root = logging.getLogger()
handlers = app_log_handlers(root)
print("HANDLER_COUNT", len(handlers))
print("ROOT_LEVEL", logging.getLevelName(root.level))
print("ACCESS_PROPAGATE", logging.getLogger("uvicorn.access").propagate)
print("ACCESS_HAS_UVICORN_HANDLER", any(
    type(h).__module__.startswith("uvicorn") for h in logging.getLogger("uvicorn.access").handlers
))
# app.api.request loggers propagate to root unchanged
print("REQ_PROPAGATE", logging.getLogger("app.api.request").propagate)
"""

out = run_smoke(APP_IMPORT).stdout
m = dict(line.split(" ", 1) for line in out.strip().splitlines())
check("app import: exactly one app handler", m.get("HANDLER_COUNT") == "1", out)
check("app import: root level INFO by default", m.get("ROOT_LEVEL") == "INFO", out)
check("app import: uvicorn.access silenced (no propagate)", m.get("ACCESS_PROPAGATE") == "False", out)
check("app import: uvicorn.access has no uvicorn handler", m.get("ACCESS_HAS_UVICORN_HANDLER") == "False", out)
check("app import: request logger propagates", m.get("REQ_PROPAGATE") == "True", out)

# --- 2. LOG_LEVEL env var is honored, invalid values fail loudly ---------------

LEVEL_SMOKE = r"""
import logging
from app.core.config import Settings
from app.core.logging import configure_logging

configure_logging(level=Settings(_env_file=None, log_level="WARNING").log_level)
print("LEVEL", logging.getLevelName(logging.getLogger().level))
try:
    Settings(_env_file=None, log_level="IFNO")
    print("INVALID accepted")
except Exception as e:
    print("INVALID rejected")
"""

out = run_smoke(LEVEL_SMOKE).stdout
check("LOG_LEVEL=WARNING raises root level", "LEVEL WARNING" in out, out)
check("LOG_LEVEL=IFNO rejected at settings load", "INVALID rejected" in out, out)

# --- 3. live request logging through a real uvicorn server --------------------

import time

UVICORN_SMOKE = r"""
import threading, time, urllib.request
import uvicorn

from app.main import app

config = uvicorn.Config(app, host="127.0.0.1", port=8765, log_config=None, access_log=False, lifespan="off")
server = uvicorn.Server(config)
thread = threading.Thread(target=server.run, daemon=True)
thread.start()

for _ in range(100):
    time.sleep(0.1)
    try:
        urllib.request.urlopen("http://127.0.0.1:8765/api/health", timeout=2)
        break
    except Exception:
        continue

req = urllib.request.Request(
    "http://127.0.0.1:8765/api/auth/me",
    headers={"Authorization": "Bearer fake.jwt.value"},
)
try:
    urllib.request.urlopen(req, timeout=2)
except urllib.error.HTTPError:
    pass  # 401 expected

# uvicorn rejects header values with newlines before the app ever sees
# them ("Invalid HTTP request received") — that's the server's line. Our
# middleware's own sanitization is probed with a value that is valid HTTP
# but fails our charset/size rules.
req2 = b"GET /api/health HTTP/1.1\r\nHost: 127.0.0.1:8765\r\nX-Request-ID: bad id;DROP\$<script>\r\nConnection: close\r\n\r\n"
import socket as _socket
s = _socket.create_connection(("127.0.0.1", 8765), timeout=5)
s.sendall(req2)
resp = b""
try:
    while True:
        chunk = s.recv(4096)
        if not chunk:
            break
        resp += chunk
except Exception:
    pass
s.close()
head = resp.decode("latin-1", errors="replace").split("\r\n\r\n", 1)[0]
for h in head.split("\r\n"):
    if h.lower().startswith("x-request-id:"):
        print("ECHO", h.split(":", 1)[1].strip())


time.sleep(0.5)
server.should_exit = True
thread.join(timeout=5)
"""

result = run_smoke(UVICORN_SMOKE, timeout=90)
err = result.stderr
request_lines = [l for l in err.splitlines() if "app.api.request" in l and "request:" in l]
security_lines = [l for l in err.splitlines() if "app.api.security" in l]

check("live server: request line emitted on stderr", len(request_lines) >= 3, err[-500:])
if request_lines:
    line = request_lines[0]
    check(
        "live server: format is ISO/level/name/pid/message",
        bool(re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}\+00:00 (INFO|WARNING) app\.api\.request pid=\d+ request: ", line)),
        line,
    )
    check(
        "live server: line has method/path/status/duration/id",
        bool(re.search(r"GET /api/health -> 200 \d+(\.\d+)?ms request_id=[0-9a-f]{32}", line)),
        line,
    )
    check(
        "live server: 401 request logged",
        any("-> 401" in l for l in request_lines),
        str(request_lines),
    )
check("live server: auth failure security line present", len(security_lines) >= 1, err[-500:])
if security_lines:
    check(
        "live server: security line has no token value",
        "fake.jwt.value" not in security_lines[0],
        security_lines[0],
    )
# hostile request id replaced (echo must be a hex id, not the input)
echo = [l for l in result.stdout.splitlines() if l.startswith("ECHO ")]
if echo:
    echoed = echo[0].split(" ", 1)[1].strip()
    check(
        "live server: hostile request id replaced",
        bool(re.fullmatch(r"[0-9a-f]{32}", echoed)),
        echoed,
    )
else:
    check("live server: hostile request id replaced", False, result.stdout)

# --- 4. worker entry point: python -m app.worker -----------------------------
#        (module import only — actually running it needs Redis; the logging
#         behavior of the running worker is exercised in the next check)

try:
    result = run_smoke(
        "import app.worker.__main__ as m; print('IMPORT-OK')", timeout=30
    )
    check("worker module imports (python -m app.worker path)", "IMPORT-OK" in result.stdout, result.stderr[-300:])
except subprocess.TimeoutExpired:
    check("worker module imports (python -m app.worker path)", False, "timeout")

WORKER_LOG_SMOKE = r"""
import asyncio, logging
from app.core.logging import configure_logging
configure_logging(level="INFO")

import fakeredis.aioredis
from arq import ArqRedis, Worker
from httpx2 import MockTransport, Response
import app.worker.worker as worker_module
from app.core.config import Settings
from app.notifications.factory import build_notification_dispatcher
from app.worker.retry import RetryPolicy
from app.worker.serialization import json_job_serializer, json_job_deserializer
from app.worker.service import BackgroundNotificationService

import arq.worker
async def _noop(redis, log_func): return None
arq.worker.log_redis_info = _noop

TOKEN = "1100000001:AA-smoke-token-never-real"

async def main():
    fake = fakeredis.aioredis.FakeRedis()
    pool = ArqRedis(pool_or_conn=fake.connection_pool,
                    job_serializer=json_job_serializer,
                    job_deserializer=json_job_deserializer,
                    default_queue_name="ketabdaneh:notifications")
    settings = Settings(_env_file=None, telegram_bot_token=TOKEN)
    svc = BackgroundNotificationService(settings, pool=pool)
    await svc.enqueue_notification(
        channel="telegram", address="111", text="smoke secret payload",
        category="event",
    )
    transport = MockTransport(lambda request: Response(200, json={"ok": True, "result": {"message_id": 7}}))
    ctx = {
        "notification_dispatcher": build_notification_dispatcher(settings, transport=transport),
        "notification_retry_policy": RetryPolicy(max_attempts=4, base_delay_seconds=0.01, max_delay_seconds=0.05),
    }
    worker = Worker(functions=worker_module.WorkerSettings.functions,
                    queue_name="ketabdaneh:notifications", burst=True,
                    redis_pool=pool,
                    job_serializer=json_job_serializer,
                    job_deserializer=json_job_deserializer,
                    handle_signals=False, poll_delay=0.005, max_tries=25, ctx=ctx)
    completed = await worker.run_check()
    await pool.aclose(); await fake.aclose()
    print("COMPLETED", completed)

asyncio.run(main())
"""

result = run_smoke(WORKER_LOG_SMOKE, timeout=90)
err = result.stderr
enq = [l for l in err.splitlines() if "app.worker.service" in l and "enqueued" in l]
dlv = [l for l in err.splitlines() if "app.worker.delivery" in l and "delivered" in l]
arq = [l for l in err.splitlines() if "arq.worker" in l]

check("worker smoke: enqueue line in shared format", len(enq) == 1, err[-400:])
if enq:
    check(
        "worker smoke: enqueue line formatted ISO/level/name/pid",
        bool(re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}\+00:00 INFO app\.worker\.service pid=\d+ ", enq[0])),
        enq[0],
    )
check("worker smoke: delivery line in shared format", len(dlv) == 1, err[-400:])
WORKER_TOKEN = "1100000001:AA-smoke-token-never-real"
if dlv:
    check(
        "worker smoke: delivery line has channel/job_id/duration",
        "channel=telegram" in dlv[0] and "job_id=" in dlv[0] and "duration_ms=" in dlv[0],
        dlv[0],
    )
    check(
        "worker smoke: delivery line leaks no text/address/token",
        "smoke secret payload" not in dlv[0] and "111" not in dlv[0] and WORKER_TOKEN not in dlv[0],
        dlv[0],
    )
check("worker smoke: arq's own lifecycle lines share the format", len(arq) >= 1, err[-400:])
if arq:
    check(
        "worker smoke: arq lines formatted consistently",
        bool(re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}\+00:00 INFO arq\.worker pid=\d+ ", arq[0])),
        arq[0],
    )
check("worker smoke: job completed", "COMPLETED 1" in result.stdout, result.stdout + err[-300:])

# --- 5. no log leakage of the api secret / db url in any smoke output ---------

for label, blob in (("uvicorn", err), ("worker", result.stderr)):
    for secret in ("change-me-insecure", "postgresql://", "redis://"):
        check(f"no leakage ({label}): {secret!r} absent", secret not in blob)

print()
if FAILURES:
    print(f"SMOKE FAILED: {len(FAILURES)} check(s):", *FAILURES, sep="\n  - ")
    sys.exit(1)
print("SMOKE PASSED: all checks ok")
