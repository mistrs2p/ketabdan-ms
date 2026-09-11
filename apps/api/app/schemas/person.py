"""Person API schemas.

`PersonRead` exposes the confirmed person attributes (docs/03 §5.1): name
(structure TBD-D1 — single field, no parts invented), phone (nullable,
uniqueness TBD-D2), active (semantics TBD-D3 — surfaced, not interpreted),
plus the person's permanent roles (D-001). Roles reuse `RoleRead` — they are
the same reference data served by `GET /api/roles`. Audit timestamps are not
exposed; assignments/reports belong to their own future endpoints.

`PersonCreate` is the request contract for `POST /api/persons`
(docs/06 §4a): name required, everything else optional; roles are given as
the stable machine codes of the seeded reference data.
"""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.role import RoleRead


class PersonCreate(BaseModel):
    """Request body for ``POST /api/persons`` (docs/06 §4a).

    No validation rules beyond presence/types: name structure/length and
    phone format/uniqueness are TBD-D1/TBD-D2 and must not be invented here.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "name": "Zahra Ahmadi",
                    "phone": "09121234567",
                    "active": True,
                    "roles": ["learner", "supporter"],
                }
            ]
        }
    )

    name: str = Field(description="Full display name of the branch member.")
    phone: str | None = Field(
        default=None,
        description="Contact phone. Free text; uniqueness semantics are "
        "TBD-D2. Example value only.",
    )
    active: bool = Field(
        default=True,
        description="Initial active flag. Semantics (e.g. what "
        "deactivation implies) are TBD-D3; the value is stored as given.",
    )
    roles: list[str] = Field(
        default_factory=list,
        description="Machine codes of the permanent roles to attach "
        "(see `GET /api/roles` for the seeded codes). An unknown code "
        "is a domain error → 422.",
    )


class PersonRead(BaseModel):
    """A branch member, as returned by ``GET /api/persons``."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                    "name": "Zahra Ahmadi",
                    "phone": "09121234567",
                    "active": True,
                    "roles": [
                        {"id": "11111111-1111-1111-1111-111111111111",
                         "code": "learner",
                         "name": "Learner / Student"}
                    ],
                }
            ]
        },
    )

    id: UUID = Field(description="Stable identifier of the person.")
    name: str = Field(description="Full display name of the branch member.")
    phone: str | None = Field(description="Contact phone, if recorded.")
    active: bool = Field(description="Current active flag.")
    roles: list[RoleRead] = Field(
        description="The person's permanent organizational roles, ordered "
        "deterministically by role code."
    )

    @field_validator("roles")
    @classmethod
    def _deterministic_role_order(cls, roles: list[RoleRead]) -> list[RoleRead]:
        """Sort roles by code — stable responses regardless of load order."""
        return sorted(roles, key=lambda role: role.code)
