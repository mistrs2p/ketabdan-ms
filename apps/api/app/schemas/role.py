"""Role API schemas.

The roles endpoint is read-only reference data (docs/03 §5.2): `code` and
`name` are the whole business payload. Audit timestamps are not exposed —
they are not part of any confirmed requirement.
"""

from uuid import UUID

from pydantic import BaseModel, ConfigDict


class RoleRead(BaseModel):
    """A permanent organizational role, as returned by ``GET /api/roles``."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
