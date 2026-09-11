#!/usr/bin/env python3
"""Deployment verification for the Ketabdaneh production stack
(Task 5.12 §17; docs/12-DEPLOYMENT.md §13).

Checks the deployed system the way a user and an attacker see it —
through the public HTTPS edge — plus the internal invariants that must
hold from the outside (no database/Redis/direct app ports reachable, no
host-published ports besides the proxy, worker heartbeat alive).

    python3 scripts/verify_deployment.py --base-url https://example.com
    python3 scripts/verify_deployment.py --base-url https://localhost \
        --insecure-tls --username admin --password <fake-local-password>

Checks (PASS / FAIL / SKIP; exit code 1 on any FAIL):

  1  http_redirects_to_https   plain HTTP / answers 301/308 -> https
  2  https_web_serves          TLS handshake + the web upstream answers (< 400)
  3  web_locale_redirect       / redirects to a locale-prefixed path
  4  web_page_renders          public page /en/login returns HTML content
  5  api_health_public         GET /api/health -> {"status": "ok"}
  6  api_readiness_public      GET /api/health/ready -> database+redis ok
  7  login_works               POST /api/auth/login issues a token (needs
                               --username/--password; otherwise SKIP)
  8  me_with_token             GET /api/auth/me + Bearer -> the user
  9  me_requires_auth          GET /api/auth/me without token -> 401
 10  protected_route_401       GET /api/persons without token -> 401
 11  metrics_not_public        GET /metrics through the edge is NOT 200
                               (internal-only policy — docs/12 §14)
 12  metrics_internal_only     /metrics IS reachable inside the Docker
                               network (from the api container)
 13-16 ports_not_public        5432/6379/8000/3000 refuse connections on
                               the host (nothing internal is exposed)
 17  only_proxy_publishes      docker: api/web/postgres/redis publish no
                               host ports; caddy publishes only 80/443
 18  containers_healthy        all services running; healthchecked ones
                               (api/worker/postgres/redis/web) healthy
 19  worker_heartbeat          readiness reports worker ok AND the worker
                               container healthcheck is healthy

--insecure-tls skips certificate verification: intended ONLY for the
local deployment simulation, where Caddy uses its internal CA
(deploy/Caddyfile.local — docs/12 §16). Never point it at a real
deployment's verification run.

Standard library only (http.client, socket, subprocess) — no pip
installs on servers. Works on Linux and Windows/Git Bash (docker CLI).
"""

from __future__ import annotations

import argparse
import http.client
import json
import os
import socket
import ssl
import subprocess
import sys
from typing import Any

DEFAULT_FORBIDDEN_PORTS = "5432,6379,8000,3000"

# Services that carry a Docker healthcheck and must report healthy
# (caddy has none by design — see docker-compose.prod.yml).
HEALTHCHECKED = ("api", "worker", "postgres", "redis", "web")
ALL_SERVICES = ("postgres", "redis", "api", "worker", "web", "caddy")


class Results:
    """Ordered PASS/FAIL/SKIP collector."""

    def __init__(self) -> None:
        self.rows: list[tuple[str, str, str]] = []

    def record(self, name: str, status: str, detail: str = "") -> None:
        self.rows.append((name, status, detail))
        marker = {"PASS": "PASS", "FAIL": "FAIL", "SKIP": "SKIP"}[status]
        # ASCII separator: Windows consoles mangle em-dashes in tool output.
        print(f"[{marker}] {name}" + (f" - {detail}" if detail else ""))

    @property
    def failed(self) -> int:
        return sum(1 for _, s, _ in self.rows if s == "FAIL")


def _connection(base_url: str, insecure_tls: bool, timeout: float):
    """An (re)opened http.client connection for a base URL."""
    parts = base_url.rstrip("/")
    scheme, _, rest = parts.partition("://")
    if not rest:
        raise ValueError(f"base URL must include scheme: {base_url!r}")
    host, _, port_s = rest.partition(":")
    port = int(port_s) if port_s else (443 if scheme == "https" else 80)
    if scheme == "https":
        if insecure_tls:
            context = ssl._create_unverified_context()
        else:
            context = ssl.create_default_context()
        return http.client.HTTPSConnection(host, port, timeout=timeout, context=context)
    return http.client.HTTPConnection(host, port, timeout=timeout)


def fetch(
    base_url: str,
    path: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    body: bytes | None = None,
    insecure_tls: bool = False,
    timeout: float = 15.0,
) -> tuple[int, dict[str, str], bytes]:
    """One request, redirects NOT followed (the redirect is the check)."""
    conn = _connection(base_url, insecure_tls, timeout)
    try:
        conn.request(method, path, body=body, headers=headers or {})
        response = conn.getresponse()
        return response.status, dict(response.getheaders()), response.read()
    finally:
        conn.close()


