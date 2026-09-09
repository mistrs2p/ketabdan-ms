"""Persons endpoints — read-only (docs/03 §5.1).

`GET /api/persons` lists branch members with their permanent roles (D-001).
Still no service layer: one ordered query with eager loading is a trivial
read; a service boundary appears once endpoints carry real logic
(docs/06 §3). Person creation is a later task — nothing is written here.
"""

from collections.abc import Sequence

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.models import Person, PersonRole
from app.schemas.person import PersonRead

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
