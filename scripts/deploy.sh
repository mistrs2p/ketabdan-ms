#!/usr/bin/env bash
# Deterministic production deployment for the Ketabdaneh stack
# (Task 5.12; docs/12-DEPLOYMENT.md).
#
# What this script does, in order — nothing else, nothing implicit:
#   1. git pull --ff-only            (bring the checkout to origin/main)
#   2. validate .env.prod            (required vars present, secret length)
#   3. docker compose build          (images from the current checkout)
#   4. alembic upgrade head          (EXPLICIT migration step — never
#                                     run automatically by any container)
#   5. docker compose up -d          (restart changed services)
#   6. wait for https readiness      (bounded, fails loudly)
#   7. run scripts/verify_deployment.py (public-edge smoke; login check
#                                     only runs when credentials are
#                                     given to THAT script, not here)
#
# Usage (on the server, from the repo checkout — see docs/12 §2/§6):
#   scripts/deploy.sh
#
# Flags:
#   --skip-pull    do not git pull (local simulation / detached builds;
#                  docs/12 §16 — NEVER a way to skip review on a server)
#   --skip-verify  skip the readiness wait + verification step
#   -h | --help    this text
#
# This script never: runs destructive database commands, drops or
# recreates volumes, edits the host firewall (an explicit operator
# action — docs/12 §9), or pushes anything anywhere.
#
# Linux-first (bash, docker, curl). It also runs under Git Bash on
# Windows for the local deployment simulation.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="${ENV_FILE:-$ROOT_DIR/.env.prod}"
COMPOSE_FILE="$ROOT_DIR/docker-compose.prod.yml"
COMPOSE=(docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE")

SKIP_PULL=0
SKIP_VERIFY=0

usage() { sed -n '2,30p' "$0" >&2; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-pull) SKIP_PULL=1 ;;
    --skip-verify) SKIP_VERIFY=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage; exit 2 ;;
  esac
  shift
done

# Read one value from the env file (last definition wins; CRLF-safe for
# files edited on Windows). Never source the file — it is data, not code.
env_value() {
  grep -E "^${1}=" "$ENV_FILE" | tail -n 1 | cut -d= -f2- | tr -d '\r'
}

fail() { echo "deploy: $*" >&2; exit 1; }

echo "==> [1/7] checkout"
[[ -f "$ENV_FILE" ]] || fail ".env.prod not found at $ENV_FILE (cp .env.prod.example .env.prod — docs/12 §4)"
if [[ $SKIP_PULL -eq 1 ]]; then
  echo "    --skip-pull: leaving the checkout as-is (local simulation)"
else
  git -C "$ROOT_DIR" pull --ff-only
fi

echo "==> [2/7] validate .env.prod"
REQUIRED_VARS=(WEB_DOMAIN POSTGRES_USER POSTGRES_PASSWORD POSTGRES_DB \
  AUTH_SECRET_KEY CORS_ALLOW_ORIGINS NEXT_PUBLIC_API_BASE_URL)
for var in "${REQUIRED_VARS[@]}"; do
  val="$(env_value "$var")"
  [[ -n "$val" ]] || fail "$var is empty or missing in $ENV_FILE"
done
AUTH_SECRET_KEY="$(env_value AUTH_SECRET_KEY)"
[[ ${#AUTH_SECRET_KEY} -ge 32 ]] \
  || fail "AUTH_SECRET_KEY is shorter than 32 characters (docs/01 §11.7)"
WEB_DOMAIN="$(env_value WEB_DOMAIN)"
NEXT_PUBLIC_API_BASE_URL="$(env_value NEXT_PUBLIC_API_BASE_URL)"
# Same-origin is the deployed architecture (docs/12 §5); a mismatch is
# almost always a misconfigured .env.prod, so make it loud — but it can
# be legitimate behind a nonstandard HTTPS port, hence warn-not-fail.
if [[ "$NEXT_PUBLIC_API_BASE_URL" != "https://$WEB_DOMAIN" ]]; then
  echo "    WARNING: NEXT_PUBLIC_API_BASE_URL ($NEXT_PUBLIC_API_BASE_URL) is not" \
       "the same origin as https://$WEB_DOMAIN — see docs/12 §5" >&2
fi
echo "    .env.prod OK (domain: $WEB_DOMAIN)"

echo "==> [3/7] build images"
"${COMPOSE[@]}" build

echo "==> [4/7] migrate (explicit alembic upgrade head)"
"${COMPOSE[@]}" run --rm api alembic upgrade head

echo "==> [5/7] start / restart the stack"
"${COMPOSE[@]}" up -d

if [[ $SKIP_VERIFY -eq 1 ]]; then
  echo "==> --skip-verify: skipping readiness wait and verification"
  exit 0
fi

echo "==> [6/7] wait for HTTPS readiness"
HTTPS_PORT="$(env_value HTTPS_PUBLISHED_PORT)"
HTTPS_PORT="${HTTPS_PORT:-443}"
BASE_URL="https://$WEB_DOMAIN:$HTTPS_PORT"
# The local simulation Caddyfile uses Caddy's internal CA (no ACME), so
# certificate verification cannot succeed there — detect it, don't guess.
INSECURE=""
CADDYFILE="$(env_value CADDYFILE)"
CADDYFILE="${CADDYFILE:-./deploy/Caddyfile}"
# Resolve relative to the repo root (the value is compose-relative);
# absolute paths pass through untouched.
case "$CADDYFILE" in
  /*) CADDYFILE_PATH="$CADDYFILE" ;;
  *) CADDYFILE_PATH="$ROOT_DIR/${CADDYFILE#./}" ;;
esac
if grep -q "tls internal" "$CADDYFILE_PATH"; then
  INSECURE="-k"
fi
READY_URL="$BASE_URL/api/health/ready"
DEADLINE=$((SECONDS + 180))
until curl -fsS $INSECURE --max-time 10 "$READY_URL" >/dev/null 2>&1; do
  [[ $SECONDS -lt $DEADLINE ]] || fail "API not ready at $READY_URL after 180s — see docs/12 §17 (troubleshooting)"
  echo "    waiting for $READY_URL ..."
  sleep 5
done
echo "    ready: $READY_URL"

echo "==> [7/7] deployment verification"
# python3 first (Linux); fall back to python (Windows Git Bash, where the
# WindowsApps python3 shim may exist but not work). A broken interpreter
# must not silently pass — probe it with an actual command.
PY=""
if command -v python3 >/dev/null 2>&1 && python3 -c "import sys" >/dev/null 2>&1; then
  PY=python3
elif command -v python >/dev/null 2>&1 && python -c "import sys" >/dev/null 2>&1; then
  PY=python
fi
if [[ -n "$PY" ]]; then
  VERIFY_ARGS=(--base-url "$BASE_URL")
  [[ -n "$INSECURE" ]] && VERIFY_ARGS+=(--insecure-tls)
  "$PY" "$SCRIPT_DIR/verify_deployment.py" "${VERIFY_ARGS[@]}"
else
  echo "    no working python found — run scripts/verify_deployment.py manually (docs/12 §13)"
fi

echo "==> deployment complete: $BASE_URL"
