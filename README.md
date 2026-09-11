# Ketabdaneh

Branch operations management system for a Ketabdaneh branch.

The goal: keep branch operations running in an organized and predictable way
when the branch manager is physically absent — with visibility into events,
assignments, tasks, completion status, and important exceptions.

## Current Architecture

```
Next.js + TypeScript (frontend, apps/web)
        ↓
      FastAPI (backend, apps/api)
        ↓
    PostgreSQL (database, via Docker Compose)
```

Architecture style: **Modular Monolith** — one deployable backend, one
database, internally organized into domain modules.

See [docs/00-PROJECT-CONTEXT.md](docs/00-PROJECT-CONTEXT.md) and
[docs/01-ARCHITECTURE.md](docs/01-ARCHITECTURE.md) for details.

## Repository Structure

```
ketabdaneh/
├── apps/
│   ├── web/          # Next.js + TypeScript frontend (App Router)
│   └── api/          # FastAPI backend
├── docs/             # Project documentation
├── infrastructure/   # Deployment/ops files (reserved, empty for now)
├── docker-compose.yml  # Local PostgreSQL
├── README.md
├── .gitignore
└── .editorconfig
```

## Local Development

### Prerequisites

- **Node.js** ≥ 20 (with npm)
- **Python** ≥ 3.12 (with [pip](https://pip.pypa.io/), or any tool that can
  install from `pyproject.toml`)
- **Docker** + Docker Compose (for PostgreSQL)

### PostgreSQL (database)

```bash
# from the repository root
cp .env.example .env        # adjust values if you like; dev-only defaults
docker compose up -d        # starts PostgreSQL with persistent storage

# stop it (data is kept in the postgres_data volume)
docker compose down
```

PostgreSQL listens on the host port configured in `.env`
(`POSTGRES_PORT`, default `5433` — 5432 is avoided because a native
PostgreSQL service on this machine may already occupy it). Data persists in
the `postgres_data` volume.

### Backend (FastAPI)

```bash
cd apps/api
python -m venv .venv
. .venv/bin/activate         # Windows (PowerShell): .venv\Scripts\Activate.ps1
pip install -e .
pip install "pytest>=8.0" "httpx>=0.27"    # dev/test dependencies
                              # (httpx is required by FastAPI's TestClient)

uvicorn app.main:app --reload --port 8000
```

The API is now available at http://localhost:8000 — health check:
`GET /api/health` → `{"status": "ok"}`; business endpoints: `GET /api/roles`
(the seeded reference roles), `GET /api/persons` (branch members with their
roles), `POST /api/persons` (create a branch member, optionally with
roles), `GET /api/events` (list events ordered by planned time — the
calendar read), `GET /api/events/{event_id}` (one event; unknown id →
404), `POST /api/events` (create an event — always `DRAFT`, with a
timezone-aware planned time), `GET /api/event-assignments`,
`GET /api/event-assignments/{assignment_id}`, and
`POST /api/event-assignments` (create an assignment — always `PENDING`;
references resolved by id/code). Interactive docs (Swagger UI) at
http://localhost:8000/docs.

Configuration is environment-based (see `apps/api/.env.example`): set
`DATABASE_URL` to point at PostgreSQL. The API starts without it — only
database-dependent features require it.

Persistence foundation (SQLAlchemy 2.x ORM models for the approved MVP
schema, database session management, tests): see
[docs/04-BACKEND-PERSISTENCE.md](docs/04-BACKEND-PERSISTENCE.md). Run the
test suite with `python -m pytest tests` from `apps/api`.

Database migrations are managed with **Alembic** (configuration and rules in
[docs/05-DATABASE-MIGRATIONS.md](docs/05-DATABASE-MIGRATIONS.md)). With
`DATABASE_URL` configured and PostgreSQL running, from `apps/api`:

```bash
alembic upgrade head    # apply all pending migrations
alembic check           # verify database matches the models
```

### Frontend (Next.js)

```bash
cd apps/web
npm install
npm run dev
```

The web app is now available at http://localhost:3000 (the login page is
at `/fa/login` / `/en/login`). Unit/component tests (vitest +
testing-library, browser DOM via jsdom): `npm test`.

### Production stack and deployment (Tasks 5.11 + 5.12)

