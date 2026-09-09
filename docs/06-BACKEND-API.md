# 06 — Backend API Layer (FastAPI)

**Project:** Ketabdaneh
**Document status:** Implementation artifact — read endpoints plus the first write endpoint (person creation) established; the API surface is intentionally minimal and grows task by task.
**Last reviewed:** 2026-09-09
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
│   ├── persons.py      # persons router
│   └── roles.py        # one router module per resource
├── schemas/
│   ├── __init__.py
│   ├── person.py       # PersonCreate (request), PersonRead (reuses RoleRead)
│   └── role.py         # RoleRead — request/response models for roles
├── services/
│   ├── __init__.py
│   └── persons.py      # create_person — first service (HTTP-free domain logic)
└── main.py             # FastAPI app: include_router() + /api/health
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
   `name` then `id`, a person's nested roles by `code`) — stable responses
   make testing and diffing reliable.
6. **No business rules are invented here.** If a route needs a rule that is
   TBD (docs/00 §7), the route waits; the API follows the domain decisions,
   never the other way around.
7. **Eager-load collection relations on list endpoints** (e.g.
   `selectinload` for a person's roles) so serialization does not issue one
   query per row. A schema may normalize output order (e.g. `PersonRead`
   sorts roles by `code`) — presentation detail, not a business rule.

## 4. Endpoints

| Method | Path | Purpose | Notes |
| --- | --- | --- | --- |
| GET | `/api/health` | Liveness check | No database involved; works without `DATABASE_URL` |
| GET | `/api/roles` | List the permanent organizational roles (reference data, seeded by migration `0002`) | Read-only; ordered by `code`; returns `[{id, code, name}]` |
| GET | `/api/persons` | List branch members with their permanent roles (D-001) | Read-only; ordered by `name`, then `id`; returns `[{id, name, phone, active, roles: [{id, code, name}]}]` |
| POST | `/api/persons` | Create a branch member, optionally with roles (§4a) | First write endpoint; `201 Created` with the `PersonRead` shape; person + memberships written atomically |

Roles are **read-only by design**: the six rows are migration-owned reference
data (docs/05 §5a). No create/update/delete endpoints exist for them —
changing the confirmed role set is a schema-level (migration) decision, not a
runtime operation.

Persons support listing (confirmed visibility need) and creation (§4a,
implemented). `PersonRead` surfaces `active` and `phone` exactly as stored,
without interpreting them — name structure is TBD-D1, phone uniqueness
TBD-D2, inactive semantics TBD-D3. Other person operations (update,
deactivate, delete) and the events/assignments APIs arrive with their own
tasks and must not invent answers to those open questions.

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
domain rules; revisit if the general error policy decides otherwise):

- An unknown role code → **422** with the unknown code(s) named in
  `detail` (FastAPI's own validation status; the 422-vs-404 question is
  folded into **TBD T5**).
- Duplicate role codes within the input list are **collapsed** — a person
  holds a *set* of roles (D-001), so `["supporter", "supporter"]` creates
  one membership.
- `active: false` in the request is carried as given — creation directly
  as inactive is technically permitted; what inactive *means* stays
  **TBD-D3**.

Explicitly unresolved (decided with the general API error policy,
docs/01 TBD T5; no runtime behavior may hard-code an answer):

- HTTP error body shape for validation failures (currently FastAPI's
  default `{detail: ...}` everywhere).
- Name emptiness/whitespace/length rules (**TBD-D1**).
- Phone format, normalization, and duplicate handling (**TBD-D2**).
- Whether the business *requires* at least one role at creation
  (**TBD-D24**).

## 5. Tests

The API test files (`tests/test_api_roles.py`, `tests/test_api_persons.py`)
exercise the full HTTP stack — routing, dependency injection, response
serialization — with FastAPI's `TestClient`. The shared `client` fixture
(conftest.py) overrides `get_db` with the in-memory SQLite session, which
uses `StaticPool` + `check_same_thread=False` because TestClient runs the
app in a worker thread. PostgreSQL behavior is verified by running the
application against the real database (§6).

## 6. Validation (development)

From `apps/api` (venv active, PostgreSQL running):

```bash
python -m pytest                 # all tests, including API tests (SQLite)
python -m app.db.check           # real database connectivity
uvicorn app.main:app --port 8000 # then: GET /api/health, GET /api/roles,
                                 #       POST /api/persons, GET /api/persons
```

## 7. Out of Scope (unchanged TBDs)

- **Authentication/authorization** — TBD-A13/A11; no route requires identity
  yet. When auth lands, it will be enforced inside this layer (docs/01 §4).
- Write endpoints: person creation is implemented (§4a); events,
  assignments, reports, and remaining person operations (update,
  deactivate, delete) arrive with their own tasks. Roles stay read-only by
  design (§4). Pagination and error-format conventions remain open
  (docs/01 §4 TBDs T4/T5).
- OpenAPI → TypeScript type generation for the frontend (TBD T3).
