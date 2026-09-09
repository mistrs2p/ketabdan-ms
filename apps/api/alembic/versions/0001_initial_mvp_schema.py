"""initial MVP schema

The seven approved MVP tables from docs/03-DATABASE-SCHEMA.md §5, exactly as
defined by the SQLAlchemy models (docs/04-BACKEND-PERSISTENCE.md):

persons, roles, person_roles, events, event_responsibilities,
event_assignments, event_reports.

Task and Availability are deliberately absent (docs/03 §13 — deferred).
Constraint names follow the naming convention on Base metadata
(apps/api/app/db/base.py), so autogenerate diffs stay stable. The
approval_status CHECK values (PENDING/APPROVED) are PROVISIONAL placeholders
(docs/03 §5.6, TBD-D10) and must not be read as finalized business rules.

Revision ID: 0001
Revises:
Create Date: 2026-09-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'persons',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('phone', sa.Text(), nullable=True),
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
        sa.PrimaryKeyConstraint('id', name=op.f('pk_persons')),
    )
    op.create_table(
        'roles',
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
        sa.PrimaryKeyConstraint('id', name=op.f('pk_roles')),
        sa.UniqueConstraint('code', name=op.f('uq_roles_code')),
        sa.UniqueConstraint('name', name=op.f('uq_roles_name')),
    )
    op.create_table(
        'person_roles',
        sa.Column('person_id', sa.Uuid(), nullable=False),
        sa.Column('role_id', sa.Uuid(), nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ['person_id'],
            ['persons.id'],
            name=op.f('fk_person_roles_person_id_persons'),
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['role_id'],
            ['roles.id'],
            name=op.f('fk_person_roles_role_id_roles'),
            ondelete='RESTRICT',
        ),
        sa.PrimaryKeyConstraint('person_id', 'role_id', name=op.f('pk_person_roles')),
    )
    op.create_index(
        op.f('ix_person_roles_role_id'), 'person_roles', ['role_id'], unique=False
    )
    op.create_table(
        'events',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('type', sa.Text(), nullable=False),
        sa.Column('planned_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            'status', sa.Text(), server_default=sa.text("'DRAFT'"), nullable=False
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
        sa.PrimaryKeyConstraint('id', name=op.f('pk_events')),
        sa.CheckConstraint(
            "status IN ('DRAFT', 'SCHEDULED', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED')",
            name=op.f('ck_events_status_in_approved_set'),
        ),
    )
    op.create_index(op.f('ix_events_planned_at'), 'events', ['planned_at'], unique=False)
    op.create_index(op.f('ix_events_status'), 'events', ['status'], unique=False)
    op.create_table(
        'event_responsibilities',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('code', sa.Text(), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
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
        sa.PrimaryKeyConstraint('id', name=op.f('pk_event_responsibilities')),
        sa.UniqueConstraint('code', name=op.f('uq_event_responsibilities_code')),
        sa.UniqueConstraint('name', name=op.f('uq_event_responsibilities_name')),
    )
    op.create_table(
        'event_assignments',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('event_id', sa.Uuid(), nullable=False),
        sa.Column('person_id', sa.Uuid(), nullable=False),
        sa.Column('responsibility_id', sa.Uuid(), nullable=False),
        sa.Column(
            'approval_status',
            sa.Text(),
            server_default=sa.text("'PENDING'"),
            nullable=False,
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
        sa.PrimaryKeyConstraint('id', name=op.f('pk_event_assignments')),
        sa.CheckConstraint(
            "approval_status IN ('PENDING', 'APPROVED')",
            name=op.f('ck_event_assignments_approval_status_in_known_set'),
        ),
        sa.ForeignKeyConstraint(
            ['event_id'],
            ['events.id'],
            name=op.f('fk_event_assignments_event_id_events'),
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['person_id'],
            ['persons.id'],
            name=op.f('fk_event_assignments_person_id_persons'),
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['responsibility_id'],
            ['event_responsibilities.id'],
            name=op.f('fk_event_assignments_responsibility_id_event_responsibilities'),
            ondelete='RESTRICT',
        ),
    )
    op.create_index(
        op.f('ix_event_assignments_event_id'),
        'event_assignments',
        ['event_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_event_assignments_person_id'),
        'event_assignments',
        ['person_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_event_assignments_responsibility_id'),
        'event_assignments',
        ['responsibility_id'],
        unique=False,
    )
    op.create_table(
        'event_reports',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('event_id', sa.Uuid(), nullable=False),
        sa.Column('author_id', sa.Uuid(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
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
        sa.PrimaryKeyConstraint('id', name=op.f('pk_event_reports')),
        sa.UniqueConstraint('event_id', name=op.f('uq_event_reports_event_id')),
        sa.ForeignKeyConstraint(
            ['event_id'],
            ['events.id'],
            name=op.f('fk_event_reports_event_id_events'),
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['author_id'],
            ['persons.id'],
            name=op.f('fk_event_reports_author_id_persons'),
            ondelete='RESTRICT',
        ),
    )
    op.create_index(
        op.f('ix_event_reports_author_id'), 'event_reports', ['author_id'], unique=False
    )


def downgrade() -> None:
    # Dependency-safe reverse order: referencing tables first.
    op.drop_index(op.f('ix_event_reports_author_id'), table_name='event_reports')
    op.drop_table('event_reports')
    op.drop_index(
        op.f('ix_event_assignments_responsibility_id'), table_name='event_assignments'
    )
    op.drop_index(
        op.f('ix_event_assignments_person_id'), table_name='event_assignments'
    )
    op.drop_index(op.f('ix_event_assignments_event_id'), table_name='event_assignments')
    op.drop_table('event_assignments')
    op.drop_table('event_responsibilities')
    op.drop_index(op.f('ix_events_status'), table_name='events')
    op.drop_index(op.f('ix_events_planned_at'), table_name='events')
    op.drop_table('events')
    op.drop_index(op.f('ix_person_roles_role_id'), table_name='person_roles')
    op.drop_table('person_roles')
    op.drop_table('roles')
    op.drop_table('persons')
