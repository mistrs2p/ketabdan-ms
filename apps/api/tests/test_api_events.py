"""API tests for the events endpoint.

Same approach as the persons tests (docs/06 §5): the shared `client`
fixture runs the full HTTP stack against the in-memory SQLite session.
These tests lock the Event creation contract (docs/06 §4c): required
title/type/planned_at, always-DRAFT status, timezone-aware instants only,
and nothing else written.
"""

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Event, EventAssignment

PLANNED_AT = "2026-09-19T17:00:00+03:30"


def parsed(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def test_create_minimal_event(client: TestClient, session: Session) -> None:
    response = client.post(
        "/api/events",
        json={"title": "Weekly Introduction", "type": "introduction", "planned_at": PLANNED_AT},
    )

    assert response.status_code == 201
    body = response.json()
    # Exactly the five business fields — no audit columns, no relations.
    assert set(body) == {"id", "title", "type", "planned_at", "status"}
    assert body["title"] == "Weekly Introduction"
    assert body["type"] == "introduction"
    assert body["status"] == "DRAFT"
    # Same instant (compare parsed values, not strings: the stored offset
    # may be normalized while the instant is identical).
    assert parsed(body["planned_at"]) == parsed(PLANNED_AT)
    # Persisted exactly once, with the schema default status.
    persisted = session.scalars(select(Event)).all()
    assert len(persisted) == 1
    assert persisted[0].status == "DRAFT"


def test_create_event_round_trips_timezone_aware_instant(
    client: TestClient, session: Session
) -> None:
    utc_value = "2026-12-05T13:30:00+00:00"
    response = client.post(
        "/api/events",
        json={"title": "Gathering", "type": "gathering", "planned_at": utc_value},
    )

    assert response.status_code == 201
    stored = parsed(response.json()["planned_at"])
    assert stored == datetime(2026, 12, 5, 13, 30, tzinfo=timezone.utc)
    assert stored.utcoffset() is not None  # never a naive datetime
    # (DB-read-back awareness is a PostgreSQL guarantee — timestamptz —
    # verified by the live check; SQLite returns naive datetimes on read.)


def test_create_event_accepts_past_planned_at(client: TestClient) -> None:
    # Past-date acceptance is TBD-D27 — no rule may reject it yet.
    response = client.post(
        "/api/events",
        json={
            "title": "Past event",
            "type": "class",
            "planned_at": "2020-01-01T10:00:00+03:30",
        },
    )

    assert response.status_code == 201


def test_create_event_rejects_naive_datetime(client: TestClient) -> None:
    response = client.post(
        "/api/events",
        json={"title": "X", "type": "class", "planned_at": "2026-09-19T17:00:00"},
    )

    assert response.status_code == 422
    assert "planned_at" in str(response.json()["detail"])


def test_create_event_rejects_bare_date(client: TestClient) -> None:
    # A bare date parses as midnight *naive* — it must not be silently
    # interpreted as local time (docs/06 §4c).
    response = client.post(
        "/api/events",
        json={"title": "X", "type": "class", "planned_at": "2026-09-19"},
    )

    assert response.status_code == 422


def test_create_event_requires_title_type_and_planned_at(
    client: TestClient,
) -> None:
    payload = {"title": "X", "type": "class", "planned_at": PLANNED_AT}
    for field in ("title", "type", "planned_at"):
        response = client.post(
            "/api/events", json={k: v for k, v in payload.items() if k != field}
        )
        assert response.status_code == 422, field


def test_create_event_ignores_status_input(client: TestClient, session: Session) -> None:
    # §4c: status is NOT part of the request. Like any unknown field it is
    # ignored (PersonCreate precedent) — the event is DRAFT regardless.
    response = client.post(
        "/api/events",
        json={
            "title": "X",
            "type": "class",
            "planned_at": PLANNED_AT,
            "status": "SCHEDULED",
        },
    )

    assert response.status_code == 201
    assert response.json()["status"] == "DRAFT"
    assert session.scalars(select(Event)).one().status == "DRAFT"


def test_create_event_ignores_assignment_and_report_fields(
    client: TestClient, session: Session
) -> None:
    # Assignments and reports are never part of creation (§4c) — unknown
    # request fields are ignored, and no related rows may appear.
    response = client.post(
        "/api/events",
        json={
            "title": "X",
            "type": "class",
            "planned_at": PLANNED_AT,
            "assignments": [{"person_id": "x", "responsibility_id": "y"}],
            "report": {"content": "never"},
        },
    )

    assert response.status_code == 201
    assert session.scalars(select(EventAssignment)).all() == []
    assert session.scalars(select(Event)).one().report is None
