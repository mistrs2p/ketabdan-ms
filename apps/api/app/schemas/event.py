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

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EventCreate(BaseModel):
    """Request body for ``POST /api/events`` (docs/06 §4c)."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "title": "Weekly book club session",
                    "type": "book-club",
                    "planned_at": "2026-09-19T17:00:00+03:30",
                }
            ]
        }
    )

    title: str = Field(description="Event title. Rules are TBD-D25 (free text).")
    type: str = Field(
        description="Event type. Free text — the taxonomy is TBD-D5/D26, "
        "so no allowed-value list is enforced. Example value only."
    )
    planned_at: datetime = Field(
        description="Planned instant. **Must be timezone-aware** (include "
        'an offset, e.g. "2026-09-19T17:00:00+03:30"); naive datetimes '
        "are rejected with 422. Past values are accepted (TBD-D27)."
    )

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

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                    "title": "Weekly book club session",
                    "type": "book-club",
                    "planned_at": "2026-09-19T17:00:00+03:30",
                    "status": "DRAFT",
                }
            ]
        },
    )

    id: UUID = Field(description="Stable identifier of the event.")
    title: str = Field(description="Event title.")
    type: str = Field(description="Event type as stored.")
    planned_at: datetime = Field(
        description="Planned instant (timezone-aware)."
    )
    status: str = Field(
        description="Event status. Creation always produces `DRAFT`; "
        "no status transition exists yet (schema default TBD-D28)."
    )