def check_http_redirect(results: Results, http_base: str, https_base: str, insecure: bool) -> None:
    try:
        status, headers, _ = fetch(http_base, "/", insecure_tls=insecure)
        location = headers.get("Location", "")
        if status in (301, 308) and location.startswith("https://"):
            results.record("http_redirects_to_https", "PASS", f"{status} -> {location}")
        else:
            results.record(
                "http_redirects_to_https", "FAIL",
                f"expected 301/308 to https://, got {status} Location={location!r}",
            )
    except OSError as exc:
        results.record("http_redirects_to_https", "FAIL", f"{exc.__class__.__name__}: {exc}")


def check_web(results: Results, base_url: str, insecure: bool) -> None:
    try:
        status, _, _ = fetch(base_url, "/", insecure_tls=insecure)
        # Any complete, non-error response proves TLS + the web upstream;
        # / itself legitimately redirects to a locale (check 3).
        if status < 400:
            results.record("https_web_serves", "PASS", f"TLS + web answered, GET / -> {status}")
        else:
            results.record("https_web_serves", "FAIL", f"GET / -> {status}")
    except OSError as exc:
        results.record("https_web_serves", "FAIL", f"{exc.__class__.__name__}: {exc}")


def check_web_pages(results: Results, base_url: str, insecure: bool) -> None:
    try:
        status, headers, _ = fetch(base_url, "/", insecure_tls=insecure)
        location = headers.get("Location", "")
        if 300 <= status < 400 and location.startswith("/"):
            results.record("web_locale_redirect", "PASS", f"{status} -> {location}")
        else:
            results.record(
                "web_locale_redirect", "FAIL",
                f"expected 3xx to a locale path, got {status} Location={location!r}",
            )
    except OSError as exc:
        results.record("web_locale_redirect", "FAIL", f"{exc.__class__.__name__}: {exc}")
        return

    try:
        # /en/login is a genuinely public page (the locale root redirects
        # to the dashboard for unauthenticated visitors).
        status, headers, body = fetch(base_url, "/en/login", insecure_tls=insecure)
        content_type = headers.get("Content-Type", "")
        is_html = "html" in content_type.lower() and b"<html" in body.lower()
        if status == 200 and is_html and len(body) > 500:
            results.record("web_page_renders", "PASS", f"/en/login 200, {len(body)} bytes of HTML")
        else:
            results.record(
                "web_page_renders", "FAIL",
                f"/en/login -> {status}, content-type={content_type!r}, {len(body)} bytes",
            )
    except OSError as exc:
        results.record("web_page_renders", "FAIL", f"{exc.__class__.__name__}: {exc}")


def check_api_health(results: Results, base_url: str, insecure: bool) -> dict[str, Any]:
    ready_checks: dict[str, Any] = {}
    try:
        status, _, body = fetch(base_url, "/api/health", insecure_tls=insecure)
        payload = json.loads(body)
        if status == 200 and payload.get("status") == "ok":
            results.record("api_health_public", "PASS", '{"status": "ok"}')
        else:
            results.record("api_health_public", "FAIL", f"{status} {payload!r}")
    except OSError as exc:
        results.record("api_health_public", "FAIL", f"{exc.__class__.__name__}: {exc}")

    try:
        status, _, body = fetch(base_url, "/api/health/ready", insecure_tls=insecure)
        payload = json.loads(body)
        ready_checks = payload.get("checks", {})
        if status == 200 and ready_checks.get("database") == "ok" and ready_checks.get("redis") == "ok":
            results.record(
                "api_readiness_public", "PASS",
                f"database={ready_checks.get('database')} "
                f"redis={ready_checks.get('redis')} worker={ready_checks.get('worker')}",
            )
        else:
            results.record("api_readiness_public", "FAIL", f"{status} {payload!r}")
    except OSError as exc:
        results.record("api_readiness_public", "FAIL", f"{exc.__class__.__name__}: {exc}")
    return ready_checks


