"""ApplicationRolePermission — the role→permission grant (docs/06 §4g).

The authorization matrix itself: which ApplicationRole holds which
Permission. Composite primary key — a role cannot hold the same
permission twice. Rows are migration-owned reference data (seeded by
``0005``); there is deliberately no HTTP endpoint to change them —
reshaping the matrix is a migration, not a runtime operation.

FK semantics: deleting a role drops its grants (CASCADE); a permission
still granted to any role cannot be deleted (RESTRICT) — the same
subject/target split as person_roles and user_application_roles.
"""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.application_role import ApplicationRole
    from app.models.permission import Permission


class ApplicationRolePermission(Base):
    __tablename__ = "application_role_permissions"
    # Composite PK covers role_id lookups; this index covers "who holds
    # permission X" (used by nothing yet — symmetry with the other join
    # tables and cheap insurance for future reverse queries).
    __table_args__ = (
        Index("ix_application_role_permissions_permission_id", "permission_id"),
    )

    application_role_id: Mapped[UUID] = mapped_column(
        ForeignKey("application_roles.id", ondelete="CASCADE"), primary_key=True
    )
    permission_id: Mapped[UUID] = mapped_column(
        ForeignKey("permissions.id", ondelete="RESTRICT"), primary_key=True
    )

    # Audit: when this grant was made. No updated_at (immutable row).
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    application_role: Mapped["ApplicationRole"] = relationship(
        back_populates="permission_links"
    )
    permission: Mapped["Permission"] = relationship(back_populates="role_links")
