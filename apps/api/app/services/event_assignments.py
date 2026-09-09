"""EventAssignment service — creation logic for
`POST /api/event-assignments` (docs/06 §4d).

The insert itself is a single row, but creation carries reference
resolution the router must not own: `event_id`/`person_id` must match
existing rows (not-found resources), and `responsibility` is a code that
must resolve against the seeded reference data (D-004, migration `0003`).
Existence-vs-approval stays separate: the row *is* the assignment;
`approval_status` is never passed in — the model default (`PENDING`,
PROVISIONAL per TBD-D10/A6) is the single source.

Carried as explicit open questions (docs/06 §4d — none may be encoded as
a rule): person active/inactive (TBD-D3), role restrictions (TBD-D8),
duplicate triples (TBD-D11 — no UNIQUE constraint exists; a second POST
of the same triple creates a second row), event-status preconditions
(TBD-D29), inactive-responsibility acceptance (TBD-D30).
"""

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Event, EventAssignment, EventResponsibility, Person
from app.schemas.event_assignment import EventAssignmentCreate


class UnknownResponsibilityError(ValueError):
    """A requested responsibility code does not exist in the reference data."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(f"Unknown responsibility code: {code}")


class EventNotFoundError(LookupError):
    """The referenced event does not exist."""

    def __init__(self, event_id: str) -> None:
        self.event_id = event_id
        super().__init__(f"Event not found: {event_id}")


class PersonNotFoundError(LookupError):
    """The referenced person does not exist."""

    def __init__(self, person_id: str) -> None:
        self.person_id = person_id
        super().__init__(f"Person not found: {person_id}")


def create_event_assignment(
    db: Session, payload: EventAssignmentCreate
) -> EventAssignment:
    """Create an EventAssignment; returns the persisted row.

    Resolves the three references first and raises before any write when
    one is unknown (atomicity, docs/06 §4d): missing event/person →
    ``EventNotFoundError``/``PersonNotFoundError`` (404 at the router,
    §4b rule 4); unknown responsibility code →
    ``UnknownResponsibilityError`` (422, §4b rule 3). No other check
    exists — every other assignment semantic is TBD (module docstring).
    """
    if db.get(Event, payload.event_id) is None:
        raise EventNotFoundError(str(payload.event_id))
    if db.get(Person, payload.person_id) is None:
        raise PersonNotFoundError(str(payload.person_id))

    responsibility = db.scalar(
        select(EventResponsibility).where(
            EventResponsibility.code == payload.responsibility
        )
    )
    if responsibility is None:
        raise UnknownResponsibilityError(payload.responsibility)

    assignment = EventAssignment(
        event_id=payload.event_id,
        person_id=payload.person_id,
        responsibility_id=responsibility.id,
        # approval_status intentionally not passed: the model default
        # (PENDING) is the single source (TBD-D10/A6).
    )
    db.add(assignment)
    db.commit()
    # Eager-load the responsibility so EventAssignmentRead serializes it
    # without a lazy load after the commit closed the old instance state.
    return db.scalar(
        select(EventAssignment)
        .where(EventAssignment.id == assignment.id)
        .options(selectinload(EventAssignment.responsibility))
    )
