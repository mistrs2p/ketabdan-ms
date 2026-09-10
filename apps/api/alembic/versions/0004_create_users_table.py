"""users table (Phase 5 authentication foundation)

The authentication identity table from docs/06-BACKEND-API.md §4f —
deliberately separate from ``persons`` (a User is *who is logged in*, a
Person is a business entity; no relationship forced). Columns exactly as
the model defines (app/models/user.py): username (unique, canonical
casefolded form), password_hash (Argon2id, never plaintext), active
(default true). Constraint names follow the Base metadata naming
convention, so autogenerate diffs stay stable.

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0004'
down_revision: Union[str, None] = '0003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'users',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('username', sa.Text(), nullable=False),
        sa.Column('password_hash', sa.Text(), nullable=False),
        sa.Column(
            'active', sa.Boolean(), nullable=False, server_default=sa.text('true')
        ),
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
        sa.PrimaryKeyConstraint('id', name=op.f('pk_users')),
        # In PostgreSQL this unique constraint is enforced by a unique
        # index — the username lookup key — so no separate index is needed.
        sa.UniqueConstraint('username', name=op.f('uq_users_username')),
    )


def downgrade() -> None:
    op.drop_table('users')
