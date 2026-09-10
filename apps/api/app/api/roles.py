"""Roles endpoints — read-only reference data (docs/03 §5.2).

The six permanent roles are seeded by Alembic migration ``0002``; this
module exposes them but creates nothing. No service layer yet: listing
reference rows is a single trivial query, and wrapping it would be
over-engineering — a service/module boundary appears once endpoints carry
actual logic.

Protected since docs/06 §4g: requires the ``roles:read`` permission.
"""

from collections.abc import Sequence

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.db.session import get_db
from app.models import Role
from app.schemas.role import RoleRead
from app.services import authz

router = APIRouter(prefix="/api", tags=["roles"])


@router.get(
    "/roles",
    response_model=list[RoleRead],
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_permission(authz.ROLES_READ))],
)
def list_roles(db: Session = Depends(get_db)) -> Sequence[Role]:
    """List the permanent organizational roles, ordered by code."""
    return db.scalars(select(Role).order_by(Role.code)).all()
