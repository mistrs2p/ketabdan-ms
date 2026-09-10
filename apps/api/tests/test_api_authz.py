"""Authorization tests — lock the Phase 5.2 contract (docs/06 §4g).

The matrix in one place: every business route requires a permission;
authentication failures (missing/invalid/expired token, inactive user) are
401, permission denials are 403 with a generic detail, and a user holding
the required permission passes. Seeds are asserted against the migration's
own constants (the way test_api_persons mirrors the 0002 seeds), and the
union semantics across multiple roles are exercised both at the service
level and over HTTP.

All tests run against the in-memory SQLite fixture (conftest.py) — no test
user ever reaches the development PostgreSQL database.
"""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import GENERIC_403_DETAIL
from app.core import security
from app.core.config import get_settings
from app.models import (
    ApplicationRole,
    ApplicationRolePermission,
    EventResponsibility,
    Permission,
    Person,
    User,
)
from app.services import auth as auth_service
from app.services import authz
from conftest import make_user_with_roles

# A well-formed UUID that matches no row (unknown-but-valid resource).
GHOST_UUID = "12345678-1234-4123-8123-123456789abc"
PLANNED_AT = "2026-09-19T17:00:00+03:30"


def auth_header(user: User) -> dict[str, str]:
    """A valid Bearer header for an existing user (token issued directly)."""
    token, _ = auth_service.issue_access_token(user)
    return {"Authorization": f"Bearer {token}"}


# All nine protected business routes (docs/06 §4g). The payloads are valid
# or well-formed-unknown: after the permission gate, whatever status the
# handler returns proves the gate itself passed.
PROTECTED_ROUTES: tuple[tuple[str, str, dict | None], ...] = (
    ("GET", "/api/roles", None),
    ("GET", "/api/persons", None),
    ("POST", "/api/persons", {"name": "Authz Person"}),
    ("GET", "/api/events", None),
    ("GET", f"/api/events/{GHOST_UUID}", None),
    ("POST", "/api/events", {"title": "Authz Event", "type": "class", "planned_at": PLANNED_AT}),
    ("GET", "/api/event-assignments", None),
    ("GET", f"/api/event-assignments/{GHOST_UUID}", None),
    (
        "POST",
        "/api/event-assignments",
        {
            "event_id": GHOST_UUID,
            "person_id": GHOST_UUID,
            "responsibility": "registration",
        },
    ),
)


# --- Authentication on protected routes: always 401 --------------------------


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    PROTECTED_ROUTES,
    ids=[f"{method} {path}" for method, path, _ in PROTECTED_ROUTES],
)
def test_protected_route_without_token_is_401(
    client: TestClient, authz_seeded: None, method: str, path: str, payload: dict | None
) -> None:
    response = client.request(method, path, json=payload)

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_protected_route_with_malformed_token_is_401(
    client: TestClient, authz_seeded: None
) -> None:
    # Even a user-shaped garbage token must not reach the permission check.
    response = client.get(
        "/api/persons", headers={"Authorization": "Bearer not-a-jwt-at-all"}
    )

    assert response.status_code == 401


def test_protected_route_with_expired_token_is_401(
    client: TestClient, session: Session, authz_seeded: None
) -> None:
    # A token for a legitimately privileged user, already expired: expiry
    # is enforced before any authorization decision is made.
    user = make_user_with_roles(session, "expired-admin", role_codes=("admin",))
    expired, _ = security.create_access_token(
        subject=str(user.id),
        secret_key=get_settings().auth_secret_key,
        algorithm=get_settings().auth_algorithm,
        expires_delta=timedelta(seconds=-60),
    )
    response = client.get("/api/roles", headers={"Authorization": f"Bearer {expired}"})

    assert response.status_code == 401


def test_inactive_user_is_401_on_protected_route(
    client: TestClient, session: Session, authz_seeded: None
) -> None:
    # Inactive is an authentication-level rejection (§4f), never a 403 —
    # and never a silent pass despite the held permissions.
    user = make_user_with_roles(session, "gone-admin", role_codes=("admin",))
    user.active = False
    session.commit()

    response = client.get("/api/roles", headers=auth_header(user))

    assert response.status_code == 401


# --- Authorization on protected routes: 403 / success ------------------------


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    PROTECTED_ROUTES,
    ids=[f"{method} {path}" for method, path, _ in PROTECTED_ROUTES],
)
def test_authenticated_user_without_roles_is_403_everywhere(
    client: TestClient,
    session: Session,
    authz_seeded: None,
    method: str,
    path: str,
    payload: dict | None,
) -> None:
    # Valid login, zero application roles → no permissions at all: every
    # business route denies, with the generic detail.
    user = make_user_with_roles(session, "plain-user")

    response = client.request(method, path, json=payload, headers=auth_header(user))

    assert response.status_code == 403
    assert response.json()["detail"] == GENERIC_403_DETAIL


