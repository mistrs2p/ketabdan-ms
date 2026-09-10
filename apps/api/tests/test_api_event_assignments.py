"""API tests for the event-assignment creation endpoint.

Same approach as the persons tests (docs/06 §5): the shared `client`
fixture runs the full HTTP stack against the in-memory SQLite session.
Reference rows (the six responsibilities seeded by Alembic migration
0003, D-004) are created directly in the test session — they mirror the
seeded reference data, but the endpoint itself reads whatever is in the
database.

The tests lock the §4d contract: response shape, always-PENDING creation,
the three reference-resolution failure classes (404/404/422 per the
error policy §4b), atomicity, and the explicitly-not-checked TBDs.
"""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Event, EventAssignment, EventResponsibility, Person


@pytest.fixture()
def client(authed_client: TestClient) -> TestClient:
    """The event-assignment endpoints require permissions (docs/06 §4g) —
    every test in this module calls them as an admin-privileged user."""
    return authed_client


# A well-formed UUID that matches no row (unknown-but-valid resource).
GHOST_UUID = "12345678-1234-4123-8123-123456789abc"


def make_responsibility(code: str, name: str) -> EventResponsibility:
    return EventResponsibility(code=code, name=name)


def seed_fixture(session: Session) -> tuple[Event, Person, EventResponsibility]:
    """One event, one person, one responsibility — the minimal assignment triple."""
    event = Event(
        title="Book analysis",
        type="book analysis",
        planned_at=datetime(2026, 9, 19, 17, 0, tzinfo=UTC),
    )
    person = Person(name="Zahra")
    responsibility = make_responsibility("registration", "Registration")
    session.add_all([event, person, responsibility])
    session.commit()
    return event, person, responsibility


