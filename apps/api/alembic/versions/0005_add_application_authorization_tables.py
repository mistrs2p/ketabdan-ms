"""application authorization tables (Phase 5 RBAC, docs/06 §4g)

Creates the three authorization tables and seeds the initial matrix:

- ``application_roles`` — admin, manager, operator (an *authorization*
  concept; entirely separate from the business-domain ``roles`` seeded
  by 0002)
- ``permissions`` — one row per capability the current API offers:
  roles:read, people:read, people:create, events:read, events:create,
  assignments:read, assignments:create (no speculative update/delete
  codes — those endpoints do not exist)
- ``user_application_roles`` / ``application_role_permissions`` —
  normalized many-to-many joins (composite PKs, the person_roles pattern)

Seeded matrix (docs/06 §4g):

- admin    → all seven permissions (the privileged bootstrap role)
- manager  → all seven (the primary business user; identical to admin
  today — admin is the role future administrative capabilities land on)
- operator → everything except people:create (runs day-to-day operations
  — the system's purpose is the branch running while the manager is
  absent — but does not manage the member roster)

Seed rows carry hard-coded stable UUIDs (the 0002 convention) so
downgrade/re-upgrade is identity-stable, and the inserts use
``ON CONFLICT DO NOTHING`` so re-execution cannot duplicate or clobber.
Audit timestamps are left to the database defaults.

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-10

"""
from typing import Sequence, TypedDict, Union
from uuid import UUID

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert

# revision identifiers, used by Alembic.
revision: str = '0005'
down_revision: Union[str, None] = '0004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


class SeedApplicationRole(TypedDict):
    id: UUID
    code: str
    name: str


class SeedPermission(TypedDict):
    id: UUID
    code: str
    name: str


class SeedRolePermission(TypedDict):
    application_role_id: UUID
    permission_id: UUID


# --- Application roles (stable migration-owned UUIDs) ----------------------

SEED_APPLICATION_ROLES: tuple[SeedApplicationRole, ...] = (
    {"id": UUID("d4a1f2b3-7c8e-4f5a-9b0c-1e2d3f4a5b6c"),
     "code": "admin", "name": "Administrator"},
    {"id": UUID("e5b2a3c4-8d9f-4a6b-8c1d-2f3a4b5c6d7e"),
     "code": "manager", "name": "Manager"},
    {"id": UUID("f6c3b4d5-9e0a-4b7c-9d2e-3a4b5c6d7e8f"),
     "code": "operator", "name": "Operator"},
)

# --- Permissions (one per capability the current API offers) ----------------

SEED_PERMISSIONS: tuple[SeedPermission, ...] = (
    {"id": UUID("b1d2e3f4-5a6b-4c7d-8e9f-0a1b2c3d4e5f"),
     "code": "roles:read", "name": "Read reference roles"},
    {"id": UUID("c2e3f4a5-6b7c-4d8e-9f0a-1b2c3d4e5f6a"),
     "code": "people:read", "name": "Read people"},
    {"id": UUID("d3f4a5b6-7c8d-4e9f-0a1b-2c3d4e5f6a7b"),
     "code": "people:create", "name": "Create people"},
    {"id": UUID("e4a5b6c7-8d9e-4f0a-1b2c-3d4e5f6a7b8c"),
     "code": "events:read", "name": "Read events"},
    {"id": UUID("f5b6c7d8-9e0a-4a1b-2c3d-4e5f6a7b8c9d"),
     "code": "events:create", "name": "Create events"},
    {"id": UUID("a6c7d8e9-0f1a-4b2c-3d4e-5f6a7b8c9d0e"),
     "code": "assignments:read", "name": "Read event assignments"},
    {"id": UUID("b7d8e9f0-1a2b-4c3d-4e5f-6a7b8c9d0e1f"),
     "code": "assignments:create", "name": "Create event assignments"},
)

# --- The matrix: role → permissions ------------------------------------------

