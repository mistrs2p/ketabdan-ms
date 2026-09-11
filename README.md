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
