"""API tests for the persons endpoint.

Same approach as the roles tests (docs/06 §5): the shared `client` fixture
runs the full HTTP stack against the in-memory SQLite session. Roles are
created directly in the test session — they mirror the reference rows seeded
by Alembic migration 0002, but the endpoint itself reads whatever is in the
database.
"""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Person, Role


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
