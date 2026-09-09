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
404), and `POST /api/events` (create an event — always `DRAFT`, with a
timezone-aware planned time). Interactive docs (Swagger UI) at
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

The web app is now available at http://localhost:3000.

## Current Project Status

**Event read API stage.** The repository contains the runnable
application skeletons, local development infrastructure, the approved domain
model and database schema design
([docs/02](docs/02-DOMAIN-MODEL.md), [docs/03](docs/03-DATABASE-SCHEMA.md)),
the SQLAlchemy ORM persistence foundation
([docs/04](docs/04-BACKEND-PERSISTENCE.md)), Alembic migrations with the six
confirmed roles seeded ([docs/05](docs/05-DATABASE-MIGRATIONS.md)), and the
first business endpoints — `GET /api/roles`, `GET /api/persons`,
`POST /api/persons`, `GET /api/events` (calendar-oriented list),
`GET /api/events/{event_id}` (single event), and
`POST /api/events` (event creation, always `DRAFT`) — plus the API error
policy ([docs/06](docs/06-BACKEND-API.md)). The remaining business APIs and
UI features follow as the open domain questions
([docs/00](docs/00-PROJECT-CONTEXT.md) §7) are resolved.

## Conventions

- Git workflow: see [docs/11-GIT-WORKFLOW.md](docs/11-GIT-WORKFLOW.md) and
  [AGENTS.md](AGENTS.md).
- Commits follow Conventional Commits (`feat:`, `fix:`, `docs:`, …).
- Never commit real secrets — `.env` is git-ignored; only `.env.example`
  files are tracked.
