"""EventAssignment endpoints (docs/06 §4d).

Creation carries real logic — reference resolution with three distinct
failure classes — so the route delegates to
``app.services.event_assignments`` (docs/06 §3 rule 4) and only
translates its errors into HTTP responses per the error policy (§4b):
not-found resources → 404, unknown domain reference code → 422.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import EventAssignment
from app.schemas.event_assignment import EventAssignmentCreate, EventAssignmentRead
from app.services import event_assignments as assignments_service

router = APIRouter(prefix="/api", tags=["event-assignments"])


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
