# 01 — Architecture

**Project:** Ketabdaneh
**Document status:** Living document — update as discovery continues.
**Last reviewed:** 2026-09-08
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
| Secrets management | Production secrets come from the deployment environment, not from files in the repo. Specific provider/mechanism **TBD**. |
| Database per environment | Each environment gets its own PostgreSQL instance/database; no shared databases across environments. |
| Migrations | The backend owns schema changes and applies them in a controlled, repeatable way. Specific migration tooling is **TBD**. |
| Frontend configuration | The Next.js app receives its environment-specific values (e.g., backend base URL) at build/deploy time — not hardcoded. |

## 6. Future Integrations — Telegram / Bale (explicitly NOT in MVP)

Telegram and Bale integrations are **future possibilities only**:

- They are **not** part of the MVP (confirmed in 00-PROJECT-CONTEXT.md §6).
- No code, modules, or detailed integration contracts exist or are designed here.
- Architectural intent only: when/if they arrive, they will be added as
  **adapters on the backend** (a module that translates domain happenings into
  platform messages) — *not* as extra services the frontend must know about, and
  *not* as logic embedded in the frontend.
- The only current obligation toward them is: **don't build anything today that
  blocks them** (e.g., don't assume the UI is the only consumer of the backend's
  domain logic).

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
| T12 | Background jobs/scheduler mechanism (needed for reminders/escalations if A7/A10 require them) | Domain rules for reminders are still TBD |

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
