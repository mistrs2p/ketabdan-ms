"""Single SQLAlchemy declarative base for all Ketabdaneh models.

A shared naming convention is attached to the metadata so that all
constraints get stable, deterministic names — this keeps future Alembic
migrations diffable (unnamed constraints would otherwise get
database-generated names that vary between environments).
"""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import DateTime, MetaData, Uuid, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

if TYPE_CHECKING:
    from uuid import UUID

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Declarative base shared by every ORM model.

    Reused as the migration target by future Alembic migrations
    (`Base.metadata` contains all tables once `app.models` is imported).
    """

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def uuid_pk() -> Mapped["UUID"]:
    """Application-generated UUIDv4 primary key (schema doc §3)."""
    return mapped_column(Uuid(), primary_key=True, default=uuid4)


class TimestampMixin:
    """Audit columns per schema doc §4.

    `created_at` is set once by the database (`now()`); `updated_at` is
    maintained by the application (SQLAlchemy `onupdate`) and also has a
    database default so raw SQL inserts stay valid. Both are timezone-aware
    (`timestamptz` on PostgreSQL).
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