The workflow above is the development workflow — local servers against
the development compose file. The production runtime topology is
containerized in `docker-compose.prod.yml`: web → api → postgres +
redis → worker, fronted by a **Caddy edge proxy** that is the only
service publishing host ports (80/443). The browser reaches the API
same-origin at `https://<domain>/api/...`; PostgreSQL, Redis, the API,
and web are internal-network only.

Deploying on a server, and running the same stack locally as a
simulation with fake credentials and Caddy's internal CA:

```bash
# on the server (docs/12 §6):            # locally (docs/12 §16):
cp .env.prod.example .env.prod           cp .env.prod.example .env.prod
# edit per docs/12 §4 (real domain,      # defaults ARE the simulation
# real secrets, ACME Caddyfile)          # values — nothing to edit
scripts/deploy.sh                        scripts/deploy.sh --skip-pull
```

`scripts/deploy.sh` is the deterministic flow: pull → validate env →
build → explicit `alembic upgrade head` → up → readiness wait →
`scripts/verify_deployment.py` (public-edge smoke, 19 checks). Backups:
`scripts/backup_db.sh`; restore rehearsal: `scripts/restore_db.sh`
(docs/12 §10–§12).

See [docs/12-DEPLOYMENT.md](docs/12-DEPLOYMENT.md) for prerequisites,
server layout, TLS, firewall, backup/restore/rollback, verification,
and troubleshooting, and [docs/01-ARCHITECTURE.md](docs/01-ARCHITECTURE.md)
§12 for the container-level facts (images, healthchecks, ports).

## Continuous Integration

Every push to `main` and every pull request runs the CI workflow
(`.github/workflows/ci.yml`): four parallel jobs — backend (compileall,
pip check, full pytest), frontend (ESLint, Vitest, production build),
docker (compose validation, image builds, worker runtime, Caddyfile
syntax), and security (gitleaks secret scan over the full git history,
pip-audit, npm audit, bandit). CI needs no secrets and runs read-only,
so fork pull requests run the same pipeline safely. Security policy and
vulnerability reporting: [SECURITY.md](SECURITY.md). How CI works, its
failure policy, documented dependency exceptions, and the local
equivalent of every check: [docs/13-CI.md](docs/13-CI.md).

## Current Project Status

**Phase 4 (Frontend) complete; Phase 5 (Auth) underway.** The repository
contains the runnable
full-stack application: local development infrastructure, the approved
domain model and database schema design
([docs/02](docs/02-DOMAIN-MODEL.md), [docs/03](docs/03-DATABASE-SCHEMA.md)),
the SQLAlchemy ORM persistence foundation
([docs/04](docs/04-BACKEND-PERSISTENCE.md)), Alembic migrations with the six
confirmed roles and six initial event responsibilities seeded
([docs/05](docs/05-DATABASE-MIGRATIONS.md)), and the frozen Phase 3 backend
API ([docs/06](docs/06-BACKEND-API.md)) — exactly 10 routes:
`GET /api/health`, `GET /api/roles`, `GET /api/persons`, `POST /api/persons`,
`GET /api/events`, `GET /api/events/{event_id}`, `POST /api/events`,
`GET /api/event-assignments`,
`GET /api/event-assignments/{assignment_id}`, and
`POST /api/event-assignments` — plus the API error policy and the
EventAssignment approval contract (defined, not implemented).

Task 5.1 added the **backend authentication foundation** (docs/06 §4f):
a `users` table (migration `0004`, separate from `persons`), Argon2id
password hashing, HS256 JWT access tokens, `POST /api/auth/login` and
`GET /api/auth/me` (generic 401s, no user enumeration), and the
`python -m app.create_user` bootstrap CLI — no default account.

Task 5.2 added **backend authorization / RBAC** (docs/06 §4g):
application roles and permissions as database rows (migration `0005` —
`application_roles`, `permissions`, and two join tables; the business
domain roles on `persons` are untouched and separate), stable permission
codes (`roles:read`, `people:read`, `people:create`, `events:read`,
`events:create`, `assignments:read`, `assignments:create`), a seeded
admin/manager/operator matrix, a single `require_permission` dependency
protecting all nine business routes (401 unauthenticated, 403
insufficient permission, permissions resolved server-side on every
request), and the `python -m app.assign_role` operator CLI
(`create_user` gained `--role`). Business routes are now
permission-protected; there is no frontend login UI yet (Task 5.3).

