"""Events endpoints (docs/06 §4c).

Reads are direct queries (docs/06 §3 rule 4); creation delegates to
``app.services.events`` because it carries the always-DRAFT invariant.
`EventRead` is the single events read shape, fixed by the creation
contract — listing and single-event reads reuse it, so the endpoints
cannot diverge.

Protected since docs/06 §4g: reads require ``events:read``, creation
requires ``events:create``.
"""

from collections.abc import Sequence
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth import GENERIC_401_DETAIL
from app.api.deps import GENERIC_403_DETAIL, require_permission
from app.db.session import get_db
from app.models import Event
from app.schemas.errors import error_response
from app.schemas.event import EventCreate, EventRead
from app.services import authz
from app.services import events as events_service

router = APIRouter(prefix="/api", tags=["Events"])


@router.get(
    "/events",
    response_model=list[EventRead],
    status_code=status.HTTP_200_OK,
    summary="List events",
    dependencies=[Depends(require_permission(authz.EVENTS_READ))],
    responses={
        401: error_response(
            "Not authenticated (missing/invalid/expired token or "
            "inactive user).",
            example_detail=GENERIC_401_DETAIL,
        ),
        403: error_response(
            "Authenticated, but the user lacks the `events:read` "
            "permission.",
            example_detail=GENERIC_403_DETAIL,
        ),
    },
)
def list_events(db: Session = Depends(get_db)) -> Sequence[Event]:
    """List events ordered by planned time, then id — the calendar read.

    Requires the **`events:read`** permission. All statuses are
    included; there is no filter yet.
    """
    return db.scalars(select(Event).order_by(Event.planned_at, Event.id)).all()


@router.get(
    "/events/{event_id}",
    response_model=EventRead,
    status_code=status.HTTP_200_OK,
    summary="Get one event",
    dependencies=[Depends(require_permission(authz.EVENTS_READ))],
    responses={
        401: error_response(
            "Not authenticated (missing/invalid/expired token or "
            "inactive user).",
            example_detail=GENERIC_401_DETAIL,
        ),
        403: error_response(
            "Authenticated, but the user lacks the `events:read` "
            "permission.",
            example_detail=GENERIC_403_DETAIL,
        ),
        404: error_response(
            "No event exists with the given id.",
            example_detail="Event not found",
        ),
    },
)
def get_event(
    event_id: UUID = Path(description="Id of the event to fetch."),
    db: Session = Depends(get_db),
) -> Event:
    """Return one event by id (§4b rule 4: not-found resource → 404).

    Requires the **`events:read`** permission.
    """
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )
    return event


@router.post(
    "/events",
    response_model=EventRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create an event",
    dependencies=[Depends(require_permission(authz.EVENTS_CREATE))],
    responses={
        401: error_response(
            "Not authenticated (missing/invalid/expired token or "
            "inactive user).",
            example_detail=GENERIC_401_DETAIL,
        ),
        403: error_response(
            "Authenticated, but the user lacks the `events:create` "
            "permission.",
            example_detail=GENERIC_403_DETAIL,
        ),
        422: {
            "description": (
                "Validation failure (Pydantic's structured detail list) — "
                "e.g. a missing field, or a `planned_at` without a "
                "timezone offset."
            ),
            "content": {
                "application/json": {
                    "example": {
                        "detail": [
                            {
                                "type": "value_error",
                                "loc": ["body", "planned_at"],
                                "msg": "Value error, planned_at must "
                                "include a timezone offset (e.g. "
                                '"2026-09-19T17:00:00+03:30")',
                            }
                        ]
                    }
                }
            },
        },
    },
)
def create_event(payload: EventCreate, db: Session = Depends(get_db)) -> Event:
    """Create an event (always `DRAFT`), atomically (docs/06 §4c).

    Requires the **`events:create`** permission. A `status` sent in the
    body is ignored — creation always produces the `DRAFT` default; no
    status transition exists yet. `planned_at` must be timezone-aware.
    """
    return events_service.create_event(db, payload)
