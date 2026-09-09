"""seed initial roles

Inserts the six confirmed permanent-role reference rows into ``roles``
(docs/03-DATABASE-SCHEMA.md §5.2, docs/00-PROJECT-CONTEXT.md §3):

    learner (Learner / Student), supporter (Supporter), coach (Coach),
    teacher (Teacher), referrer (Referrer), manager (Manager)

These are confirmed reference data — nothing beyond the six known roles is
seeded. EventResponsibility rows are deliberately NOT seeded here: that
taxonomy remains unresolved (TBD-D9) and must not be turned into finalized
reference data.

Each role gets a hard-coded stable UUID (no new library — plain ``uuid.UUID``
literals), so the seed rows have stable identities and ``downgrade()`` removes
exactly the rows this migration owns (by id — never a broad ``DELETE FROM
roles``). The insert resolves conflicts with the existing ``uq_roles_code``
unique constraint via ``ON CONFLICT (code) DO NOTHING``, so re-executing it
against an already-seeded database cannot create duplicates or clobber
existing rows. Audit timestamps (``created_at``/``updated_at``) are left to
the existing database defaults (docs/03 §4).

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-09

"""
from typing import Sequence, TypedDict, Union
from uuid import UUID

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert

# revision identifiers, used by Alembic.
revision: str = '0002'
down_revision: Union[str, None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


class SeedRole(TypedDict):
    id: UUID
    code: str
    name: str


# The six confirmed roles (docs/03 §5.2), with stable migration-owned UUIDs.
SEED_ROLES: tuple[SeedRole, ...] = (
    {"id": UUID("a3f5c2e1-7b4d-4e8f-9c1a-2d6b8e4f0a71"),
     "code": "learner", "name": "Learner / Student"},
    {"id": UUID("b7e2d9a4-3c5f-4a1b-8d9e-6f0a2c4e6b83"),
     "code": "supporter", "name": "Supporter"},
    {"id": UUID("c9d4f1b5-2a6e-4c3d-9e8f-1b3d5f7a9c25"),
     "code": "coach", "name": "Coach"},
    {"id": UUID("d2b6a3c7-8e4f-4d2c-a1b9-3e5c7d9f1b47"),
     "code": "teacher", "name": "Teacher"},
    {"id": UUID("e5c8b1d9-4f7a-4e6c-b3d8-2f4a6c8e0d69"),
     "code": "referrer", "name": "Referrer"},
    {"id": UUID("f1d3e5a7-6b9c-4f8d-b2e4-4a6e8b0d2f8b"),
     "code": "manager", "name": "Manager"},
)

SEED_ROLE_IDS: tuple[UUID, ...] = tuple(row["id"] for row in SEED_ROLES)

# Minimal table shape for the data operations (the table itself is created by
# revision 0001; id/code/name are all this migration touches).
_roles_table = sa.table(
    "roles",
    sa.column("id", sa.Uuid()),
    sa.column("code", sa.Text()),
    sa.column("name", sa.Text()),
)


def insert_seed_roles(connection: sa.Connection) -> None:
    """Insert the six seed roles; rows that already exist are left untouched."""
    statement = (
        pg_insert(_roles_table)
        .values(list(SEED_ROLES))
        .on_conflict_do_nothing(index_elements=["code"])
    )
    connection.execute(statement)


def delete_seed_roles(connection: sa.Connection) -> None:
    """Delete only the role rows this migration owns (by id), nothing else."""
    connection.execute(
        _roles_table.delete().where(_roles_table.c.id.in_(SEED_ROLE_IDS))
    )


def upgrade() -> None:
    insert_seed_roles(op.get_bind())


def downgrade() -> None:
    delete_seed_roles(op.get_bind())
