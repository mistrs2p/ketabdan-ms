# 04 — Backend Persistence Foundation

**Project:** Ketabdaneh
**Document status:** Implementation artifact — ORM/model and session foundation. No migrations, no business APIs yet.
**Last reviewed:** 2026-09-09
**Depends on:** [03-DATABASE-SCHEMA.md](03-DATABASE-SCHEMA.md) (authoritative design), [02-DOMAIN-MODEL.md](02-DOMAIN-MODEL.md) (approved decisions D-001/D-002/D-003)

---

## 1. Purpose

Document the backend persistence layer implementing the approved MVP schema
(docs/03) as SQLAlchemy 2.x ORM models, plus the database engine/session
foundation that future tasks (Alembic migrations, business APIs) will build on.

```
FastAPI (app/main.py)
   ↓
SQLAlchemy 2.x (app/db, app/models) — synchronous ORM
   ↓
PostgreSQL (psycopg 3 driver)
```

## 2. Structure

```
apps/api/
├── app/
│   ├── core/
│   │   └── config.py            # pydantic-settings: DATABASE_URL etc.
│   ├── db/
│   │   ├── base.py              # declarative Base, naming convention,
│   │   │                        #   uuid_pk() helper, TimestampMixin
│   │   ├── session.py           # lazy engine, session factory, get_db
│   │   └── check.py             # dev-only connectivity check (CLI)
│   ├── models/                  # 7 MVP models (imports register metadata)
│   │   ├── __init__.py
│   │   ├── person.py            # Person (+ roles association proxy)
│   │   ├── role.py              # Role
│   │   ├── person_role.py       # PersonRole (composite PK association)
│   │   ├── event.py             # Event, EventStatus
│   │   ├── event_responsibility.py
│   │   ├── event_assignment.py  # EventAssignment, ApprovalStatus
│   │   └── event_report.py      # EventReport
│   └── main.py                  # FastAPI app (health endpoint unchanged)
└── tests/
    ├── conftest.py              # in-memory SQLite fixtures
    ├── test_models_metadata.py  # metadata matches docs/03
    └── test_persistence.py      # round-trip/constraint/delete-behavior tests
```

## 3. Configuration

`app/core/config.py` uses **pydantic-settings**. The key setting is
`DATABASE_URL` (example in `apps/api/.env.example`):

```text
DATABASE_URL=postgresql+psycopg://ketabdaneh:ketabdaneh_dev@localhost:5433/ketabdaneh
```

- No credentials are hard-coded; `.env` files are git-ignored.
- `database_url` is **optional**: the application starts and serves
  `/api/health` without it. `get_engine()` raises a clear
  `DatabaseNotConfiguredError` only when a database session is actually
  requested.
- The engine is created **lazily** (first use) and cached per process.

## 4. Engine / Session

`app/db/session.py`:

| Component | Role |
| --- | --- |
| `get_engine()` | Cached `create_engine(url, pool_pre_ping=True)` |
| `get_session_factory()` | Cached `sessionmaker` bound to the engine |
| `get_db()` | FastAPI dependency (`Depends(get_db)`) yielding a session, always closed |

## 5. Declarative Base

`app/db/base.py` defines the single `Base` with a **naming convention**
(`pk_`, `fk_`, `uq_`, `ck_`, `ix_` prefixes). Deterministic constraint names
keep future Alembic autogenerate diffs stable across environments.

Helpers:

- `uuid_pk()` — application-generated **UUIDv4** primary key (docs/03 §3).
- `TimestampMixin` — `created_at` (DB default `now()`, never updated) and
  `updated_at` (DB default + SQLAlchemy `onupdate`), both
  `DateTime(timezone=True)` → `timestamptz` (docs/03 §4).

## 6. Models ↔ Schema Mapping

Exactly the 7 MVP tables from docs/03 §5 — no more, no less (verified by
tests):

| Model | Table | Notes |
| --- | --- | --- |
| `Person` | `persons` | `name` free text (TBD-D1); `phone` not unique (TBD-D2); `active` default true (TBD-D3 not encoded) |
| `Role` | `roles` | reference data; `code`/`name` UNIQUE. The six known codes are seeded by migration `0002` (docs/05 §5a) |
| `PersonRole` | `person_roles` | composite PK `(person_id, role_id)`; `created_at` only (immutable row); index on `role_id` |
| `Event` | `events` | status `text` + CHECK with the exact D-002 set; default `DRAFT`; `type` free text (TBD-D5); indexes on `planned_at`, `status` |
| `EventResponsibility` | `event_responsibilities` | `code`/`name` UNIQUE, `active` flag |
| `EventAssignment` | `event_assignments` | `approval_status` **PROVISIONAL** `PENDING`/`APPROVED` (text + CHECK); indexes on all three FKs; **no** UNIQUE(event_id, responsibility_id) (TBD-D11) |
| `EventReport` | `event_reports` | `event_id` **UNIQUE** (D-003: 0..1 per event); `author_id` RESTRICT; index on `author_id` |

Status values are represented Python-side by `EventStatus` and
`ApprovalStatus` (`str`-based enums). **No PostgreSQL ENUM type is created**
(docs/03 §6.1); the CHECK constraints live in the SQLAlchemy metadata.

Multi-role (D-001): `Person.roles` is an **association proxy** over the
`PersonRole` association objects — appending a `Role` creates the
membership row; the association objects remain the source of truth.

FK delete behaviors (docs/03 §7) are encoded on every `ForeignKey`
(CASCADE for owned links, RESTRICT for reference data / report authors).
Collection relationships use `passive_deletes=True` so the ORM defers to
the database's ON DELETE behavior instead of nullifying child FKs.

## 7. Deferred / Out of Scope (unchanged from docs/03)

- **Alembic migrations** — future task; `Base.metadata` is the target.
- **Task / Availability models** — deferred (docs/03 §13).
- **Seed data** (six roles) — seeded by Alembic migration `0002`
  (docs/05 §5a). Example responsibilities are **not** seeded (taxonomy
  TBD-D9).
- Remaining business APIs (the read-only roles endpoint exists — docs/06),
  auth, calendar/Jalali logic, etc.

## 8. Validation

From `apps/api` (venv active):

```bash
python -m pytest tests          # 24 tests: metadata + round-trip (SQLite)
python -m app.db.check          # dev-only PostgreSQL connectivity check
uvicorn app.main:app --port 8000  # /api/health works without DATABASE_URL
```

Unit tests run against **in-memory SQLite** (no PostgreSQL required):
CHECK/UNIQUE/PK constraints and FK delete behaviors (with
`PRAGMA foreign_keys=ON`) are exercised there, and the full DDL is
additionally compiled for the PostgreSQL dialect in a metadata test. The
`python -m app.db.check` CLI verifies the real database when it is running.

## 9. Environment Notes (this machine)

- The Docker PostgreSQL container publishes host port **5433** (not 5432):
  a native Windows `postgresql-x64-18` service already listens on host
  5432 and silently intercepts `localhost:5432` connections. Override with
  `POSTGRES_PORT` in `.env` if needed.
- psycopg 3 (binary build) is the driver; SQLAlchemy is the synchronous ORM
  (async was not required by the current architecture).
