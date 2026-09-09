"""Event API schemas.

`EventCreate` is the request contract for `POST /api/events`
(docs/06 §4c): title, type, and a timezone-aware planned_at are required;
`status` is deliberately absent — creation always produces `DRAFT`
(schema default, TBD-D28 open) and the input field is ignored if sent,
like any other unknown field.

`EventRead` is the events read shape fixed by the same contract: the five
business fields, no audit columns (docs/06 §3 rule 2).

No validation rules beyond presence/types/awareness: title rules are
TBD-D25, type acceptance is TBD-D26 (taxonomy TBD-D5 — free text, no
allowed-value list), past planned_at is TBD-D27 (accepted until decided),
and recurrence (TBD-D6) is not modeled.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator


class EventCreate(BaseModel):
    """Request body for ``POST /api/events`` (docs/06 §4c)."""

    title: str
    type: str
    planned_at: datetime

    @field_validator("planned_at")
    @classmethod
    def _must_be_timezone_aware(cls, value: datetime) -> datetime:
        """Reject naive datetimes and bare dates — they must not be
        silently interpreted as local time (docs/03 §4: business
        datetimes are always timezone-aware instants)."""
        if value.tzinfo is None:
            raise ValueError(
                "planned_at must include a timezone offset "
                '(e.g. "2026-09-19T17:00:00+03:30")'
            )
        return value


class EventRead(BaseModel):
    """An event, as returned by event endpoints (docs/06 §4c)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    type: str
    planned_at: datetime
    status: str
