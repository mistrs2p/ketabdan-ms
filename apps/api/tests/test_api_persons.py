"""API tests for the persons endpoints.

Same approach as the roles tests (docs/06 §5): the shared `client` fixture
runs the full HTTP stack against the in-memory SQLite session. Roles are
created directly in the test session — they mirror the reference rows seeded
by Alembic migration 0002, but the endpoints themselves read whatever is in
the database.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Person, PersonRole, Role


@pytest.fixture()
def client(authed_client: TestClient) -> TestClient:
    """The persons endpoints require permissions (docs/06 §4g) — every
    test in this module calls them as an admin-privileged user."""
    return authed_client


def make_role(code: str, name: str) -> Role:
    return Role(code=code, name=name)


def test_persons_returns_empty_list_when_table_empty(client: TestClient) -> None:
    response = client.get("/api/persons")

    assert response.status_code == 200
    assert response.json() == []


def test_person_shape_exposes_confirmed_attributes(
    client: TestClient, session: Session
) -> None:
    session.add(Person(name="Seyed", phone="09120000000"))
    session.commit()

    response = client.get("/api/persons")

    assert response.status_code == 200
    (person,) = response.json()
    # Exactly the confirmed attributes (docs/03 §5.1) — no audit columns,
    # no assignments/reports.
    assert set(person) == {"id", "name", "phone", "active", "roles"}
    assert person["name"] == "Seyed"
    assert person["phone"] == "09120000000"
    assert person["active"] is True
    assert person["roles"] == []


def test_persons_include_roles_and_are_ordered_by_name(
    client: TestClient, session: Session
) -> None:
    # D-001: a person may hold multiple simultaneous roles.
    learner = make_role("learner", "Learner / Student")
    supporter = make_role("supporter", "Supporter")
    manager = make_role("manager", "Manager")
    # Appended out of code order on purpose — the response must be sorted.
    multi = Person(name="Zahra", roles=[supporter, learner])
    coach_only = Person(name="Ali", roles=[manager])
    session.add_all([learner, supporter, manager, multi, coach_only])
    session.commit()

    response = client.get("/api/persons")

    assert response.status_code == 200
    body = response.json()
    assert [person["name"] for person in body] == ["Ali", "Zahra"]

    ali, zahra = body
    assert [role["code"] for role in zahra["roles"]] == ["learner", "supporter"]
    assert [role["code"] for role in ali["roles"]] == ["manager"]
    for role in zahra["roles"] + ali["roles"]:
        assert set(role) == {"id", "code", "name"}


def test_persons_reflect_inactive_state_and_missing_phone(
    client: TestClient, session: Session
) -> None:
    # `active` is surfaced as stored (semantics TBD-D3 — not interpreted);
    # phone is optional (uniqueness TBD-D2).
    session.add(Person(name="Reza", phone=None, active=False))
    session.commit()

    response = client.get("/api/persons")

    assert response.status_code == 200
    (person,) = response.json()
    assert person["active"] is False
    assert person["phone"] is None


class TestCreatePerson:
    """POST /api/persons — the creation contract (docs/06 §4a)."""

    def test_create_minimal_person(self, client: TestClient, session: Session) -> None:
        response = client.post("/api/persons", json={"name": "Seyed"})

        assert response.status_code == 201
        body = response.json()
        assert set(body) == {"id", "name", "phone", "active", "roles"}
        assert body["name"] == "Seyed"
        # Contract defaults: phone absent → null, active → true, roles → [].
        assert body["phone"] is None
        assert body["active"] is True
        assert body["roles"] == []
        # Persisted exactly once.
        persisted = session.scalars(select(Person)).all()
        assert [p.name for p in persisted] == ["Seyed"]

    def test_create_person_with_multiple_roles(
        self, client: TestClient, session: Session
    ) -> None:
        session.add_all(
            [
                make_role("learner", "Learner / Student"),
                make_role("supporter", "Supporter"),
            ]
        )
        session.commit()

        response = client.post(
            "/api/persons",
            json={
                "name": "Zahra",
                "phone": "09120000000",
                "roles": ["supporter", "learner"],
            },
        )

        assert response.status_code == 201
        body = response.json()
        assert body["phone"] == "09120000000"
        # Nested roles sorted by code (PersonRead), both memberships written.
        assert [role["code"] for role in body["roles"]] == ["learner", "supporter"]
        person = session.scalars(select(Person)).one()
        assert len(person.role_links) == 2

    def test_create_person_collapses_duplicate_role_codes(
        self, client: TestClient, session: Session
    ) -> None:
        session.add(make_role("supporter", "Supporter"))
        session.commit()

        response = client.post(
            "/api/persons", json={"name": "Ali", "roles": ["supporter", "supporter"]}
        )

        assert response.status_code == 201
        assert [role["code"] for role in response.json()["roles"]] == ["supporter"]
        person = session.scalars(select(Person)).one()
        assert len(person.role_links) == 1  # a person holds a *set* of roles

    def test_create_person_with_unknown_role_code_writes_nothing(
        self, client: TestClient, session: Session
    ) -> None:
        session.add(make_role("supporter", "Supporter"))
        session.commit()

        response = client.post(
            "/api/persons", json={"name": "Reza", "roles": ["supporter", "ghost"]}
        )

        assert response.status_code == 422
        assert "ghost" in response.json()["detail"]
        # Atomicity: nothing was written, not even a partial person.
        assert session.scalars(select(Person)).all() == []
        assert session.scalars(select(PersonRole)).all() == []

    def test_create_person_requires_name(self, client: TestClient) -> None:
        response = client.post("/api/persons", json={})

        assert response.status_code == 422

    def test_create_person_carries_active_as_given(
        self, client: TestClient, session: Session
    ) -> None:
        # `active` is carried as stored; its business meaning is TBD-D3 and
        # is not interpreted by the endpoint.
        response = client.post(
            "/api/persons", json={"name": "Maryam", "active": False}
        )

        assert response.status_code == 201
        assert response.json()["active"] is False
        assert session.scalars(select(Person)).one().active is False