def check_auth(
    results: Results, base_url: str, insecure: bool,
    username: str | None, password: str | None,
) -> None:
    token: str | None = None
    if username and password:
        try:
            payload = json.dumps({"username": username, "password": password}).encode()
            status, _, body = fetch(
                base_url, "/api/auth/login", method="POST",
                headers={"Content-Type": "application/json", "Accept": "application/json"},
                body=payload, insecure_tls=insecure,
            )
            data = json.loads(body)
            if status == 200 and data.get("access_token"):
                token = data["access_token"]
                results.record("login_works", "PASS", f"token issued for {username!r}")
            else:
                results.record("login_works", "FAIL", f"login -> {status}")
        except OSError as exc:
            results.record("login_works", "FAIL", f"{exc.__class__.__name__}: {exc}")
    else:
        results.record(
            "login_works", "SKIP",
            "no --username/--password given (the login round-trip needs real credentials)",
        )

    if token:
        try:
            status, _, body = fetch(
                base_url, "/api/auth/me",
                headers={"Authorization": f"Bearer {token}"}, insecure_tls=insecure,
            )
            data = json.loads(body)
            if status == 200 and data.get("username") == username:
                results.record("me_with_token", "PASS", f"/me -> {username!r}")
            else:
                results.record("me_with_token", "FAIL", f"/me -> {status} {data!r}")
        except OSError as exc:
            results.record("me_with_token", "FAIL", f"{exc.__class__.__name__}: {exc}")
    else:
        results.record("me_with_token", "SKIP", "depends on login_works")

    try:
        status, _, _ = fetch(base_url, "/api/auth/me", insecure_tls=insecure)
        if status == 401:
            results.record("me_requires_auth", "PASS", "401 without token")
        else:
            results.record("me_requires_auth", "FAIL", f"expected 401, got {status}")
    except OSError as exc:
        results.record("me_requires_auth", "FAIL", f"{exc.__class__.__name__}: {exc}")

    try:
        status, _, _ = fetch(base_url, "/api/persons", insecure_tls=insecure)
        if status == 401:
            results.record("protected_route_401", "PASS", "GET /api/persons -> 401")
        else:
            results.record("protected_route_401", "FAIL", f"expected 401, got {status}")
    except OSError as exc:
        results.record("protected_route_401", "FAIL", f"{exc.__class__.__name__}: {exc}")


def check_metrics(results: Results, base_url: str, insecure: bool, compose: list[str]) -> None:
    try:
        status, _, _ = fetch(base_url, "/metrics", insecure_tls=insecure)
        if status != 200:
            results.record("metrics_not_public", "PASS", f"/metrics through the edge -> {status} (not 200)")
        else:
            results.record(
                "metrics_not_public", "FAIL",
                "/metrics is served through the public edge (internal-only policy, docs/12 §14)",
            )
    except OSError as exc:
        results.record("metrics_not_public", "FAIL", f"{exc.__class__.__name__}: {exc}")

    probe = (
        "import urllib.request; "
        "print(urllib.request.urlopen('http://api:8000/metrics', timeout=5).status)"
    )
    try:
        proc = subprocess.run(
            [*compose, "exec", "-T", "api", "python", "-c", probe],
            capture_output=True, text=True, timeout=30,
        )
        if proc.returncode == 0 and proc.stdout.strip() == "200":
            results.record("metrics_internal_only", "PASS", "200 from inside the Docker network")
        else:
            detail = (proc.stderr or proc.stdout).strip().splitlines()
            results.record(
                "metrics_internal_only", "FAIL",
                f"exit={proc.returncode} {detail[-1] if detail else 'no output'}",
            )
    except (OSError, subprocess.TimeoutExpired) as exc:
        results.record("metrics_internal_only", "FAIL", f"{exc.__class__.__name__}: {exc}")


def check_ports(results: Results, forbidden_ports: list[int]) -> None:
    for port in forbidden_ports:
        name = f"port_{port}_not_public"
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1.5):
                results.record(name, "FAIL", f"something is listening on 127.0.0.1:{port}")
        except OSError:
            results.record(name, "PASS", "refused")


def compose_ps(compose: list[str]) -> list[dict[str, Any]]:
    """docker compose ps --format json (array or JSON-lines)."""
    proc = subprocess.run(
        [*compose, "ps", "--all", "--format", "json"],
        capture_output=True, text=True, timeout=60,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "docker compose ps failed")
    text = proc.stdout.strip()
    if not text:
        return []
    try:
        data = json.loads(text)
        return data if isinstance(data, list) else [data]
    except json.JSONDecodeError:
        return [json.loads(line) for line in text.splitlines() if line.strip()]