class TestCreateEventAssignment:
    """POST /api/event-assignments — the creation contract (docs/06 §4d)."""

    def test_create_assignment_returns_contract_shape(
        self, client: TestClient, session: Session
    ) -> None:
        event, person, responsibility = seed_fixture(session)

        response = client.post(
            "/api/event-assignments",
            json={
                "event_id": str(event.id),
                "person_id": str(person.id),
                "responsibility": "registration",
            },
        )

        assert response.status_code == 201
        body = response.json()
        # Exactly the §4d response shape — no audit columns, no embedded
        # event/person.
        assert set(body) == {
            "id",
            "event_id",
            "person_id",
            "responsibility",
            "approval_status",
        }
        assert body["event_id"] == str(event.id)
        assert body["person_id"] == str(person.id)
        assert body["responsibility"] == {
            "id": str(responsibility.id),
            "code": "registration",
            "name": "Registration",
            "active": True,
        }
        # Creation always produces the provisional default (TBD-D10/A6).
        assert body["approval_status"] == "PENDING"
        # Persisted exactly once, with the resolved reference.
        persisted = session.scalars(select(EventAssignment)).all()
        assert len(persisted) == 1
        assert persisted[0].responsibility_id == responsibility.id

    def test_create_assignment_ignores_supplied_approval_status(
        self, client: TestClient, session: Session
    ) -> None:
        # §4d: approval_status is not part of the request; a supplied value
        # is ignored like any other unknown field (the §4c status precedent).
        event, person, _ = seed_fixture(session)

        response = client.post(
            "/api/event-assignments",
            json={
                "event_id": str(event.id),
                "person_id": str(person.id),
                "responsibility": "registration",
                "approval_status": "APPROVED",
            },
        )

        assert response.status_code == 201
        assert response.json()["approval_status"] == "PENDING"

    def test_unknown_event_is_404_resource_not_found(
        self, client: TestClient, session: Session
    ) -> None:
        # §4b rule 4: unknown-but-valid UUID → 404 with detail string.
        _, person, _ = seed_fixture(session)

        response = client.post(
            "/api/event-assignments",
            json={
                "event_id": GHOST_UUID,
                "person_id": str(person.id),
                "responsibility": "registration",
            },
        )

        assert response.status_code == 404
        assert response.json() == {"detail": "Event not found"}
        assert session.scalars(select(EventAssignment)).all() == []

    def test_unknown_person_is_404_resource_not_found(
        self, client: TestClient, session: Session
    ) -> None:
        event, _, _ = seed_fixture(session)

        response = client.post(
            "/api/event-assignments",
            json={
                "event_id": str(event.id),
                "person_id": GHOST_UUID,
                "responsibility": "registration",
            },
        )

        assert response.status_code == 404
        assert response.json() == {"detail": "Person not found"}
        assert session.scalars(select(EventAssignment)).all() == []

    def test_unknown_responsibility_code_is_422_domain_content(
        self, client: TestClient, session: Session
    ) -> None:
        # §4b rule 3: content that violates domain reference data → 422,
        # human-readable string detail naming the unknown code.
        event, person, _ = seed_fixture(session)

        response = client.post(
            "/api/event-assignments",
            json={
                "event_id": str(event.id),
                "person_id": str(person.id),
                "responsibility": "ghost",
            },
        )

        assert response.status_code == 422
        assert response.json()["detail"] == "Unknown responsibility code: ghost"
        # Atomicity: nothing was written.
        assert session.scalars(select(EventAssignment)).all() == []

    def test_malformed_uuid_is_fastapi_default_422(
        self, client: TestClient
    ) -> None:
        # Type-level validation stays the framework default (§4b rule 2):
        # a non-UUID event_id is a structured validation error.
        response = client.post(
            "/api/event-assignments",
            json={
                "event_id": "not-a-uuid",
                "person_id": GHOST_UUID,
                "responsibility": "registration",
            },
        )

        assert response.status_code == 422
        assert isinstance(response.json()["detail"], list)

    def test_missing_fields_are_fastapi_default_422(
        self, client: TestClient
    ) -> None:
        response = client.post("/api/event-assignments", json={})

        assert response.status_code == 422
        detail = response.json()["detail"]
        assert isinstance(detail, list)
        assert {tuple(item["loc"]) for item in detail} == {
            ("body", "event_id"),
            ("body", "person_id"),
            ("body", "responsibility"),
        }

    def test_inactive_person_is_accepted_as_given(
        self, client: TestClient, session: Session
    ) -> None:
        # TBD-D3 is carried, not interpreted: the contract neither rejects
        # nor promises anything about inactive persons.
        event, _, _ = seed_fixture(session)
        person = Person(name="Reza", active=False)
        session.add(person)
        session.commit()

        response = client.post(
            "/api/event-assignments",
            json={
                "event_id": str(event.id),
                "person_id": str(person.id),
                "responsibility": "registration",
            },
        )

        assert response.status_code == 201
        assert session.scalars(select(EventAssignment)).one().person.active is False

    def test_cancelled_event_is_accepted_as_given(
        self, client: TestClient, session: Session
    ) -> None:
        # TBD-D29 is carried, not interpreted: no event-status precondition
        # exists; the contract accepts any existing event.
        event, person, _ = seed_fixture(session)
        event.status = "CANCELLED"
        session.commit()

        response = client.post(
            "/api/event-assignments",
            json={
                "event_id": str(event.id),
                "person_id": str(person.id),
                "responsibility": "registration",
            },
        )

        assert response.status_code == 201

    def test_inactive_responsibility_is_accepted_as_given(
        self, client: TestClient, session: Session
    ) -> None:
        # TBD-D30 is carried, not interpreted: whether retired
        # responsibilities may be referenced stays open.
        event, person, _ = seed_fixture(session)
        retired = EventResponsibility(code="follow_up", name="Follow-up", active=False)
        session.add(retired)
        session.commit()

        response = client.post(
            "/api/event-assignments",
            json={
                "event_id": str(event.id),
                "person_id": str(person.id),
                "responsibility": "follow_up",
            },
        )

        assert response.status_code == 201
        assert response.json()["responsibility"]["active"] is False

    def test_duplicate_triple_creates_second_row(
        self, client: TestClient, session: Session
    ) -> None:
        # TBD-D11 is carried, not interpreted: no UNIQUE constraint exists
        # (docs/03 §5.6), so a repeated POST creates a second row. This
        # locks the *current* schema-permitted behavior, explicitly not a
        # business rule — when D11 resolves, this test changes with it.
        event, person, _ = seed_fixture(session)

        for _ in range(2):
            response = client.post(
                "/api/event-assignments",
                json={
                    "event_id": str(event.id),
                    "person_id": str(person.id),
                    "responsibility": "registration",
                },
            )
            assert response.status_code == 201

        assert len(session.scalars(select(EventAssignment)).all()) == 2


