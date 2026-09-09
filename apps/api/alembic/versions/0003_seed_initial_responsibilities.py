"""seed initial event responsibilities

Inserts the six initial event-responsibility reference rows into
``event_responsibilities`` (docs/03-DATABASE-SCHEMA.md §5.5, decision
**D-004** in docs/02-DOMAIN-MODEL.md §1.1 — resolves the blocking part of
TBD-D9):

    pre_introduction (Pre-introduction), welcome_reception
    (Welcome / reception), technique_execution (Technique execution),
    persuasion (Persuasion), registration (Registration),
    follow_up (Follow-up)

These are exactly the six responsibility examples already documented in
docs/02 §2.3, docs/03 §5.5, and docs/05 §5a — nothing beyond them is
seeded, no code is renamed, no synonyms or translated duplicates are
introduced. The codes stay stable snake_case machine keys. Whether
responsibilities may also be created at runtime remains open (TBD-D9,
narrowed).

Mirrors the 0002 role-seed conventions exactly: hard-coded stable UUIDs
(plain ``uuid.UUID`` literals) so ``downgrade()`` removes exactly the rows
this migration owns (by id — never a broad ``DELETE FROM
event_responsibilities``), and ``ON CONFLICT (code) DO NOTHING`` against
the existing ``uq_event_responsibilities_code`` unique constraint so
re-execution cannot create duplicates or clobber existing rows. All rows
are seeded ``active = true`` (the retire mechanism itself is TBD-S2 —
only the flag exists). Audit timestamps are left to the existing database
defaults (docs/03 §4).

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-09

"""
from typing import Sequence, TypedDict, Union
from uuid import UUID

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert

# revision identifiers, used by Alembic.
revision: str = '0003'
down_revision: Union[str, None] = '0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


class SeedResponsibility(TypedDict):
    id: UUID
    code: str
    name: str


# The six initial responsibilities (D-004, docs/03 §5.5), with stable
# migration-owned UUIDs.
SEED_RESPONSIBILITIES: tuple[SeedResponsibility, ...] = (
    {"id": UUID("3a1c5e7b-9d4f-4b6a-8e2c-7f0b4d6a2c84"),
     "code": "pre_introduction", "name": "Pre-introduction"},
    {"id": UUID("4b2d6f8c-0e5a-4c7b-9f3d-8a1c5e7b3d95"),
     "code": "welcome_reception", "name": "Welcome / reception"},
    {"id": UUID("5c3e7a9d-1f6b-4d8c-8a4e-9b2d6f8c4ea6"),
     "code": "technique_execution", "name": "Technique execution"},
    {"id": UUID("6d4f8bae-2a7c-4e9d-ab5f-ac3e7a9d5fb7"),
     "code": "persuasion", "name": "Persuasion"},
    {"id": UUID("7e5a9cbf-3b8d-4fae-bc6a-bd4f8bae6ac8"),
     "code": "registration", "name": "Registration"},
    {"id": UUID("8f6badc0-4c9e-4abf-cd7b-ce5a9cbf7bd9"),
     "code": "follow_up", "name": "Follow-up"},
)

SEED_RESPONSIBILITY_IDS: tuple[UUID, ...] = tuple(
    row["id"] for row in SEED_RESPONSIBILITIES
)

# Minimal table shape for the data operations (the table itself is created by
# revision 0001; id/code/name are all this migration touches — `active` is
# seeded via the insert values and falls back to the column default).
_responsibilities_table = sa.table(
    "event_responsibilities",
    sa.column("id", sa.Uuid()),
    sa.column("code", sa.Text()),
    sa.column("name", sa.Text()),
    sa.column("active", sa.Boolean()),
)


def insert_seed_responsibilities(connection: sa.Connection) -> None:
    """Insert the six seed responsibilities; existing rows stay untouched."""
    rows = [
        {**row, "active": True} for row in SEED_RESPONSIBILITIES
    ]
    statement = (
        pg_insert(_responsibilities_table)
        .values(rows)
        .on_conflict_do_nothing(index_elements=["code"])
    )
    connection.execute(statement)


def delete_seed_responsibilities(connection: sa.Connection) -> None:
    """Delete only the rows this migration owns (by id), nothing else."""
    connection.execute(
        _responsibilities_table.delete().where(
            _responsibilities_table.c.id.in_(SEED_RESPONSIBILITY_IDS)
        )
    )


def upgrade() -> None:
    insert_seed_responsibilities(op.get_bind())


def downgrade() -> None:
    delete_seed_responsibilities(op.get_bind())