def check_docker(results: Results, compose: list[str], ready_checks: dict[str, Any]) -> None:
    try:
        rows = compose_ps(compose)
    except (OSError, RuntimeError, json.JSONDecodeError) as exc:
        results.record("only_proxy_publishes", "FAIL", f"{exc.__class__.__name__}: {exc}")
        results.record("containers_healthy", "FAIL", f"{exc.__class__.__name__}: {exc}")
        results.record("worker_heartbeat", "FAIL", f"{exc.__class__.__name__}: {exc}")
        return

    by_service = {row.get("Service") or row.get("Name", ""): row for row in rows}

    # 17: only the proxy publishes host ports (80/443). Publishers entries
    # with PublishedPort 0/None are container-EXPOSE-only (no host
    # binding) — docker compose ps lists them too; they are not publishes.
    violations: list[str] = []
    for service, row in sorted(by_service.items()):
        publishers = row.get("Publishers") or []
        for pub in publishers:
            published = pub.get("PublishedPort")
            target = pub.get("TargetPort")
            if not published or int(published) == 0:
                continue  # exposed on the container only, not host-published
            if service == "caddy" and int(target) in (80, 443):
                continue
            violations.append(f"{service}:{published}->{target}")
    if violations:
        results.record("only_proxy_publishes", "FAIL", ", ".join(violations))
    else:
        results.record("only_proxy_publishes", "PASS", "only caddy publishes 80/443")

    # 18: all services running; healthchecked ones healthy.
    problems: list[str] = []
    for service in ALL_SERVICES:
        row = by_service.get(service)
        if row is None:
            problems.append(f"{service}: missing")
            continue
        if row.get("State") != "running":
            problems.append(f"{service}: {row.get('State')}")
        elif service in HEALTHCHECKED and row.get("Health") != "healthy":
            problems.append(f"{service}: health={row.get('Health')!r}")
    if problems:
        results.record("containers_healthy", "FAIL", ", ".join(problems))
    else:
        results.record("containers_healthy", "PASS", f"{len(ALL_SERVICES)} services running")

    # 19: worker heartbeat — arq's Redis key seen by readiness AND the
    # worker container's own healthcheck.
    worker_row = by_service.get("worker", {})
    worker_container_healthy = worker_row.get("Health") == "healthy"
    readiness_ok = ready_checks.get("worker") == "ok"
    if readiness_ok and worker_container_healthy:
        results.record("worker_heartbeat", "PASS", "readiness worker=ok, container healthy")
    elif readiness_ok != worker_container_healthy:
        results.record(
            "worker_heartbeat", "FAIL",
            f"readiness worker={ready_checks.get('worker')!r}, container health="
            f"{worker_row.get('Health')!r} (disagree)",
        )
    else:
        results.record(
            "worker_heartbeat", "FAIL",
            f"readiness worker={ready_checks.get('worker')!r}, container health="
            f"{worker_row.get('Health')!r}",
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="verify_deployment.py",
        description="Verify a deployed Ketabdaneh stack through its public edge "
                    "(Task 5.12; docs/12 §13).",
    )
    parser.add_argument("--base-url", default="https://localhost",
                        help="public base URL, e.g. https://example.com (default: %(default)s)")
    parser.add_argument("--http-base-url", default=None,
                        help="plain-HTTP base for the redirect check "
                             "(default: derived from --base-url)")
    parser.add_argument("--insecure-tls", action="store_true",
                        help="skip certificate verification — LOCAL SIMULATION ONLY "
                             "(Caddy internal CA, docs/12 §16)")
    parser.add_argument("--username", default=None, help="login check username")
    parser.add_argument("--password", default=None, help="login check password")
    parser.add_argument("--forbidden-ports", default=DEFAULT_FORBIDDEN_PORTS,
                        help="host ports that must NOT be reachable "
                             "(default: %(default)s; the development stack's "
                             "5433/6390 are not listed)")
    parser.add_argument("--env-file", default=None,
                        help="path to .env.prod (default: <repo>/.env.prod)")
    parser.add_argument("--compose-file", default=None,
                        help="path to docker-compose.prod.yml "
                             "(default: <repo>/docker-compose.prod.yml)")
    args = parser.parse_args()

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env_file = args.env_file or os.path.join(root, ".env.prod")
    compose_file = args.compose_file or os.path.join(root, "docker-compose.prod.yml")
    compose = ["docker", "compose", "--env-file", env_file, "-f", compose_file]

    http_base = args.http_base_url or args.base_url.replace("https://", "http://", 1)
    forbidden = [int(p) for p in args.forbidden_ports.split(",") if p.strip()]

    results = Results()
    check_http_redirect(results, http_base, args.base_url, args.insecure_tls)
    check_web(results, args.base_url, args.insecure_tls)
    check_web_pages(results, args.base_url, args.insecure_tls)
    ready_checks = check_api_health(results, args.base_url, args.insecure_tls)
    check_auth(results, args.base_url, args.insecure_tls, args.username, args.password)
    check_metrics(results, args.base_url, args.insecure_tls, compose)
    check_ports(results, forbidden)
    check_docker(results, compose, ready_checks)

    passed = sum(1 for _, s, _ in results.rows if s == "PASS")
    skipped = sum(1 for _, s, _ in results.rows if s == "SKIP")
    print(f"\n{passed} PASS, {results.failed} FAIL, {skipped} SKIP "
          f"({len(results.rows)} checks)")
    return 1 if results.failed else 0


if __name__ == "__main__":
    sys.exit(main())
