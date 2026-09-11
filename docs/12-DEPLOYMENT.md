# 12 — Production Deployment (implemented — Task 5.12)

The Task 5.11 container baseline turned into a repeatable
single-Linux-server deployment: a Caddy edge proxy as the single public
entry point (HTTPS, HTTP→HTTPS redirect, same-origin `/api` routing), a
deterministic deploy script, explicit migrations, backup/restore/
rollback procedures, and a public-edge verification script.

> **Real deployment status (honest, per task spec):**
>
> **REAL PRODUCTION DEPLOYMENT: NOT PERFORMED.**
> **LOCAL DEPLOYMENT SIMULATION: VERIFIED.**
>
> No real server, real domain, or real TLS certificate was involved.
> Everything in this document that touches a real server (DNS, ACME,
> firewall) is written as the operator procedure; everything else
> (proxy routing, TLS termination, same-origin API access, auth through
> the edge, startup ordering, migrations, backup and restore) was
> executed and verified locally with Docker — see §16.

Related: docs/01-ARCHITECTURE.md §12 (container baseline), docs/01 §10
(health/metrics), docs/01 §11 (configuration/secrets), docs/06 §4
(API), docs/05 (migrations).

## 1. Scope

One Linux server, Docker Engine + Compose v2, one public domain. No
cloud services, no Kubernetes, no CI/CD, no secret managers, no
third-party backup storage — provider-neutral, deliberately boring.

## 2. Prerequisites (server)

- A Linux x86-64 server (any provider) with:
  - **Docker Engine** and **Compose v2** (`docker compose ...` works)
  - **SSH access** and a persistent disk for the Docker volumes
    (`postgres_data`, `caddy_data`) and backups
  - A **non-root user** with docker group membership (or root — but the
    containers themselves never run as root)
- **DNS**: an A/AAAA record for the deployment domain
  (e.g. `ketabdaneh.example.org`) pointing at the server's public IP
- **Inbound ports open**: 22 (SSH), 80 and 443 (the deployment —
  see §9)
- `curl` (readiness wait in deploy.sh) and `python3` (verification
  script); both are near-universal

## 3. Topology and networking

```text
                 ┌── caddy :80/:443 ── the ONLY host-published ports ──┐
   Internet ─────┤   80  -> 308 redirect -> 443 (and ACME HTTP-01)
                 │   443 -> TLS termination (ACME certificate)
                 │        /api/* -> api:8000      (same-origin, §5)
                 │        *       -> web:3000     (Next.js)
                 └──────────────────── internal Docker network ───────┘
   web ──> api ──> postgres (5432, internal only)
               └──> redis (6379, internal only) ──> worker
```

- **Only Caddy publishes host ports** (80/443, defaults overridable via
  `HTTP_PUBLISHED_PORT`/`HTTPS_PUBLISHED_PORT`). The API (8000), web
  (3000), PostgreSQL (5432) and Redis (6379) have **no host ports** —
  they are reachable only on the internal Docker network.
- Caddy is **not an open proxy**: it forwards to exactly two fixed
  upstreams (`api:8000`, `web:3000`) on that network, never to
  arbitrary addresses. `reverse_proxy` sets
  `X-Forwarded-For`/`X-Forwarded-Proto`/`X-Forwarded-Host` and preserves
  `Host`; WebSocket upgrades pass through transparently.
- Startup ordering is expressed with the Task 5.11 healthchecks:
  postgres/redis healthy → (migrations, explicit §7) → api → worker
  (needs redis) and web (needs api healthy) → caddy (needs api + web
  healthy).
