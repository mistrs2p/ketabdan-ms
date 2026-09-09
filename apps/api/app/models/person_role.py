"""PersonRole — normalized Person↔Role membership (schema doc §5.3, D-001).

Composite primary key (person_id, role_id): the same person cannot hold the
same role twice. Immutable row (created, then deleted) — hence `created_at`
only, no `updated_at`. Role-grant history is not a confirmed requirement
(TBD-S1).
"""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.person import Person
    from app.models.role import Role


class PersonRole(Base):
    __tablename__ = "person_roles"
    # Index for "all people with role X" queries (schema doc §8) — the
    # composite PK covers person_id lookups, not role_id.
    __table_args__ = (Index("ix_person_roles_role_id", "role_id"),)

    person_id: Mapped[UUID] = mapped_column(
        ForeignKey("persons.id", ondelete="CASCADE"), primary_key=True
    )
    role_id: Mapped[UUID] = mapped_column(
        ForeignKey("roles.id", ondelete="RESTRICT"), primary_key=True
    )

    # Audit: when this role was granted. No updated_at by design (§5.3).
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    person: Mapped["Person"] = relationship(back_populates="role_links")
    role: Mapped["Role"] = relationship(back_populates="person_links")
