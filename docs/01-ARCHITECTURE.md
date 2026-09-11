# 01 — Architecture

**Project:** Ketabdaneh
**Document status:** Living document — update as discovery continues.
**Last reviewed:** 2026-09-11
**Depends on:** [00-PROJECT-CONTEXT.md](00-PROJECT-CONTEXT.md)

---

## 1. System Overview (Current Architecture)

A single web application with a classic three-layer structure:

```
Next.js + TypeScript (Frontend)
        ↓
      FastAPI (Backend)
        ↓
    PostgreSQL (Database)
```

One deployable backend, one database — a **Modular Monolith** (see §2).

## 2. Why Modular Monolith

The project's reality (from [00-PROJECT-CONTEXT.md](00-PROJECT-CONTEXT.md)):

- It serves **one branch** with a small set of users — not a multi-tenant platform.
- The team and budget are small; operational overhead must stay low.
- The domain concepts (events, assignments, tasks, availability, reports) are
  closely related and will share data constantly.
- The full domain is **not yet discovered** — several business rules are still TBD
  (see the TBD list in 00-PROJECT-CONTEXT.md §7). The architecture must absorb
  change cheaply.

Given that:

| Alternative | Why rejected (for now) |
|---|---|
| Microservices | High operational cost (deployment, networking, distributed transactions) for a workload that a single process handles easily; cross-module data sharing would turn into distributed-join pain. |
| Serverless | Cold starts and vendor coupling add friction with little benefit at this scale. |
| Pure monolith (no internal modularity) | Tends to rot into a tangled codebase; the *modular* part protects us as the domain grows. |

A modular monolith gives:

- **Cheap cross-module queries** — one process, one database, no network hops.
- **Enforced boundaries** — modules communicate through explicit internal
  interfaces, not by reaching into each other's internals.
- **A path to extraction later** — if a module ever needs to scale or deploy
  independently (e.g., a future notification service for Telegram/Bale), its
  boundary is the natural seam.

> **Definition used here:** a single FastAPI application whose internal code is
> organized into domain modules (events, tasks, people, …). Each module owns its
  own logic and data access; modules may call each other only through public
  internal APIs. Database-per-module, event bus, and other advanced variants are
  **not** adopted — see §7.

## 3. Layer Responsibilities

### 3.1 Frontend — Next.js + TypeScript

**Owns:**

- All UI rendering and user interaction for every role (manager, supporter, …).
- Client-side state for the current view (form state, optimistic updates, filters,
  calendar navigation).
- Calling the backend over its HTTP/JSON boundary (§4) and presenting results,
  including loading/error states.
- Routing between pages/screens.

**Does not own:**

- Business rules. Authorization decisions, validation of business invariants, and
  state transitions (e.g., what "completing" an event means) are decided by the
  backend. The frontend may pre-validate for UX but never as the source of truth.
- Direct database access. **The frontend never talks to PostgreSQL.**
- Scheduling/reminder logic.

**Notes:**

- The concrete list of screens (calendar view, task board, manager dashboard,
  assignment approval view, …) is **TBD — UI design is out of scope for this
  document.**
- Whether any Next.js server-side features (SSR/API routes) are used for anything
  beyond standard page rendering is **TBD** (see §7).
