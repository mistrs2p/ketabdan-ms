"""EventAssignment endpoints (docs/06 §4d).

Creation carries real logic — reference resolution with three distinct
failure classes — so the route delegates to
``app.services.event_assignments`` (docs/06 §3 rule 4) and only
translates its errors into HTTP responses per the error policy (§4b):
not-found resources → 404, unknown domain reference code → 422.

Reads stay direct queries (docs/06 §3 rule 4): deterministic ordering
(assignment `id` — no business sort is documented anywhere), with only
the responsibility eager-loaded because it is the one relation embedded
in `EventAssignmentRead`.
"""

from collections.abc import Sequence
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.models import EventAssignment
from app.schemas.event_assignment import EventAssignmentCreate, EventAssignmentRead
from app.services import event_assignments as assignments_service

router = APIRouter(prefix="/api", tags=["event-assignments"])


@router.get(
    "/event-assignments",
    response_model=list[EventAssignmentRead],
    status_code=status.HTTP_200_OK,
)
def list_event_assignments(db: Session = Depends(get_db)) -> Sequence[EventAssignment]:
    """List assignments ordered by id — the stable baseline read."""
    return db.scalars(
        select(EventAssignment)
        # Only the responsibility is embedded in the read shape; event and
        # person are referenced by id and must not be eagerly loaded.
        .options(selectinload(EventAssignment.responsibility))
        .order_by(EventAssignment.id)
    ).all()


@router.get(
    "/event-assignments/{assignment_id}",
    response_model=EventAssignmentRead,
    status_code=status.HTTP_200_OK,
)
def get_event_assignment(
    assignment_id: UUID, db: Session = Depends(get_db)
) -> EventAssignment:
    """Return one assignment by id (§4b rule 4: not-found resource → 404)."""
    assignment = db.scalar(
        select(EventAssignment)
        .where(EventAssignment.id == assignment_id)
        .options(selectinload(EventAssignment.responsibility))
    )
    if assignment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event assignment not found",
        )
    return assignment


@router.post(
    "/event-assignments",
    response_model=EventAssignmentRead,
    status_code=status.HTTP_201_CREATED,
)
def create_event_assignment(
    payload: EventAssignmentCreate, db: Session = Depends(get_db)
) -> EventAssignment:
    """Create an assignment (row exists; approval stays PENDING), docs/06 §4d."""
    try:
        return assignments_service.create_event_assignment(db, payload)
    except assignments_service.EventNotFoundError as exc:
        # §4b rule 4: not-found *resource* → 404 with human-readable detail.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        ) from exc
    except assignments_service.PersonNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Person not found",
        ) from exc
    except assignments_service.UnknownResponsibilityError as exc:
        # §4b rule 3: request content violates domain reference data → 422.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
