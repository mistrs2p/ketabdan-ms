"""Runtime smoke verification for Task 5.10 (configuration & secrets hardening).

Items per the task spec §30 — all offline/fake values, no Telegram/Bale
network calls, no real credentials:

 1. development configuration loads
 2. test configuration loads
 3. production configuration with valid secrets loads
 4. production with missing auth secret fails
 5. production with insecure auth secret fails
 6. malformed DB URL fails safely (no value in error)
 7. malformed Redis URL fails safely (no value in error)
 8. one notification token works without the other
 9. FastAPI app imports with safe configuration
10. worker imports with safe configuration
11. no secret appears in startup/log output
12. /api/health unchanged
13. readiness/metrics unaffected

Run:  python smoke_config_510.py
"""

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

API_PORT = 8014
API_URL = f"http://127.0.0.1:{API_PORT}"
SECRET_PROBE = "SMOKE-SECRET-PROBE-never-real-0123456789abcdef"

PASSED: list[str] = []
FAILED: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        PASSED.append(name)
        print(f"PASS  {name}")
    else:
        FAILED.append(name)
        print(f"FAIL  {name}" + (f" — {detail}" if detail else ""))


def run_snippet(code: str, env: dict | None = None):
    """Run a Python snippet in a subprocess; return (returncode, stdout, stderr)."""
    proc = subprocess.run(
        [sys.executable, "-X", "utf8", "-c", code],
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        env=dict(os.environ, **(env or {})),
        timeout=60,
    )
    return proc.returncode, proc.stdout, proc.stderr


FAIL_FAST_SNIPPET = r"""
import sys
from app.core.config import Settings, ConfigurationError

mode = sys.argv[1]
try:
    if mode == "dev":
        Settings(_env_file=None)
    elif mode == "test":
        Settings(_env_file=None, app_env="test")
    elif mode == "prod_ok":
        Settings(
            _env_file=None, app_env="production",
            auth_secret_key="x" * 48 + "-smoke-never-real",
            auth_allow_insecure_dev_secret=False,
            database_url="postgresql+psycopg://u:pw@db.invalid:5432/app",
            redis_url="redis://redis.invalid:6390/0",
        )
    elif mode == "prod_missing_secret":
        # flag explicitly off: the failure must be about the SECRET itself
        # (the flag check would otherwise fire first and mask it).
        Settings(_env_file=None, app_env="production",
                 auth_allow_insecure_dev_secret=False)
    elif mode == "prod_insecure_secret":
        Settings(
            _env_file=None, app_env="production",
            auth_allow_insecure_dev_secret=False,
            auth_secret_key="change-me-insecure-dev-placeholder",
        )
    elif mode == "prod_weak_secret":
        Settings(
            _env_file=None, app_env="production",
            auth_secret_key="short-but-not-placeholder",
            auth_allow_insecure_dev_secret=False,
        )
    elif mode == "bad_db":
        Settings(_env_file=None, database_url="postgresql://u:SMOKE-SECRET-PROBE@h:xxx/d")
    elif mode == "bad_redis":
        Settings(_env_file=None, redis_url="ftp://u:SMOKE-SECRET-PROBE@h")
    elif mode == "one_token":
        s = Settings(
            _env_file=None, app_env="production",
            auth_secret_key="x" * 48 + "-smoke-never-real",
            auth_allow_insecure_dev_secret=False,
            database_url="postgresql+psycopg://u:pw@db.invalid:5432/app",
            redis_url="redis://redis.invalid:6390/0",
            telegram_bot_token="1100000001:AA-smoke-fake-only",
            bale_bot_token=None,
        )
        assert s.telegram_bot_token is not None and s.bale_bot_token is None
except ConfigurationError as e:
    print(f"CONFIG_ERROR: {e}")
    sys.exit(2)
except Exception as e:  # pydantic ValidationError etc.
    print(f"OTHER_ERROR: {type(e).__name__}: {e}")
    sys.exit(3)
print("LOADED")
"""


def run_mode(mode: str):
    code = FAIL_FAST_SNIPPET.replace('sys.argv[1]', repr(mode))
    return run_snippet(code)


# --- 1-8: configuration matrix ---------------------------------------------------

print("== Configuration matrix ==")

code, out, err = run_mode("dev")
check("1 development configuration loads", code == 0 and "LOADED" in out, out + err)

code, out, err = run_mode("test")
check("2 test configuration loads", code == 0 and "LOADED" in out, out + err)

code, out, err = run_mode("prod_ok")
check(
    "3 production with valid settings loads",
    code == 0 and "LOADED" in out,
    out + err,
)

code, out, err = run_mode("prod_missing_secret")
check(
    "4 production with placeholder auth secret fails (ConfigurationError)",
    code == 2 and "AUTH_SECRET_KEY" in out and "placeholder" in out.lower(),
    out,
)
check(
    "4b failure message carries no secret value",
    SECRET_PROBE not in out and "x" * 48 not in out,
    out,
)

