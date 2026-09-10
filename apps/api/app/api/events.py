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

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.db.session import get_db
from app.models import Event
from app.schemas.event import EventCreate, EventRead
from app.services import authz
from app.services import events as events_service

router = APIRouter(prefix="/api", tags=["events"])


@router.get(
    "/events",
    response_model=list[EventRead],
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_permission(authz.EVENTS_READ))],
)
def list_events(db: Session = Depends(get_db)) -> Sequence[Event]:
    """List events ordered by planned time, then id — the calendar read."""
    return db.scalars(select(Event).order_by(Event.planned_at, Event.id)).all()


@router.get(
    "/events/{event_id}",
    response_model=EventRead,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_permission(authz.EVENTS_READ))],
)
def get_event(event_id: UUID, db: Session = Depends(get_db)) -> Event:
    """Return one event by id (§4b rule 4: not-found resource → 404)."""
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
    dependencies=[Depends(require_permission(authz.EVENTS_CREATE))],
)
def create_event(payload: EventCreate, db: Session = Depends(get_db)) -> Event:
    """Create an event (always `DRAFT`), atomically (docs/06 §4c)."""
    return events_service.create_event(db, payload)
