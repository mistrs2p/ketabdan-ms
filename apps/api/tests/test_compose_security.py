"""Repository-level security regression tests (Task 5.13; docs/13-CI.md).

These tests lock in the deployment-security properties established in
Tasks 5.11–5.13 at the *configuration* level, so a compose/Dockerfile
edit that silently weakens them fails CI exactly like a code regression:

- only the Caddy proxy publishes host ports (80/443); PostgreSQL, Redis,
  the API, and web are internal-network only
- no privileged containers, host networking/PID/IPC, or Docker socket
  mounts anywhere in the production stack
- the only bind mount is the Caddyfile (read-only); everything else is
  a named volume
- every service runs with no-new-privileges, a read-only root
  filesystem, and dropped capabilities (documented additions only)
- the application images run as non-root users

The runtime counterparts (ports actually refused, login/401s through
the public edge, metrics internal-only) are covered by the deployment
verification script (scripts/verify_deployment.py, docs/12 §13); the
application-level properties (fail-closed production config, no
wildcard CORS, no insecure JWT fallback, secret masking, 401/403
contracts) are covered by test_config_hardening.py, test_api_auth.py,
test_api_authz.py, and test_observability.py — deliberately not
duplicated here.
"""

import re
from pathlib import Path

import yaml

# tests/test_compose_security.py -> apps/api -> apps -> repository root.
REPO_ROOT = Path(__file__).resolve().parents[3]
COMPOSE_PROD = REPO_ROOT / "docker-compose.prod.yml"
COMPOSE_DEV = REPO_ROOT / "docker-compose.yml"
API_DOCKERFILE = REPO_ROOT / "apps" / "api" / "Dockerfile"
WEB_DOCKERFILE = REPO_ROOT / "apps" / "web" / "Dockerfile"

# Services that must never publish a host port in the production stack
# (docs/12 §3: only Caddy publishes, 80/443).
INTERNAL_SERVICES = ("postgres", "redis", "api", "worker", "web")


