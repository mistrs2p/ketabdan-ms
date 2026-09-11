"""Runtime smoke verification for Task 5.9 (observability / health / metrics).

Checks the observability foundation against the REAL local infrastructure
(PostgreSQL on 5433, Redis on 6390 — both from docker-compose; no
Telegram/Bale network calls: the one worker delivery uses a scripted
dispatcher). Items follow docs/01 §10 / the task spec §23:

  1.  app import
  2.  liveness (real HTTP server) — no dependencies touched
  3.  readiness with dependencies available
  4.  readiness fails cleanly when Redis is deliberately unavailable
  5.  /metrics exposition
  6.  request metrics update (and health/metrics paths stay unmetered)
  7.  worker import + startup (metrics port)
  8.  worker job metrics update
  9.  notification path updates bounded metrics
  10. log lines are the Task 5.8 format
  11. no secret leakage anywhere (metrics, health responses, logs)

Run:  python smoke_observability_59.py
"""

import json
import os
import re
import subprocess
import sys
import time
import urllib.request

API_PORT = 8012
WORKER_METRICS_PORT = 9112
API_URL = f"http://127.0.0.1:{API_PORT}"
SECRET_PROBE = "smoke-secret-jwt-value-never-real"

PASSED: list[str] = []
FAILED: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        PASSED.append(name)
        print(f"PASS  {name}")
    else:
        FAILED.append(name)
        print(f"FAIL  {name}" + (f" — {detail}" if detail else ""))


def get(url: str, headers: dict | None = None):
    """GET tolerating non-2xx (error statuses are expected probe outcomes)."""
    request = urllib.request.Request(url, headers=headers or {})
    try:
        response = urllib.request.urlopen(request, timeout=10)
    except urllib.error.HTTPError as http_error:
        response = http_error
    with response:
        return response.status, dict(response.headers), response.read().decode(
            "utf-8", errors="replace"
        )


# --- Phase A: readiness with Redis deliberately unavailable (dead port) ----------

DEAD_REDIS_SNIPPET = r"""
import json
import os
from fastapi.testclient import TestClient
from app.main import app

with TestClient(app) as client:
    live = client.get("/api/health/live")
    ready = client.get("/api/health/ready")
print(json.dumps({
    "live_status": live.status_code,
    "live_body": live.json(),
    "ready_status": ready.status_code,
    "ready_body": ready.json(),
    "ready_text": ready.text,
}))
"""

env_dead_redis = dict(os.environ, REDIS_URL="redis://localhost:6399/0")  # nothing listens
proc = subprocess.run(
    [sys.executable, "-X", "utf8", "-c", DEAD_REDIS_SNIPPET],
    capture_output=True, encoding="utf-8", errors="replace", env=env_dead_redis,
    timeout=60,
)
if proc.returncode != 0:
    print(proc.stdout)
    print(proc.stderr)
    sys.exit("Phase A subprocess failed")
result_a = json.loads(proc.stdout.strip().splitlines()[-1])

print("== Phase A: Redis deliberately unavailable ==")
check(
    "A1 liveness still 200 when redis is down",
    result_a["live_status"] == 200 and result_a["live_body"] == {"status": "ok"},
    str(result_a["live_body"]),
)
check(
    "A2 readiness 503 not_ready",
    result_a["ready_status"] == 503 and result_a["ready_body"].get("status") == "not_ready",
    str(result_a["ready_body"]),
)
check(
    "A3 redis reported unavailable, database ok",
    result_a["ready_body"].get("checks", {}).get("redis") == "unavailable"
    and result_a["ready_body"].get("checks", {}).get("database") == "ok",
    str(result_a["ready_body"]),
)
blob_a = result_a["ready_text"]
check(
    "A4 failure response carries no internals",
    all(s not in blob_a for s in ("redis://", "6399", "Error", "Connection", "password")),
    blob_a,
)

