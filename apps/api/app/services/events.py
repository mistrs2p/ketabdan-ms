"""Event service — creation logic for `POST /api/events` (docs/06 §4c).

The insert itself is a single row, but creation carries a domain
invariant the router must not own: a newly created event is **always
`DRAFT`** (docs/03 §5.4 default; whether creation may ever start in
another status is TBD-D28). Status is therefore never passed in — the
model default is the only source. When event status transitions are
decided (TBD-D7/D23), their logic lands here too, next to creation.
"""

from sqlalchemy.orm import Session

from app.models import Event
from app.schemas.event import EventCreate


def create_event(db: Session, payload: EventCreate) -> Event:
    """Create an event in `DRAFT`; returns the persisted row.

    Only title/type/planned_at are written (docs/06 §4c): `id` and audit
    timestamps are system-managed; assignments and reports are never part
    of creation (own entities, TBD-D8/D10/D11; report is post-event, D-003).
    """
    event = Event(
        title=payload.title,
        type=payload.type,
        planned_at=payload.planned_at,
        # status intentionally not passed: the model default (DRAFT) is
        # the single source of the initial status (TBD-D28).
    )
    db.add(event)
    db.commit()
    return event