- **API integration foundation (implemented, Phase 4):** all backend calls go
  through one typed, fetch-based client in `apps/web/lib/api/` —
  `client.ts` (base-URL handling from `NEXT_PUBLIC_API_BASE_URL`, JSON
  headers, shared error path), `types.ts` (hand-maintained contract types
  matching docs/06 exactly — OpenAPI codegen stays deferred, TBD T3),
  `errors.ts` (the `ApiError` classification: validation 422 / not-found
  404 / server / network, preserving FastAPI's `detail` payload), and one
  module per domain (`roles`, `persons`, `events`, `eventAssignments`,
  `health`) exporting plain async functions. API modules contain no UI,
  state, or business decisions (§3.1 rules above). See
  `apps/web/.env.example` for configuration.
- **Frontend authentication (implemented, Phase 5.3):** a client auth
  module in `apps/web/lib/auth/` — `types.ts` (login/me contract types
  only; no password hashes or backend internals), `storage.ts` (the
  access token in `localStorage` — an **MVP client-token strategy, not
  XSS-safe storage**; a future httpOnly-cookie/BFF approach may provide
  stronger protection), `api.ts` (`login`/`getCurrentUser`/`logout` over
  the shared client; logout is client-side session termination only —
  the backend has no token-revocation endpoint), and `context.tsx` (the
  `AuthProvider` session state: `{user, isAuthenticated, isLoading,
  login, logout, refreshUser}`, restoring exactly once on mount via
  `/api/auth/me`; a stored token never renders authenticated UI without
  that validation). Bearer injection is centralized in `client.ts` —
  every request carries `Authorization: Bearer <token>` when a token is
  stored, and a token-carrying 401 clears the token and flips the app to
  unauthenticated. The login page renders
  at `/fa/login` / `/en/login`. The frontend holds **no authorization
  logic**: roles/permissions are never modeled or inferred client-side
  (backend RBAC is docs/06 §4g). Because the browser now calls the API
  directly, the backend serves CORS from configured origins
  (`CORS_ALLOW_ORIGINS`, no wildcard credentials).
- **Protected routes & auth-aware navigation (implemented, Phase 5.4):**
  the `(app)` route group (every business page, both locales) is wrapped
  once in its layout by a client-side `AuthGate`
  (`apps/web/components/auth/AuthGate.tsx`); the login page stays public
  outside the group. Unauthenticated visitors are redirected
  (locale-preserving, `replace` not `push`) to `/{locale}/login` with a
  validated `returnTo`; the loading state renders no protected content,
  so nothing leaks into the server HTML. Because the token lives in
  `localStorage`, middleware cannot read it — the guard is deliberately
  client-side, an *authentication boundary in the browser* rather than
  server-side access control (the httpOnly-cookie/BFF alternative stays
  a documented future option). The header shows the username plus a
  logout button; there is **no role/permission-based UI hiding** —
  authenticated ≠ authorized, and backend RBAC (docs/06 §4g) remains
  the sole permission enforcement. Details: docs/06 §4i.

### 3.2 Backend — FastAPI (Python)

**Owns:**

- The entire domain: events, assignments, tasks, availability, reports, people
  and their roles — expressed as an internally modular codebase.
- **Authorization** — every request is checked against the caller's identity and
  role(s) before doing anything. (The exact permission matrix is a domain TBD,
  not an architectural one.)
- Business validation and state transitions — the single source of truth for
  whether an action is allowed and what happens next.
- Persistence: the only layer that writes to or reads from PostgreSQL.
- The HTTP/JSON contract consumed by the frontend (§4).
- Consistency and transactional integrity (e.g., an assignment and its approval
  record change together or not at all).

**Does not own:**

- Rendering, navigation, or client state — that's the frontend's job.
- Storage layout of the database (schema ownership is shared with the DB layer,
  see §3.3).

**Notes:**

- Module boundaries inside the monolith (which modules exist, their names, and
  their public internal APIs) are **TBD — defined in a later design document**,
  once the domain TBDs from 00-PROJECT-CONTEXT.md §7 are resolved.
- Authentication mechanism (sessions vs tokens, etc.) is **TBD** (A13).

### 3.3 Database — PostgreSQL

**Owns:**

- Durable, relational storage of all domain data.
- Relational integrity (foreign keys, constraints) and the transactional
  guarantees the backend relies on.

**Does not own:**

- Business rules. Constraints are a *safety net* that mirrors invariants already
  enforced by the backend — they do not invent or decide rules.
- Any application logic (no stored procedures/triggers carrying business rules).

**Notes:**

- Concrete schema design is **intentionally deferred** (per project rules — no
  schema definition until domain TBDs are resolved).
- Read replicas, backups, migrations tooling: operational concerns, **TBD** (§7).

## 4. Communication Boundary (Frontend ⇄ Backend)

The single communication channel between the two applications:

| Aspect | Decision |
|---|---|
| Protocol | HTTP(S) with JSON request/response bodies |
| Style | Resource-oriented REST API |
| Entry point | One FastAPI service; the frontend has no other backend to call |
| Errors | Non-2xx responses; JSON error body `{"detail": ...}` (FastAPI-native) — MVP error policy defined in [06-BACKEND-API.md](06-BACKEND-API.md) §4b |
| Real-time | None in MVP — updates are visible on page load/refresh or explicit refetch. A push channel (SSE/WebSocket) is **TBD / out of MVP** |
| Auth (browser) | The web app's browser code calls the API directly with a Bearer token obtained from `POST /api/auth/login` (Phase 5.3); CORS origins are configured server-side (`CORS_ALLOW_ORIGINS`). Token persistence and session semantics: `apps/web/lib/auth/` (localStorage MVP strategy — see §3.1 notes) |

Rules of the boundary:

1. **The HTTP/JSON contract is the only coupling** between frontend and backend.
   No shared code, no shared types generation (codegen from OpenAPI is possible
   later but is **TBD**), no direct DB access from the frontend.
2. The contract is **versioned** in practice via the API surface; a formal
   versioning scheme is **TBD** (§7).
3. All authorization happens **inside the boundary** — the backend never trusts
   role/identity claims coming only from the client.
4. Pagination/filtering conventions and endpoint definitions are
   **TBD — deliberately not defined in this document** (per task rules);
   the error body shape **is** defined (docs/06 §4b).

## 5. Environments & Configuration (high level)

| Concern | Responsibility |
|---|---|
| Environment separation | At minimum: local development, production. A staging environment is **TBD**. |
| Configuration values | Database connection settings, service ports, environment flags — kept **outside code** and injected per environment (`.env`-style files locally; real secrets never committed). |
| Secrets management | Production secrets come from the deployment environment (injected as environment variables — no secret manager), not from files in the repo. See §11 (implemented — Task 5.10). |
| Database per environment | Each environment gets its own PostgreSQL instance/database; no shared databases across environments. |
| Migrations | The backend owns schema changes and applies them in a controlled, repeatable way. Specific migration tooling is **TBD**. |
| Frontend configuration | The Next.js app receives its environment-specific values (e.g., backend base URL) at build/deploy time — not hardcoded. |

## 6. Notifications — Abstraction + Telegram/Bale Providers + Background Delivery

**Status (updated, Phase 5.7):** the backend has the provider-agnostic
notification abstraction (Task 5.5), concrete Telegram and Bale providers
(Task 5.6), **and** Redis-backed background delivery with bounded retries
(Task 5.7). Providers deliver over real HTTP to the platforms' verified
Bot API endpoints; delivery happens in a background worker (no business
request path waits on a provider network call once the background service
is used). There are **no automatic business-event notifications yet** —
the infrastructure is ready for future triggers to call
`enqueue_notification(...)`.

### 6.1 The boundary (`apps/api/app/notifications/`)

```text
business service (future triggers)
      ↓  enqueue_notification(...)                service.py (Task 5.7)
Redis (arq queue, JSON jobs)                      app/worker/
      ↓  Worker → reconstruct NotificationMessage
NotificationDispatcher.send() / send_many()     dispatcher.py
      ↓
NotificationProvider (Protocol, async send)     providers.py
      ↓
TelegramNotificationProvider / BaleNotificationProvider
      ↓ (shared Telegram-style wire handling: _botapi.py)
https://api.telegram.org / https://tapi.bale.ai
```

- **Neutral domain model** (`models.py`): `NotificationMessage`
  (recipient, text, category, metadata), `NotificationRecipient`
  (channel + opaque provider-external address — *no* `chat_id` /
  `phone_number` in the generic layer), `NotificationChannel` (StrEnum;
  `telegram` and `bale`), and `NotificationResult` (success, channel,
  optional `external_message_id` / `error_code` / `error_message` — the
  only shape business code ever sees; raw provider responses never leak
  through).
- **Provider interface** (`providers.py`): a `Protocol` with a stable
  `channel` and an async `send(message) -> NotificationResult`. Not bound
  to HTTP — future local/in-app providers fit too.
- **Dispatcher / registry** (`dispatcher.py`): built explicitly with its
  providers (constructor injection — no global registry state); routes by
  the recipient's channel. Business code never instantiates providers.
- **Error model** (`errors.py`): distinct failures —
  `UnsupportedChannelError` (no provider registered — a wiring bug,
  *raised*), `ProviderUnavailableError` and `NotificationRejectedError`
  (delivery failures, *normalized into failure results*),
  `InvalidNotificationError` (malformed message/recipient, raised at
  construction). Unexpected provider crashes are normalized into a
  `provider_error` result — never silently swallowed, never turned into an
  application 500 by the infrastructure itself. Business services decide
  whether a failure is fatal, retryable, or ignorable.

### 6.2 The concrete providers (implemented — Phase 5.6)

`telegram.py` and `bale.py` are the **only** places that know their
platform: endpoint, wire format, error semantics, message limits. Both
verified contracts (2026-09) share one wire shape — POST
`{base}/bot<token>/sendMessage` with JSON `{"chat_id": <address>,
"text": <text>}`, and a JSON envelope `{"ok": bool, "result":
{"message_id": ...}, "error_code", "description", "parameters"}` — so
the common wire handling lives once in `_botapi.py` (each provider keeps
its own endpoint/limits; if either API diverges, that provider splits
off without touching the other). Telegram's contract was verified via
the grammY types generated from the official Bot API reference and
aiogram's client source; Bale's via the current `balethon` client
implementing it.

- **Authentication:** the bot token travels in the URL path
  (`/bot<token>/…`) — the platforms' documented mechanism. No
  Authorization header; the token never appears in results, exception
  messages, metadata, or logs.
- **Configuration** (`factory.py` + `app/core/config.py`): tokens come
  from `TELEGRAM_BOT_TOKEN` / `BALE_BOT_TOKEN` (never committed; see
  `apps/api/.env.example`). `build_notification_dispatcher(settings)` is
  the single composition point. Both providers are always registered —
  an unconfigured one reports a `provider_unavailable` failure **only
  when a send is attempted**, so the app runs with one, both, or no
  providers configured. Nothing consumes the dispatcher yet (no
  business triggers); Task 5.7 and future business events build on the
  factory.
- **Failure mapping** (HTTP → domain): 400/403/other 4xx →
  `NotificationRejectedError` (recipient/message refused, e.g. "chat not
  found"); 401 → `ProviderUnavailableError` (bot token rejected — a
  configuration failure); 429 → `ProviderUnavailableError` (the
  provider's `retry_after` hint is preserved in the message text);
  5xx / timeout / connection failure / malformed response →
  `ProviderUnavailableError`. The dispatcher normalizes all of these
  into failure `NotificationResult`s with stable error codes.
- **Message size (policy):** oversized messages are **rejected**
  (`message_too_long`), never truncated or chunked. Telegram's
  documented limit is 4096 characters; no public Bale limit was
  verifiable, so the same 4096 guard is applied as a conservative bound.
- **Timeouts:** every provider request is bounded
  (`NOTIFICATION_TIMEOUT_SECONDS`, default 10 s); redirects are never
  followed.
- **SSRF safety:** the HTTP destination is assembled only from the
  provider's constant base URL and the configured token. The recipient
  address is *data* (a chat id in the JSON body) and can never steer the
  URL — `NotificationRecipient(address="http://internal/…")` is simply a
  string a provider will reject.

Tests (`tests/test_notification_providers.py`,
`tests/test_notification_factory.py`) run the full matrix — success,
endpoint/auth/recipient/message assertions, Persian and mixed
RTL/LTR Unicode, every HTTP status class, timeout/connection failure,
malformed responses, missing tokens, and token/response-leakage checks —
for **both** providers against an in-memory `httpx2.MockTransport`. No
test touches the network or needs credentials. The Task 5.5 guard test
still enforces the boundary: the generic contract modules stay
network-free, and no module may import a Telegram/Bale SDK.

### 6.3 Deliberately not in this layer (yet)

- **Business-event notifications** — no workflow sends notifications
  yet; when a domain event requires one (see TBD A7), the service will
  build the notification and call
  `BackgroundNotificationService.enqueue_notification(...)` (§6.5) — or
  the dispatcher directly, when a synchronous send is genuinely wanted.
- ~~**Retries / background delivery / queues / Redis** — Task 5.7~~
  **[IMPLEMENTED — Phase 5.7, see §6.5]**.
- **Persistence** (notification/delivery-history tables, subscriptions) —
  deferred until a requirement asks for it. The worker intentionally has
  no notification database table: job state lives in Redis, bounded by
  the retry policy and job expiry.
- **HTTP endpoints** — none; this is application infrastructure, not an
  API feature.

### 6.5 Background delivery — Redis, worker, retries (implemented — Phase 5.7)

```text
business service (future triggers)
      ↓  enqueue_notification(...)                app/worker/service.py
Redis (arq queue, JSON-serialized jobs)           REDIS_URL
      ↓  Worker (arq)                             app/worker/worker.py
      ↓  reconstruct NotificationMessage          app/worker/jobs.py
NotificationDispatcher via build_notification_dispatcher (§6.2)
      ↓
Telegram / Bale provider → external delivery
```

- **Technology:** [ARQ](https://arq-docs.helpmanual.io/) 0.28 — a small
  asyncio-native job queue on redis-py's async client (chosen over
  Celery: the codebase is async, the delivery job is one async call, and
  ARQ's `Retry`/`max_tries` semantics map exactly onto the classification
  below; no broker/beat machinery needed). Jobs are serialized as
  **strict JSON, not pickle** — a compromised Redis cannot execute code
  in the worker, and anything non-serializable fails loudly at enqueue
  time instead of silently entering the queue.
- **The job contract** (`app/worker/jobs.py`): a `NotificationJob` is
  the queue-safe image of a `NotificationMessage` — channel, recipient
  address, text, category, metadata. Only stable JSON data; no Python
  objects, callbacks, provider instances, credentials, or endpoints.
  Reconstruction goes back through the Task 5.5 model, and unknown keys
  are rejected (a corrupt or hostile payload fails permanently on its
  first attempt).
- **Redis configuration:** `REDIS_URL` (default
  `redis://localhost:6390/0`, the compose port). Like `DATABASE_URL`, a
  missing/unreachable Redis **never breaks importing or starting the
  API** — the connection is made when the queue is used (enqueue) or the
  worker starts, with bounded connect timeouts and retries; an outage
  becomes a controlled `NotificationQueueError` ("nothing was queued"),
  never an obscure import-time crash.
- **Retry classification** (the Task 5.5/5.6 failure semantics, applied):
  successful result → done; `NotificationRejectedError`-class failures
  (`notification_rejected` and specific codes like `recipient_invalid`,
  `message_too_long`) → **permanent, never retried**;
  `provider_unavailable` and `provider_error` → **retryable** with
  bounded exponential backoff; unexpected worker exceptions are isolated
  per job (one job can never crash another or the worker).
- **Retry policy** (`NOTIFICATION_MAX_ATTEMPTS` = 5,
  `NOTIFICATION_RETRY_BASE_DELAY_SECONDS` = 5,
  `NOTIFICATION_RETRY_MAX_DELAY_SECONDS` = 300): attempt 1 runs
  immediately; retry *n* waits `base · 2^(n-2)` seconds (5, 10, 20, 40…)
  capped at the max delay; after the attempt budget is spent the job
  fails permanently — **no infinite retries**. A provider rate-limit
  hint (`retry_after`, parsed from the provider layer's fixed diagnostic
  text) extends the wait up to the cap — a hostile hint cannot stall the
  queue unbounded.
- **Delivery semantics: at-least-once.** A worker shutdown mid-job
  returns the job to the queue and it may run again — exactly-once is
  **not** claimed and not yet needed (notifications are informational,
  not financial). Idempotency keys / a delivery-history table are
  deliberately deferred.
- **Local development:** `docker compose up -d redis` (Redis 8, host
  port 6390, no persistence — queue-only). The worker runs as
  `python -m app.worker` or `arq app.worker.worker.WorkerSettings` in a
  separate process, reading the same `.env`.
- **Security:** the Redis endpoint comes only from settings — never from
  notification data; queued payloads are strictly generic (no tokens —
  tokens live only in the worker process's provider instances); worker
  log/failure text carries channels, categories, and stable error codes,
  never tokens, full provider URLs, or raw responses.

Tests: `tests/test_worker_jobs.py` (job contract, serialization
strictness, configuration validation, enqueue behavior including the
unreachable-Redis controlled failure),
`tests/test_worker_retry.py` (backoff math, retry-after handling,
classification of every failure class),
`tests/test_worker_integration.py` (the full pipeline — real service,
real arq Worker, real factory dispatcher, real provider wire code —
against fakeredis and `httpx2.MockTransport`; success, retry-then-
succeed, rejected-first-attempt, attempt exhaustion, multi-job
isolation, and queue-content security checks). No test touches real
Redis or a real provider.

### 6.4 Standing rules from 00-PROJECT-CONTEXT.md §6

- Telegram/Bale adapters live **on the backend behind this boundary** —
  not as extra services the frontend must know about, and not as logic
  embedded in the frontend (the frontend was not touched by Phase 5.6).
- **No real credentials in source**: tokens come from the environment
  only; `.env.example` carries placeholders; the test suite runs with
  clearly-fake constants against mocked transport.

## 7. Architectural Decisions Still TBD

| # | Deferred Decision | Why deferred |
|---|---|---|
| T1 | Internal module list and boundaries of the modular monolith | Depends on unresolved domain TBDs (A1–A12 in 00-PROJECT-CONTEXT.md §7) |
| T2 | Authentication & session mechanism | Domain TBD A13 |
| T3 | OpenAPI → TypeScript type generation for the frontend | Useful but optional; decide when the API stabilizes |
| T4 | Formal API versioning scheme | Single consumer in MVP; revisit if external consumers (Telegram/Bale adapters) appear |
| T5 | ~~Structured error response format~~ **[RESOLVED — MVP]**: FastAPI-native `{"detail": ...}` body plus a status-code mapping (422 validation/domain-content, 404 unknown path, 405 method, 500 unexpected; 404-resource/409 reserved) — defined and locked in [06-BACKEND-API.md](06-BACKEND-API.md) §4b. Revisit only if a real consumer requirement appears (e.g. Telegram/Bale adapters). | Needed before API design; belongs to the API design document |
| T6 | Real-time updates (SSE/WebSocket) for calendar/task status | Not MVP; depends on clarified exception/notification requirements (A7) |
| T7 | Staging environment (yes/no) | Operational decision; revisit near deployment |
| T8 | Migration tooling (e.g., Alembic vs other) | Needed before first schema; tooling choice not yet made |
| T9 | Deployment topology & hosting (where FastAPI, Next.js, and PostgreSQL run) | Not yet decided |
| T10 | Use of Next.js server-side features (SSR modes, API routes) beyond standard rendering | UI architecture decision; belongs to frontend design |
| T11 | Backups, read replicas, and DB operational hardening | Operational; single-branch scale doesn't force an early answer |
| T12 | ~~Background jobs/scheduler mechanism (needed for reminders/escalations if A7/A10 require them)~~ **[PARTIALLY RESOLVED — MVP]**: background *notification delivery* is implemented (Phase 5.7, §6.5: Redis + ARQ worker with bounded retries). Reminders/escalations scheduling remains TBD with the domain rules (A7/A10). | Domain rules for reminders are still TBD |

---

## 8. Out of Scope for This Document

- Database schemas and models.
- API endpoints and request/response shapes.
- Internal module design of the monolith.
- UI structure, screens, or design system.
- Any Telegram/Bale integration design.
- Any code.

These belong to later documents, after the domain TBDs in
[00-PROJECT-CONTEXT.md](00-PROJECT-CONTEXT.md) §7 are resolved.

---

## 9. Logging (implemented — Task 5.8)

Task 5.8 established the backend's logging foundation: **stdlib `logging`
only** — no logging framework, no JSON dependency, no observability stack
(metrics/tracing/Sentry/ELK are explicitly out of scope).

### 9.1 Central configuration — `apps/api/app/core/logging.py`

The ONE place logging is configured. Every other module only calls
`logging.getLogger(...)` (convention: `app.*` namespaces via
`get_logger`); `basicConfig`/`addHandler`/`dictConfig` appear nowhere
else (pinned by a structural test).

- **Idempotent**: one `StreamHandler` on the root logger, marked so a
  second `configure_logging()` call never duplicates handlers (it may
  adjust the level — tests do).
- **One format**, identical everywhere:
  `<ISO-8601 UTC timestamp> <LEVEL> <logger name> pid=<pid> <message>`.
  The timestamp is explicit UTC with milliseconds and offset — machine-
  parsable, non-locale-dependent. `pid` distinguishes the API process
  from the background worker process in interleaved output.
- **`LOG_LEVEL`** (`Settings.log_level`, `.env.example`): standard levels
  only, case-insensitive; anything else is a clean startup
  `ValidationError` — never a silent fallback to a different level.
- **Call sites**: `app/main.py` (at import — after uvicorn's own config,
  so our handler wins) and `app/worker/__main__.py` (only the `arq` CLI
  configures logging itself; `python -m app.worker` would otherwise run
  on stdlib defaults).

### 9.2 Who logs what — no duplicates

| Concern | Logger | Notes |
|---|---|---|
| HTTP requests | `app.api.request` | one line per request: method, path, status, duration_ms, request_id. uvicorn's access log is silenced by the central config so requests are logged exactly once. |
| Unhandled 5xx | `uvicorn.error` | Starlette's `ServerErrorMiddleware` re-raises; the server logs the single stack trace. We deliberately register NO app-level exception handler for 500s — that would log the traceback twice. The `{"detail": ...}` API error contract is unchanged. |
| Auth/authz failures | `app.api.security` | WARNING on every authentication failure (reason + request_id, username on login failures, user_id on permission denials) and INFO on successful logins. |
| Notification queue | `arq.worker` | arq's own lifecycle lines propagate to the root handler unchanged. |
| Notification delivery | `app.worker.delivery` / `app.worker.service` | see §9.4 |
| Everything else | `app.*` per module | via `get_logger` |

Expected domain outcomes (401/403/422, rejected notifications) log at
INFO/WARNING — never ERROR. ERROR is reserved for genuine failures:
exhausted retries, Redis outages, corrupt job payloads.

### 9.3 Request correlation id

`RequestLoggingMiddleware` (pure ASGI, `app/api/middleware.py`) accepts
an incoming `X-Request-ID` **only** if ≤64 chars and matching
`[A-Za-z0-9_.-]` — a hostile oversized/header-injecting value is replaced
by a fresh `uuid4` hex. The id is exposed on `request.state.request_id`
(for the security log lines), printed on the request line, and echoed
back in the `X-Request-ID` response header so clients can quote it.

### 9.4 What is never logged

Locked by tests (`tests/test_logging_*.py`) and by construction:

- **Credentials & secrets**: passwords (attempted or real), password
  hashes, JWT/Bearer token values, the Authorization header, bot tokens,
  Redis/DB URLs with embedded credentials, cookies, API keys.
- **Notification content** (by default): message text, recipient
  addresses, raw provider HTTP responses, provider URLs with tokens.
  Worker lines carry channel, category, `job_id`, attempt counts,
  external message id, duration — enough to diagnose, nothing personal.
- **Request bodies, headers, or query strings** — the request line is
  method, path, status, duration, request_id, nothing else.

The `Authorization`-failure log lines record the *reason* and a minimal
user reference (username on login, `user_id` on token/permission
failures) — the API responses stay generic; the log is the only place
the reason is recorded.

### 9.5 `print()` policy

`print()` remains ONLY in the three interactive CLI scripts whose
console output IS their user interface: `app/assign_role.py`,
`app/create_user.py`, `app/db/check.py`. There are no `print()` calls on
any production path (API, worker, services) — pinned by a structural
test.

### 9.6 Explicitly out of scope (Task 5.8)

Metrics, tracing, OpenTelemetry, Sentry, Prometheus, ELK/Loki/Grafana,
dashboards, alerting, an audit database, and any frontend logging UI.
Task 5.8 is logging only; structured logging/observability decisions are
deferred (T13+ TBDs stay open).

---

## 10. Observability — Health Checks & Metrics (implemented — Task 5.9)

Task 5.9 adds the *foundation* only: health endpoints and
Prometheus-compatible metrics, via the plain `prometheus-client`
library (no framework integration package, no monitoring stack — see
§10.9). Everything here is deliberately boring and bounded.

### 10.1 Health endpoints (`apps/api/app/api/health.py`)

All public (no authentication) — probes must work independently of
auth:

| Endpoint | Meaning | Checks dependencies? | Failure mode |
|---|---|---|---|
| `GET /api/health` | liveness (the pre-5.9 contract, unchanged — the frontend health client depends on it) | never | `{"status": "ok"}` while the process serves |
| `GET /api/health/live` | liveness, explicit name | never | same |
| `GET /api/health/ready` | readiness: can we serve correctly? | PostgreSQL + Redis (bounded timeouts: 3s / 2s) | `503` `{"status": "not_ready", "checks": {...}}` |

- **Liveness never touches dependencies.** A liveness probe that fails
  because Redis is down gets a healthy process killed by a restart loop.
- **Readiness gates on database + Redis only.** The database check is
  one `SELECT 1` on the *existing* engine (`app.db.session.get_engine`
  — no second connection system); the Redis check is one `PING` on a
  short-lived client created per check from the same `redis_url`
  setting as Task 5.7 (no global client at import time). Both run under
  hard timeouts, so a wedged dependency cannot hang readiness.
- **The notification providers (Telegram/Bale) are NOT readiness
  dependencies** — an external messenger outage must not make the API
  unready.
- Failure responses carry **only fixed words** (`ok` /
  `unavailable` / `not_ready` / `no_recent_heartbeat`) — never URLs,
  credentials, or exception text. Failures are logged (logger
  `app.api.health`) with the exception **class name only**.

### 10.2 Worker heartbeat (honesty about the worker)

The `worker` field in `/api/health/ready` is **informational, never
gating** (the worker is optional infrastructure — no business trigger
depends on it yet). It distinguishes "Redis reachable" from "a worker
process is actually alive" using **arq's own health-key mechanism**:
the running worker refreshes `<queue>:health` in Redis every 30s with a
31s TTL (`WorkerSettings.health_check_interval`), and readiness reports
`ok` only when that key exists — a missing key is reported honestly as
`no_recent_heartbeat`, never as a false "ok" merely because Redis
answered.

Documented limitations (no registry/lease/database involved — the
heartbeat proves *a* worker is alive, not *which* one, how many, or
that it is not stuck mid-job; a worker stalled between heartbeats still
looks alive for up to ~31s).

### 10.3 Metrics (`apps/api/app/core/metrics.py`)

`prometheus-client` counters/histograms/gauges on the process-local
default registry:

| Metric | Labels | Where recorded |
|---|---|---|
| `http_requests_total` | method, route, status_class | request middleware |
| `http_request_duration_seconds` (histogram) | method, route | request middleware |
| `http_requests_in_progress` (gauge) | method | request middleware |
| `worker_jobs_total` | function, outcome | worker job paths |
| `notification_delivery_total` | channel, outcome | worker job paths |
| `notification_delivery_duration_seconds` (histogram) | channel | worker job paths |

- The **API process** exposes `GET /metrics` (Prometheus convention:
  bare path at the server root). It is **unauthenticated by design** —
  meant for infrastructure scraping on an internal network. Protect it
  at the infrastructure level (bind to an internal interface /
  reverse-proxy ACL).
- The **worker process** serves no HTTP; `WORKER_METRICS_PORT`
  (default `0` = disabled) makes its startup hook expose the same
  registry on `GET :<port>/metrics` via the library's built-in server.
- Timing uses the monotonic clock (`time.perf_counter`). No DB or
  Redis call is made per request for metrics purposes.
- **No** database-query metrics, **no** Redis command instrumentation,
  **no** SQL tracing (§10.9).

### 10.4 Cardinality rules — labels are bounded by construction

Only these label dimensions exist, ever: `method`, `route` (the route
**template**), `status_class` (`2xx`–`5xx`), `function` (arq job
function name — one constant today), `outcome` (a fixed vocabulary:
completed/retried/failed, success/rejected/retryable/failed),
`channel` (validated against the known set; anything else collapses to
the literal `unknown`).

- `route` comes from `scope["route"]` (set by FastAPI routing) — the
  template `/api/persons/{person_id}`, **never the raw path**;
  unmatched requests collapse to the literal `unmatched`. Label
  cardinality is bounded by the static route table.
- **NEVER labels**: user IDs, person/event IDs, notification text,
  recipient addresses, JWTs/tokens, query strings, or exception text.
  Pinned by tests (`tests/test_observability.py`).
- Health and metrics paths themselves are **not metered**
  (`/metrics`, `/api/health`, `/api/health/live`, `/api/health/ready`)
  — scraping and probing must not inflate the request counters.

### 10.5 Error policy: observability must never take the app down

Every metric helper (`observe_*` in `app/core/metrics.py`) swallows
its own instrumentation errors (debug-level log with the exception,
never a raise). A broken metric can cost a data point; it can never
cost a request or a job.

### 10.6 Local verification

- Tests: `apps/api/tests/test_observability.py` (28 tests — liveness,
  readiness gates, honest worker heartbeat, failure-response hygiene,
  metric names, route-template labels, cardinality, secret-leakage
  probes, worker/notification metric paths).
- Runtime smoke against the real local PostgreSQL + Redis:
  `apps/api/smoke_observability_59.py` (26 checks — includes readiness
  with Redis deliberately down, worker metrics scrape, log-format
  consistency with §9).

### 10.7 Deployment notes

- Scrape `/metrics` from your infrastructure (Prometheus server or any
  compatible scraper) on an internal network; the endpoint is not
  authenticated.
- The worker's metrics exist **per worker process**; if you run several
  workers, give each its own `WORKER_METRICS_PORT`.
- The readiness gate is `database + redis`; wire your orchestrator's
  readiness probe to `/api/health/ready` and liveness probe to
  `/api/health/live` (or the legacy `/api/health`).

### 10.8 Configuration

One setting (`apps/api/.env.example`): `WORKER_METRICS_PORT` (0–65535,
default 0). No feature flags for health/metrics — they are always on.

### 10.9 Explicitly out of scope (Task 5.9)

OpenTelemetry, Sentry, a Prometheus **server**, Grafana, Loki, Tempo,
alerting, distributed tracing, an audit database, notification delivery
history, DB-query/Redis-command metrics, and any frontend observability
UI. What exists is the exposition foundation those would build on.

## 11. Configuration & Secrets (implemented — Task 5.10)

Task 5.10 hardens `app/core/config.py` (the single `Settings` surface —
no scattered `os.environ` reads) around one principle: **the application
must fail closed rather than silently run with a dangerous
configuration.** All runtime configuration flows through
`pydantic-settings` `Settings` with a typed, validated model; every
setting whose value is (or may embed) a credential is a
`pydantic.SecretStr`.

### 11.1 APP_ENV

- `APP_ENV` selects the environment: `development` | `test` |
  `production` (case-insensitive; default `development`).
- **Never inferred** — not from `DEBUG`, not from the hostname, not
  from anything else. A typo'd value (`prod`, `staging`, an empty
  string) is a validation error at startup, never a guess.
- Development/test keep every documented convenience below; production
  adds the requirements in §11.2 and fails to start otherwise.

### 11.2 Required in production (fail-closed at startup)

The API refuses to start (`ConfigurationError` raised from Settings
construction — before the server serves anything) in `production` when
any of the following holds:

| Requirement | Rejected condition |
|---|---|
| `AUTH_SECRET_KEY` real | is the development placeholder, or shorter than 32 characters |
| `AUTH_ALLOW_INSECURE_DEV_SECRET=0` | the flag is enabled (whatever the secret is) |
| `DATABASE_URL` set | unset (`None`) |
| `REDIS_URL` set **explicitly** | relying on the localhost default (an explicitly-set localhost Redis is a legitimate same-host deployment) |
| `CORS_ALLOW_ORIGINS` explicit | any entry is `*` |

Outside production, the local-development conveniences still work:
the placeholder secret (with the flag on), omitted `DATABASE_URL`
(health endpoints still serve), the default Redis URL, and a wildcard
CORS origin (`allow_credentials` is always False — bearer auth, no
cookies — so a dev wildcard is not credential-exposing).

There are deliberately **no other debug/insecure flags** in the
codebase: no `DEBUG` toggle, no flag to weaken auth, no option to
disable validation. OpenAPI stays enabled in production (see §11.8).

### 11.3 Setting categories

- **Non-secret runtime config** — `APP_ENV`, `API_HOST`, `API_PORT`,
  `AUTH_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `LOG_LEVEL`,
  `CORS_ALLOW_ORIGINS`, `NOTIFICATION_TIMEOUT_SECONDS`,
  `NOTIFICATION_MAX_ATTEMPTS`, retry delays, `WORKER_METRICS_PORT`.
- **Secrets (SecretStr)** — `AUTH_SECRET_KEY` (JWT signing key),
  `TELEGRAM_BOT_TOKEN`, `BALE_BOT_TOKEN`.
- **URLs that may embed credentials (SecretStr)** — `DATABASE_URL`,
  `REDIS_URL` (both can carry `user:password@`).
- **Infrastructure (docker-compose, root `.env`)** — `POSTGRES_*`
  variables; `extra="ignore"` means they never crash Settings even
  though the application does not use them.

All three notification-ish providers remain **optional in every
environment, including production**: the core application never
requires Telegram or Bale credentials. Telegram may be configured
without Bale and vice versa; an unconfigured provider reports a
provider-unavailable failure only when a send is attempted (unchanged
from Task 5.6).

### 11.4 Secret handling policy

- Secret values live as `SecretStr`: `repr()`/`str()` of Settings show
  `**********`, and `model_dump()` masks them.
- Consumers unwrap with `get_secret_value()` at the **single point of
  use** (`app/services/auth.py`, the notification factory,
  `app/db/session.py`, `app/api/health.py`, the worker, Alembic's
  `env.py`) — never into a module global, never into a log line.
- **Configuration errors never echo the offending value.** Policy
  validators raise `ConfigurationError` (a `RuntimeError`, NOT a
  `ValueError`): pydantic renders `ValueError`-style validator
  failures with an `input_value=...` suffix that can contain the raw
  credential, while a non-ValueError propagates verbatim with only
  our clean message. `hide_input_in_errors=True` covers pydantic's own
  type-validation errors the same way. Every error message names the
  setting and the requirement — never the value.
- `DATABASE_URL`/`REDIS_URL` are validated by **shape only**
  (SQLAlchemy `make_url` / scheme check) — no connection is made
  during Settings construction. Configuration validation ≠ connectivity
  validation; connectivity is readiness' concern (§10.1).
- The JWT secret is explicitly configured, never auto-generated, never
  rotated by the application, and never logged, never in validation
  errors, never in `/metrics`, never in health responses.

### 11.5 CORS

Comma-separated origins (`cors_origins_list`); every entry must be an
`http(s)` URL or `*`. Production must not use `*` (§11.2). Safe
development defaults: `http://localhost:3000,http://127.0.0.1:3000`.
An empty value disables the CORS middleware entirely (no origins are
then allowed, since the frontend calls the API directly from the
browser — see §4).

### 11.6 `.env` rules

- `apps/api/.env.example` is the documented template — safe values
  only, no token-like fakes; committed.
- `apps/api/.env` (and the root `.env`) are **not tracked**; real
  credentials never enter the repository.
- Tests construct Settings with `_env_file=None` so a developer's real
  `.env` can never influence the suite.
- Production-only validation never breaks the test suite: tests run
  under `APP_ENV` development/test defaults, and the production rules
  have their own dedicated test matrix
  (`tests/test_config_hardening.py`).

### 11.7 Production secret injection (deployment-time)

There is **no secret manager and deliberately so** (§11.8): production
secrets should be injected as environment variables by the deployment
platform (systemd `EnvironmentFile=`, Docker/Kubernetes secrets
mounted as env, the platform's equivalent). Where to put what:

- `AUTH_SECRET_KEY` — generate with `secrets.token_urlsafe(48)` once,
  inject as an env var, ≥32 characters.
- `DATABASE_URL` / `REDIS_URL` — full connection URLs (with
  credentials) as env vars.
- `TELEGRAM_BOT_TOKEN` / `BALE_BOT_TOKEN` — only if those channels are
  actually used; both optional.
- Nothing secret is ever stored in the application database (no
  database-stored secrets, no encrypted-blob store).

### 11.8 Explicitly out of scope (Task 5.10)

Vault, AWS Secrets Manager, Doppler, or any other secret manager;
secret rotation; CI secrets; an auth redesign or JWT migration; audit
logging; observability changes; disabling OpenAPI in production (the
schema is public API documentation — protecting it is an
infrastructure-level decision, out of scope here).