def _load(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _prod_services() -> dict:
    return _load(COMPOSE_PROD)["services"]


_VAR_DEFAULT = re.compile(r"^\$\{[A-Za-z_][A-Za-z0-9_]*:-(?P<default>[^}]*)\}$")


def _resolve_default(value: str) -> str:
    """Resolve `${VAR:-default}` interpolation to its default (for checks).

    The compose files use defaults everywhere so the stack runs from the
    template env file alone; a port without a default is an operator
    override and stays as-is (and then fails the exact-set assertions).
    """
    match = _VAR_DEFAULT.match(value.strip())
    return match.group("default") if match else value.strip()


def _published_ports(services: dict) -> set[tuple[str, str, str]]:
    """(service, host port, container port) from short- or long-form ports.

    Short form is what both compose files use ("80:443", "${VAR:-80}:80");
    long form ({target, published}) is parsed too so a future rewrite of
    the compose files does not silently weaken this check.
    """
    result = set()
    for name, service in services.items():
        for entry in service.get("ports", []):
            if isinstance(entry, str):
                # Short form "HOST:CONTAINER[/proto]". rpartition, not
                # split: the host side may be ${VAR:-default}, whose
                # interpolation itself contains a colon.
                host, _, container = entry.rpartition(":")
                published = host or container
                container = container.split("/")[0]
            else:
                published = str(entry.get("published", ""))
                container = str(entry.get("target", ""))
            result.add((name, _resolve_default(published), _resolve_default(container)))
    return result


# --- public exposure --------------------------------------------------------


def test_only_caddy_publishes_host_ports() -> None:
    services = _prod_services()
    for name in INTERNAL_SERVICES:
        assert "ports" not in services[name], (
            f"{name} must not publish host ports (only caddy does; docs/12 §3)"
        )
    published = _published_ports(services)
    assert published == {("caddy", "80", "80"), ("caddy", "443", "443")}, (
        f"unexpected host-published ports: {sorted(published)}"
    )


def test_internal_services_are_on_the_internal_network_only() -> None:
    services = _prod_services()
    for name in INTERNAL_SERVICES:
        assert services[name].get("networks") == ["internal"], (
            f"{name} must be attached to exactly the internal network"
        )


# --- container hardening ----------------------------------------------------


def test_no_privileged_or_host_namespaces() -> None:
    for name, service in _prod_services().items():
        assert not service.get("privileged", False), f"{name} is privileged"
        assert service.get("network_mode") != "host", f"{name} uses host networking"
        for key in ("pid", "ipc"):
            assert service.get(key) != "host", f"{name} uses host {key} namespace"


def test_no_docker_socket_or_unexpected_bind_mounts() -> None:
    for name, service in _prod_services().items():
        sources = [v.split(":")[0] for v in service.get("volumes", [])]
        for source in sources:
            assert "docker.sock" not in source, f"{name} mounts the Docker socket"
        # Named volumes (no leading path separator / no "./") and exactly
        # one bind mount in the whole stack: the Caddyfile, read-only.
        binds = [s for s in sources if s.startswith("/") or s.startswith("./")]
        allowed = {"./deploy/Caddyfile", "deploy/Caddyfile"}
        assert set(binds) <= allowed, f"{name} has unexpected bind mounts: {binds}"
    caddy_volumes = _prod_services()["caddy"]["volumes"]
    caddyfile_mounts = [v for v in caddy_volumes if "Caddyfile" in v]
    assert len(caddyfile_mounts) == 1 and caddyfile_mounts[0].endswith(":ro"), (
        "the Caddyfile must be mounted exactly once, read-only"
    )


def test_all_services_drop_privileges_and_caps() -> None:
    services = _prod_services()
    for name, service in services.items():
        opts = service.get("security_opt", [])
        assert "no-new-privileges:true" in opts, (
            f"{name} must set no-new-privileges"
        )
        assert "ALL" in service.get("cap_drop", []), (
            f"{name} must drop all capabilities (add back only what is documented)"
        )
        assert service.get("read_only") is True, (
            f"{name} must run with a read-only root filesystem"
        )


def test_capability_additions_are_the_documented_minimal_set() -> None:
    services = _prod_services()
    # postgres: the official entrypoint/initdb needs user switching and
    # file ownership; caddy binds 80/443 as root. Everything else: none.
    assert set(services["postgres"].get("cap_add", [])) == {
        "CHOWN", "DAC_OVERRIDE", "FOWNER", "SETGID", "SETUID",
    }
    assert services["caddy"].get("cap_add", []) == ["NET_BIND_SERVICE"]
    for name in ("redis", "api", "worker", "web"):
        assert not services[name].get("cap_add", []), (
            f"{name} should not need any added capabilities"
        )


def test_redis_runs_as_unprivileged_user() -> None:
    assert _prod_services()["redis"]["user"] == "999:999"


# --- images -----------------------------------------------------------------


def test_application_images_run_non_root() -> None:
    """The USER directives in both Dockerfiles must exist and not be root.

    (The worker shares the API image; Caddy/Postgres/Redis official
    images are outside this repository's control — their handling is
    documented in docs/13-CI.md §container hardening.)
    """
    for dockerfile in (API_DOCKERFILE, WEB_DOCKERFILE):
        lines = dockerfile.read_text(encoding="utf-8").splitlines()
        users = [ln.split()[1] for ln in lines if ln.startswith("USER ")]
        assert users, f"{dockerfile.name} has no USER directive"
        assert users[-1] not in ("root", "0", "0:0"), (
            f"{dockerfile.name} runtime USER must not be root (got {users[-1]!r})"
        )


def test_dev_compose_publishes_only_the_documented_dev_ports() -> None:
    """The development compose publishes 5433/6399-style dev ports only.

    This is the developer's local convenience (docs/01 §12.1) — the test
    keeps anyone from accidentally "fixing" a dev-only port clash by
    publishing production-shaped ports there.
    """
    services = _load(COMPOSE_DEV)["services"]
    published = _published_ports(services)
    assert published == {
        ("postgres", "5433", "5432"),
        ("redis", "6390", "6379"),
    }, f"unexpected dev-compose published ports: {sorted(published)}"
