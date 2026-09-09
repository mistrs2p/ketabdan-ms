"""Events endpoints (docs/06 §4c).

Creation delegates to ``app.services.events`` (write-endpoint precedent,
docs/06 §3 rule 4); the router stays translation-only. There is no
read endpoint yet — `EventRead` here is the read shape the future
`GET /api/events` will reuse, fixed by the creation contract.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Event
from app.schemas.event import EventCreate, EventRead
from app.services import events as events_service

router = APIRouter(prefix="/api", tags=["events"])


@router.post(
    "/events",
    response_model=EventRead,
    status_code=status.HTTP_201_CREATED,
)
def create_event(payload: EventCreate, db: Session = Depends(get_db)) -> Event:
    """Create an event (always `DRAFT`), atomically (docs/06 §4c)."""
    return events_service.create_event(db, payload)
