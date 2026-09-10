"""ApplicationRole — an *authorization* role (docs/06 §4g, Phase 5.2).

Deliberately separate from the business-domain ``roles`` table (docs/03
§5.2): a domain Role describes what a Person *is in the branch*
(learner, coach, …); an ApplicationRole describes what an authenticated
User *may do in the application*. The two systems share nothing — not
rows, not codes, not semantics (docs/06 §4g documents the distinction).

Rows are migration-owned reference data (seeded by ``0005``): admin,
manager, operator. Like ``Role``, this model contains no seed data and
no Python enum — adding a role is a data change, not a code change.
"""

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, uuid_pk

if TYPE_CHECKING:
    from app.models.application_role_permission import ApplicationRolePermission
    from app.models.user_application_role import UserApplicationRole


class ApplicationRole(TimestampMixin, Base):
    __tablename__ = "application_roles"

    id: Mapped[UUID] = uuid_pk()

    # Stable machine key (admin/manager/operator — seeded by 0005).
    code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    # Display name.
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)

    permission_links: Mapped[list["ApplicationRolePermission"]] = relationship(
        back_populates="application_role", passive_deletes=True
    )
    user_links: Mapped[list["UserApplicationRole"]] = relationship(
        back_populates="application_role", passive_deletes=True
    )
