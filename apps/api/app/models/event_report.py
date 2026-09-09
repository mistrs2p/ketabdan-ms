"""EventReport — the optional post-event report (schema doc §5.7, D-003).

`event_id` is UNIQUE: at most one report per event, ever. The report is NOT
mandatory (D-003) — nothing here or elsewhere enforces "event must have a
report". Authorship semantics are TBD-D19; `author_id` is a design candidate
with RESTRICT delete behavior. No acknowledgement workflow (TBD-D21).
Content structure is TBD-A9 — a single text field is the minimal choice.
"""

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, uuid_pk

if TYPE_CHECKING:
    from app.models.event import Event
    from app.models.person import Person


class EventReport(TimestampMixin, Base):
    __tablename__ = "event_reports"

    id: Mapped[UUID] = uuid_pk()

    event_id: Mapped[UUID] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    author_id: Mapped[UUID] = mapped_column(
        ForeignKey("persons.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    content: Mapped[str] = mapped_column(Text, nullable=False)

    event: Mapped["Event"] = relationship(back_populates="report")
    author: Mapped["Person"] = relationship(back_populates="authored_reports")