# admin: all seven.
# manager: all seven (identical set today; the roles are conceptually
# distinct — admin is where future administrative permissions land).
# operator: everything except people:create.
SEED_APPLICATION_ROLE_PERMISSIONS: tuple[SeedRolePermission, ...] = (
    # admin
    {"application_role_id": UUID("d4a1f2b3-7c8e-4f5a-9b0c-1e2d3f4a5b6c"),
     "permission_id": UUID("b1d2e3f4-5a6b-4c7d-8e9f-0a1b2c3d4e5f")},
    {"application_role_id": UUID("d4a1f2b3-7c8e-4f5a-9b0c-1e2d3f4a5b6c"),
     "permission_id": UUID("c2e3f4a5-6b7c-4d8e-9f0a-1b2c3d4e5f6a")},
    {"application_role_id": UUID("d4a1f2b3-7c8e-4f5a-9b0c-1e2d3f4a5b6c"),
     "permission_id": UUID("d3f4a5b6-7c8d-4e9f-0a1b-2c3d4e5f6a7b")},
    {"application_role_id": UUID("d4a1f2b3-7c8e-4f5a-9b0c-1e2d3f4a5b6c"),
     "permission_id": UUID("e4a5b6c7-8d9e-4f0a-1b2c-3d4e5f6a7b8c")},
    {"application_role_id": UUID("d4a1f2b3-7c8e-4f5a-9b0c-1e2d3f4a5b6c"),
     "permission_id": UUID("f5b6c7d8-9e0a-4a1b-2c3d-4e5f6a7b8c9d")},
    {"application_role_id": UUID("d4a1f2b3-7c8e-4f5a-9b0c-1e2d3f4a5b6c"),
     "permission_id": UUID("a6c7d8e9-0f1a-4b2c-3d4e-5f6a7b8c9d0e")},
    {"application_role_id": UUID("d4a1f2b3-7c8e-4f5a-9b0c-1e2d3f4a5b6c"),
     "permission_id": UUID("b7d8e9f0-1a2b-4c3d-4e5f-6a7b8c9d0e1f")},
    # manager
    {"application_role_id": UUID("e5b2a3c4-8d9f-4a6b-8c1d-2f3a4b5c6d7e"),
     "permission_id": UUID("b1d2e3f4-5a6b-4c7d-8e9f-0a1b2c3d4e5f")},
    {"application_role_id": UUID("e5b2a3c4-8d9f-4a6b-8c1d-2f3a4b5c6d7e"),
     "permission_id": UUID("c2e3f4a5-6b7c-4d8e-9f0a-1b2c3d4e5f6a")},
    {"application_role_id": UUID("e5b2a3c4-8d9f-4a6b-8c1d-2f3a4b5c6d7e"),
     "permission_id": UUID("d3f4a5b6-7c8d-4e9f-0a1b-2c3d4e5f6a7b")},
    {"application_role_id": UUID("e5b2a3c4-8d9f-4a6b-8c1d-2f3a4b5c6d7e"),
     "permission_id": UUID("e4a5b6c7-8d9e-4f0a-1b2c-3d4e5f6a7b8c")},
    {"application_role_id": UUID("e5b2a3c4-8d9f-4a6b-8c1d-2f3a4b5c6d7e"),
     "permission_id": UUID("f5b6c7d8-9e0a-4a1b-2c3d-4e5f6a7b8c9d")},
    {"application_role_id": UUID("e5b2a3c4-8d9f-4a6b-8c1d-2f3a4b5c6d7e"),
     "permission_id": UUID("a6c7d8e9-0f1a-4b2c-3d4e-5f6a7b8c9d0e")},
    {"application_role_id": UUID("e5b2a3c4-8d9f-4a6b-8c1d-2f3a4b5c6d7e"),
     "permission_id": UUID("b7d8e9f0-1a2b-4c3d-4e5f-6a7b8c9d0e1f")},
    # operator — no people:create (d3f4a5b6-…)
    {"application_role_id": UUID("f6c3b4d5-9e0a-4b7c-9d2e-3a4b5c6d7e8f"),
     "permission_id": UUID("b1d2e3f4-5a6b-4c7d-8e9f-0a1b2c3d4e5f")},
    {"application_role_id": UUID("f6c3b4d5-9e0a-4b7c-9d2e-3a4b5c6d7e8f"),
     "permission_id": UUID("c2e3f4a5-6b7c-4d8e-9f0a-1b2c3d4e5f6a")},
    {"application_role_id": UUID("f6c3b4d5-9e0a-4b7c-9d2e-3a4b5c6d7e8f"),
     "permission_id": UUID("e4a5b6c7-8d9e-4f0a-1b2c-3d4e5f6a7b8c")},
    {"application_role_id": UUID("f6c3b4d5-9e0a-4b7c-9d2e-3a4b5c6d7e8f"),
     "permission_id": UUID("f5b6c7d8-9e0a-4a1b-2c3d-4e5f6a7b8c9d")},
    {"application_role_id": UUID("f6c3b4d5-9e0a-4b7c-9d2e-3a4b5c6d7e8f"),
     "permission_id": UUID("a6c7d8e9-0f1a-4b2c-3d4e-5f6a7b8c9d0e")},
    {"application_role_id": UUID("f6c3b4d5-9e0a-4b7c-9d2e-3a4b5c6d7e8f"),
     "permission_id": UUID("b7d8e9f0-1a2b-4c3d-4e5f-6a7b8c9d0e1f")},
)