Task 5.3 added **frontend authentication** (docs/06 §4h): the web app's
browser code now consumes the auth backend — a login page at
`/fa/login`/`/en/login` (bilingual, themed, generic 401 messaging),
`lib/auth/` (contract types, token storage, login/me/logout calls, and
the `AuthProvider` session state that restores exactly once via
`/api/auth/me` — a token alone never renders authenticated UI), central
Bearer injection in the shared API client, and 401-driven session
clearing. The token is kept in `localStorage` — an explicitly documented
MVP trade-off (not XSS-safe; httpOnly-cookie/BFF is the future option);
logout is client-side only (the backend has no revocation endpoint).
The frontend contains **no authorization logic** — roles/permissions
stay server-side. The API now also serves CORS from a configured
allow-list (`CORS_ALLOW_ORIGINS`) since the browser calls it directly.

Task 5.4 added **protected routes and auth-aware navigation**
(docs/06 §4i): the `(app)` route group (dashboard, calendar, events,
people, tasks — both locales) is wrapped in a client-side `AuthGate`
that redirects unauthenticated visitors to the locale-aware login with
a validated `returnTo` (internal locale-prefixed paths only — no open
redirect), renders a loading state instead of protected content (no
flash in the served HTML), and sends already-authenticated visitors on
`/login` to the dashboard. Because the token lives in `localStorage`,
middleware cannot read it — the guard is deliberately client-side: an
authentication boundary in the browser, not server-side access control
(httpOnly-cookie/BFF remains the documented future option). The header
now shows the signed-in username and a localized logout button.
Navigation distinguishes only authenticated vs unauthenticated —
**no permission-based UI hiding** (backend RBAC stays the real
permission enforcement).

Task 5.5 added the **notification abstraction** (docs/01 §6):
`apps/api/app/notifications/` — a provider-agnostic boundary so future
providers (Telegram/Bale in Task 5.6, later email/SMS/in-app) can plug
in without business services knowing any provider detail. It defines a
neutral `NotificationMessage` / `NotificationRecipient` (channel + an
opaque provider-external address) model, an async `NotificationProvider`
protocol, a `NotificationDispatcher` built by explicit constructor
injection (no global state), normalized `NotificationResult`s, and
distinct error types — an unregistered channel raises
`UnsupportedChannelError`, while unavailable/rejected/crashing providers
come back as failure results (never silently swallowed, never an
automatic 500). No real provider, token, SDK, network call, persistence,
or retry exists yet — those belong to Tasks 5.6/5.7. No HTTP endpoint
was added; this is infrastructure only.