class TestListEventAssignments:
    """GET /api/event-assignments — the list read (docs/06 §4d)."""

    def test_list_returns_empty_array_when_table_empty(
        self, client: TestClient
    ) -> None:
        response = client.get("/api/event-assignments")

        assert response.status_code == 200
        assert response.json() == []

    def test_list_returns_assignmentread_items_ordered_by_id(
        self, client: TestClient, session: Session
    ) -> None:
        event, person, responsibility = seed_fixture(session)
        assignment = EventAssignment(
            event_id=event.id,
            person_id=person.id,
            responsibility_id=responsibility.id,
        )
        session.add(assignment)
        session.commit()
        first_id = assignment.id

        # A second assignment on a different event, created afterwards so
        # the id ordering is exercised (UUIDs are random — insert-order
        # independence is checked by sorting whatever ids exist).
        second_event = Event(
            title="Gathering",
            type="gathering",
            planned_at=datetime(2026, 9, 26, 17, 0, tzinfo=UTC),
        )
        session.add(second_event)
        session.commit()
        second = EventAssignment(
            event_id=second_event.id,
            person_id=person.id,
            responsibility_id=responsibility.id,
        )
        session.add(second)
        session.commit()

        response = client.get("/api/event-assignments")

        assert response.status_code == 200
        body = response.json()
        assert len(body) == 2
        for item in body:
            # Exactly the EventAssignmentRead shape — reused, not a
            # competing schema; no audit columns, no embedded event/person.
            assert set(item) == {
                "id",
                "event_id",
                "person_id",
                "responsibility",
                "approval_status",
            }
        # Deterministic ordering by id ASC (no business sort documented).
        assert [item["id"] for item in body] == sorted(
            [str(first_id), str(second.id)]
        )


class TestGetEventAssignment:
    """GET /api/event-assignments/{assignment_id} — the single read."""

    def test_get_returns_assignmentread_shape(
        self, client: TestClient, session: Session
    ) -> None:
        event, person, responsibility = seed_fixture(session)
        assignment = EventAssignment(
            event_id=event.id,
            person_id=person.id,
            responsibility_id=responsibility.id,
        )
        session.add(assignment)
        session.commit()

        response = client.get(f"/api/event-assignments/{assignment.id}")

        assert response.status_code == 200
        body = response.json()
        assert set(body) == {
            "id",
            "event_id",
            "person_id",
            "responsibility",
            "approval_status",
        }
        assert body["id"] == str(assignment.id)
        assert body["event_id"] == str(event.id)
        assert body["person_id"] == str(person.id)
        assert body["responsibility"]["id"] == str(responsibility.id)
        assert body["responsibility"]["code"] == "registration"
        assert body["approval_status"] == "PENDING"

    def test_unknown_uuid_is_404_resource_not_found(
        self, client: TestClient
    ) -> None:
        response = client.get(f"/api/event-assignments/{GHOST_UUID}")

        assert response.status_code == 404
        assert response.json() == {"detail": "Event assignment not found"}

    def test_malformed_uuid_is_fastapi_default_422(
        self, client: TestClient
    ) -> None:
        response = client.get("/api/event-assignments/not-a-uuid")

        assert response.status_code == 422
        assert isinstance(response.json()["detail"], list)
