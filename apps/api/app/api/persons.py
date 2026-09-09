"""Persons endpoints (docs/03 §5.1, docs/06 §4a).

Reads stay direct queries; creation carries real logic (role-code resolution
plus an atomic write), so the route delegates to ``app.services.persons``
(docs/06 §3 rule 4) and only translates its errors into HTTP responses.
"""

from collections.abc import Sequence

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.models import Person, PersonRole
from app.schemas.person import PersonCreate, PersonRead
from app.services import persons as persons_service

router = APIRouter(prefix="/api", tags=["persons"])


@router.get(
    "/persons",
    response_model=list[PersonRead],
    status_code=status.HTTP_200_OK,
)
def list_persons(db: Session = Depends(get_db)) -> Sequence[Person]:
    """List branch members (ordered by name, then id), each with their roles."""
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
)
def create_person(
    payload: PersonCreate, db: Session = Depends(get_db)
) -> Person:
    """Create a branch member, optionally with roles, atomically (docs/06 §4a)."""
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
