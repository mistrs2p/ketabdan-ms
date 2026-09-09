"""Person API schemas.

`PersonRead` exposes the confirmed person attributes (docs/03 §5.1): name
(structure TBD-D1 — single field, no parts invented), phone (nullable,
uniqueness TBD-D2), active (semantics TBD-D3 — surfaced, not interpreted),
plus the person's permanent roles (D-001). Roles reuse `RoleRead` — they are
the same reference data served by `GET /api/roles`. Audit timestamps are not
exposed; assignments/reports belong to their own future endpoints.
"""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

from app.schemas.role import RoleRead


class PersonRead(BaseModel):
    """A branch member, as returned by ``GET /api/persons``."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    phone: str | None
    active: bool
    roles: list[RoleRead]

    @field_validator("roles")
    @classmethod
    def _deterministic_role_order(cls, roles: list[RoleRead]) -> list[RoleRead]:
        """Sort roles by code — stable responses regardless of load order."""
        return sorted(roles, key=lambda role: role.code)