Task 5.6 added the **Telegram and Bale providers** (docs/01 §6.2):
`TelegramNotificationProvider` (`api.telegram.org`) and
`BaleNotificationProvider` (`tapi.bale.ai`) implement the Task 5.5
provider protocol on top of verified Bot API contracts (POST
`/bot<token>/sendMessage`; both platforms share the wire shape, so the
common handling lives in `_botapi.py` while each adapter owns its
endpoint and limits). Bot tokens come from `TELEGRAM_BOT_TOKEN` /
`BALE_BOT_TOKEN` (`.env.example` documents them; no real credentials in
source); `build_notification_dispatcher(settings)` is the single wiring
point, and an unconfigured provider reports a provider-unavailable
failure only when a send is actually attempted. Failures map to the
5.5 error model (4xx → rejected, 401/429/5xx/timeout → unavailable,
with the provider's retry hint preserved), requests are bounded by
`NOTIFICATION_TIMEOUT_SECONDS` (default 10 s), oversized messages are
rejected (4096-char guard) rather than truncated, and the recipient
address is data in the JSON body — never a URL (SSRF-safe). The whole
test matrix runs against an in-memory mock transport: no network, no
credentials. No business workflow sends notifications yet — automatic
triggers are a future task.

Task 5.7 added **background delivery with bounded retries** (docs/01
§6.5): `BackgroundNotificationService.enqueue_notification(...)` queues a
generic, strictly-JSON job on Redis (ARQ 0.28 — asyncio-native, no
pickle in Redis), and a separate worker process (`python -m app.worker`)
consumes jobs, reconstructs the `NotificationMessage`, and delivers
through the same `build_notification_dispatcher` factory — the provider
layer is not duplicated. Failures classify per the 5.5/5.6 semantics:
rejected → never retried; unavailable/unexpected → exponential backoff
(`NOTIFICATION_MAX_ATTEMPTS` / base / max delay settings; provider
retry-after hints respected, capped), after which the job fails
permanently — no infinite retries. Delivery is **at-least-once**.
Redis is `REDIS_URL` (default `redis://localhost:6390/0`; `docker
compose up -d redis` provides it for local development) and is never
required just to import or serve the API. The full pipeline (real
service → real arq worker → real providers) is tested offline against
fakeredis + a mock HTTP transport. No business event triggers
notifications yet — this is the reusable infrastructure they will call.

Task 5.8 added the **production logging foundation** (docs/01 §9): one
central configuration in `apps/api/app/core/logging.py` (stdlib `logging`
only — no framework, no observability stack), one consistent format
(UTC ISO-8601, level, logger name, pid) for the API and the worker, and
`LOG_LEVEL` as a validated setting. HTTP requests are logged once per
request (method, path, status, duration, request id) with a size- and
charset-bounded `X-Request-ID` correlation id echoed in the response;
authentication/authorization failures log the reason and a minimal user
reference at WARNING while responses stay generic; unexpected exceptions
get exactly one stack trace (the server's — no duplicate app-level
handler). Credentials, tokens, notification text, and recipient
addresses are never logged — pinned by tests. The worker's logs carry
job id, attempt, channel, and category for diagnosability. Metrics,
tracing, and alerting remain out of scope.

Task 5.9 added the **observability foundation** (docs/01 §10): health
endpoints and Prometheus-compatible metrics, deliberately foundation-only
(no monitoring stack). `GET /api/health` keeps its pre-existing contract
while `/api/health/live` (liveness — never touches dependencies, so a
Redis outage can't restart-loop a healthy process) and
`/api/health/ready` (readiness — PostgreSQL `SELECT 1` on the existing
engine plus a Redis `PING`, each under a hard timeout; `503 not_ready`
when either is down, fixed words only, never exception text) join it.
The worker's aliveness is reported honestly from arq's Redis heartbeat
key (`no_recent_heartbeat`, not a false "ok") and is informational, not
gating. `GET /metrics` (API process) and an optional
`WORKER_METRICS_PORT` (worker process) expose request
counters/durations, in-flight gauge, and worker job / notification
delivery counters via `prometheus-client`. Labels are bounded by
construction — route templates (never raw paths), status classes, fixed
outcome vocabularies, validated channels — and never user ids, texts,
recipients, tokens, or query strings; health/metrics paths themselves
are unmetered. Instrumentation failures are swallowed: observability
can never take the app down.

Task 5.10 hardened the **production configuration and secrets story**
(docs/01 §11): the application now **fails closed** rather than
silently running with a dangerous configuration. `APP_ENV`
(`development` | `test` | `production`, case-insensitive, never
inferred) selects the environment; in production, Settings
construction rejects the placeholder or a short (`<32` chars)
`AUTH_SECRET_KEY`, the `AUTH_ALLOW_INSECURE_DEV_SECRET` flag, a
missing `DATABASE_URL`, an unset `REDIS_URL`, and wildcard CORS —
with a clear `ConfigurationError` before the server serves anything.
Every credential-bearing setting (JWT key, bot tokens, and the DB and
Redis URLs, which can embed `user:password@`) is a `SecretStr`;
configuration errors name the setting and the requirement but never
echo the value (pydantic's `input_value=...` leaking is defeated by
raising `RuntimeError`-based errors and
`hide_input_in_errors=True`). URL validation is shape-only — no
connection is made during Settings construction (connectivity stays
readiness' job, per 5.9). Telegram/Bale tokens stay optional in every
environment, one without the other is fine, and the core app never
requires notification credentials. Local development keeps every
documented convenience, including the placeholder secret with the
explicit flag. No secret manager was added (deployment injects
secrets as environment variables — see docs/01 §11.7), no secrets are
stored in the database, and no new dependencies were introduced.

Task 5.11 established the **production container baseline**
(docs/01 §12): production Docker images for the whole application —
multi-stage, non-root, no dev tooling or test dependencies — plus a
production-oriented compose topology (`docker-compose.prod.yml`) with
an explicit internal network, named-volume PostgreSQL persistence,
native healthchecks for every service, `depends_on: service_healthy`
startup ordering, and restart/graceful-stop policies (the worker's
stop window exceeds its 120s job timeout). PostgreSQL and Redis are
not exposed to the host in the production stack; only the API (8000)
and web (3000) are published, because the browser calls the API
directly until a reverse proxy task fronts them. The API and worker
share one image (`ketabdaneh-api`) with different commands; the web
image builds on Next.js standalone output. Migrations are an explicit
`docker compose ... run --rm api alembic upgrade head` — never
automatic. All runtime values come from a git-ignored `.env.prod`
(`.env.prod.example` is the fake-values template); the only build
argument is the public `NEXT_PUBLIC_API_BASE_URL`. Local development
is unchanged (`docker-compose.yml` still provides PostgreSQL/Redis
for local dev servers). The first real containerized run surfaced and
fixed two latent bugs: the arq worker ignored `REDIS_URL` (arq's
default localhost was used), and the readiness heartbeat check looked
for a key arq never writes. No cloud deployment, TLS, reverse proxy,
CI/CD, or Kubernetes — those are later tasks.

Task 5.12 turned that baseline into the **production deployment story**
(docs/12-DEPLOYMENT.md): a Caddy edge proxy is the only service
publishing host ports (80/443) — TLS termination with automatic ACME
certificates (a `tls internal` variant drives the local simulation),
HTTP→HTTPS redirect, and same-origin routing (`https://<domain>/api/*`
→ API, everything else → web; the browser calls the API same-origin, so
CORS never triggers in production and no frontend rewrite was needed —
every frontend path already starts with `/api/`). The API, web,
PostgreSQL, and Redis publish nothing. `scripts/deploy.sh` is the
deterministic deployment flow (pull → validate env → build → explicit
migration → up → readiness wait → verify); `scripts/verify_deployment.py`
checks the deployed system through its public edge (19 checks: redirect,
TLS, web, API health/readiness, login + 401s, internal-only metrics,
no exposed ports, worker heartbeat); `scripts/backup_db.sh` /
`scripts/restore_db.sh` implement the pg_dump backup baseline and the
rehearsed restore procedure. No real-server deployment was performed —
the deployment was verified as a full local simulation with fake
credentials and Caddy's internal CA (docs/12 §16 states this
distinction explicitly).

Task 5.13 added the **CI and security hardening layer**
(docs/13-CI.md, SECURITY.md): the four-job CI workflow described above
(SHA-pinned actions, `contents: read` only, zero secrets — fork-safe by
construction), a blocking gitleaks secret scan over the full git
history (the repository is clean; no allowlist exists), pip-audit and
a calibrated npm-audit gate with the one documented dependency
exception (postcss-via-next, docs/13 §6), bandit at the calibrated
medium+ level, and compose-level security regression tests
(`apps/api/tests/test_compose_security.py`) that pin the deployment
posture: only Caddy publishes 80/443, no privileged containers or
Docker-socket mounts, non-root images, read-only root filesystems, and
capability sets pinned to the documented minimum. All six production
containers were hardened (read_only + tmpfs, cap_drop ALL, no-new-
privileges) and validated by re-running the full local deployment
simulation: 18/18 verification checks through the public edge,
including login, plus a stack-recreation persistence check and direct
runtime probes. CI has not yet run on the remote platform; every check
was rehearsed locally (docs/13 §12 has the local equivalents).

On top of that API, the Phase 4 frontend (tasks 4.1–4.9) is complete:
bilingual (fa/en) locale routing with full RTL/LTR support, light/dark
theming, the typed API client layer (`apps/web/lib/api/`), and the
operational screens — People list / create / detail, Events list / create /
detail, weekly Calendar (read-only visualization), event Assignments
(read/create) inside Event detail, and the manager Dashboard (operational
overview built from the existing list APIs). No dashboard backend endpoint
was added. The remaining business APIs and UI features (tasks, reports,
approval workflow, availability, frontend auth) follow as the open domain
questions ([docs/00](docs/00-PROJECT-CONTEXT.md) §7) are resolved.

## Conventions

- Git workflow: see [docs/11-GIT-WORKFLOW.md](docs/11-GIT-WORKFLOW.md) and
  [AGENTS.md](AGENTS.md).
- Commits follow Conventional Commits (`feat:`, `fix:`, `docs:`, …).
- Never commit real secrets — `.env` is git-ignored; only `.env.example`
  files are tracked.