# --- Phase B: real HTTP server with live dependencies ----------------------------

log_path = os.path.abspath("smoke_59_api.log")
log_file = open(log_path, "w", encoding="utf-8")
server = subprocess.Popen(
    [
        sys.executable, "-X", "utf8", "-m", "uvicorn", "app.main:app",
        "--host", "127.0.0.1", "--port", str(API_PORT), "--log-level", "info",
    ],
    stdout=log_file, stderr=subprocess.STDOUT, encoding="utf-8", errors="replace",
)

try:
    for _ in range(60):
        try:
            get(f"{API_URL}/api/health/live")
            break
        except OSError:
            time.sleep(0.5)
    else:
        sys.exit("server never came up")

    print("\n== Phase B: live API server ==")
    # 1. app import happened inside the server process; a first successful
    #    request proves it. Liveness:
    status, headers, body = get(f"{API_URL}/api/health/live")
    check("B1 liveness 200 {status: ok}", status == 200 and json.loads(body) == {"status": "ok"}, body)

    status, _, body = get(f"{API_URL}/api/health")
    check("B2 legacy /api/health contract unchanged", status == 200 and json.loads(body) == {"status": "ok"}, body)

    # 3. readiness with real postgres + redis; no worker process runs, so
    #    the heartbeat must be reported absent (the 5.9 §10 honesty rule).
    status, _, body = get(f"{API_URL}/api/health/ready")
    ready_body = json.loads(body)
    check(
        "B3 readiness 200, database+redis ok",
        status == 200
        and ready_body.get("checks", {}).get("database") == "ok"
        and ready_body.get("checks", {}).get("redis") == "ok",
        body,
    )
    check(
        "B4 no worker running → 'no_recent_heartbeat' (not a false ok)",
        ready_body.get("checks", {}).get("worker") == "no_recent_heartbeat",
        body,
    )

    # 5. metrics exposition
    status, headers, metrics_before = get(f"{API_URL}/metrics")
    check(
        "B5 /metrics 200, prometheus text type",
        status == 200 and headers.get("content-type", "").startswith("text/plain"),
        headers.get("content-type", ""),
    )
    for name in (
        "http_requests_total", "http_request_duration_seconds",
        "http_requests_in_progress", "worker_jobs_total",
        "notification_delivery_total",
    ):
        check(f"B6 metric present: {name}", f"# TYPE {name}" in metrics_before)

    # 6. request metrics update; health/metrics paths stay unmetered
    get(f"{API_URL}/api/persons")  # 401 → 4xx, route template label
    status, headers, metrics_after = get(f"{API_URL}/metrics")
    check(
        "B7 request counter recorded the 401 under the route template",
        'http_requests_total{method="GET",route="/api/persons",status_class="4xx"} 1.0' in metrics_after
        or 'http_requests_total{method="GET",route="/api/persons",status_class="4xx"} 1' in metrics_after,
        metrics_after,
    )
    check(
        "B8 /metrics and /api/health* are not metered (no self-loop)",
        not re.search(r'http_requests_total\{[^}]*route="/metrics"', metrics_after)
        and not re.search(r'http_requests_total\{[^}]*route="/api/health', metrics_after),
    )

    # 11. secret leakage: a bearer token must not reach metrics
    get(f"{API_URL}/api/persons", headers={"Authorization": f"Bearer {SECRET_PROBE}"})
    status, headers, metrics_secret = get(f"{API_URL}/metrics")
    check("B9 bearer token absent from metrics", SECRET_PROBE not in metrics_secret)

finally:
    server.terminate()
    try:
        server.wait(timeout=10)
    except subprocess.TimeoutExpired:
        server.kill()
    log_file.close()

# 10. log lines are the Task 5.8 format (ISO timestamp, request line)
with open(log_path, encoding="utf-8", errors="replace") as fh:
    log_text = fh.read()
