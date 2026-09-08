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

PostgreSQL listens on the port configured in `.env`
(`POSTGRES_PORT`, default `5432`). Data persists in the `postgres_data` volume.

### Backend (FastAPI)

```bash
cd apps/api
python -m venv .venv
. .venv/bin/activate         # Windows (PowerShell): .venv\Scripts\Activate.ps1
pip install -e .

uvicorn app.main:app --reload --port 8000
```

The API is now available at http://localhost:8000 — health check:
`GET /api/health` → `{"status": "ok"}`.
Interactive docs (Swagger UI) at http://localhost:8000/docs.

### Frontend (Next.js)

```bash
cd apps/web
npm install
npm run dev
```

The web app is now available at http://localhost:3000.

## Current Project Status

**Bootstrap stage.** The repository contains only the runnable application
skeletons and local development infrastructure described above. No business
features have been implemented — no events, tasks, assignments, calendar,
authentication, or database schema. Those will be built after the open domain
questions listed in [docs/00-PROJECT-CONTEXT.md](docs/00-PROJECT-CONTEXT.md)
(§7) are resolved.

## Conventions

- Git workflow: see [docs/11-GIT-WORKFLOW.md](docs/11-GIT-WORKFLOW.md) and
  [AGENTS.md](AGENTS.md).
- Commits follow Conventional Commits (`feat:`, `fix:`, `docs:`, …).
- Never commit real secrets — `.env` is git-ignored; only `.env.example`
  files are tracked.
