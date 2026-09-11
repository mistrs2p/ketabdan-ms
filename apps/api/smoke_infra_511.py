"""Runtime smoke verification for Task 5.11 (production container baseline).

Verifies the running production-like compose stack (docker-compose.prod.yml,
started with fake credentials from .env.prod) against the task spec §16.
No Telegram/Bale contact (tokens empty), no real credentials.

 1. PostgreSQL becomes healthy
 2. Redis becomes healthy
 3. API becomes healthy
 4. API liveness returns success
 5. API readiness returns success when dependencies are ready
 6. Web starts successfully (serves, and localized content renders —
    proves the i18n message catalogs made it into the image)
 7. Worker starts successfully (healthy via the Redis heartbeat)
 8. API can reach PostgreSQL
 9. API/worker can reach Redis
10. Worker health signal behaves as expected
11. No service requires public DB/Redis exposure (no host ports)
12. Logs do not reveal secrets
 + graceful shutdown: the worker exits cleanly on SIGTERM and is
   independently restartable

Run from the repository root with the stack up:
    python apps/api/smoke_infra_511.py
"""

import json
import os
import subprocess
import sys
import time
import urllib.request

PROD_ARGS = ["--env-file", ".env.prod", "-f", "docker-compose.prod.yml"]
API_URL = "http://localhost:8000"
WEB_URL = "http://localhost:3000"

PASSED: list[str] = []
FAILED: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        PASSED.append(name)
        print(f"PASS  {name}")
    else:
        FAILED.append(name)
        print(f"FAIL  {name}" + (f" — {detail}" if detail else ""))


def docker_compose(*args: str, timeout: int = 120) -> tuple[int, str]:
    proc = subprocess.run(
        ["docker", "compose", *PROD_ARGS, *args],
        capture_output=True, encoding="utf-8", errors="replace",
        timeout=timeout,
    )
    return proc.returncode, proc.stdout + proc.stderr


def inspect_health(container: str) -> str:
    proc = subprocess.run(
        ["docker", "inspect", "--format", "{{.State.Health.Status}}", container],
        capture_output=True, encoding="utf-8", errors="replace", timeout=30,
    )
    return proc.stdout.strip()


def get_json(url: str, timeout: int = 10) -> tuple[int, dict]:
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.status, json.loads(r.read())


# Secrets from the fake env file — used only as leak probes.
SECRET_VALUES = [
    "local-fake-jwt-secret-0123456789abcdef0123456789abcdef",
    "local-fake-not-a-real-password",
]

print("== Service health ==")
check("1 PostgreSQL healthy", inspect_health("ketabdaneh-prod-postgres-1") == "healthy",
      inspect_health("ketabdaneh-prod-postgres-1"))
check("2 Redis healthy", inspect_health("ketabdaneh-prod-redis-1") == "healthy",
      inspect_health("ketabdaneh-prod-redis-1"))
check("3 API healthy", inspect_health("ketabdaneh-prod-api-1") == "healthy",
      inspect_health("ketabdaneh-prod-api-1"))

print("\n== HTTP contracts ==")
try:
    status, body = get_json(f"{API_URL}/api/health/live")
    check("4 API liveness returns success", status == 200 and body == {"status": "ok"},
          f"{status} {body}")
except Exception as exc:  # noqa: BLE001
    check("4 API liveness returns success", False, str(exc))

try:
    status, body = get_json(f"{API_URL}/api/health/ready")
    checks = body.get("checks", {})
    check(
        "5 API readiness returns success",
        status == 200 and body.get("status") == "ok"
        and all(v == "ok" for v in checks.values()),
        f"{status} {body}",
    )
    check("8 API can reach PostgreSQL", checks.get("database") == "ok", str(checks))
    check("9a API can reach Redis", checks.get("redis") == "ok", str(checks))
    check(
        "10 worker health signal behaves as expected",
        checks.get("worker") == "ok",
        str(checks),
    )