request_lines = re.findall(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[.,\d:+\-]*\S* \w+ app\.api\.request pid=\d+ "
    r"request: GET /api/health/live -> 200",
    log_text,
    re.MULTILINE,
)
check(
    "B10 request log lines use the 5.8 format",
    len(request_lines) >= 1,
    log_text[-800:],
)
check("B11 bearer token absent from logs", SECRET_PROBE not in log_text)

# --- Phase C: worker process metrics ---------------------------------------------

WORKER_SNIPPET = r"""
import asyncio
import json
import urllib.request

from app.core.logging import configure_logging, get_logger
configure_logging(level="INFO")
logger = get_logger("smoke.worker")

import app.worker.worker as worker_module
from app.core.config import get_settings
from app.notifications import NotificationResult
from app.worker.retry import RetryPolicy


class ScriptedDispatcher:
    # No Telegram/Bale network: a scripted successful delivery.
    async def send(self, message):
        return NotificationResult(
            success=True,
            channel=message.recipient.channel,
            external_message_id="smoke-1",
        )


async def main():
    settings = get_settings()
    ctx = {}
    await worker_module.startup(ctx)
    assert ctx.get("_metrics_server") is not None, "metrics server not started"
    ctx["notification_dispatcher"] = ScriptedDispatcher()
    ctx["notification_retry_policy"] = RetryPolicy(
        max_attempts=3, base_delay_seconds=0.01, max_delay_seconds=0.05
    )
    status = await worker_module.deliver_notification(
        ctx,
        {"channel": "telegram", "address": "100200300",
         "text": "smoke secret text 123", "category": "event", "metadata": {}},
    )
    await asyncio.sleep(0.3)  # let the exposition thread observe the counters
    blob = urllib.request.urlopen(
        f"http://127.0.0.1:%d/metrics" % settings.worker_metrics_port, timeout=5
    ).read().decode("utf-8")
    await worker_module.shutdown(ctx)
    return {"status": status, "metrics": blob}


print(json.dumps(asyncio.run(main())))
"""

print("\n== Phase C: worker process ==")
env_worker = dict(os.environ, WORKER_METRICS_PORT=str(WORKER_METRICS_PORT))
proc = subprocess.run(
    [sys.executable, "-X", "utf8", "-c", WORKER_SNIPPET],
    capture_output=True, encoding="utf-8", errors="replace", env=env_worker,
    timeout=120,
)
if proc.returncode != 0:
    print(proc.stdout)
    print(proc.stderr)
    sys.exit("Phase C subprocess failed")
result_c = json.loads(proc.stdout.strip().splitlines()[-1])
worker_metrics = result_c["metrics"]

check(
    "C1 worker metrics endpoint scraped (startup + port live)",
    "# TYPE" in worker_metrics,
)
check("C2 worker delivered the job", result_c["status"] == "delivered", result_c["status"])
check(
    "C3 worker job metric: completed",
    'worker_jobs_total{function="deliver_notification",outcome="completed"}' in worker_metrics,
)
check(
    "C4 notification metric: success on telegram",
    'notification_delivery_total{channel="telegram",outcome="success"}' in worker_metrics,
)
check(
    "C5 notification duration histogram present",
    "notification_delivery_duration_seconds_bucket" in worker_metrics,
)
check(
    "C6 notification text/recipient never in worker metrics",
    "100200300" not in worker_metrics and "smoke secret text" not in worker_metrics,
)
check(
    "C7 worker logs are the 5.8 format with job context",
    "notification delivered: channel=telegram" in proc.stderr
    and re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", proc.stderr) is not None,
    proc.stderr[-500:],
)

# --- summary ----------------------------------------------------------------------

print("\n" + "=" * 60)
print(f"PASSED: {len(PASSED)}   FAILED: {len(FAILED)}")
for name in FAILED:
    print(f"  FAILED: {name}")
if os.path.exists(log_path):
    os.remove(log_path)
sys.exit(1 if FAILED else 0)