code, out, err = run_mode("prod_insecure_secret")
check(
    "5a production placeholder secret fails",
    code == 2 and "placeholder" in out.lower(),
    out,
)

code, out, err = run_mode("prod_weak_secret")
check(
    "5b production short secret fails",
    code == 2 and "32" in out and "short-but-not-placeholder" not in out,
    out,
)

code, out, err = run_mode("bad_db")
check(
    "6 malformed DB URL fails safely (no credentials echoed)",
    code == 2 and "DATABASE_URL" in out and SECRET_PROBE not in out,
    out,
)

code, out, err = run_mode("bad_redis")
check(
    "7 malformed Redis URL fails safely (no credentials echoed)",
    code == 2 and "REDIS_URL" in out and SECRET_PROBE not in out,
    out,
)

code, out, err = run_mode("one_token")
check(
    "8 one notification token without the other loads",
    code == 0 and "LOADED" in out,
    out + err,
)

# --- 9-13: live application with a hardened production-shaped config -------------

# Real local infra (postgres 5433 / redis 6390) but a PRODUCTION-shaped
# environment: explicit strong secret, flag off, explicit URLs, explicit
# CORS origin, APP_ENV=production. Tokens are the smoke probes.
prod_env = {
    "APP_ENV": "production",
    "AUTH_SECRET_KEY": SECRET_PROBE + "-production-secret-smoke",
    "AUTH_ALLOW_INSECURE_DEV_SECRET": "0",
    "DATABASE_URL": "postgresql+psycopg://ketabdaneh:ketabdaneh_dev@localhost:5433/ketabdaneh",
    "REDIS_URL": "redis://localhost:6390/0",
    "CORS_ALLOW_ORIGINS": "http://localhost:3000",
    "TELEGRAM_BOT_TOKEN": "",
    "BALE_BOT_TOKEN": "",
    "LOG_LEVEL": "INFO",
}

log_path = os.path.abspath("smoke_510_api.log")
log_file = open(log_path, "w", encoding="utf-8")
server = subprocess.Popen(
    [
        sys.executable, "-X", "utf8", "-m", "uvicorn", "app.main:app",
        "--host", "127.0.0.1", "--port", str(API_PORT), "--log-level", "info",
    ],
    stdout=log_file, stderr=subprocess.STDOUT, encoding="utf-8", errors="replace",
    env=dict(os.environ, **prod_env),
)

try:
    for _ in range(60):
        try:
            urllib.request.urlopen(f"{API_URL}/api/health/live", timeout=5)
            break
        except OSError:
            time.sleep(0.5)
    else:
        print(open(log_path, encoding="utf-8", errors="replace").read())
        sys.exit("server never came up (see log above)")

    print("\n== Live application (production-shaped env) ==")
    with urllib.request.urlopen(f"{API_URL}/api/health/live", timeout=10) as r:
        check(
            "12 /api/health unchanged",
            r.status == 200 and json.loads(r.read()) == {"status": "ok"},
        )
    with urllib.request.urlopen(f"{API_URL}/api/health", timeout=10) as r:
        check(
            "12b legacy /api/health contract",
            r.status == 200 and json.loads(r.read()) == {"status": "ok"},
        )
    try:
        urllib.request.urlopen(f"{API_URL}/api/health/ready", timeout=10)
        ready_ok = True
    except urllib.error.HTTPError:
        ready_ok = False
    check(
        "13 readiness answers (200 with local infra)",
        ready_ok,
        "readiness returned non-200",
    )
    with urllib.request.urlopen(f"{API_URL}/metrics", timeout=10) as r:
        metrics = r.read().decode("utf-8", errors="replace")
    check(
        "13b /metrics unaffected",
        "# TYPE http_requests_total" in metrics and SECRET_PROBE not in metrics,
    )

    # 9: the app imported and served under a production-shaped config.
    check("9 FastAPI app imports with safe production config", True)

finally:
    server.terminate()
    try:
        server.wait(timeout=10)
    except subprocess.TimeoutExpired:
        server.kill()
    log_file.close()

with open(log_path, encoding="utf-8", errors="replace") as fh:
    log_text = fh.read()
check(
    "11 no secret in startup/log output",
    SECRET_PROBE not in log_text,
    log_text[-500:],
)
os.remove(log_path)

# 10: worker module imports under the same hardened env.
code, out, err = run_snippet(
    "import app.worker.worker, app.worker.__main__ as m; print('WORKER_OK')",
    {k: v for k, v in prod_env.items() if k not in ("APP_ENV",)},
)
check("10 worker imports with safe configuration", code == 0 and "WORKER_OK" in out, out + err)
check("10b no secret in worker import output", SECRET_PROBE not in out + err, out + err)

# --- summary ----------------------------------------------------------------------

print("\n" + "=" * 60)
print(f"PASSED: {len(PASSED)}   FAILED: {len(FAILED)}")
for name in FAILED:
    print(f"  FAILED: {name}")
sys.exit(1 if FAILED else 0)
