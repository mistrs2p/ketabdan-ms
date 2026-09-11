"""Authentication tests â€” lock the Phase 5.1 contract (docs/06 Â§4f).

Behavioral locks, in the style of test_api_error_policy.py: every auth
failure (wrong password, unknown user, inactive, missing/malformed/
invalid/expired token) must be an indistinguishable generic 401 â€” no
user enumeration, no 500s, no leaked internals. Positive paths pin the
login body shape, the /me projection (no hash), and token claims.

All tests run against the in-memory SQLite fixture (conftest.py) â€” no
test user ever reaches the development PostgreSQL database.
"""

from datetime import timedelta

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core import security
from app.core.config import get_settings
from app.models import User
from app.services import auth as auth_service

USERNAME = "smoke-admin"
PASSWORD = "correct-horse-battery"


@pytest.fixture()
def existing_user(session: Session) -> User:
    """One active user, created through the same service the CLI uses."""
    return auth_service.create_user(session, username=USERNAME, password=PASSWORD)


# --- Password hashing ------------------------------------------------------


def test_hash_is_not_plaintext(existing_user: User) -> None:
    hash_value = existing_user.password_hash

    assert hash_value != PASSWORD
    assert PASSWORD not in hash_value
    assert hash_value.startswith("$argon2id$")


def test_correct_password_verifies(existing_user: User) -> None:
    assert security.verify_password(existing_user.password_hash, PASSWORD)


def test_wrong_password_fails_to_verify(existing_user: User) -> None:
    assert not security.verify_password(existing_user.password_hash, "not-it-123")


# --- Login endpoint ---------------------------------------------------------


def test_login_success_returns_token_contract(
    client: TestClient, existing_user: User
) -> None:
    response = client.post(
        "/api/auth/login", json={"username": USERNAME, "password": PASSWORD}
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"access_token", "token_type", "expires_in"}
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == get_settings().access_token_expire_minutes * 60
    assert isinstance(body["access_token"], str) and body["access_token"]


def test_login_wrong_password_is_generic_401(
    client: TestClient, existing_user: User
) -> None:
    response = client.post(
        "/api/auth/login", json={"username": USERNAME, "password": "wrong-pass"}
    )

    assert response.status_code == 401
    assert response.json()["detail"] == auth_service.GENERIC_AUTH_FAILURE


def test_login_unknown_user_same_generic_401(client: TestClient) -> None:
    # Same status AND same body as the wrong-password case â€” callers
    # cannot distinguish "user exists" from "user unknown".
    response = client.post(
        "/api/auth/login", json={"username": "no-such-user", "password": "whatever1"}
    )

    assert response.status_code == 401
    assert response.json()["detail"] == auth_service.GENERIC_AUTH_FAILURE


def test_login_inactive_user_same_generic_401(
    client: TestClient, session: Session, existing_user: User
) -> None:
    existing_user.active = False
    session.commit()

    response = client.post(
        "/api/auth/login", json={"username": USERNAME, "password": PASSWORD}
    )

    assert response.status_code == 401
    assert response.json()["detail"] == auth_service.GENERIC_AUTH_FAILURE


# --- GET /api/auth/me --------------------------------------------------------


def test_me_with_valid_token_returns_user_without_hash(
    client: TestClient, existing_user: User
) -> None:
    login = client.post(
        "/api/auth/login", json={"username": USERNAME, "password": PASSWORD}
    )
    token = login.json()["access_token"]

    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(existing_user.id)
    assert body["username"] == USERNAME
    assert body["active"] is True
    # Security rule (Â§4f): the hash never appears anywhere in the response.
    assert "password_hash" not in body
    assert existing_user.password_hash not in response.text


def test_me_without_token_is_401(client: TestClient) -> None:
    response = client.get("/api/auth/me")

    assert response.status_code == 401


def test_me_with_malformed_token_is_401(client: TestClient) -> None:
    response = client.get(
        "/api/auth/me", headers={"Authorization": "Bearer not-a-jwt-at-all"}
    )

    assert response.status_code == 401


def test_me_with_wrong_signature_token_is_401(client: TestClient) -> None:
    # Signed with the wrong secret â€” must fail verification, not 500.
    forged, _ = security.create_access_token(
        subject="someone",
        secret_key="a-completely-different-secret-key",
        algorithm="HS256",
        expires_delta=timedelta(minutes=5),
    )
    response = client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {forged}"}
    )

    assert response.status_code == 401


def test_me_with_expired_token_is_401(
    client: TestClient, existing_user: User
) -> None:
    # Issued and already expired â€” expiry must be enforced.
    expired, _ = security.create_access_token(
        subject=str(existing_user.id),
        secret_key=get_settings().auth_secret_key.get_secret_value(),
        algorithm=get_settings().auth_algorithm,
        expires_delta=timedelta(seconds=-60),
    )
    response = client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {expired}"}
    )

    assert response.status_code == 401


def test_me_with_valid_token_for_deleted_user_is_401(
    client: TestClient, session: Session, existing_user: User
) -> None:
    # A structurally valid token whose subject no longer exists.
    token, _ = security.create_access_token(
        subject="00000000-0000-0000-0000-000000000000",
        secret_key=get_settings().auth_secret_key.get_secret_value(),
        algorithm=get_settings().auth_algorithm,
        expires_delta=timedelta(minutes=5),
    )
    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


# --- Token contents -----------------------------------------------------------


def test_issued_token_contains_identity_and_expiry(
    client: TestClient, existing_user: User
) -> None:
    login = client.post(
        "/api/auth/login", json={"username": USERNAME, "password": PASSWORD}
    )
    token = login.json()["access_token"]

    payload = jwt.decode(
        token,
        get_settings().auth_secret_key.get_secret_value(),
        algorithms=[get_settings().auth_algorithm],
    )

    assert payload["sub"] == str(existing_user.id)
    assert payload["typ"] == "access"
    assert payload["exp"] > payload["iat"]
    assert payload["exp"] - payload["iat"] == login.json()["expires_in"]


# --- Health stays public -------------------------------------------------------


def test_health_public_without_any_token(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# --- Bootstrap service -----------------------------------------------------------


def test_duplicate_username_rejected(
    session: Session, existing_user: User
) -> None:
    with pytest.raises(auth_service.UsernameTakenError):
        auth_service.create_user(
            session, username=USERNAME.upper(), password="another-pass-123"
        )


def test_password_policy_rejects_short_password(session: Session) -> None:
    with pytest.raises(auth_service.PasswordPolicyError):
        auth_service.create_user(session, username="policy-test", password="short")
