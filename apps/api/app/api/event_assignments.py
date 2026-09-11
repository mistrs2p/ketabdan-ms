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

Protected since docs/06 §4g: reads require ``assignments:read``,
creation requires ``assignments:create``.
"""

from collections.abc import Sequence
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.auth import GENERIC_401_DETAIL
from app.api.deps import GENERIC_403_DETAIL, require_permission
from app.db.session import get_db
from app.models import EventAssignment
from app.schemas.errors import error_response
from app.schemas.event_assignment import EventAssignmentCreate, EventAssignmentRead
from app.services import authz
from app.services import event_assignments as assignments_service

router = APIRouter(prefix="/api", tags=["Event Assignments"])


@router.get(
    "/event-assignments",
    response_model=list[EventAssignmentRead],
    status_code=status.HTTP_200_OK,
    summary="List event assignments",
    dependencies=[Depends(require_permission(authz.ASSIGNMENTS_READ))],
    responses={
        401: error_response(
            "Not authenticated (missing/invalid/expired token or "
            "inactive user).",
            example_detail=GENERIC_401_DETAIL,
        ),
        403: error_response(
            "Authenticated, but the user lacks the `assignments:read` "
            "permission.",
            example_detail=GENERIC_403_DETAIL,
        ),
    },
)
def list_event_assignments(db: Session = Depends(get_db)) -> Sequence[EventAssignment]:
    """List assignments ordered by id — the stable baseline read.

    Requires the **`assignments:read`** permission. The responsibility
    is embedded as its full reference object; event and person are
    referenced by id only.
    """
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
    summary="Get one event assignment",
    dependencies=[Depends(require_permission(authz.ASSIGNMENTS_READ))],
    responses={
        401: error_response(
            "Not authenticated (missing/invalid/expired token or "
            "inactive user).",
            example_detail=GENERIC_401_DETAIL,
        ),
        403: error_response(
            "Authenticated, but the user lacks the `assignments:read` "
            "permission.",
            example_detail=GENERIC_403_DETAIL,
        ),
        404: error_response(
            "No assignment exists with the given id.",
            example_detail="Event assignment not found",
        ),
    },
)
def get_event_assignment(
    assignment_id: UUID = Path(description="Id of the assignment to fetch."),
    db: Session = Depends(get_db),
) -> EventAssignment:
    """Return one assignment by id (§4b rule 4: not-found resource → 404).

    Requires the **`assignments:read`** permission.
    """
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
    summary="Create an event assignment",
    dependencies=[Depends(require_permission(authz.ASSIGNMENTS_CREATE))],
    responses={
        401: error_response(
            "Not authenticated (missing/invalid/expired token or "
            "inactive user).",
            example_detail=GENERIC_401_DETAIL,
        ),
        403: error_response(
            "Authenticated, but the user lacks the `assignments:create` "
            "permission.",
            example_detail=GENERIC_403_DETAIL,
        ),
        404: {
            "description": (
                "The referenced event or person does not exist — the "
                "detail names which one."
            ),
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/ErrorDetail"},
                    "examples": {
                        "event": {"value": {"detail": "Event not found"}},
                        "person": {"value": {"detail": "Person not found"}},
                    },
                }
            },
        },
        422: {
            "description": (
                "Validation failure (Pydantic's structured detail list), "
                "or an unknown responsibility code (plain string detail) — "
                "domain reference violations share the validation status "
                "family (docs/06 §4b rule 3)."
            ),
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Unknown responsibility code: ghost"
                    }
                }
            },
        },
    },
)
def create_event_assignment(
    payload: EventAssignmentCreate, db: Session = Depends(get_db)
) -> EventAssignment:
    """Create an assignment (row exists; approval stays PENDING), docs/06 §4d.

    Requires the **`assignments:create`** permission. The event, person,
    and responsibility references are resolved server-side: an unknown
    event or person → 404, an unknown responsibility code → 422, and
    nothing is written on failure. An `approval_status` sent in the
    body is ignored — creation always produces the provisional
    `PENDING` default (the approval flow §4e is not implemented yet).
    """
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
