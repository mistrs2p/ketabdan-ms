"""Event — a planned branch activity (schema doc §5.4).

Status is the approved D-002 set, stored as text + CHECK constraint
(representation choice §6.1) — deliberately NOT a PostgreSQL enum. The
allowed *transitions* remain TBD (D-7/D-23) and are not encoded. Event
`type` is free text validated by the application; the taxonomy is TBD-D5.
"""

import enum
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, uuid_pk

if TYPE_CHECKING:
    from app.models.event_assignment import EventAssignment
    from app.models.event_report import EventReport


class EventStatus(str, enum.Enum):
    """The exact approved event status set (D-002).

    Python-side representation only — the database column stays text with a
    CHECK constraint so the set can evolve via a simple migration. No
    "REPORTED" status exists (rejected with D-002).
    """

    DRAFT = "DRAFT"
    SCHEDULED = "SCHEDULED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


EVENT_STATUS_VALUES = tuple(status.value for status in EventStatus)

_STATUS_CHECK = "status IN ({})".format(
    ", ".join(f"'{value}'" for value in EVENT_STATUS_VALUES)
)


class Event(TimestampMixin, Base):
    __tablename__ = "events"
    __table_args__ = (
        CheckConstraint(_STATUS_CHECK, name="status_in_approved_set"),
    )

    id: Mapped[UUID] = uuid_pk()

    title: Mapped[str] = mapped_column(Text, nullable=False)

    # Free text, application-validated (taxonomy TBD-D5, schema doc §6.2).
    type: Mapped[str] = mapped_column(Text, nullable=False)

    # Business datetime — when the event is planned to occur (schema doc §4).
    planned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default=EventStatus.DRAFT,
        server_default=EventStatus.DRAFT.value,
        index=True,
    )

    assignments: Mapped[list["EventAssignment"]] = relationship(
        back_populates="event", passive_deletes=True
    )
    # D-003: zero or one report per event (enforced by UNIQUE(event_id)).
    report: Mapped["EventReport | None"] = relationship(
        back_populates="event", uselist=False, passive_deletes=True
    )