except Exception as exc:  # noqa: BLE001
    check("5 API readiness returns success", False, str(exc))
    check("8 API can reach PostgreSQL", False, str(exc))
    check("9a API can reach Redis", False, str(exc))
    check("10 worker health signal behaves as expected", False, str(exc))

print("\n== Web ==")
try:
    # GET / redirects to the default locale; follow it and require the
    # localized page to render real translated content (proves the i18n
    # message catalogs are present in the standalone image).
    with urllib.request.urlopen(f"{WEB_URL}/en", timeout=10) as r:
        html = r.read().decode("utf-8", errors="replace")
        check("6a web serves", r.status == 200, f"{r.status}")
    check(
        "6b localized content renders (i18n catalogs in image)",
        "Branch operations management system" in html,
        "English subtitle string not found in page",
    )
except Exception as exc:  # noqa: BLE001
    check("6a web serves", False, str(exc))
    check("6b localized content renders (i18n catalogs in image)", False, str(exc))

check("7 worker healthy (Redis heartbeat)", inspect_health("ketabdaneh-prod-worker-1") == "healthy",
      inspect_health("ketabdaneh-prod-worker-1"))

print("\n== Worker connected to Redis ==")
code, out = docker_compose("exec", "-T", "worker", "python", "-c",
                           "import os,redis; r=redis.Redis.from_url(os.environ['REDIS_URL']); "
                           "print('PING', r.ping())")
check("9b worker can reach Redis (in-container PING)", code == 0 and "PING True" in out, out)

print("\n== Port exposure ==")
for service in ("postgres", "redis"):
    proc = subprocess.run(
        ["docker", "inspect", "--format",
         "{{range .NetworkSettings.Ports}}{{.}}{{end}}",
         f"ketabdaneh-prod-{service}-1"],
        capture_output=True, encoding="utf-8", errors="replace", timeout=30,
    )
    ports = proc.stdout.strip()
    # No published host ports: the mapping entries have empty HostIp/HostPort.
    published = "0.0.0.0" in ports or "[::]" in ports
    check(f"11a {service} not exposed to host", not published, ports)
for service in ("api", "web"):
    proc = subprocess.run(
        ["docker", "inspect", "--format",
         "{{range .NetworkSettings.Ports}}{{.}}{{end}}",
         f"ketabdaneh-prod-{service}-1"],
        capture_output=True, encoding="utf-8", errors="replace", timeout=30,
    )
    check(f"11b {service} published to host", "0.0.0.0" in proc.stdout, proc.stdout.strip())

print("\n== Logs do not reveal secrets ==")
all_logs = ""
for service in ("postgres", "redis", "api", "worker", "web"):
    _, out = docker_compose("logs", service, "--no-log-prefix", timeout=120)
    all_logs += out
for secret in SECRET_VALUES:
    check(f"12 no secret in logs ({secret[:24]}…)", secret not in all_logs)

print("\n== Graceful shutdown / independent restart ==")
code, out = docker_compose("stop", "worker", timeout=180)
check("13a worker stops cleanly (SIGTERM honored)", code == 0, out[-300:])
_, out = docker_compose("logs", "worker", "--no-log-prefix", "--tail", "5", timeout=60)
check("13b worker logged graceful shutdown", "shutting down" in out, out[-300:])
code, out = docker_compose("start", "worker", timeout=120)
check("13c worker independently restartable", code == 0, out[-200:])

# Wait for the heartbeat to return before finishing (the stack stays up).
deadline = time.time() + 120
worker_ok = False
while time.time() < deadline:
    try:
        _, body = get_json(f"{API_URL}/api/health/ready", timeout=5)
        if body.get("checks", {}).get("worker") == "ok":
            worker_ok = True
            break
    except Exception:  # noqa: BLE001
        pass
    time.sleep(5)
check("13d worker heartbeat returns after restart", worker_ok)

print("\n" + "=" * 60)
print(f"PASSED: {len(PASSED)}   FAILED: {len(FAILED)}")
for name in FAILED:
    print(f"  FAILED: {name}")
sys.exit(1 if FAILED else 0)
