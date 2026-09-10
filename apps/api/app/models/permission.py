"""Permission — a single application-level capability (docs/06 §4g).

One row per stable machine code (``roles:read``, ``events:create``, …).
Permissions are the *only* thing route protection references — routes
never check application-role codes, so reshaping which role holds which
permission is a pure data change. Rows are migration-owned reference
data seeded by ``0005``; exactly one permission exists per capability
the current API actually offers (no speculative update/delete codes).
"""

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, uuid_pk

if TYPE_CHECKING:
    from app.models.application_role_permission import ApplicationRolePermission


class Permission(TimestampMixin, Base):
    __tablename__ = "permissions"

    id: Mapped[UUID] = uuid_pk()

    # Stable machine key, e.g. "events:create" (docs/06 §4g).
    code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    # Display name.
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)

    role_links: Mapped[list["ApplicationRolePermission"]] = relationship(
        back_populates="permission", passive_deletes=True
    )
