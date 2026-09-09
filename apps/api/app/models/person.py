"""Person — a human member of the branch (schema doc §5.1)."""

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, Text, true
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, uuid_pk
from app.models.person_role import PersonRole

if TYPE_CHECKING:
    from app.models.event_assignment import EventAssignment
    from app.models.event_report import EventReport


class Person(TimestampMixin, Base):
    __tablename__ = "persons"

    id: Mapped[UUID] = uuid_pk()

    # Single free-text field; structure TBD-D1, so no name parts are invented.
    name: Mapped[str] = mapped_column(Text, nullable=False)

    # Known concept; uniqueness deliberately NOT enforced (TBD-D2).
    phone: Mapped[str | None] = mapped_column(Text)

    # Active/inactive concept; what "inactive" implies is TBD-D3 — not encoded.
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=true()
    )

    # D-001: a person may hold multiple simultaneous roles, exposed as a
    # set-like view over the normalized person_roles association. Creation
    # and deletion of membership rows go through the association objects.
    role_links: Mapped[list["PersonRole"]] = relationship(
        back_populates="person", passive_deletes=True
    )
    roles = association_proxy(
        "role_links", "role", creator=lambda role: PersonRole(role=role)
    )

    assignments: Mapped[list["EventAssignment"]] = relationship(
        back_populates="person", passive_deletes=True
    )
    authored_reports: Mapped[list["EventReport"]] = relationship(
        back_populates="author", passive_deletes=True
    )
