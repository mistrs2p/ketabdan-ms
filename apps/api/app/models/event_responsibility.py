"""EventResponsibility — reusable operational responsibility definition
(schema doc §5.5).

Data, not an enum: the taxonomy is TBD-D9, so responsibilities are rows
with a stable `code` and display `name`; the set can grow without a schema
change. Lifecycle (retire/reactivate rules) is TBD-S2 — only an `active`
flag is modeled.
"""

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, Text, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, uuid_pk

if TYPE_CHECKING:
    from app.models.event_assignment import EventAssignment


class EventResponsibility(TimestampMixin, Base):
    __tablename__ = "event_responsibilities"

    id: Mapped[UUID] = uuid_pk()

    code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=true()
    )

    assignments: Mapped[list["EventAssignment"]] = relationship(
        back_populates="responsibility", passive_deletes=True
    )
