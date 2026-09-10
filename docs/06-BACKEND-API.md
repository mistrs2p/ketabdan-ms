# 06 — Backend API Layer (FastAPI)

**Project:** Ketabdaneh
**Document status:** Implementation artifact — read endpoints (roles, persons, events incl. single-event reads, event assignments incl. single-assignment reads), three write endpoints (person, event, and event-assignment creation), the MVP error policy (§4b) established, the EventAssignment approval contract **defined but not implemented** (§4e), the authentication foundation (§4f — login/me), and application authorization / RBAC (§4g — all business routes permission-protected, 401 vs 403 semantics, seeded roles/permissions matrix); the API surface is intentionally minimal and grows task by task. **Phase 3 — CLOSED / FROZEN 2026-09-09 (§8).**
**Last reviewed:** 2026-09-10
**Depends on:** [01-ARCHITECTURE.md](01-ARCHITECTURE.md) (communication boundary), [04-BACKEND-PERSISTENCE.md](04-BACKEND-PERSISTENCE.md) (session foundation), [05-DATABASE-MIGRATIONS.md](05-DATABASE-MIGRATIONS.md) (seed data)

---

## 1. Purpose

Document the backend HTTP layer and the **pattern every future endpoint
follows**. This layer is deliberately thin: per docs/01 §3.2, the backend owns
the domain, but business logic lives in domain code — routers translate HTTP,
they do not decide rules.

The established pattern:

```
HTTP route (app/api/<resource>.py)
        ↓
API schema (app/schemas/<resource>.py)   — the HTTP/JSON contract
        ↓
service / domain logic  — only when a route is more than a trivial query
        ↓
SQLAlchemy persistence (app/models, via the get_db session dependency)
        ↓
response model (same API schema) → JSON
```

## 2. Structure

```
apps/api/app/
├── api/
│   ├── __init__.py
│   ├── auth.py         # auth router: login, me, get_current_user (§4f)
│   ├── deps.py         # require_permission factory — route protection (§4g)
│   ├── event_assignments.py  # event-assignments router (POST create)
│   ├── events.py       # events router (GET list/single, POST create)
│   ├── persons.py      # persons router
│   └── roles.py        # one router module per resource
├── core/
│   ├── config.py       # Settings (pydantic-settings; auth vars §4f,
│   │                   #   CORS_ALLOW_ORIGINS §4h)
│   └── security.py     # all cryptography: Argon2id + JWT (§4f)
├── assign_role.py      # operator CLI: python -m app.assign_role (§4g)
├── create_user.py      # bootstrap CLI: python -m app.create_user (§4f, §4g)
├── schemas/
│   ├── __init__.py
│   ├── auth.py         # LoginRequest, TokenResponse, UserRead (§4f)
│   ├── event_assignment.py  # EventAssignmentCreate (request),
│   │                        #   EventAssignmentRead (response, §4d)
│   ├── event.py        # EventCreate (request), EventRead (response)
│   ├── person.py       # PersonCreate (request), PersonRead (reuses RoleRead)
│   └── role.py         # RoleRead — request/response models for roles
├── services/
│   ├── __init__.py
│   ├── auth.py         # authenticate / issue / verify tokens, create_user (§4f)
│   ├── authz.py        # permission resolution + role assignment (§4g)
│   ├── event_assignments.py  # create_event_assignment — reference
│   │                          #   resolution (§4d)
│   ├── events.py       # create_event — always-DRAFT invariant (§4c)
│   └── persons.py      # create_person — first service (HTTP-free domain logic)
└── main.py             # FastAPI app: CORS middleware (§4h) + include_router()
                       #   + /api/health
```

## 3. Conventions

1. **All business routes live under `/api`** (matching `/api/health`).
   A router declares `APIRouter(prefix="/api", tags=["<resource>"])` and is
   included from `app/main.py`.
2. **Schemas are the only HTTP contract.** Pydantic models in
   `app/schemas/` shape input and output; ORM models never leak through.
   Read models use `ConfigDict(from_attributes=True)` so ORM rows serialize
   directly, and expose only confirmed business fields — audit columns
   (`created_at`/`updated_at`) are not returned unless a requirement asks
   for them.
3. **Every database route takes `Session = Depends(get_db)`** (docs/04 §4).
   The session is closed by the dependency, including on error.
4. **Service layer only when justified.** `GET /api/roles` is a single
   ordered query — the router issues it directly. The moment an endpoint
   carries real logic (validation beyond types, multi-step changes,
   cross-module coordination), that logic moves into a service/domain
   function the router calls; `app/services/persons.py` (`create_person`)
   is the first instance. Wrapping every trivial query "for symmetry"
   is over-engineering, not architecture. Services are HTTP-free: they
   raise domain-meaningful exceptions, and the router translates those
   into HTTP responses.
