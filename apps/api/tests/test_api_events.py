"""API tests for the events endpoints.

Same approach as the persons tests (docs/06 §5): the shared `client`
fixture runs the full HTTP stack against the in-memory SQLite session.
The creation tests lock the Event creation contract (docs/06 §4c):
required title/type/planned_at, always-DRAFT status, timezone-aware
instants only, and nothing else written. The listing tests lock the
calendar-oriented read: the `EventRead` shape, deterministic order, and
status surfaced as stored.
"""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Event, EventAssignment


@pytest.fixture()
def client(authed_client: TestClient) -> TestClient:
    """The events endpoints require permissions (docs/06 §4g) — every
    test in this module calls them as an admin-privileged user."""
    return authed_client


PLANNED_AT = "2026-09-19T17:00:00+03:30"


def parsed(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def make_event(title: str, planned_at: datetime, status: str = "DRAFT") -> Event:
    return Event(title=title, type="class", planned_at=planned_at, status=status)


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


# --- GET /api/events — the calendar-oriented read (docs/06 §4c) ---


def test_events_returns_empty_list_when_table_empty(client: TestClient) -> None:
    response = client.get("/api/events")

    assert response.status_code == 200
    assert response.json() == []


def test_events_shape_exposes_contract_fields(
    client: TestClient, session: Session
) -> None:
    session.add(make_event("Weekly Introduction", parsed(PLANNED_AT)))
    session.commit()

    response = client.get("/api/events")

    assert response.status_code == 200
    (event,) = response.json()
    # Exactly the five business fields (docs/06 §4c) — no audit columns,
    # no assignments/report relations.
    assert set(event) == {"id", "title", "type", "planned_at", "status"}
    assert event["title"] == "Weekly Introduction"
    assert event["type"] == "class"
    assert event["status"] == "DRAFT"
    # Wall-clock equality: SQLite drops the offset on read-back (no
    # timestamptz); the instant round-trip is a PostgreSQL guarantee,
    # verified by the live check.
    assert parsed(event["planned_at"]).replace(tzinfo=None) == parsed(
        PLANNED_AT
    ).replace(tzinfo=None)


def test_events_ordered_by_planned_at_then_id(
    client: TestClient, session: Session
) -> None:
    # Same offset throughout so ordering is unambiguous even where SQLite
    # compares stored values lexically; PostgreSQL orders by true instant.
    first = make_event("First", parsed("2026-09-05T17:00:00+03:30"))
    second = make_event("Second", parsed("2026-09-12T17:00:00+03:30"))
    third = make_event("Third", parsed("2026-09-19T17:00:00+03:30"))
    session.add_all([third, first, second])  # out of order on purpose
    session.commit()

    response = client.get("/api/events")

    assert response.status_code == 200
    assert [event["title"] for event in response.json()] == [
        "First",
        "Second",
        "Third",
    ]


def test_events_order_ties_break_deterministically_by_id(
    client: TestClient, session: Session
) -> None:
    same_instant = parsed(PLANNED_AT)
    session.add_all(
        [make_event("A", same_instant), make_event("B", same_instant)]
    )
    session.commit()

    response = client.get("/api/events")

    assert response.status_code == 200
    returned_ids = [event["id"] for event in response.json()]
    expected = sorted(
        session.scalars(select(Event)).all(), key=lambda e: (e.planned_at, e.id)
    )
    assert returned_ids == [str(event.id) for event in expected]


def test_events_surface_status_as_stored(
    client: TestClient, session: Session
) -> None:
    # Events other than DRAFT cannot exist via the API yet (creation is
    # always DRAFT; transitions are TBD-D7/D23) — rows written directly
    # exercise the read: status is surfaced as stored, not interpreted.
    session.add_all(
        [
            make_event("Planned", parsed("2026-09-05T17:00:00+03:30"), "SCHEDULED"),
            make_event("Off", parsed("2026-09-12T17:00:00+03:30"), "CANCELLED"),
        ]
    )
    session.commit()

    response = client.get("/api/events")

    assert response.status_code == 200
    assert [event["status"] for event in response.json()] == [
        "SCHEDULED",
        "CANCELLED",
    ]


# --- GET /api/events/{event_id} — the single-resource read ---


def test_get_event_returns_the_event_with_contract_fields(
    client: TestClient, session: Session
) -> None:
    event = make_event("Weekly Introduction", parsed(PLANNED_AT))
    session.add(event)
    session.commit()

    response = client.get(f"/api/events/{event.id}")

    assert response.status_code == 200
    body = response.json()
    # Same five business fields as the list — no audit columns, no
    # assignments/report relations.
    assert set(body) == {"id", "title", "type", "planned_at", "status"}
    assert body["id"] == str(event.id)
    assert body["title"] == "Weekly Introduction"
    assert body["type"] == "class"
    assert body["status"] == "DRAFT"


def test_get_event_with_unknown_id_is_404(client: TestClient) -> None:
    # §4b rule 4: a well-formed UUID that matches no event → 404 with the
    # FastAPI-native error body.
    unknown = "11111111-1111-4111-8111-111111111111"

    response = client.get(f"/api/events/{unknown}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Event not found"}


def test_get_event_with_malformed_id_is_default_validation_422(
    client: TestClient,
) -> None:
    # Malformed UUIDs take FastAPI's standard path-parameter validation —
    # no custom handling (§4b rule 2): 422 with the structured detail list.
    response = client.get("/api/events/not-a-uuid")

    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)
    (item,) = response.json()["detail"]
    assert item["type"] == "uuid_parsing"
    assert item["loc"] == ["path", "event_id"]
