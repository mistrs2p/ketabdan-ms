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

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.role import RoleRead


class EventAssignmentCreate(BaseModel):
    """Request body for ``POST /api/event-assignments`` (docs/06 §4d)."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "event_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                    "person_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
                    "responsibility": "registration",
                }
            ]
        }
    )

    event_id: UUID = Field(
        description="Id of an existing event (→ 404 when it does not exist)."
    )
    person_id: UUID = Field(
        description="Id of an existing person (→ 404 when it does not exist)."
    )
    responsibility: str = Field(
        description="Machine code of an event responsibility (seeded "
        "reference data — e.g. `pre_introduction`, `welcome_reception`, "
        "`technique_execution`, `persuasion`, `registration`, "
        "`follow_up`). An unknown code is a domain error → 422."
    )


class EventResponsibilityRead(BaseModel):
    """An event responsibility, as referenced by assignment endpoints."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "id": "22222222-2222-2222-2222-222222222222",
                    "code": "registration",
                    "name": "Registration",
                    "active": True,
                }
            ]
        },
    )

    id: UUID = Field(description="Stable identifier of the responsibility.")
    code: str = Field(description="Stable machine code of the responsibility.")
    name: str = Field(description="Human-readable name.")
    active: bool = Field(description="Whether the responsibility is active.")


class EventAssignmentRead(BaseModel):
    """An assignment, as returned by assignment endpoints (docs/06 §4d)."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                    "event_id": "9b2f6a1e-0c3d-4e5f-8a7b-6c5d4e3f2a1b",
                    "person_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
                    "responsibility": {
                        "id": "22222222-2222-2222-2222-222222222222",
                        "code": "registration",
                        "name": "Registration",
                        "active": True,
                    },
                    "approval_status": "PENDING",
                }
            ]
        },
    )

    id: UUID = Field(description="Stable identifier of the assignment.")
    event_id: UUID = Field(
        description="The assigned event, referenced by id (not embedded)."
    )
    person_id: UUID = Field(
        description="The assigned person, referenced by id (not embedded)."
    )
    responsibility: EventResponsibilityRead = Field(
        description="The assigned responsibility as the full reference "
        "object `{id, code, name, active}`."
    )
    approval_status: str = Field(
        description="Approval state. Creation always produces the "
        "provisional `PENDING` default; the approval flow (§4e) is "
        "defined but not implemented yet."
    )
