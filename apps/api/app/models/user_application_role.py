"""UserApplicationRole — normalized User↔ApplicationRole grant (docs/06 §4g).

Composite primary key (user_id, application_role_id): the same user
cannot hold the same application role twice; multiple *different* roles
are allowed and their permissions are unioned (services.authz).

Mirrors the PersonRole design (schema doc §5.3): an immutable
created-then-deleted row — `created_at` only, no `updated_at`, no grant
history (that would be an audit-trail feature, out of scope). FK
semantics follow the same precedent: deleting a user removes their
grants (CASCADE); a role still held by anyone cannot be deleted
(RESTRICT).
"""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.application_role import ApplicationRole
    from app.models.user import User


class UserApplicationRole(Base):
    __tablename__ = "user_application_roles"
    # Composite PK covers user_id lookups; this index covers "who holds
    # role X" (the same asymmetry as person_roles, schema doc §8).
    __table_args__ = (
        Index("ix_user_application_roles_application_role_id", "application_role_id"),
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    application_role_id: Mapped[UUID] = mapped_column(
        ForeignKey("application_roles.id", ondelete="RESTRICT"), primary_key=True
    )

    # Audit: when this grant was made. No updated_at (immutable row).
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="application_role_links")
    application_role: Mapped["ApplicationRole"] = relationship(
        back_populates="user_links"
    )
