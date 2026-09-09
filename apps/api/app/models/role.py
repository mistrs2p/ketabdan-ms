"""Role — permanent organizational role definition (schema doc §5.2).

Roles are reference **data** (rows), not an enum. The six known codes are
`learner`, `supporter`, `coach`, `teacher`, `referrer`, `manager` — seeding
them belongs to a future task; this model intentionally contains no seed
data and no Python enum of role codes.
"""

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, uuid_pk

if TYPE_CHECKING:
    from app.models.person_role import PersonRole


class Role(TimestampMixin, Base):
    __tablename__ = "roles"

    id: Mapped[UUID] = uuid_pk()

    # Stable machine key (learner/supporter/coach/teacher/referrer/manager).
    code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    # Display name.
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)

    person_links: Mapped[list["PersonRole"]] = relationship(
        back_populates="role", passive_deletes=True
    )
