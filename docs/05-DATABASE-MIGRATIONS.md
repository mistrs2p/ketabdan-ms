# 05 — Database Migrations (Alembic)

**Project:** Ketabdaneh
**Document status:** Implementation artifact — local/development migration infrastructure. No production database has been migrated.
**Last reviewed:** 2026-09-09
**Depends on:** [03-DATABASE-SCHEMA.md](03-DATABASE-SCHEMA.md) (authoritative schema design), [04-BACKEND-PERSISTENCE.md](04-BACKEND-PERSISTENCE.md) (ORM models)

---

## 1. Why Alembic

The database schema must change in a **controlled, repeatable, reviewable**
way (docs/01 §5: "the backend owns schema changes and applies them in a
controlled, repeatable way"). Alembic is the standard migration tool for
SQLAlchemy and connects directly to what we already have:

```
SQLAlchemy ORM models (app/models — docs/04)
        ↓
Alembic migrations (apps/api/alembic/versions)
        ↓
PostgreSQL schema
```

The **models remain the source of truth** for the intended schema; Alembic
records how to get an existing database from one schema version to the next.
`alembic check` compares the models' metadata against the live database, so
drift between code and database is detected instead of silently accumulating.

## 2. Where Migrations Live

```
apps/api/
├── alembic.ini          # tool configuration (NO database URL)
└── alembic/
    ├── env.py           # reads DATABASE_URL from app settings; sets
    │                    #   target_metadata = Base.metadata
    ├── script.py.mako   # template for new migration files
    └── versions/        # one Python file per migration revision
```

All alembic commands are run **from `apps/api`** (the directory containing
`alembic.ini`).

## 3. Database URL Configuration

`alembic/env.py` takes the URL from the **application's pydantic-settings
configuration** — the same `DATABASE_URL` (environment variable or
`apps/api/.env`) that drives the application at runtime (docs/04 §3).
There are **no credentials in `alembic.ini`** or in migration code; the
`sqlalchemy.url` option in `alembic.ini` is intentionally empty. If
`DATABASE_URL` is not set, migrations fail fast with a clear message.

Example (`apps/api/.env`, see `.env.example`):

```text
DATABASE_URL=postgresql+psycopg://ketabdaneh:ketabdaneh_dev@localhost:5433/ketabdaneh
```

## 4. Common Commands

All from `apps/api` (venv active):

| Command | Purpose |
| --- | --- |
| `alembic upgrade head` | Apply all pending migrations |
| `alembic downgrade -1` | Roll back the most recent migration |
| `alembic current` | Show the database's current revision |
| `alembic history` | List the migration chain |
| `alembic check` | Verify the database matches the models (no pending changes) |
| `alembic revision --autogenerate -m "..."` | Create a migration from model changes |

After any model change: create a migration with `revision --autogenerate`,
**review the generated file by hand** (autogenerate is a starting point, not
an approval), then `upgrade head` and `alembic check`.

## 5. The Initial Migration (`0001`)

Revision `0001_initial_mvp_schema` creates exactly the seven approved MVP
tables (docs/03 §5): `persons`, `roles`, `person_roles`, `events`,
`event_responsibilities`, `event_assignments`, `event_reports` — including
all designed constraints and indexes (docs/03 §8):

- the D-002 event status CHECK (5 values, text column — no DB enum),
- the **provisional** `approval_status` CHECK (`PENDING`/`APPROVED`, TBD-D10),
- `UNIQUE(event_reports.event_id)` enforcing D-003 (0..1 report per event),
- FK delete behaviors (CASCADE for owned links, RESTRICT for reference data),
- the seven justified indexes.

Task and Availability tables are deliberately absent (docs/03 §13).

Constraint names (op.f('pk_…'), 'fk_…', 'uq_…', 'ck_…', 'ix_…') follow the
naming convention on `Base.metadata` (docs/04 §5) so names are deterministic
across environments and autogenerate diffs stay stable.

`downgrade()` drops the schema in dependency-safe reverse order.

## 5a. The Seed Migration (`0002`)

Revision `0002_seed_initial_roles` inserts the **six confirmed permanent
roles** into `roles` as reference data (docs/03 §5.2, docs/00 §3):
`learner` (Learner / Student), `supporter`, `coach`, `teacher`, `referrer`,
`manager`.

- **Why these six:** they are the confirmed set of primary roles from
  discovery (docs/00 §7 ✅3) — confirmed reference data, not a speculative
  taxonomy. The schema design (docs/03 §5.2) explicitly defines them as the
  seed rows.
- **EventResponsibilities are deliberately NOT seeded.** The example
  responsibilities (`pre_introduction`, `welcome_reception`,
  `technique_execution`, `persuasion`, `registration`, `follow_up`) are known
  *examples* only; the taxonomy remains unresolved (**TBD-D9**) and is not
  turned into finalized reference data here.
- **How it behaves:** each role is inserted with a hard-coded stable UUID (no
  generation library), using `INSERT ... ON CONFLICT (code) DO NOTHING`
  against the existing `uq_roles_code` unique constraint — re-executing the
  insert cannot create duplicates or clobber existing rows. Audit timestamps
  are left to the existing database defaults. `downgrade()` deletes **only
  the six migration-owned rows (by id)** — never a broad `DELETE FROM roles`
  — so unrelated role rows survive a downgrade.
- The seed lives in the versioned migration history (not application startup,
  `create_all()`, or ad-hoc SQL), per the rules in §6.

## 6. Rules

1. **Migrations are version-controlled and reviewed like any other code.**
   Every schema change arrives as a migration file in a pull request/branch
   and is reviewed before merge.
2. **Production database changes happen through migrations only** — never via
   ad-hoc DDL, `CREATE TABLE` by hand, or application-side `create_all()`.
   (No production database exists yet; this rule applies from day one.)
3. Never edit an already-merged migration — add a new one instead.
4. A migration must always implement both `upgrade()` and `downgrade()`.
5. Autogenerated migrations are reviewed by a human before commit; autogenerate
   output is a draft, not an authority (it can miss renames and data changes).
6. Never commit credentials: `DATABASE_URL` lives in `.env` files, which are
   git-ignored (only `.env.example` is tracked).

## 7. Validation (development)

The checks below are the required validation for this migration, run against
the local Docker PostgreSQL:

- `alembic upgrade head`, followed by schema inspection (tables, columns,
  PKs, FKs with ON DELETE behavior, unique constraints, CHECK contents,
  indexes) — must match docs/03 exactly.
- `alembic check` must report no new upgrade operations (models ↔ database
  in sync).
- Upgrade → downgrade round-trip against a disposable test database (the
  persistent development database is not destroyed).
- The existing pytest suite (docs/04 §8) passes unchanged.
- `python -m app.db.check` and `GET /api/health` still work.

See the task's final report for the results actually executed.

## 8. Out of Scope

- Seeding EventResponsibilities (taxonomy TBD-D9 — not confirmed reference data).
- Business APIs, CRUD endpoints, auth — later tasks.
- Any production deployment/migration (no production environment exists).
