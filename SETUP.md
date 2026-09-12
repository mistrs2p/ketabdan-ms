# Ketabdaneh — Complete Local Setup Guide

English | [فارسی](SETUP.fa.md)

Step-by-step instructions for running the entire system locally (Windows / PowerShell; the same steps apply on macOS/Linux with `source .venv/bin/activate` instead).

---

## 0) Architecture at a Glance

```text
Next.js + TypeScript (frontend, apps/web, port 3000)
        ↓ (HTTP / JSON + Bearer token)
FastAPI (backend, apps/api, port 8000)
        ↓
PostgreSQL (database, port 5433 — inside Docker)
Redis (notification queue, port 6390 — inside Docker)
```

Three services must run: **Docker (database + Redis)**, **API**, **Web**.
The notification worker is optional (only for real Bale/Telegram message delivery).

---

## 1) Prerequisites

| Tool | Version | Needed for |
| --- | --- | --- | --- |
| [Node.js](https://nodejs.org) + npm | ≥ 20 | Frontend |
| [Python](https://www.python.org) | ≥ 3.12 | Backend |
| Docker + Docker Compose | — | PostgreSQL and Redis |
| Git | — | Version control |

Verify installations:

```powershell
node --version
python --version
docker --version
```

---

## 2) Clone and Environment Files

```powershell
git clone <repo-url>
cd ketabdaneh
```

Three env files are required — copy them from the example files:

```powershell
# 1) Repository root (values for Docker Compose)
Copy-Item .env.example .env

# 2) Backend
Copy-Item apps\api\.env.example apps\api\.env

# 3) Frontend
Copy-Item apps\web\.env.example apps\web\.env
```

The defaults work out of the box for local development and are consistent with each other. The important ones:

| File | Variable | Default | Notes |
| --- | --- | --- | --- | --- |
| root `.env` | `POSTGRES_PORT` | `5433` | Database port on your machine |
| `apps/api/.env` | `DATABASE_URL` | `postgresql+psycopg://ketabdaneh:ketabdaneh_dev@localhost:5433/ketabdaneh` | Must match the above |
| `apps/api/.env` | `REDIS_URL` | `redis://localhost:6390/0` | For the notification worker |
| `apps/api/.env` | `AUTH_SECRET_KEY` | placeholder | Dev only; must be replaced in production |
| `apps/api/.env` | `CORS_ALLOW_ORIGINS` | `http://localhost:3000,http://127.0.0.1:3000` | Browser origins allowed to call the API |
| `apps/web/.env` | `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:8000` | Backend address |

> ⚠️ **Why port 5433, not 5432?** A native Windows PostgreSQL may already occupy
> 5432 and silently hijack connections meant for the container. Same for Redis:
> 6390 instead of 6379.
>
> ⚠️ Real `.env` files are never committed (only the `*.example` files are tracked).

---

## 3) Database and Redis (Docker)

From the **repository root**:

```powershell
docker compose up -d
```

This starts two services with healthchecks:

- PostgreSQL → `localhost:5433` (user/password/database from the root `.env`)
- Redis → `localhost:6390`

Verify they are healthy:

```powershell
docker ps          # both should show "healthy"
docker compose ps
```

Management commands:

```powershell
docker compose down              # stop (data is kept in the volume)
docker compose down -v           # stop + delete ALL data (!dangerous)
docker compose logs -f postgres  # database logs
```

> PostgreSQL data lives in the `postgres_data` volume — it survives Windows,
> Docker restarts, and `docker compose down`.

---

## 4) Backend (FastAPI)

### 4-1) Install (first time only)

```powershell
cd apps\api
python -m venv .venv
.venv\Scripts\Activate.ps1        # activate the venv
pip install -e .
pip install "pytest>=8.0" "httpx>=0.27"   # dev/test dependencies
```

> If PowerShell blocks script execution:
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

### 4-2) Database Migrations (first time + after every pull)

```powershell
# inside apps\api, venv active, Docker running
alembic upgrade head
```

This creates all tables (persons, events, roles, users, …) and the seed data
(6 organizational roles, 6 event responsibilities, the RBAC roles/permissions).

```powershell
alembic check      # verify the database matches the models (should report no diff)
```

> ⚠️ **Skipping this step means no tables exist at all** — every
> database-backed endpoint (even login) returns 500. Get in the habit of running
> `alembic upgrade head` after every `git pull`.

### 4-3) Create the First User (first time only)

There is no public registration; users are created only via this CLI:

```powershell
python -m app.create_user admin --role admin
```

The password is prompted **interactively**, twice (so it must run in your own
terminal — not piped or non-interactive).

Available roles: `admin` (all permissions), `manager`, `operator` (no
`people:create`). A user with no role can log in but gets 403 on every business
route.

Related command:

```powershell
python -m app.assign_role <username> <role_code>   # grant a role to an existing user
```

### 4-4) Run the API Server

```powershell
uvicorn app.main:app --reload --port 8000 --host 0.0.0.0
```

Then these are live:

| URL | What it is |
| --- | --- |
| <http://localhost:8000/api/health> | Liveness — `{"status": "ok"}` |
| <http://localhost:8000/api/health/ready> | Readiness — database/Redis/worker status |
| <http://localhost:8000/docs> | **Swagger UI** — interactive API testing |
| <http://localhost:8000/redoc> | ReDoc documentation |
| <http://localhost:8000/metrics> | Prometheus metrics (internal) |

**Using Swagger UI:** run `POST /api/auth/login` with your credentials, copy the
`access_token`, click **Authorize** at the top, paste the token — now every
protected endpoint runs with `Authorization: Bearer <token>`.

> Note: `--host 0.0.0.0` guarantees the API is reachable even when the browser
> resolves `localhost` to IPv6. If you bind to 127.0.0.1 only and the frontend
> shows "The service is unreachable", restart with this flag.

---

## 5) Frontend (Next.js)

In a **separate terminal**:

```powershell
cd apps\web
npm install        # first time only
npm run dev
```

Site: <http://localhost:3000> — login page at `/fa/login` (Persian) or `/en/login`.

Sign in with the user created in step 4-3.

---

## 6) Notification Worker (optional)

Only needed when real Bale/Telegram delivery must be tested:

```powershell
# inside apps\api, venv active
python -m app.worker
```

Requires: Redis running (step 3) + a bot token in `apps/api/.env`:

```text
TELEGRAM_BOT_TOKEN=...
BALE_BOT_TOKEN=...
```

Without this service the rest of the system works fully (the worker status in
`/api/health/ready` is informational only).

---

## 7) Running Tests

```powershell
# Backend — from apps\api (no PostgreSQL needed; in-memory SQLite)
python -m pytest

# Frontend — from apps\web
npm test

# Frontend lint
npm run lint
```

---

## 8) Daily Routine (once everything is installed)

Open three terminals:

```powershell
# Terminal 1 — infrastructure (only needed if it was restarted)
docker compose up -d

# Terminal 2 — API
cd apps\api
.venv\Scripts\Activate.ps1
# if there was a new pull: alembic upgrade head
uvicorn app.main:app --reload --port 8000 --host 0.0.0.0

# Terminal 3 — web
cd apps\web
npm run dev
```

After every `git pull`:

```powershell
cd apps\api ; .venv\Scripts\Activate.ps1 ; alembic upgrade head
```

---

## 9) Quick Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| Tables are empty / login returns 500 | Migrations never ran | `alembic upgrade head` (§4-2) |
| "The service is unreachable" on the login form | Browser could not reach the API | Is the API up? Port 8000? Correct value in the web `.env`? Restart with `--host 0.0.0.0` |
| "Invalid username or password" | No such user, or wrong password | Create a user (§4-3) — the message is deliberately identical for all three cases |
| Everything is 403 after login | The user has no role | `python -m app.assign_role <user> admin` |
| Database connection refused | A native PostgreSQL took over 5432 / container is down | `docker compose ps`; use port 5433 |
| AUTH_SECRET_KEY error at startup | Placeholder without the dev allowance | In dev set `AUTH_ALLOW_INSECURE_DEV_SECRET=1` |
| `alembic` is not recognized | venv not activated | `.venv\Scripts\Activate.ps1` |

---

## 10) Note: Full Production Stack (local simulation)

To simulate the full production topology (Caddy + all services with fake
credentials) — full documentation: [docs/12-DEPLOYMENT.md](docs/12-DEPLOYMENT.md)

```powershell
# from the repository root
Copy-Item .env.prod.example .env.prod    # defaults ARE the simulation values
scripts\deploy.sh --skip-pull
```

Not needed for day-to-day development.