SEED_APPLICATION_ROLE_IDS: tuple[UUID, ...] = tuple(
    row["id"] for row in SEED_APPLICATION_ROLES
)
SEED_PERMISSION_IDS: tuple[UUID, ...] = tuple(
    row["id"] for row in SEED_PERMISSIONS
)

# Minimal table shapes for the data operations (the tables themselves are
# created above; these cover only the columns the seeds touch).
_application_roles_table = sa.table(
    "application_roles",
    sa.column("id", sa.Uuid()),
    sa.column("code", sa.Text()),
    sa.column("name", sa.Text()),
)
_permissions_table = sa.table(
    "permissions",
    sa.column("id", sa.Uuid()),
    sa.column("code", sa.Text()),
    sa.column("name", sa.Text()),
)
_application_role_permissions_table = sa.table(
    "application_role_permissions",
    sa.column("application_role_id", sa.Uuid()),
    sa.column("permission_id", sa.Uuid()),
)


def insert_seed_authorization_data(connection: sa.Connection) -> None:
    """Insert the roles/permissions/matrix; existing rows are left untouched."""
    connection.execute(
        pg_insert(_application_roles_table)
        .values(list(SEED_APPLICATION_ROLES))
        .on_conflict_do_nothing(index_elements=["code"])
    )
    connection.execute(
        pg_insert(_permissions_table)
        .values(list(SEED_PERMISSIONS))
        .on_conflict_do_nothing(index_elements=["code"])
    )
    connection.execute(
        pg_insert(_application_role_permissions_table)
        .values(list(SEED_APPLICATION_ROLE_PERMISSIONS))
        .on_conflict_do_nothing(
            index_elements=["application_role_id", "permission_id"]
        )
    )


def upgrade() -> None:
    op.create_table(
        'application_roles',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('code', sa.Text(), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_application_roles')),
        sa.UniqueConstraint('code', name=op.f('uq_application_roles_code')),
        sa.UniqueConstraint('name', name=op.f('uq_application_roles_name')),
    )
    op.create_table(
        'permissions',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('code', sa.Text(), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_permissions')),
        sa.UniqueConstraint('code', name=op.f('uq_permissions_code')),
        sa.UniqueConstraint('name', name=op.f('uq_permissions_name')),
    )
    op.create_table(
        'user_application_roles',
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('application_role_id', sa.Uuid(), nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint(
            'user_id', 'application_role_id', name=op.f('pk_user_application_roles')
        ),
        sa.ForeignKeyConstraint(
            ['user_id'],
            ['users.id'],
            name=op.f('fk_user_application_roles_user_id_users'),
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['application_role_id'],
            ['application_roles.id'],
            name=op.f(
                'fk_user_application_roles_application_role_id_application_roles'
            ),
            ondelete='RESTRICT',
        ),
    )
    op.create_index(
        op.f('ix_user_application_roles_application_role_id'),
        'user_application_roles',
        ['application_role_id'],
        unique=False,
    )
    op.create_table(
        'application_role_permissions',
        sa.Column('application_role_id', sa.Uuid(), nullable=False),
        sa.Column('permission_id', sa.Uuid(), nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint(
            'application_role_id',
            'permission_id',
            name=op.f('pk_application_role_permissions'),
        ),
        sa.ForeignKeyConstraint(
            ['application_role_id'],
            ['application_roles.id'],
            name=op.f(
                'fk_application_role_permissions_application_role_id_application_roles'
            ),
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['permission_id'],
            ['permissions.id'],
            name=op.f('fk_application_role_permissions_permission_id_permissions'),
            ondelete='RESTRICT',
        ),
    )
    op.create_index(
        op.f('ix_application_role_permissions_permission_id'),
        'application_role_permissions',
        ['permission_id'],
        unique=False,
    )

    insert_seed_authorization_data(op.get_bind())


def downgrade() -> None:
    # Dependency-safe reverse order: joins first, then the reference
    # tables they point at. Dropping the tables removes the seed rows;
    # the users table (0004) is untouched.
    op.drop_index(
        op.f('ix_application_role_permissions_permission_id'),
        table_name='application_role_permissions',
    )
    op.drop_table('application_role_permissions')
    op.drop_index(
        op.f('ix_user_application_roles_application_role_id'),
        table_name='user_application_roles',
    )
    op.drop_table('user_application_roles')
    op.drop_table('permissions')
    op.drop_table('application_roles')