5. **Deterministic ordering** on list endpoints (roles by `code`, persons by
   `name` then `id`, events by `planned_at` then `id` — the calendar read —
   a person's nested roles by `code`) — stable responses
   make testing and diffing reliable.
6. **No business rules are invented here.** If a route needs a rule that is
   TBD (docs/00 §7), the route waits; the API follows the domain decisions,
   never the other way around.
7. **Eager-load collection relations on list endpoints** (e.g.
   `selectinload` for a person's roles) so serialization does not issue one
   query per row. A schema may normalize output order (e.g. `PersonRead`
   sorts roles by `code`) — presentation detail, not a business rule.

## 4. Endpoints

| Method | Path | Purpose | Permission (§4g) | Notes |
| --- | --- | --- | --- | --- |
| GET | `/api/health` | Liveness check | — public | No database involved; works without `DATABASE_URL` |
| GET | `/api/roles` | List the permanent organizational roles (reference data, seeded by migration `0002`) | `roles:read` | Read-only; ordered by `code`; returns `[{id, code, name}]` |
| GET | `/api/persons` | List branch members with their permanent roles (D-001) | `people:read` | Read-only; ordered by `name`, then `id`; returns `[{id, name, phone, active, roles: [{id, code, name}]}]` |
| POST | `/api/persons` | Create a branch member, optionally with roles (§4a) | `people:create` | First write endpoint; `201 Created` with the `PersonRead` shape; person + memberships written atomically |
| GET | `/api/events` | List events — the calendar-oriented read | `events:read` | Ordered by `planned_at`, then `id`; returns `EventRead` items `{id, title, type, planned_at, status}`; `planned_at` is a timezone-aware instant |
| GET | `/api/events/{event_id}` | Return one event by id | `events:read` | `EventRead`; unknown-but-valid UUID → `404 {"detail": "Event not found"}` (§4b rule 4); malformed UUID → FastAPI's default 422 |
| POST | `/api/events` | Create an event, always in `DRAFT` (§4c) | `events:create` | `201 Created` with the `EventRead` shape `{id, title, type, planned_at, status}`; timezone-aware `planned_at` required |
| GET | `/api/event-assignments` | List assignments — the stable baseline read | `assignments:read` | Ordered by `id`; returns `EventAssignmentRead` items (responsibility embedded, event/person referenced by id); no pagination/filter/search (deliberately) |
| GET | `/api/event-assignments/{assignment_id}` | Return one assignment by id | `assignments:read` | `EventAssignmentRead`; unknown-but-valid UUID → `404 {"detail": "Event assignment not found"}` (§4b rule 4); malformed UUID → FastAPI's default 422 |
| POST | `/api/event-assignments` | Create an assignment (§4d) | `assignments:create` | `201 Created` with the `EventAssignmentRead` shape `{id, event_id, person_id, responsibility: {id, code, name, active}, approval_status}` — always `PENDING`; unknown event/person UUID → 404, unknown responsibility code → 422 |
| POST | `/api/auth/login` | Verify credentials, issue an access token (§4f) | — public | `200 {access_token, token_type: "bearer", expires_in}`; any failure → generic `401` (no user enumeration) |
| GET | `/api/auth/me` | The authenticated identity (§4f) | — authenticated only | Requires `Authorization: Bearer <token>`; returns `{id, username, active}` (never `password_hash`); any token failure → generic `401`; no permission required (§4g) |

Every business route above (roles, persons, events, event-assignments) is
**permission-protected** since Task 5.2 (§4g): no token → `401`, valid token
without the required permission → `403`. `/api/health` and
`POST /api/auth/login` stay public; `GET /api/auth/me` requires
authentication but no permission.

Roles are **read-only by design**: the six rows are migration-owned reference
data (docs/05 §5a). No create/update/delete endpoints exist for them —
changing the confirmed role set is a schema-level (migration) decision, not a
runtime operation.

Persons support listing (confirmed visibility need) and creation (§4a,
implemented). `PersonRead` surfaces `active` and `phone` exactly as stored,
without interpreting them — name structure is TBD-D1, phone uniqueness
TBD-D2, inactive semantics TBD-D3. Other person operations (update,
deactivate, delete) and the events/assignments APIs arrive with their own
tasks and must not invent answers to those open questions. Events support
listing (calendar-oriented read), single-event reads by id, and creation
(§4c, implemented — always `DRAFT`); filters and status transitions arrive
with their own tasks.

## 4a. Person Creation Contract (implemented)

### Request

| Field | Required | Type | Notes |
| --- | --- | --- | --- |
| `name` | yes | string | Confirmed concept; single free-text field (docs/03 §5.1). Structure, normalization, and maximum length are **TBD-D1** — no rules invented until resolved. |
| `phone` | no | string or null | Optional (nullable). Duplicate phone numbers are currently allowed; uniqueness is **TBD-D2**. No format/normalization rules are defined yet. |
| `active` | no | boolean | Defaults to `true` at creation (docs/03 §5.1). The contract carries the flag as stored; the meaning of inactive is **TBD-D3** and is not interpreted here. |
| `roles` | no | list of role **codes** | e.g. `["supporter", "learner"]`. Multiple entries allowed (**D-001**). Zero entries permitted — whether the business *requires* at least one role is **TBD-D24**. |

**API design choice (technical, not a domain rule):** role input identifies
roles by `code` — the documented *stable machine key* of the seeded
reference data (docs/03 §5.2, migration `0002`) — not by UUID. Responses
continue to return both `id` and `code`, exactly as `GET /api/persons` does
today.

### Response

`201 Created` with the created person in the `PersonRead` shape already
served by `GET /api/persons`: `{id, name, phone, active, roles}`.

### Transactional expectation

If roles are supplied, the person row and its `person_roles` memberships are
written in the **same transaction**: the request either creates the person
with all of its roles, or creates nothing (docs/01 §3.2 — consistency and
transactional integrity). This is a technical guarantee, not a business rule.

### Validation boundaries

Guaranteed by the approved schema (docs/03 §5.1/§5.3):

- `name` must be present (`NOT NULL`) → FastAPI returns its standard 422
  validation response when it is missing.
- `phone`, when present, is free text — no format constraint exists.
- every supplied role code must reference an existing seeded role
  (FK `person_roles.role_id` → `roles.id`, `ON DELETE RESTRICT`).

Implementation choices made for this endpoint (technical/API details, not
domain rules; the status code and body shape are now fixed by the general
error policy, §4b):

- An unknown role code → **422** with the unknown code(s) named in
  `detail` (§4b: request content that violates domain reference data
  shares the validation status family).
- Duplicate role codes within the input list are **collapsed** — a person
  holds a *set* of roles (D-001), so `["supporter", "supporter"]` creates
  one membership.
- `active: false` in the request is carried as given — creation directly
  as inactive is technically permitted; what inactive *means* stays
  **TBD-D3**.

Explicitly unresolved (business/domain questions — no runtime behavior may
hard-code an answer):

- Name emptiness/whitespace/length rules (**TBD-D1**).
- Phone format, normalization, and duplicate handling (**TBD-D2**).
- Whether the business *requires* at least one role at creation
  (**TBD-D24**).

The transport of these failures — status codes and body shape — is no
longer open: it follows the general error policy (§4b).

## 4b. Error Policy (MVP)

This section defines how the API reports failures. It **resolves TBD T5**
(docs/01 §7) for the MVP: the structured error response format is
FastAPI's native shape, not a custom envelope. The policy was established
by observing the actual runtime behavior first (§4b.1) — the framework
defaults already give a consistent, OpenAPI-documented contract, and
overriding them would add code for no current benefit.

### 4b.1 Observed behavior (runtime evidence, 2026-09-09)

No global exception handlers or middleware exist — every response below is
FastAPI/starlette default behavior plus the one router-level translation
in `POST /api/persons` (§4a):

| Situation | Status | Body |
| --- | --- | --- |
| Missing/invalid request field, wrong type, malformed JSON | `422` | `{"detail": [ {type, loc, msg, input, ...} ]}` — Pydantic's structured error list |
| Domain error: request content violates domain reference data (unknown role code) | `422` | `{"detail": "Unknown role code(s): ghost"}` — human-readable string |
| Unknown path | `404` | `{"detail": "Not Found"}` |
| HTTP method not supported by the path | `405` | `{"detail": "Method Not Allowed"}` |
| Unexpected exception in a route/dependency | `500` | `Internal Server Error` — **plain text**, starlette's default (not JSON) |
| Success | `200`/`201` | the resource, JSON |

### 4b.2 Rules

1. **No custom error envelope.** Every JSON error body is
   `{"detail": ...}` — FastAPI's native shape, single consumer, and
   already documented by OpenAPI (`/docs`). A wrapper format
   (`{"error": {"code": ...}}`, RFC 9457 `application/problem+json`, …)
   is deliberately **not** introduced for theoretical consistency.
2. **Request validation errors keep the framework default.** Routers do
   not catch or reformat Pydantic validation failures; `detail` remains
   the structured list (§4b.1). Clients read `detail[*].loc`/`msg`.
3. **Domain errors are translated at the router.** Services raise
   domain-meaningful exceptions (e.g. `UnknownRoleError`,
   `app/services/persons.py`) and stay HTTP-free; the router catches the
   specific exception and raises `HTTPException` with the mapped status
   and a human-readable `detail` string. Request content that passes type
   validation but violates domain reference data → **422** — the same
   status family as validation, because the payload (not the server
   state) is at fault.
4. **Status codes are policy, not per-endpoint improvisation.** Current
   mapping: unknown path 404, not-found *resource* 404 (`GET
   /api/events/{event_id}` → `{"detail": "Event not found"}`), method
   405, validation/domain-content 422, unexpected 500. **Reserved for
   future endpoints** (no endpoint exercises them yet; add rows here when
   the first such endpoint lands): state conflicts (e.g. an illegal event
   status transition, D-002 / TBD-D7) → `409`.
5. **No global handler for unexpected exceptions (deliberate).** The
   starlette default 500 (plain text) is accepted for the MVP; no stack
   traces or details leak to the client. Data safety does not depend on
   it: the `get_db` dependency closes the session on error, so an
   uncommitted transaction rolls back — no partial writes (docs/04 §4).
   If the frontend later needs a JSON 500 body, add one
   `@app.exception_handler(Exception)` returning
   `{"detail": "Internal server error"}` — a small, contained change.
6. **This policy fixes transport, not user-facing wording.** Which
   message a user sees (and in which language, TBD-A14) is a presentation
   concern of the frontend; the backend's `detail` strings are for
   developers/API consumers and are not a UI copy source.

## 4c. Event Creation Contract (implemented)

`POST /api/events` is implemented per this contract (same approach as
Person creation, §4a: contract first, then implementation). "Create Event"
is the first step of the approved MVP workflow (docs/02 §8), so the
creation need itself is confirmed. Nothing here adds a business rule
beyond what docs/02, docs/03, and D-002 already establish; wherever a rule
is not supported by project evidence it is listed as open (docs/02 §7
TBD-D25…D28), not guessed.

### Request

| Field | Required | Type | Notes |
| --- | --- | --- | --- |
| `title` | yes | string | Confirmed concept; single free-text field (docs/03 §5.4, `NOT NULL`). Emptiness/whitespace/length rules are **TBD-D25** — none may be invented. |
| `type` | yes | string | Required by the schema (`text NOT NULL`) and stored as free text (docs/03 §6.2 — no CHECK, no reference table, no enum). The known examples (introduction, film analysis, book analysis, gathering, group games, class) are **examples only**; the taxonomy is **TBD-D5** and must not be hard-coded. What the endpoint accepts before D5 resolves is **TBD-D26**. |
| `planned_at` | yes | ISO 8601 datetime **with timezone offset** | `timestamptz` business instant (docs/03 §4) — always timezone-aware, never a bare date. JSON representation is an RFC 3339 string (technical choice, e.g. `"2026-09-19T17:00:00+03:30"`). Past values: **TBD-D27**. Recurrence is not part of creation (**TBD-D6**). |
| `status` | no | — | **Not part of the request.** The schema default is `DRAFT` (docs/03 §5.4) and the endpoint never passes a status — creation always produces `DRAFT`. Like any other unknown field, a `status` value in the request is **ignored** (the `PersonCreate` precedent), so a client cannot create directly as `SCHEDULED`/`COMPLETED`/…. Whether creation may ever start in another status is **TBD-D28**, tied to the transition matrix (**TBD-D7**) and its authorization (**TBD-D23**). |

**Explicitly not in the request:** `id` (server-generated, docs/03 §3),
`created_at`/`updated_at` (system-set audit, docs/03 §4), `assignments`
(an EventAssignment is its own entity with open semantics — approval
**TBD-D10/A6**, exclusivity **TBD-D11**, role restrictions **TBD-D8** —
and `event_responsibilities` is now seeded per **D-004**, migration
`0003`; assignments get their own future endpoint(s), §4d), and any
report field (a report is a post-event record, **D-003**).

### Response

`201 Created` with the created event in the events read shape — exactly
the five business fields, audit columns not exposed (§3 rule 2):
`{id, title, type, planned_at, status}`. `EventRead`
(`app/schemas/event.py`) is that shape, defined with the creation
endpoint and reused by `GET /api/events` — read and write cannot diverge.

### Transactional expectation

Event creation writes exactly **one row** in `events` (no related rows by
design — see above). If the endpoint ever grows related writes, they
follow the §4a atomicity rule: all-or-nothing in one transaction.

### Validation boundaries

Guaranteed by the approved schema (docs/03 §5.4) and enforced by
`EventCreate`:

- `title` and `type` must be present (`NOT NULL`).
- `planned_at` must be a timezone-aware instant (`timestamptz`) — a naive
  datetime or bare date is rejected with 422 rather than silently
  interpreted as local time (docs/03 §4).
- `status` is constrained to the D-002 set by CHECK — but creation does
  not accept a status input (see request table).

Transport of failures follows the error policy (§4b): malformed/missing
fields and naive datetimes → FastAPI's default 422. No domain rejection
exists yet — if a future rule from D26/D27 adds one, it is a 422 with a
human-readable `detail`, translated at the router.

Explicitly unresolved (business questions — docs/02 §7; no runtime
behavior may hard-code an answer):

- Title emptiness/whitespace/length rules (**TBD-D25**).
- Type acceptance before the taxonomy resolves (**TBD-D26**, tied to
  **TBD-D5**).
- Past `planned_at` at creation (**TBD-D27**).
- Whether the initial status may be chosen by the caller (**TBD-D28**,
  tied to **TBD-D7/D23**).

## 4d. EventAssignment Creation Contract (implemented)

`POST /api/event-assignments` and its list/single reads
(`GET /api/event-assignments`, `GET /api/event-assignments/{assignment_id}`)
are implemented per this contract (same approach as Person and Event
creation, §4a/§4c: contract first — defined
in a documentation-only task and already reviewed — then implementation).
It defines exactly what the endpoint accepts and returns, using
only facts already established by docs/02, docs/03, and the implemented
schema; nothing here adds a business rule, and every
open question is listed, not guessed.

"Assign Person" is the second step of the approved MVP workflow
(docs/02 §8), so the creation need itself is confirmed.

### Domain shape (what an EventAssignment *is*)

```text
Event + Person + EventResponsibility = EventAssignment
```

- A **specific Person** takes on a **specific EventResponsibility** for a
  **specific Event** (docs/02 §2.3). The row itself *is* the assignment;
  approval is an attribute of it, never a prerequisite for existence
  (docs/03 §5.6).
- Event responsibilities are **not** permanent organizational roles
  (learner/supporter/coach/teacher/referrer/manager) — different concept,
  different table. Whether permanent roles *restrict* which responsibilities
  a person may take is **TBD-D8** and is not checked.

### Already established vs. still TBD

**Established** (encoded in the approved schema / migration `0001`, and in
the two implemented creation contracts):

- All three references (`event_id`, `person_id`, `responsibility_id`) are
  `NOT NULL` FKs — an assignment without all three cannot exist
  (docs/03 §5.6).
- `approval_status` exists as a **PROVISIONAL** attribute with values
  `PENDING`/`APPROVED`, defaulting to `PENDING` at creation (docs/03 §5.6,
  docs/05 §5). The provisional values are a placeholder for TBD-D10/A6 —
  *which* states are real is open, but that creation starts not-approved
  follows directly from the default.
- No `UNIQUE` constraint exists on the triple — duplicates are
  **schema-permitted**; exclusivity is **TBD-D11**.
- No constraint ties assignments to `persons.active` (**TBD-D3**) or to
  any role (**TBD-D8**).
- Reference-data lookups by stable machine `code` are the established
  input pattern (`POST /api/persons` roles, §4a); `event_responsibilities`
  has the same `code`/`name` reference-data shape as `roles` (docs/03 §5.5)
  and — since **D-004** (migration `0003`) — is seeded with its initial
  six-row set, so codes resolve exactly like role codes do.
- Failure transport is fixed by the error policy (§4b): malformed/missing
  fields → FastAPI default 422; unknown-but-valid UUID references
  (not-found *resources*) → **404** with a human-readable `detail`;
  domain-content violations → **422**.

**Resolved (formerly blocking):**

| # | Question |
| --- | --- |
| ~~**TBD-D9**~~ | ~~The responsibility taxonomy. `event_responsibilities` is deliberately **unseeded** (docs/05 §5a) — no responsibility rows exist to reference, so no valid `responsibility` value can be resolved yet.~~ **[RESOLVED — D-004, 2026-09-09]**: the six documented responsibilities are seeded (migration `0003`, docs/05 §5b), so a `responsibility` code now resolves against real reference data. Whether responsibilities may also be created at runtime stays open (TBD-D9, narrowed) — non-blocking for this endpoint. |

**Still TBD — non-blocking (contract shape unaffected; the future
implementation must carry each as an explicit open check or absence):**

| # | Question | Effect on the contract |
| --- | --- | --- |
| **TBD-D10 / TBD-A6 / TBD-S13** | Real approval states, approval scope, approver identity | `approval_status` values are provisional; creation semantics ("starts PENDING") may change with the real approval workflow |
| **TBD-D11** | Exclusivity: one person per responsibility per event? | No uniqueness is enforced; the endpoint's duplicate behavior is deliberately unspecified until resolved |
| **TBD-D3** | May an inactive person be assigned? | No check encoded; the contract neither rejects nor promises to accept inactive persons |
| **TBD-D8** | Role-based restrictions on responsibilities | No check encoded |
| **TBD-D29** (new) | Event-status precondition: from which event statuses (D-002 set) may assignments be created (e.g., may persons be assigned to a `COMPLETED` or `CANCELLED` event)? No evidence either way; tied to the transition matrix **TBD-D7** | The contract accepts any existing event until resolved; the future endpoint must not hard-code an answer |
| **TBD-D30** (new) | May an assignment reference an **inactive** `event_responsibilities` row (`active=false`, retire mechanism per **TBD-S2**)? | Unspecified until resolved |

*(TBD-D29/D30 are registered in docs/02 §7 by this task.)*

### Request

| Field | Required | Type | Notes |
| --- | --- | --- | --- |
| `event_id` | yes | UUID | The event being staffed. Must reference an existing `events` row (FK, docs/03 §5.6). Status-precondition rules are **TBD-D29** — not checked. |
| `person_id` | yes | UUID | The person taking the responsibility. Must reference an existing `persons` row (FK). Active/inactive is **TBD-D3** — surfaced, not interpreted. Role restrictions are **TBD-D8** — not checked. |
| `responsibility` | yes | string (responsibility **code**) | The stable machine key of an `event_responsibilities` row (docs/03 §5.5, seeded per **D-004**, migration `0003`), following the §4a role-by-code precedent. An unknown code → **422** (domain reference data, §4b rule 3). Whether inactive rows are accepted is **TBD-D30**. |

**Explicitly not in the request:**

- `id` — server-generated UUID (docs/03 §3).
- `approval_status` — **not settable by the caller.** Like `status` on
  event creation (§4c), creation always produces the default (`PENDING`,
  PROVISIONAL — TBD-D10/A6); a supplied value is ignored like any other
  unknown field. Approval, when designed, is its own future
  operation/endpoint (TBD-S13) — creation is existence, not approval
  (docs/03 §5.6).
- `created_at`/`updated_at` — system-set audit (docs/03 §4).
- Any approver identity (`approved_by`/…) — not modeled, TBD-S13.

### Response

`201 Created` with the created assignment in the `EventAssignmentRead`
shape (`app/schemas/event_assignment.py`):

```json
{
  "id": "…uuid…",
  "event_id": "…uuid…",
  "person_id": "…uuid…",
  "responsibility": {"id": "…uuid…", "code": "registration", "name": "Registration", "active": true},
  "approval_status": "PENDING"
}
```

- The three references are echoed as given (UUIDs as strings).
- `responsibility` is returned as the full reference-data object
  (`{id, code, name, active}` — the `EventResponsibility` counterpart of
  `RoleRead`), not a bare code, so read and write shapes stay symmetric
  with the persons pattern (`PersonRead.roles`).
- `approval_status` is always `"PENDING"` in the creation response
  (PROVISIONAL default — TBD-D10).
- Audit timestamps are not exposed (§3 rule 2).
- `event`/`person` are **not** embedded — they are identified by id; their
  full representations are served by their own endpoints. Nesting the
  event (with its assignments) would recurse.

### Reads (implemented)

- **`GET /api/event-assignments`** — the list read: a plain JSON array of
  `EventAssignmentRead` items (empty table → `[]`, never `{items: []}`),
  ordered by `id` (deterministic ordering per §3 rule 5; no business sort
  — by event, person, responsibility, or approval status — is documented
  anywhere, so none is invented). No pagination, filtering, search, or
  date-range parameters exist (deliberately; docs/01 §4 TBD T4).
- **`GET /api/event-assignments/{assignment_id}`** — the single read by
  UUID path parameter; unknown-but-valid UUID →
  `404 {"detail": "Event assignment not found"}` (§4b rule 4), malformed
  UUID → FastAPI's default 422.
- Both reuse `EventAssignmentRead` exactly — no competing read schema —
  and eagerly load only the `responsibility` relation (the one embedded
  in the read shape, §3 rule 7); `event` and `person` are not eagerly
  loaded because they are not embedded.

### Transactional expectation

Creation writes exactly **one row** in `event_assignments` (no related
rows exist to write). If the endpoint ever grows related writes, they
follow the §4a atomicity rule: all-or-nothing in one transaction.

### Validation boundaries

Guaranteed by the approved schema (docs/03 §5.6) and enforced by the
request contract:

- all three fields must be present and well-typed → FastAPI default 422
  on missing/malformed input (including non-UUID `event_id`/`person_id`).
- an unknown-but-valid-UUID `event_id`/`person_id` (no such row) → **404**
  `{"detail": "Event not found"}` / `{"detail": "Person not found"}` —
  §4b rule 4: not-found *resources* (this activates the reserved
  resource-404 row for these references).
- an unknown `responsibility` code → **422** with the unknown code named
  in `detail` (§4b rule 3 — domain reference data, same shape as
  `POST /api/persons`).
- duplicates of the same triple → **no constraint exists** (TBD-D11);
  the endpoint currently **creates a second row** — the schema-permitted
  behavior, locked by test as current behavior, explicitly not a business
  rule: when D11 resolves, endpoint and test change together.

Explicitly unresolved (business questions — no runtime behavior may
hard-code an answer): ~~D9 (blocking)~~ (**resolved by D-004** — seed
migration `0003`; runtime creation of responsibilities stays open,
narrowed), D29, D30, D11, D3, D8, D10/A6/S13 —
see the TBD table above. The approval semantics (D10/A6/S13 and the
lifecycle questions they opened) now have a defined contract in §4e —
still entirely unimplemented.

## 4e. EventAssignment Approval Contract (defined — **not implemented**)

**Status: contract only.** No endpoint below exists. Nothing in this section
is implemented, and no runtime behavior changes because of it: the
implemented surface remains exactly §4d (list, single, create). The
`approval_status` column is carried by the reads, never transitioned.
The domain-side lifecycle contract lives in
[02-DOMAIN-MODEL.md](02-DOMAIN-MODEL.md) §2.3 ("EventAssignment Approval
Lifecycle"); this section defines what the *API layer* will need to decide
when the business decisions land.

### What exists today (evidence, not design)

- The schema carries `approval_status` (`text NOT NULL DEFAULT 'PENDING'`,
  `CHECK (approval_status IN ('PENDING','APPROVED'))` — docs/03 §5.6,
  **provisional**, deliberately widenable by a plain migration once the
  real states are decided; not a DB enum for exactly that reason).
- Creation always produces `PENDING` (the column default —
  `EventAssignmentCreate` deliberately has no `approval_status` field; a
  supplied value is ignored like any unknown field, locked by test).
- Reads return every row regardless of `approval_status` — the column is
  reported, never interpreted. (Whether `PENDING` assignments should be
  visible/inert in the calendar is **TBD-D32**.)
- No transition of any kind — PENDING→APPROVED included — is implemented
  or decided anywhere. **PENDING→APPROVED must not be assumed to be the
  final workflow.**

### Existence vs. approval (prerequisite answer)

The assignment row *is* the assignment; approval is an *attribute*
(docs/03 §5.6, §2.3 lifecycle). Consequences for the future API: approval
cannot be modeled as creation-with-approval, an approval prerequisite,
or a separate "request" resource awaiting approval. Whatever the endpoint
model, it operates on an **already-existing** assignment row.

### Open questions the future endpoint must wait on

| Question | TBD | Why no answer exists |
| --- | --- | --- |
| Real state set (`PENDING`/`APPROVED` sufficient? `REJECTED`/`REVOKED`/…) | TBD-D10 | values are schema placeholders, not decisions |
| Scope: every assignment approved, or only some? | TBD-A6 | discovery records the need, never the scope |
| Workflow authority: manager only? another role? | TBD-D31 | discovery names only the manager's *need* — not an authority decision |
| Technical authorization: which authenticated caller? | TBD-A13/A11 | no auth exists yet — separate from the workflow question |
| Transitions incl. reversal (`APPROVED→PENDING`) and post-approval rejection (`APPROVED→REJECTED`) | TBD-D10 | nothing is decided; the schema encodes no transition rules |
| `PENDING` visibility/use semantics (reads, calendar, operational activity) | TBD-D32 | current reads return all rows — carried behavior, not a rule |
| Audit fields (`approved_by`/`approved_at`/`rejected_by`/`rejected_at`/reason) | TBD-S13 | none are modeled (docs/03 §9); if required → **future schema work** (a migration + read-shape decision), not added now |

### Endpoint model — deliberately undecided

Three candidate shapes appear in general API practice: a field-partial
update (`PATCH /api/event-assignments/{id}` with `{"approval_status": …}`),
an action sub-resource (`POST /api/event-assignments/{id}/approve` and
possibly `…/reject`, `…/revoke`), or a state-machine endpoint carrying a
transition plus reason. **No repository evidence supports any one of
them** — no existing endpoint updates anything (all writes are creates;
the §4d pattern gives no precedent to extend), and the choice depends on
unresolved business facts (one state field vs. per-action audit, D10 vs.
D31 vs. S13). Choosing now would be an invented rule; the choice is part
of the future implementation task, decided together with D10/D31/S13 and
the error policy rows it will need (e.g. transition-not-allowed is likely
a new §4b row, status code TBD — 409 is reserved and unused).

The only **shape facts** that any future endpoint inherits for free:

- the target is an existing assignment id (UUID path parameter; unknown →
  `404 {"detail": "Event assignment not found"}`, §4b rule 4 — same
  message as the single read);
- the response is an `EventAssignmentRead` (the established read shape,
  re-used, not a competing schema) — extended only if/when audit fields
  are added to the read by their own contract;
- unknown extra body fields are ignored (Pydantic default, the §4c/§4d
  precedent).

Everything else — method, path, request body, semantics of the response
status code, side effects — is decided by the future task together with
the TBDs above.

## 4f. Authentication Foundation (implemented — Phase 5, Task 5.1)

**Status: authentication only — *who a caller is*.** Login, token
verification, `GET /api/auth/me`. Task 5.2 (§4g) built authorization on
top of this foundation without changing any of its primitives: hashing,
token issuance/verification, the login/me endpoints, and the generic-401
semantics below are exactly as shipped in 5.1.

### Identity model — decisions

- **`users` table (migration `0004`), separate from `persons`.** A User
  is *who is logged in*; a Person is a business entity (a branch
  member). No foreign key between them — linking a user to a person is
  future work with its own TBDs, and forcing it now would invent a
  rule. Columns: `id` (UUID PK), `username` (unique), `password_hash`
  (Argon2id), `active` (bool, default true), `created_at`/`updated_at`
  (existing TimestampMixin conventions).
- **Login identifier: username, not email.** No email exists anywhere
  in the domain model (docs/03 §5.1), the app is internal and
  manager-operated, and there is no mail flow — email would be an
  invented requirement. Usernames are stored and compared in one
  canonical form (trimmed + casefolded, applied at creation *and*
  lookup in `app/services/auth.py`).
- **No public registration.** This is an internal application; the only
  user-creation path is the bootstrap CLI below. There is no signup
  endpoint, and none is planned.
- **Password policy (minimal):** non-empty and ≥ 8 characters, enforced
  at creation only (login treats the password as an opaque secret).
  No complexity rules — the app is internal; inventing enterprise
  policy is out of scope.

### Hashing and tokens

- **Passwords:** Argon2id via `argon2-cffi` with the library's curated
  defaults (`app/core/security.py`). No custom crypto, no SHA/MD5, no
  reversible storage. Verification is the library's constant-time
  `verify`; a parameter change on old hashes triggers a transparent
  rehash on the next successful login.
- **Access tokens:** JWT HS256 via `pyjwt`. The decode path pins the
  algorithm list (a token's `alg` header can never select another
  algorithm) and requires `exp` + `sub`. The token carries `sub` (user
  id), `typ: "access"` (future refresh tokens will be rejected by
  today's code), `iat`, `exp`. There is no refresh token and no logout
  endpoint — MVP scope; tokens simply expire.
- **Configuration (env, see `apps/api/.env.example`):**
  `AUTH_SECRET_KEY`, `AUTH_ALGORITHM` (default `HS256`),
  `ACCESS_TOKEN_EXPIRE_MINUTES` (default `60`), and
  `AUTH_ALLOW_INSECURE_DEV_SECRET`. The secret's placeholder default is
  intentionally unsafe and allowed only for local development; with
  `AUTH_ALLOW_INSECURE_DEV_SECRET=0`, login and token verification
  refuse to run on the placeholder — production can never silently
  sign tokens with a publicly known secret.

### Endpoints

| Method | Route | Purpose | Notes |
| --- | --- | --- | --- |
| POST | `/api/auth/login` | Verify credentials, issue an access token | Body `{"username", "password"}`; `200` below; any failure → generic `401` |
| GET | `/api/auth/me` | The authenticated identity | Requires `Authorization: Bearer <token>`; `200` below; any failure → generic `401` |

`POST /api/auth/login` success:

```json
{"access_token": "<jwt>", "token_type": "bearer", "expires_in": 3600}
```

`expires_in` is seconds (OAuth2-style field name). `GET /api/auth/me`
success: `{"id", "username", "active"}` — the public projection of a
User; `password_hash` is never in any response.

**Request header format** for authenticated calls (all protected business
routes since Task 5.2, §4g):

```
Authorization: Bearer <access_token>
```

### Error semantics — one generic 401, always

Every authentication failure is `401` with the same body — no caller
can distinguish unknown user, wrong password, inactive account, missing
token, malformed token, wrong signature, or expired token:

- login failures: `{"detail": "Invalid username or password"}`
- token failures: `{"detail": "Not authenticated"}`, plus
  `WWW-Authenticate: Bearer`

This is deliberate user-enumeration protection (unknown-user and
wrong-password responses are byte-identical; the unknown-user path also
performs a dummy Argon2 verification so timing does not leak account
existence). Authorization denials are never 401 — they are 403, defined
in §4g. No auth failure produces a 500 or leaks
internal exception details; the password policy and duplicate-username
errors exist only in the bootstrap path, not in any HTTP response.

### Bootstrap: creating the first user

There is no default account and no well-known password anywhere in the
codebase. A developer/admin creates the first (or any) user
interactively:

```bash
cd apps/api
python -m app.create_user <username>     # prompts for the password twice
```

Since Task 5.2 the same CLI accepts `--role <code>` to grant an
application role at creation (§4g) — without it the user is created
unprivileged.

The password is read via `getpass` — never a command-line argument,
never written to logs or output (only the username and id are echoed).
Re-running with an existing username fails cleanly and never resets the
account. The service behind it (`app/services/auth.py: create_user`)
enforces the password policy and rejects duplicate canonical usernames
atomically.

### Where the code lives

| File | Role |
| --- | --- |
| `app/core/security.py` | Hashing + JWT primitives (all crypto in one module) |
| `app/services/auth.py` | HTTP-free domain logic: authenticate, issue/verify tokens, create_user |
| `app/api/auth.py` | Router + `get_current_user` dependency (reused by §4g) |
| `app/schemas/auth.py` | `LoginRequest`, `TokenResponse`, `UserRead` (no hash) |
| `app/models/user.py` | `User` ORM model |
| `app/create_user.py` | Bootstrap CLI (with `--role`, §4g) |
| `alembic/versions/0004_create_users_table.py` | Migration |

## 4g. Authorization & Permissions — RBAC (implemented — Phase 5, Task 5.2)

**Status: authorization — *what a caller may do*.** Every business route
requires a permission; the check is a composable FastAPI dependency;
roles, permissions, and their mapping are database rows seeded by
migration `0005`. No policy engine, no per-route ad-hoc logic.

### Authentication vs. authorization

| Question | Layer | Failure status | Detail |
| --- | --- | --- | --- |
| Who is calling? | Authentication (§4f) | `401` | `"Not authenticated"` (token paths) / `"Invalid username or password"` (login) |
| May they do this? | Authorization (this section) | `403` | `"Not authorized"` |

An authorization failure is **never** 401: a valid, active,
authenticated user who lacks the required permission gets 403. A request
with no/invalid/expired token or an inactive user gets 401 before any
permission is consulted — the two never mix. The 403 detail is a single
generic message that never names the missing permission, mirroring the
§4f anti-enumeration discipline.

### Four role concepts — keep them apart

| Concept | Table | Meaning | Phase |
| --- | --- | --- | --- |
| **User** | `users` | A login identity (who can authenticate, §4f) | 5.1 |
| **Person** | `persons` | A business entity — a branch member | 3 (frozen) |
| **ApplicationRole** | `application_roles` | An *authorization* role held by a User (admin/manager/operator) | 5.2 |
| **DomainRole** | `roles` | A *business* role of a Person (learner/supporter/coach/teacher/referrer/manager, D-001) | 3 (frozen) |

The Phase 3 domain roles on `persons`/`roles` (0002 seeds) are **not**
authorization roles and were not touched: a Person being a domain
"manager" grants no permission, and an application "manager" role says
nothing about any Person. There is deliberately **no User↔Person foreign
key** — linking a login to a branch member is future work with its own
TBDs, and the permission system never consults `persons`. The name
collision between the domain role `manager` and the application role
`manager` is unfortunate but the concepts live in different tables and
different layers.

### Model (migration `0005`)

```
users ──< user_application_roles >── application_roles ──< application_role_permissions >── permissions
```

- `application_roles` — code (unique), name (unique): admin, manager,
  operator.
- `permissions` — code (unique), name (unique): exactly one row per
  capability the API offers (below).
- `user_application_roles` — composite PK `(user_id, application_role_id)`;
  user FK CASCADE (deleting a user drops their grants), role FK RESTRICT.
- `application_role_permissions` — composite PK `(application_role_id,
  permission_id)`; role FK CASCADE, permission FK RESTRICT.
- Both joins follow the `person_roles` pattern: immutable rows
  (`created_at` only), subject-side CASCADE, target-side RESTRICT,
  explicit index on the non-leading FK column.

A User ↔ ApplicationRole is many-to-many (a user may hold several
roles); effective permissions are the **union** across all held roles.

### Permission codes — exactly the current API, nothing speculative

Stable machine codes, one per capability the API actually offers today
(constants in `app/services/authz.py`, rows seeded by `0005`):

`roles:read`, `people:read`, `people:create`, `events:read`,
`events:create`, `assignments:read`, `assignments:create`.

No update/delete codes exist because those endpoints do not exist; no
future permission is pre-created. Route modules reference the constants
(`authz.EVENTS_READ`, …) — permission strings never appear as scattered
literals in business code.

### The seeded matrix (and why)

| Role | Permissions | Rationale |
| --- | --- | --- |
| admin | all 7 | The privileged bootstrap role; future administrative capabilities land here |
| manager | all 7 | The primary business user — full current surface |
| operator | all except `people:create` (6) | Runs day-to-day operations — the system's purpose is the branch running while the manager is absent (docs/00 §1–2) — but does not manage the member roster |

Admin and manager hold an identical set *today*; they are conceptually
distinct roles, not one role with two names — administrative permissions
that arrive in later tasks attach to admin only. The single deliberate
difference now is operator lacking `people:create`.

Seeds follow the 0002/0003 conventions: hard-coded stable UUIDs,
`ON CONFLICT DO NOTHING` inserts (re-execution cannot duplicate or
clobber), downgrade drops only the tables 0005 created (`users` is
untouched), audit timestamps left to database defaults.

### Route protection — one dependency, applied per route

`app/api/deps.py` provides the single factory:

```python
require_permission(permission)   # → FastAPI dependency
```

Routes declare it in the decorator, handlers stay untouched:

```python
@router.get("/events", dependencies=[Depends(require_permission(authz.EVENTS_READ))])
```

Semantics inside the dependency: `get_current_user` (§4f) runs first —
past it, the caller is authenticated and active; then the permission is
resolved **server-side from the database** (`authz.user_has_permission`)
— never from the token payload, never from any client-provided value, so
revoking a role takes effect on the very next request. Public
(`GET /api/health`, `POST /api/auth/login`) and authenticated-only
(`GET /api/auth/me`) routes declare no permission dependency.

### Bootstrap and role assignment (CLI only — no HTTP endpoint)

There is **no default account, no well-known password, and no silent
admin**. Users and grants are created by operators on the server:

```bash
cd apps/api
# Create a user and grant a role in one step (role validated before the
# password prompt; password via getpass, never an argument):
python -m app.create_user <username> --role admin
# Grant a role to an existing user / list roles and holders:
python -m app.assign_role <username> <role_code>
python -m app.assign_role --list
```

`assign_role` is explicit: unknown user/role fail loudly (exit 1);
re-granting an already-held role is a friendly no-op (exit 0), never a
duplicate row. `create_user` without `--role` creates an unprivileged
user (zero permissions — can log in and call `/me`, nothing else);
granting a role is always a separate, visible operator action. The
service layer behind both (`app/services/authz.py:
assign_application_role`) is the only grant path.

### Extending (no code changes needed for new grants)

Adding a user's role, a role's permissions, or a whole new role is data
— insert rows (a migration for reference data, the CLI for grants).
Adding a *new capability* (new endpoint) is the one case that touches
code: define the constant in `authz`, seed its row, and attach the
dependency — the model itself never changes.

### Where the code lives

| File | Role |
| --- | --- |
| `app/services/authz.py` | Permission constants; union resolution; role assignment (HTTP-free) |
| `app/api/deps.py` | `require_permission` factory — the only protection mechanism |
| `app/models/application_role.py`, `permission.py`, `user_application_role.py`, `application_role_permission.py` | ORM models |
| `app/assign_role.py`, `app/create_user.py` | Operator/bootstrap CLIs |
| `alembic/versions/0005_add_application_authorization_tables.py` | Tables + seed matrix |

## 4h. Frontend Authentication Integration (implemented — Phase 5, Task 5.3)

**Status: the web app now consumes §4f/§4g as a browser client.** The
backend contract is unchanged — §4f's endpoints and §4g's protection are
exactly as shipped. What 5.3 added is the client side
(`apps/web/lib/auth/`) plus one server-side enabler: CORS.

### What the frontend does

| Concern | Decision |
| --- | --- |
| Login page | `/fa/login` and `/en/login` (default locale fa; full RTL/LTR + theming like every other page). Client-side validation is *required-fields only*; everything else stays backend-owned. |
| Token storage | `localStorage` (`ketabdaneh.auth.access_token`) — an **MVP client-token strategy, not XSS-safe storage**. `lib/auth/storage.ts` documents this explicitly: a future httpOnly-cookie/BFF approach may provide stronger protection. The password is never persisted anywhere. |
| Bearer injection | Centralized in `lib/api/client.ts` — one place attaches `Authorization: Bearer <token>` when a token is stored. No per-component headers; no token means no header (never a malformed `Bearer null`). |
| Session state | `AuthProvider` (`lib/auth/context.tsx`) exposes `{user, isAuthenticated, isLoading, login, logout, refreshUser}`. Restoration is exactly-once per mount: on load, a stored token triggers **one** `GET /api/auth/me` — a token alone never renders authenticated UI without that validation. Network failure during restore keeps the token (a refresh retries); a 401 clears it. |
| 401 handling | A token-carrying request rejected 401 → the client clears the stored token and the provider flips to unauthenticated. A tokenless 401 (the login attempt itself) clears nothing. No retry loops. |
| Logout semantics | Client-side session termination only — the stored token is removed and the session state reset. **The backend has no token-revocation endpoint; none was invented.** Until one exists, a logged-out token remains technically valid server-side until expiry (60 min). |
| Error display | The §4f anti-enumeration rule is preserved client-side: one generic localized message for 401 (fa: «نام کاربری یا رمز عبور نادرست است.», en: "Invalid username or password."), a separate network-failure message, and no raw backend detail is ever shown. |
| Authorization | **None in the frontend.** The client models only `{id, username, active}` from `/me`. No roles, no permissions, no inference — the server stays the source of truth (§4g). |

### CORS (the one backend change)

Until 5.3 every browser page called the API from *server* code (SSG/SSR
fetches), which is same-machine and CORS-exempt. Client-side auth made
the browser itself a cross-origin caller (dev: frontend `:3000`, API
`:8000`), so the API now runs `CORSMiddleware` with an explicit
allow-list: `CORS_ALLOW_ORIGINS` (comma-separated; defaults to the two
web dev origins; empty disables the middleware). `allow_credentials` is
False — authentication is a Bearer header, not cookies, so no
wildcard-credential combination exists.

### What is deliberately *not* in 5.3

- No token refresh mechanism (the token simply expires; the user
  re-logs).

Protected routes, auth-aware navigation, and redirect logic were Task
5.4 scope and are implemented — see §4i.

### Where the code lives

| File | Role |
| --- | --- |
| `apps/web/lib/auth/{types,storage,api,context}.ts(x)`, `index.ts` | Contract types, token storage, login/me/logout calls, session provider |
| `apps/web/lib/api/client.ts` | Central Bearer injection + 401 token-clear/listener mechanism |
| `apps/web/app/[locale]/login/page.tsx`, `apps/web/components/auth/LoginForm.tsx` | The login page and its client form |
| `apps/web/tests/auth-{storage,api,provider}.test.*`, `tests/login-form.test.tsx` | Unit/component tests (vitest + testing-library) |
| `app/main.py`, `app/core/config.py` | CORS middleware + `CORS_ALLOW_ORIGINS` setting |


## 4i. Protected Routes & Auth-Aware Navigation (implemented — Phase 5, Task 5.4)

**Status: the web app now has a client-side authentication boundary
around its application pages.** The backend contract is again unchanged
— no endpoint was added, modified, or removed. What 5.4 added lives
entirely in `apps/web`.

### Protection strategy and its (documented) limitation

The token is in `localStorage` (§4h), which **server code cannot read**
— Next.js middleware would have no access to it, so it cannot make a
real authentication decision. Pretending otherwise (e.g. an
unauthenticated-looking middleware guess) would be security theater.
The chosen architecture is therefore a **client-side guard at the
route-group boundary**, with a structural no-flash guarantee:

- The `(app)` route group (dashboard, calendar, events list/new/detail,
  people list/new/detail, tasks — both locales) is wrapped once in its
  layout by `AuthGate`. The `login` page sits *outside* that group and
  stays public. Protection is structural (route-group membership), not
  a hard-coded URL list, and no page duplicates the check.
- On the very first render — including the server render (SSR/SSG) —
  the gate is in its `isLoading` state and renders only a `role=status`
  loading indicator. **Protected content is never part of the server
  HTML**, so there is no unauthenticated flash before the redirect.

**Limitation:** this is an *authentication boundary in the browser*,
not a server-side access control. A determined user can inspect client
bundle code; nothing in the served HTML is secret (business data still
requires a valid Bearer token from the API). A server-side gate would
require moving the token to an httpOnly cookie behind a BFF —
deliberately out of scope for the MVP (§4h's storage decision).

### Route classification

| Class | Routes | Behavior |
| --- | --- | --- |
| Public | `/fa/login`, `/en/login` | Fully rendered without a session. An *already-authenticated* visitor is redirected to the locale-aware dashboard. |
| Protected | every `(app)` route: dashboard, calendar, events (list/new/`[eventId]`), people (list/new/`[personId]`), tasks — in both locales | Unauthenticated → redirect to the locale-aware login with `returnTo`. Loading → localized "restoring session" indicator, no content. Authenticated → the normal app shell. |

### Redirect rules

| Situation | Redirect |
| --- | --- |
| Unauthenticated visiting a protected route | `router.replace` to `/{locale}/login?returnTo={currentPath}` — locale preserved (fa→fa, en→en). `replace` (not `push`) keeps the protected URL out of the history stack. |
| Mid-session 401 (expired/invalidated token) | The §4h client clears the token, the provider flips to unauthenticated, and the same gate redirects to the locale-aware login. No loops, no repeated `/me` calls, no raw 401 detail shown. |
| Login success with `returnTo` | Back to the validated original route (see below). |
| Login success without `returnTo` | The locale-aware dashboard. |
| Authenticated user visiting `/login` | The locale-aware dashboard (only after session restoration settles — never during `isLoading`). |
| Logout | Token cleared + session reset (§4h semantics), then `replace` to the locale-aware login. Back-after-logout lands before the protected page and the gate re-checks — no usable protected page. |

### `returnTo` validation (open-redirect prevention)

`returnTo` is **never** used unvalidated. `sanitizeReturnTo`
(`apps/web/lib/auth/returnTo.ts`) accepts only locale-prefixed internal
paths and rejects everything else — absolute URLs (`https://…`),
protocol-relative URLs (`//evil.example`, `/\evil.example`), any `:` or
`\` anywhere (kills `javascript:`, `data:`, and scheme tricks), paths
without a locale prefix, and any `/login` target including its query
variants (`/login?…`, `/login/…`) as a loop guard. A rejected value
falls back to the dashboard. The login page's post-login navigation
uses only this validated result — there is no raw
`router.push(returnTo)` anywhere.

### Auth-aware navigation (and what it deliberately is *not*)

The header shows the signed-in **username only** (the `/me` contract:
`{id, username, active}`) and a localized logout button — nothing
else. There is **no permission- or role-based UI hiding**: navigation
visibility distinguishes only authenticated vs unauthenticated.
**Frontend route protection is an authentication boundary; backend RBAC
(§4g) is the real permission enforcement** — an authenticated user
without `people:create` still sees the People screens and receives a
403 from the API when acting beyond their permissions. No roles or
permissions are displayed, inferred from the username, or modeled
client-side.

### Where the code lives

| File | Role |
| --- | --- |
| `apps/web/components/auth/AuthGate.tsx` | The (app)-group guard: loading state, unauthenticated redirect (locale-aware, with `returnTo`, exactly-once), authenticated render |
| `apps/web/lib/auth/returnTo.ts` | `sanitizeReturnTo` / `splitLocalePath` — the closed set of safe internal targets |
| `apps/web/components/layout/UserMenu.tsx` | Username display + localized logout (clear + locale-aware redirect) |
| `apps/web/components/auth/LoginForm.tsx` | Post-login navigation (validated `returnTo` or dashboard); authenticated-visitor bounce to dashboard |
| `apps/web/app/[locale]/(app)/layout.tsx` | The single wrap point: `AuthGate` around the existing `AppShell` |
| `apps/web/components/LocaleSwitcher.tsx` | Preserves the query string so `returnTo` survives a locale switch on the login page |
| `apps/web/tests/{return-to,auth-gate}.test.*`, `tests/login-form.test.tsx` | Guard/redirect/locale/returnTo/logout/401 tests |


## 5. Tests

The API test files (`tests/test_api_health.py`, `tests/test_api_roles.py`,
`tests/test_api_persons.py`,
`tests/test_api_events.py`, `tests/test_api_event_assignments.py`,
`tests/test_api_error_policy.py`, `tests/test_api_auth.py`,
`tests/test_api_authz.py`) exercise the
full HTTP stack — routing, dependency injection, response serialization —
with FastAPI's `TestClient`. The error-policy tests lock the status codes
and body shapes documented in §4b; the assignment tests additionally lock
the carried-not-interpreted TBDs (D3, D29, D30, D11) as current behavior,
and the list/single read shape and ordering. The auth tests
(`tests/test_api_auth.py`) lock the §4f contract: hashing properties
(not plaintext, verifies, wrong fails), the login body shape, the
indistinguishable generic 401s (wrong password / unknown user / inactive
/ missing / malformed / wrong-signature / expired / deleted-user token),
the no-hash `/me` projection, token claims, health staying public, and
the bootstrap service rules (duplicate username, password policy).
The authorization tests (`tests/test_api_authz.py`) lock the §4g
contract: the full 401/403 matrix across all nine protected business
routes (no token / malformed / expired / inactive → 401; no-roles and
wrong-permission users → 403 with the generic detail), the seeded
role/permission/matrix shape (loaded from the 0005 migration's own
constants, so tests and database cannot drift), multiple roles per user
with unioned permissions, operator's single deliberate denial
(`people:create`), the role-assignment service rules, and the
public/authenticated-only routes staying as they were.
Since Task 5.2 the business-endpoint tests run through an
admin-authenticated client (`authed_client` fixture in conftest.py);
`tests/test_authz_seed_migration.py` runs the real migration chain
against a disposable PostgreSQL database (the test_seed_migration.py
pattern) to verify upgrade seeds, seed idempotency, and
downgrade/re-upgrade of the authorization tables.
The shared `client` fixture
(conftest.py) overrides `get_db` with the in-memory SQLite session, which
uses `StaticPool` + `check_same_thread=False` because TestClient runs the
app in a worker thread. PostgreSQL behavior is verified by running the
application against the real database (§6) — including the
responsibility-seed migration tests (docs/05 §5b) against disposable
databases.

## 6. Validation (development)

From `apps/api` (venv active, PostgreSQL running):

```bash
python -m pytest                 # all tests, including API tests (SQLite)
python -m app.db.check           # real database connectivity
python -m app.create_user <name> --role admin   # bootstrap a user + grant (§4f, §4g)
python -m app.assign_role --list                # roles and holders (§4g)
uvicorn app.main:app --port 8000 # then: GET /api/health (public),
                                 #       GET /api/roles without a token → 401,
                                 #       POST /api/auth/login → token (§4f),
                                 #       then with Authorization: Bearer <token>:
                                 #       GET /api/roles, POST /api/persons,
                                 #       GET /api/persons, POST /api/events,
                                 #       GET /api/events, GET /api/events/{event_id},
                                 #       POST /api/event-assignments,
                                 #       GET /api/event-assignments,
                                 #       GET /api/event-assignments/{assignment_id},
                                 #       GET /api/auth/me (§4f); a token for a
                                 #       user without the required permission → 403;
                                 #       OPTIONS preflight from the web origin
                                 #       (Origin: http://localhost:3000) → 2xx (§4h)
```

## 7. Out of Scope (unchanged TBDs)

- **Authorization (A13) — implemented (Task 5.2, §4g).** Application
  RBAC protects all business routes with the 401/403 semantics of §4g.
  Still open (A11, deliberately not invented here): the *mapping* of
  which real-world branch positions get which application roles is an
  operational decision for the branch, not a code decision; fine-grained
  per-branch or per-person scoping remains future work.
- Write endpoints: person creation (§4a), event creation (§4c), and
  event-assignment creation plus its list/single reads (§4d) are
  implemented. **Not implemented** (deliberately): assignment
  update/delete, approval/rejection — the approval semantics
  (TBD-D10/A6/S13, plus D31/D32) now have a **defined, unimplemented
  contract** in §4e; the provisional `approval_status` is carried, never
  transitioned —
  assignment filtering (e.g. assignments *of* an event / *of* a person —
  a filtered read pattern for the calendar/event views, arrives with its
  own task), reports (D19/A9), remaining person operations (update,
  deactivate, delete), and event status transitions (D7/D23) — each
  carrying its open TBDs. Roles stay read-only by
  design (§4). There is **no HTTP endpoint** for role assignment or
  user management — the CLIs of §4g are the only grant path (an
  admin-facing API is future work). Pagination conventions remain open
  (docs/01 §4 TBD T4);
  the error format is **defined** (§4b) and the reserved 409 row activates
  with its first endpoint.
- OpenAPI → TypeScript type generation for the frontend (TBD T3).

## 8. Phase 3 — CLOSED / FROZEN (2026-09-09)

**Completion record.** Phase 3 — Backend Foundation — is closed and frozen
as of 2026-09-09. The hardening/gap audit (task 3.21) found the foundation
sound; this record is the final state at freeze.

### Completed backend scope

- **Infrastructure:** FastAPI application, pydantic-settings configuration,
  SQLAlchemy 2.x persistence, session/dependency foundation
  (docs/04), Docker PostgreSQL development database, Alembic setup.
- **Schema:** the seven MVP business tables (persons, roles, person_roles,
  events, event_responsibilities, event_assignments, event_reports) via
  migration chain `0001 → 0002 → 0003`, single head, no drift
  (`alembic check` clean).
- **Reference data:** six roles (learner, supporter, coach, teacher,
  referrer, manager — migration `0002`) and six event responsibilities
  (pre_introduction, welcome_reception, technique_execution, persuasion,
  registration, follow_up — migration `0003`, D-004); stable migration-owned
  UUIDs; no other rows.
- **API surface — exactly these 10 routes** (verified against live
  OpenAPI):

  | # | Route |
  | --- | --- |
  | 1 | `GET /api/health` |
  | 2 | `GET /api/roles` |
  | 3 | `GET /api/persons` |
  | 4 | `POST /api/persons` |
  | 5 | `GET /api/events` |
  | 6 | `GET /api/events/{event_id}` |
  | 7 | `POST /api/events` |
  | 8 | `GET /api/event-assignments` |
  | 9 | `GET /api/event-assignments/{assignment_id}` |
  | 10 | `POST /api/event-assignments` |

  Plus the defined-but-unimplemented EventAssignment approval contract
  (§4e) and the error policy (§4b).

- **Final validation at freeze:** pytest **82 passed**; `alembic current`
  = `0003 (head)`; `alembic check` — no new upgrade operations;
  `python -m app.db.check` — OK; live smoke of all five read families plus
  single-resource 404s and creation atomicity — all per contract; business
  tables empty (reference seed data only).

  *Post-freeze note (Phase 5, 2026-09-10):* the ten routes above are the
  frozen Phase 3 business surface and remain unchanged. Task 5.1 added
  two auth routes outside it — `POST /api/auth/login` and
  `GET /api/auth/me` (§4f) — without modifying any frozen route.
  Task 5.2 then wrapped all nine frozen business routes (every route
  above except `GET /api/health`) in the §4g permission dependency —
  route paths, handlers, and response contracts untouched; only the
  decorator gained `dependencies=[...]`.

### Intentionally NOT in Phase 3 (later phases/tasks)

Authentication/authorization (A13/A11) · assignment approval
implementation (§4e stays unimplemented; D10/A6/S13/D31/D32 open) ·
assignment update/delete · event status transitions (D7/D23) · event
reports (D19/A9) · person update/deactivate/delete · pagination (T4) ·
advanced filters/search · Task / Availability modules · Telegram/Bale
integration · frontend UI (calendar, dashboard) · OpenAPI client
generation (T3) · production deployment.

**All business TBDs (docs/02 §7, docs/00 §7) remain open.** None was
resolved to close this phase; the TBD discipline continues unchanged.

### Freeze statement

From this point, any new backend work — endpoint, schema change,
migration, or behavior change — requires a **new explicitly assigned
task/phase** that follows the documented contract-first workflow and
respects the open-TBD protection. This closeout changes documentation
only: no code, schema, migration, or runtime behavior was modified.
