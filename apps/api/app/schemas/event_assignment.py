"""EventAssignment API schemas.

`EventAssignmentCreate` is the request contract for
`POST /api/event-assignments` (docs/06 §4d): the three references are
required; `approval_status` is deliberately absent — creation always
produces the provisional `PENDING` default (TBD-D10/A6) and the input
field is ignored if sent, like any other unknown field.

`EventAssignmentRead` is the assignment read shape fixed by the same
contract: the three references plus `approval_status`, no audit columns
(docs/06 §3 rule 2). The responsibility is echoed as the full
reference-data object (`{id, code, name, active}` — the
EventResponsibility counterpart of `RoleRead`), symmetric with the
persons pattern (`PersonRead.roles`); `event`/`person` are not embedded —
they are identified by id and served by their own endpoints.

No validation rules beyond presence/types: unknown references are domain
errors (404/422 per the error policy), not schema rules; the remaining
assignment semantics (D3, D8, D11, D29, D30) are TBD and not encoded.
"""

from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.schemas.role import RoleRead


class EventAssignmentCreate(BaseModel):
    """Request body for ``POST /api/event-assignments`` (docs/06 §4d)."""

    event_id: UUID
    person_id: UUID
    responsibility: str


class EventResponsibilityRead(BaseModel):
    """An event responsibility, as referenced by assignment endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    active: bool


class EventAssignmentRead(BaseModel):
    """An assignment, as returned by assignment endpoints (docs/06 §4d)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    event_id: UUID
    person_id: UUID
    responsibility: EventResponsibilityRead
    approval_status: str