def test_403_detail_never_names_the_missing_permission(
    client: TestClient, session: Session, authz_seeded: None
) -> None:
    # §4g: the denial reveals nothing about *which* permission was needed.
    user = make_user_with_roles(session, "plain-user")

    response = client.get("/api/persons", headers=auth_header(user))

    assert response.status_code == 403
    assert response.json()["detail"] == GENERIC_403_DETAIL
    assert authz.PEOPLE_READ not in response.text
    assert "permission" not in response.text.lower()


def test_operator_is_denied_only_people_create(
    client: TestClient, session: Session, authz_seeded: None
) -> None:
    # The one deliberate difference in the seeded matrix (docs/06 §4g):
    # operator lacks people:create. An unrelated-role denial in practice —
    # the role exists, the permission does not attach to it.
    operator = make_user_with_roles(session, "day-operator", role_codes=("operator",))
    headers = auth_header(operator)

    denied = client.post("/api/persons", json={"name": "Nope"}, headers=headers)
    assert denied.status_code == 403
    assert denied.json()["detail"] == GENERIC_403_DETAIL

    # Everything else the operator holds passes the gate (whatever the
    # handler then does with the payload is not an authorization outcome).
    for method, path, payload in PROTECTED_ROUTES:
        if path == "/api/persons" and method == "POST":
            continue
        response = client.request(method, path, json=payload, headers=headers)
        assert response.status_code not in (401, 403), f"{method} {path}"


def test_operator_succeeds_where_authorized(
    client: TestClient, session: Session, authz_seeded: None
) -> None:
    operator = make_user_with_roles(session, "create-operator", role_codes=("operator",))
    headers = auth_header(operator)

    assert client.get("/api/persons", headers=headers).status_code == 200
    created = client.post(
        "/api/events",
        json={"title": "Operator Event", "type": "class", "planned_at": PLANNED_AT},
        headers=headers,
    )
    assert created.status_code == 201


def test_admin_passes_every_gate(
    client: TestClient, session: Session, authz_seeded: None
) -> None:
    admin = make_user_with_roles(session, "matrix-admin", role_codes=("admin",))
    headers = auth_header(admin)

    for method, path, payload in PROTECTED_ROUTES:
        response = client.request(method, path, json=payload, headers=headers)
        assert response.status_code not in (401, 403), f"{method} {path}"


def test_admin_creates_across_all_business_resources(
    client: TestClient, session: Session, authz_seeded: None
) -> None:
    # The full happy path as one privileged user: read the reference roles,
    # create a person, create an event, assign the person to the event,
    # read all of it back.
    admin = make_user_with_roles(session, "flow-admin", role_codes=("admin",))
    headers = auth_header(admin)

    assert client.get("/api/roles", headers=headers).status_code == 200

    person_response = client.post(
        "/api/persons", json={"name": "Flow Person"}, headers=headers
    )
    assert person_response.status_code == 201
    person_id = person_response.json()["id"]

    event_response = client.post(
        "/api/events",
        json={"title": "Flow Event", "type": "class", "planned_at": PLANNED_AT},
        headers=headers,
    )
    assert event_response.status_code == 201
    event_id = event_response.json()["id"]
    assert client.get(f"/api/events/{event_id}", headers=headers).status_code == 200

    session.add(EventResponsibility(code="registration", name="Registration"))
    session.commit()
    assignment_response = client.post(
        "/api/event-assignments",
        json={
            "event_id": event_id,
            "person_id": person_id,
            "responsibility": "registration",
        },
        headers=headers,
    )
    assert assignment_response.status_code == 201
    assignment_id = assignment_response.json()["id"]
    assert client.get("/api/event-assignments", headers=headers).status_code == 200
    assert (
        client.get(f"/api/event-assignments/{assignment_id}", headers=headers).status_code
        == 200
    )


# --- Multiple roles and permission union --------------------------------------


def add_role_with_permissions(
    session: Session, code: str, name: str, permission_codes: tuple[str, ...]
) -> ApplicationRole:
    """Insert a test-only application role holding exactly the given codes."""
    role = ApplicationRole(code=code, name=name)
    session.add(role)
    session.flush()
    for permission_code in permission_codes:
        permission = session.scalars(
            select(Permission).where(Permission.code == permission_code)
        ).one()
        session.add(
            ApplicationRolePermission(
                application_role_id=role.id, permission_id=permission.id
            )
        )
    session.commit()
    return role


def test_user_can_hold_multiple_roles_with_unioned_permissions(
    client: TestClient, session: Session, authz_seeded: None
) -> None:
    # operator (six permissions, no people:create) plus a minimal extra
    # role holding only people:create — the union is the full set.
    add_role_with_permissions(
        session, "roster-clerk", "Roster Clerk", (authz.PEOPLE_CREATE,)
    )
    user = make_user_with_roles(session, "union-user", role_codes=("operator",))
    authz.assign_application_role(
        session, username="union-user", role_code="roster-clerk"
    )

    assert authz.user_permission_codes(session, user=user) == set(
        authz.ALL_PERMISSION_CODES
    )

    # And over HTTP: the operator's own denial is lifted by the second role.
    response = client.post(
        "/api/persons", json={"name": "Union Person"}, headers=auth_header(user)
    )
    assert response.status_code == 201


