"""Role API schemas.

The roles endpoint is read-only reference data (docs/03 §5.2): `code` and
`name` are the whole business payload. Audit timestamps are not exposed —
they are not part of any confirmed requirement.
"""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RoleRead(BaseModel):
    """A permanent organizational role, as returned by ``GET /api/roles``."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "id": "11111111-1111-1111-1111-111111111111",
                    "code": "learner",
                    "name": "Learner / Student",
                }
            ]
        },
    )

    id: UUID = Field(description="Stable identifier of the role.")
    code: str = Field(
        description="Stable machine code (e.g. `learner`, `supporter`, "
        "`coach`, `teacher`, `referrer`, `manager`)."
    )
    name: str = Field(description="Human-readable name.")
