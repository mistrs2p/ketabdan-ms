"""API tests for the roles endpoint.

Uses the shared `client` fixture (conftest.py): FastAPI's TestClient with
`get_db` overridden by the in-memory SQLite session, so the full HTTP stack
(routing, validation, response serialization) runs without PostgreSQL. The
live PostgreSQL behavior is additionally exercised by running the
application against the real database (docs/06, Validation).
"""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Role

# The six confirmed roles (docs/03 §5.2) — the same set seeded by
# Alembic migration 0002.
CONFIRMED_ROLES: dict[str, str] = {
    "learner": "Learner / Student",
    "supporter": "Supporter",
    "coach": "Coach",
    "teacher": "Teacher",
    "referrer": "Referrer",
    "manager": "Manager",
}


def test_roles_returns_empty_list_when_table_empty(client: TestClient) -> None:
    response = client.get("/api/roles")

    assert response.status_code == 200
    assert response.json() == []


def test_roles_returns_the_six_confirmed_reference_roles(
    client: TestClient, session: Session
) -> None:
    session.add_all(
        Role(code=code, name=name) for code, name in CONFIRMED_ROLES.items()
    )
    session.commit()

    response = client.get("/api/roles")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == len(CONFIRMED_ROLES)
    # Deterministic order (by code) and exact reference values.
    assert [role["code"] for role in body] == sorted(CONFIRMED_ROLES)
    assert {role["code"]: role["name"] for role in body} == CONFIRMED_ROLES
    # Response shape: exactly id / code / name — no leaked audit columns.
    for role in body:
        assert set(role) == {"id", "code", "name"}
        assert role["id"]