- `deploy/Caddyfile` is the production configuration (automatic ACME
  TLS). `deploy/Caddyfile.local` is the local-simulation variant
  (Caddy's internal CA) — identical routing, one `tls internal` line.

## 4. Environment file (.env.prod)

Copy the committed template and edit — the file is git-ignored and
never committed:

```bash
cp .env.prod.example .env.prod
```

Real-server values that differ from the template's local-simulation
defaults:

| Variable | Real deployment | Template default (local sim) |
| --- | --- | --- |
| `WEB_DOMAIN` | the real DNS name, e.g. `ketabdaneh.example.org` | `localhost` |
| `CADDYFILE` | `./deploy/Caddyfile` (ACME — the default) | `./deploy/Caddyfile.local` |
| `ACME_EMAIL` | a real operator address | *(empty)* |
| `NEXT_PUBLIC_API_BASE_URL` | `https://<WEB_DOMAIN>` | `https://localhost` |
| `CORS_ALLOW_ORIGINS` | `https://<WEB_DOMAIN>` | `https://localhost` |
| `POSTGRES_PASSWORD`, `AUTH_SECRET_KEY` | generated secrets (below) | fake local values |

Secrets are generated on the server, never committed, never sent
anywhere:

```bash
openssl rand -hex 32        # AUTH_SECRET_KEY (>= 32 chars, enforced at startup)
openssl rand -hex 24        # POSTGRES_PASSWORD
```

`NEXT_PUBLIC_API_BASE_URL` is **public by nature** (it is inlined into
browser JavaScript at build time). It must contain only the public site
origin — never a JWT secret, DB password, Redis credential, or bot
token. None of those exist in the web image at all (docs/01 §12.2).
`CORS_ALLOW_ORIGINS` stays an exact origin — no `*` (Task 5.10
rejects wildcards in production).

## 5. Public URL model: same-origin /api

The browser calls the API **same-origin**: `https://<domain>/api/...`.
This works with zero frontend changes because every frontend call path
already begins with `/api/` (apps/web/lib/api/*) and the API client
only joins base + path (`apiBaseUrl`/`buildApiUrl`): the base URL is
simply the site origin. Caddy routes `/api/*` to the API container and
everything else to the web app.

Consequences:

- **Same-origin requests never trigger CORS** — no preflight, no
  cross-origin exposure. `CORS_ALLOW_ORIGINS` remains configured (exact
  origin) as defense-in-depth; Task 5.10 forbids `*` regardless.
- No frontend rewrite was needed (the task explicitly forbade forcing
  one); nothing about `apps/web/lib/api/client.ts` changed.

## 6. Deployment workflow

### 6.1 Server layout

```text
/opt/ketabdaneh/
├── repo/            # git checkout of this repository
│   └── .env.prod    # environment file (git-ignored by the repo itself)
├── backups/         # pg_dump archives (backup_db.sh default target)
└── logs/            # optional: collected docker logs (see §13)
```

```bash
sudo mkdir -p /opt/ketabdaneh/{backups,logs}
sudo chown -R <operator> /opt/ketabdaneh
git clone <repository-url> /opt/ketabdaneh/repo
```

`.env.prod` lives inside the checkout because every command in this
stack takes `--env-file .env.prod` from the repo root; the repository's
own `.gitignore` covers `.env.*` (only `*.example` templates are
committed), so it cannot be committed accidentally.

### 6.2 First deployment

```bash
cd /opt/ketabdaneh/repo
cp .env.prod.example .env.prod   # then edit per §4
scripts/deploy.sh
```

`deploy.sh` is deterministic — same checkout + same env file ⇒ same
result. In order: `git pull --ff-only` → validate `.env.prod`
(required vars present, `AUTH_SECRET_KEY` ≥ 32 chars) → `docker compose
build` → `alembic upgrade head` (explicit, §7) → `docker compose up -d`
→ wait for HTTPS readiness (bounded at 180 s) → run
`scripts/verify_deployment.py` (§13). It never edits the firewall,
never runs destructive database commands, and never touches volumes.

Then create the first user (there is no public registration —
docs/06 §4f):

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml \
  run --rm api python -m app.create_user <username> --role admin
```

(The password is prompted interactively — never a command-line
argument; `--role admin` matches the bootstrap role seeded by migration
0005.)

### 6.3 Updating

The same script: `scripts/deploy.sh`. A code update is pull → rebuild →
migrate → restart → verify; an env-only change needs
`docker compose --env-file .env.prod -f docker-compose.prod.yml up -d`
(recreate with the new values). `--skip-pull` exists for detached
builds and the local simulation (§16) — it is not a way to skip review
on a server.

## 7. Database migrations

Migrations are **explicit and only ever explicit** — nothing runs
Alembic on container startup (an API restart must never rewrite schema
on its own; docs/01 §12.4, docs/05):

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml \
  run --rm api alembic upgrade head
```

`deploy.sh` runs exactly this command as its migration step. There is
no automatic downgrade, and no destructive reset anywhere: the scripts
never run `dropdb`, `downgrade base`, or volume recreation. Rolling a
migration back is a deliberate operator action — see §12 for what is
and is not possible.

## 8. TLS

- **Real server**: Caddy automatically obtains a certificate for
  `WEB_DOMAIN` from Let's Encrypt/ZeroSSL on first start and renews it
  before expiry — no cron jobs, no certbot. Port 80 must stay reachable
  (ACME HTTP-01 challenges and the HTTPS redirect both live there).
  Certificates persist in the `caddy_data` volume.
- **No certificate or key is ever committed.** The committed Caddyfiles
  contain no certificate material at all; `ACME_EMAIL` is the only
  TLS-adjacent setting and it is an email address, not a credential.
- **Local simulation** (§16): `deploy/Caddyfile.local` uses
  `tls internal` — Caddy's own CA issues the certificate locally. No
  ACME, no public trust; verification runs with `--insecure-tls`.

If certificate issuance fails on a real server, see §17
("certificate issue").

## 9. Firewall

The final topology needs exactly these inbound ports: **22, 80, 443**.
PostgreSQL, Redis, the API and web ports are internal to Docker and
must not be opened. Docker publishes only 80/443 (§3), so the host
firewall is the remaining gate.

Firewall mutation is an **explicit operator action** — deliberately
NOT scripted by anything in this repository. Example with ufw (run by
the operator, reviewed by the operator):

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp    # verify SSH access BEFORE enabling, or lock yourself out
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo ufw status verbose
```

These commands were NOT executed by this task (no real server); they
are the standard ufw procedure. Verify afterwards that
`https://<domain>` works and that `5432`/`6379`/`8000`/`3000` are
refused from outside (§13 checks the local side of exactly this).

## 10. Backup

```bash
scripts/backup_db.sh
# -> /opt/ketabdaneh/backups/ketabdaneh-<UTC-timestamp>.dump
```

- `pg_dump` **custom format** (`-Fc`), streamed to a **host-side** file
  — the dump never lives inside an ephemeral container.
- Location: `KETABDANEH_BACKUP_DIR` (default `/opt/ketabdaneh/backups`).
- The script verifies the archive magic bytes (`PGDMP`) and reports the
  size.
- **No automatic deletion/rotation** — retention is a deliberate
  operator decision (e.g. "keep 14 dailies + monthlies" executed by
  hand or by an operator-owned cron job that THEY wrote and reviewed).
- **No third-party storage** — nothing is uploaded anywhere, ever.
- Suggested cadence: daily, before/after every migration (§7).
- Backups are git-ignored (`backups/`, `*.dump` in .gitignore).

## 11. Restore (rehearse first, always)

Restores are **rehearsed against a throwaway database** — never
straight onto the live one:

```bash
# 1. Restore into a throwaway target (created if missing):
scripts/restore_db.sh /opt/ketabdaneh/backups/ketabdaneh-<stamp>.dump ketabdaneh_restore_test

# 2. Inspect the rehearsal database:
docker compose --env-file .env.prod -f docker-compose.prod.yml \
  exec postgres psql -U ketabdaneh -d ketabdaneh_restore_test -c '\dt'

# 3. Drop ONLY the throwaway database when done:
docker compose --env-file .env.prod -f docker-compose.prod.yml \
  exec postgres dropdb -U ketabdaneh ketabdaneh_restore_test
```

This exact procedure was executed and verified against a temporary
database during the local simulation (§16) — including the table-count
check and the cleanup drop.

Restoring **over the live database** is not automated (restore_db.sh
restores into a named target and makes you type the name twice; if the
target IS the live database it warns and asks again). The manual
live-restore procedure, for when it is genuinely needed:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml stop api worker
docker compose --env-file .env.prod -f docker-compose.prod.yml \
  exec postgres dropdb -U ketabdaneh ketabdaneh          # destroys live data — deliberate, by hand
docker compose --env-file .env.prod -f docker-compose.prod.yml \
  exec postgres createdb -U ketabdaneh ketabdaneh
scripts/restore_db.sh /opt/ketabdaneh/backups/ketabdaneh-<stamp>.dump ketabdaneh
docker compose --env-file .env.prod -f docker-compose.prod.yml \
  run --rm api alembic upgrade head                      # stamps/repairs schema state if the backup predates a migration
docker compose --env-file .env.prod -f docker-compose.prod.yml start api worker
```

## 12. Rollback

**Image/code rollback — straightforward.** The previous deployment is
the previous git commit; roll back to it and redeploy:

```bash
cd /opt/ketabdaneh/repo
git log --oneline -5                # identify the last known-good commit
git checkout <good-commit>
scripts/deploy.sh --skip-pull       # rebuild + migrate + restart + verify from that commit
git checkout main                   # when done investigating
```

**Database rollback — conditional, and honestly limited.** Code that no
longer matches the database schema fails; therefore:

- If the new migration is **backward-compatible** (the old code tolerates
  the new schema), image rollback alone suffices.
- Every migration so far (0001–0005) ships a `downgrade()` path, so
  `docker compose ... run --rm api alembic downgrade <revision>` is
  possible — run it deliberately, by hand, after the image rollback.
  The scripts never do this automatically.
- If a migration is **irreversible** (data loss or a destructive
  downgrade), the honest options are **restore from backup (§11)** or a
  **forward fix** (new migration repairing the damage). No tooling in
  this repository will pretend otherwise.

There is no automatic, no-questions-asked rollback: both rollback
paths above are operator decisions made with the incident in view.

## 13. Health checks and verification

Public endpoints (through the edge, unauthenticated by design):

| Endpoint | Meaning |
| --- | --- |
| `GET https://<domain>/api/health` | liveness `{"status":"ok"}` |
| `GET https://<domain>/api/health/live` | liveness (explicit name) |
| `GET https://<domain>/api/health/ready` | readiness: database + redis gate; worker informational |

Container healthchecks (docs/01 §12.5): api via `/api/health/live`,
worker via arq's Redis heartbeat key, postgres `pg_isready`, redis
`ping`, web via node fetch. Caddy has none (image ships no wget/curl)
— the external verification below covers it.

The deployment verification script checks the deployed system the way
a user and an attacker see it:

```bash
python3 scripts/verify_deployment.py --base-url https://<domain> \
    [--username <user> --password <pass>]
```

19 checks: HTTP→HTTPS redirect, HTTPS serves, web locale redirect,
page renders, API health and readiness through the public path, login
issues a token (needs credentials; skipped otherwise), `/me` works with
the token, `/me` and a protected route 401 without it, `/metrics` NOT
public, `/metrics` reachable internally, ports 5432/6379/8000/3000
refused on the host, only caddy publishes host ports, all containers
running/healthy, worker heartbeat alive. Exit code 1 on any failure;
`deploy.sh` runs it automatically as its last step.

Logs (no secrets by construction — Task 5.8's logging and Task 5.10's
SecretStr guarantee it; bearer tokens and passwords are never logged):

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml logs -f api worker
```

## 14. Metrics policy: internal-only

The API's Prometheus endpoint (`GET /metrics` at the server root,
docs/01 §10) is **deliberately not routed through the proxy** — a
request for `/metrics` on the public edge falls through to the web app
(Next.js 404). Metrics are reachable **only inside the Docker network**:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml \
  exec api python -c "import urllib.request; print(urllib.request.urlopen('http://api:8000/metrics', timeout=5).read()[:200])"
```

Metrics therefore never automatically become public. A future scraper
(Prometheus or otherwise) joins the internal network — that is a later
observability task; nothing here installs one. No Prometheus was added
by this task.

## 15. Security notes

- **Public surface**: exactly ports 80/443 on the proxy. No wildcard
  CORS (exact origin, and same-origin in practice — §5).
- **Proxy**: not an open proxy (two fixed internal upstreams); forwards
  only the standard `X-Forwarded-*` headers; no directory listing
  (Caddy serves no filesystem at all — it proxies); `.env.prod`,
  `.git/`, and `backups/` are not servable by anything (they are not
  inside any served container; the web image contains only server.js,
  static assets, and message catalogs).
- **Secrets**: never committed (git-ignored env file), never in build
  args, never in images, never in `NEXT_PUBLIC_*`, never logged.
  Task 5.10's `APP_ENV=production` fail-closed validation runs inside
  the containers.
- **Containers**: non-root (api `app`/1000, web `nextjs`/1001); worker
  and API share one image with no test/tooling files.
- **Certification material**: none committed (§8).

## 16. Local deployment simulation (verified)

No real server exists in this environment, so the deployment was
simulated locally with Docker — fake domain (`localhost`), fake
credentials, Caddy's internal CA (`deploy/Caddyfile.local`), no real
Telegram/Bale. The developer's normal dev stack (docker-compose.yml,
ports 5433/6390) stayed untouched.

```bash
cp .env.prod.example .env.prod        # defaults ARE the simulation values
scripts/deploy.sh --skip-pull         # build -> migrate -> up -> wait -> verify
```

Verified (see the task report for the raw transcript): proxy build and
routing, TLS termination (internal CA), HTTP→HTTPS redirect, web and
API through the public edge, login + authenticated `/me` + 401s through
the edge, readiness, worker heartbeat, explicit migrations, PostgreSQL
persistence, Redis, internal-only metrics, no direct API/web/DB/Redis
port exposure, backup (`backup_db.sh`) and a full restore rehearsal
into a throwaway database (`restore_db.sh`), then teardown
(`docker compose ... down -v` on the ketabdaneh-prod project — the
development stack is a different project and stays untouched).

Differences from a real deployment, honestly: no ACME (internal CA +
`--insecure-tls`), no DNS (`localhost`), no firewall (§9 is the
operator's action), fake secrets. One machine artifact: the local run
passes `--forbidden-ports 6379,8000,3000` instead of the defaults —
this development machine runs a native Windows PostgreSQL on 5432
(pre-existing, unrelated to the stack; the `only_proxy_publishes`
check proves the stack's own postgres publishes nothing).

## 17. Troubleshooting

All commands from the repo root with
`docker compose --env-file .env.prod -f docker-compose.prod.yml ...`
(abbreviated below as `...`).

**API unhealthy / API not ready (deploy.sh step 6 times out)**
`... ps` — is `api` running/healthy? `... logs api` — a startup crash
is usually configuration: Task 5.10's fail-closed validation names the
offending setting (missing/short `AUTH_SECRET_KEY`, wildcard CORS,
unset `REDIS_URL`). Readiness 503 with `database: unavailable` → see
"DB unavailable" below; `redis: unavailable` → "Redis unavailable".

**Worker unhealthy / no heartbeat**
`... ps` (worker health), `... logs worker`. The worker needs Redis
first (`depends_on: service_healthy`); its healthcheck is arq's Redis
heartbeat key refreshed every 30 s — a freshly restarted worker needs
~45 s before "healthy". Persistent unhealthiness with healthy Redis =
worker crash-looping; the log shows why (the Task 5.11 `redis_settings`
class-attribute requirement is regression-tested, so suspect
configuration first).

**Database unavailable**
`... ps` (postgres healthy?), `... logs postgres`. Startup ordering
waits for `pg_isready`; if postgres is healthy but readiness says
`database: unavailable`, check `DATABASE_URL` assembly in `.env.prod`
(`POSTGRES_USER`/`POSTGRES_PASSWORD`/`POSTGRES_DB`). Data survives
restarts in the `postgres_data` volume — do NOT recreate it when
debugging; that is the data.

**Redis unavailable**
`... ps` (redis healthy?), `... logs redis`. Redis is intentionally
ephemeral (no persistence, docs/01 §12) — restarting it is safe; queued
notification jobs are lost by design (at-least-once applies to running
jobs, not to an erased queue).

**Certificate issue (real server only)**
`... logs caddy` — issuance failures name the ACME problem. Checklist:
DNS A record actually points at the server (`dig +short <domain>`),
port 80 reachable from the Internet (HTTP-01), `WEB_DOMAIN` set
correctly (no `https://` prefix — just the name), the `caddy_data`
volume not deleted mid-issuance. Rate limits apply after repeated
failed attempts — fix the cause before retrying.

**Port conflict (80/443 already in use)**
`ss -tlnp | grep -E ':80|:443'` — usually another web server or a
stale container. Either stop the offender or remap via
`HTTP_PUBLISHED_PORT`/`HTTPS_PUBLISHED_PORT` in `.env.prod` (then
`... up -d` and adjust `--base-url`/`--http-base-url` in verification
accordingly).

**Migration failure (deploy.sh step 4)**
`... run --rm api alembic upgrade head` shows Alembic's error. The API
keeps running on the old schema (migrations ran against a `run --rm`
container, not the live one). A half-applied multi-statement migration
is transactional in our migrations — check the revision with
`... run --rm api alembic current`, fix the cause (usually a schema
conflict from a skipped migration), re-run. Destructive shortcuts
(`downgrade base`, `dropdb`) are never the first move — §12.