def test_role_with_unrelated_permission_still_denied(
    client: TestClient, session: Session, authz_seeded: None
) -> None:
    # Holding *a* permission is not holding *the* permission: a role whose
    # only capability is people:create does not unlock events:read.
    add_role_with_permissions(
        session, "roster-clerk", "Roster Clerk", (authz.PEOPLE_CREATE,)
    )
    user = make_user_with_roles(session, "clerk-only", role_codes=("roster-clerk",))

    assert authz.user_permission_codes(session, user=user) == {authz.PEOPLE_CREATE}

    response = client.get("/api/events", headers=auth_header(user))
    assert response.status_code == 403
    assert response.json()["detail"] == GENERIC_403_DETAIL


# --- Seeded reference data (mirror of migration 0005) --------------------------


def test_seeded_application_roles_exist(session: Session, authz_seeded: None) -> None:
    roles = authz.list_application_roles(session)
    assert [role.code for role in roles] == ["admin", "manager", "operator"]


def test_seeded_permissions_are_exactly_the_api_capabilities(
    session: Session, authz_seeded: None
) -> None:
    codes = set(session.scalars(select(Permission.code)).all())
    assert codes == set(authz.ALL_PERMISSION_CODES)


def test_seeded_role_permission_matrix_is_correct(
    session: Session, authz_seeded: None
) -> None:
    # admin and manager hold all seven; operator all but people:create.
    expected = {
        "admin": set(authz.ALL_PERMISSION_CODES),
        "manager": set(authz.ALL_PERMISSION_CODES),
        "operator": set(authz.ALL_PERMISSION_CODES) - {authz.PEOPLE_CREATE},
    }
    for role_code, permission_codes in expected.items():
        user = make_user_with_roles(
            session, f"seed-check-{role_code}", role_codes=(role_code,)
        )
        assert authz.user_permission_codes(session, user=user) == permission_codes

    # 7 + 7 + 6 rows in the matrix — no stray grants, none missing.
    total = len(session.scalars(select(ApplicationRolePermission)).all())
    assert total == 20


# --- Role-assignment service (the CLI path; no HTTP endpoint exists) -----------


class TestAssignApplicationRole:
    def test_unknown_role_raises(
        self, session: Session, authz_seeded: None
    ) -> None:
        make_user_with_roles(session, "target-user")
        with pytest.raises(authz.UnknownApplicationRoleError):
            authz.assign_application_role(
                session, username="target-user", role_code="bogus"
            )

    def test_unknown_user_raises(
        self, session: Session, authz_seeded: None
    ) -> None:
        with pytest.raises(authz.UserNotFoundError):
            authz.assign_application_role(
                session, username="no-such-user", role_code="admin"
            )

    def test_already_granted_raises(
        self, session: Session, authz_seeded: None
    ) -> None:
        make_user_with_roles(session, "once-only", role_codes=("operator",))
        with pytest.raises(authz.RoleAlreadyGrantedError):
            authz.assign_application_role(
                session, username="once-only", role_code="operator"
            )

    def test_grant_gives_the_roles_permissions(
        self, session: Session, authz_seeded: None
    ) -> None:
        user = make_user_with_roles(session, "fresh-user")
        assert authz.user_permission_codes(session, user=user) == set()

        authz.assign_application_role(session, username="fresh-user", role_code="admin")

        assert authz.user_permission_codes(session, user=user) == set(
            authz.ALL_PERMISSION_CODES
        )


# --- Public and authenticated-only routes stay as they were --------------------


def test_health_remains_public(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_login_remains_public(
    client: TestClient, session: Session, authz_seeded: None
) -> None:
    make_user_with_roles(session, "login-user")

    response = client.post(
        "/api/auth/login",
        json={"username": "login-user", "password": "test-pass-12345"},
    )

    assert response.status_code == 200
    assert "access_token" in response.json()


def test_me_still_works_for_user_without_any_role(
    client: TestClient, session: Session, authz_seeded: None
) -> None:
    # /me is authenticated-only (§4f): zero permissions change nothing.
    user = make_user_with_roles(session, "me-only")

    response = client.get("/api/auth/me", headers=auth_header(user))

    assert response.status_code == 200
    assert response.json()["username"] == "me-only"


def test_business_roles_are_unrelated_to_application_roles(
    session: Session, authz_seeded: None
) -> None:
    # The Phase 3 domain roles (roles table — learner/supporter/…) and the
    # Phase 5 application roles are separate tables with separate codes; a
    # Person's business role grants no permission, and an application role
    # says nothing about a Person (there is no required User↔Person link).
    from app.models import Role

    session.add(Role(code="manager", name="Manager"))  # the *domain* manager
    session.commit()

    domain_manager_codes = set(session.scalars(select(Role.code)).all())
    application_codes = {
        role.code for role in authz.list_application_roles(session)
    }

    assert domain_manager_codes == {"manager"}
    assert application_codes == {"admin", "manager", "operator"}
    # No user needs a Person: the permission system never consults persons.
    user = make_user_with_roles(session, "personless-admin", role_codes=("admin",))
    assert authz.user_permission_codes(session, user=user) == set(
        authz.ALL_PERMISSION_CODES
    )
