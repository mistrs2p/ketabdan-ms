"""Persons endpoints (docs/03 §5.1, docs/06 §4a).

Reads stay direct queries; creation carries real logic (role-code resolution
plus an atomic write), so the route delegates to ``app.services.persons``
(docs/06 §3 rule 4) and only translates its errors into HTTP responses.

Protected since docs/06 §4g: reads require ``people:read``, creation
requires ``people:create``.
"""

from collections.abc import Sequence

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.auth import GENERIC_401_DETAIL
from app.api.deps import GENERIC_403_DETAIL, require_permission
from app.db.session import get_db
from app.models import Person, PersonRole
from app.schemas.errors import error_response
from app.schemas.person import PersonCreate, PersonRead
from app.services import authz
from app.services import persons as persons_service

router = APIRouter(prefix="/api", tags=["People"])


@router.get(
    "/persons",
    response_model=list[PersonRead],
    status_code=status.HTTP_200_OK,
    summary="List branch members",
    dependencies=[Depends(require_permission(authz.PEOPLE_READ))],
    responses={
        401: error_response(
            "Not authenticated (missing/invalid/expired token or "
            "inactive user).",
            example_detail=GENERIC_401_DETAIL,
        ),
        403: error_response(
            "Authenticated, but the user lacks the `people:read` "
            "permission.",
            example_detail=GENERIC_403_DETAIL,
        ),
    },
)
def list_persons(db: Session = Depends(get_db)) -> Sequence[Person]:
    """List branch members (ordered by name, then id), each with their roles.

    Requires the **`people:read`** permission. Roles are attached to
    each person, deterministically ordered by role code.
    """
    return db.scalars(
        select(Person)
        # Eager-load role memberships and the role rows behind them, so the
        # response serialization does not issue one query per person.
        .options(selectinload(Person.role_links).selectinload(PersonRole.role))
        .order_by(Person.name, Person.id)
    ).all()


@router.post(
    "/persons",
    response_model=PersonRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a branch member",
    dependencies=[Depends(require_permission(authz.PEOPLE_CREATE))],
    responses={
        401: error_response(
            "Not authenticated (missing/invalid/expired token or "
            "inactive user).",
            example_detail=GENERIC_401_DETAIL,
        ),
        403: error_response(
            "Authenticated, but the user lacks the `people:create` "
            "permission.",
            example_detail=GENERIC_403_DETAIL,
        ),
        422: {
            "description": (
                "Validation failure (Pydantic's structured detail list), "
                "or an unknown role code in `roles` (plain string detail) — "
                "domain reference violations share the validation status "
                "family (docs/06 §4b rule 3)."
            ),
            "content": {
                "application/json": {
                    "example": {"detail": "Unknown role code(s): ghost"}
                }
            },
        },
    },
)
def create_person(
    payload: PersonCreate, db: Session = Depends(get_db)
) -> Person:
    """Create a branch member, optionally with roles, atomically (docs/06 §4a).

    Requires the **`people:create`** permission. Roles are given as the
    stable machine codes of the seeded reference data (`GET /api/roles`
    lists them); the person and their role memberships are written in
    one transaction — an unknown role code leaves nothing behind and
    returns 422.
    """
    try:
        return persons_service.create_person(db, payload)
    except persons_service.UnknownRoleError as exc:
        # 422 per the error policy (docs/06 §4b rule 3): request content
        # that violates domain reference data shares the validation
        # status family.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
