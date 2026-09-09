"""EventAssignment — Person performs an EventResponsibility for an Event
(schema doc §5.6).

Existence vs approval are clearly separated: the row itself *is* the
assignment; `approval_status` is an *attribute* of it. The values below are
PROVISIONAL placeholders — the real approval states and workflow are TBD
(D-10 / A-6 / S-13). No `approved_by`/`approved_at`/transition rules are
encoded. No UNIQUE(event_id, responsibility_id): responsibility exclusivity
is TBD-D11.
"""

import enum
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, uuid_pk

if TYPE_CHECKING:
    from app.models.event import Event
    from app.models.event_responsibility import EventResponsibility
    from app.models.person import Person


class ApprovalStatus(str, enum.Enum):
    """PROVISIONAL approval states (TBD-D10/A6) — not a finalized rule set.

    Chosen as a two-value starting point because the manager's approval need
    is confirmed; can be widened (e.g. 'REJECTED') by a simple migration
    once the real states are decided. Kept as a Python enum for the
    application side only — the column stays text + CHECK, not a DB enum.
    """

    PENDING = "PENDING"
    APPROVED = "APPROVED"


APPROVAL_STATUS_VALUES = tuple(status.value for status in ApprovalStatus)

_APPROVAL_STATUS_CHECK = "approval_status IN ({})".format(
    ", ".join(f"'{value}'" for value in APPROVAL_STATUS_VALUES)
)


class EventAssignment(TimestampMixin, Base):
    __tablename__ = "event_assignments"
    __table_args__ = (
        CheckConstraint(_APPROVAL_STATUS_CHECK, name="approval_status_in_known_set"),
    )

    id: Mapped[UUID] = uuid_pk()

    event_id: Mapped[UUID] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True
    )
    person_id: Mapped[UUID] = mapped_column(
        ForeignKey("persons.id", ondelete="CASCADE"), nullable=False, index=True
    )
    responsibility_id: Mapped[UUID] = mapped_column(
        ForeignKey("event_responsibilities.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    approval_status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default=ApprovalStatus.PENDING,
        server_default=ApprovalStatus.PENDING.value,
    )

    event: Mapped["Event"] = relationship(back_populates="assignments")
    person: Mapped["Person"] = relationship(back_populates="assignments")
    responsibility: Mapped["EventResponsibility"] = relationship(
        back_populates="assignments"
    )
