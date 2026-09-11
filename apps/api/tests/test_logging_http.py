"""Tests for HTTP request logging and security logging (Task 5.8 §16).

Behavioral, offline (TestClient against the real app/SQLite), with caplog
assertions that never depend on timing — durations are asserted present,
never to a value.
"""

import logging
import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.services import auth as auth_service


@pytest.fixture()
def capture(caplog):
    """Records from every logger, at any level, for the duration."""
    with caplog.at_level(logging.DEBUG, logger=""):
        yield caplog


def request_lines(records) -> list[str]:
    return [
        r.getMessage() for r in records if r.name == "app.api.request"
    ]


def security_records(records) -> list[logging.LogRecord]:
    return [r for r in records if r.name == "app.api.security"]


# --- one request line per request ------------------------------------------------


def test_every_request_logs_exactly_one_line(client: TestClient, capture) -> None:
    client.get("/api/health")
    lines = request_lines(capture.records)
    assert len(lines) == 1
    assert "GET /api/health -> 200" in lines[0]


def test_request_line_contains_method_path_status_duration_request_id(
    client: TestClient, capture
) -> None:
    client.get("/api/health")
    line = request_lines(capture.records)[0]
    # duration is present and formatted as milliseconds — never asserted
    # to a specific value (no wall-clock flakiness).
    assert re.search(r"-> 200 \d+(\.\d+)?ms request_id=", line)


def test_request_line_is_logged_for_4xx_and_5xx(
    client: TestClient, capture
) -> None:
    client.get("/api/nope")  # 404
    client.get("/api/persons")  # 401 (no token)
    lines = request_lines(capture.records)
    assert "-> 404" in lines[0]
    assert "-> 401" in lines[1]


def test_request_log_level_is_warning_for_5xx_info_otherwise(
    client: TestClient, capture
) -> None:
    from app.db.session import get_db
    from app.main import app

    def boom():
        raise RuntimeError("kaboom")
        yield  # pragma: no cover

    app.dependency_overrides[get_db] = boom
    try:
        raw = TestClient(app, raise_server_exceptions=False)
        raw.get("/api/persons")
    finally:
        app.dependency_overrides.pop(get_db, None)

    request_records = [r for r in capture.records if r.name == "app.api.request"]
    assert len(request_records) == 1
    assert request_records[0].levelno == logging.WARNING
    assert "-> 500" in request_records[0].getMessage()


# --- no sensitive data in request logs --------------------------------------------


def test_request_log_never_contains_authorization_or_query_string(
    authed_client: TestClient, capture
) -> None:
    # The authenticated client sends a real Bearer token; the request line
    # must carry only method/path/status/duration/request_id — no headers,
    # no query string, no body.
    authed_client.get("/api/auth/me")
    line = request_lines(capture.records)[0]

    token = authed_client.headers["Authorization"].split(" ", 1)[1]
    assert token not in line
    assert "Authorization" not in line
    assert "Bearer" not in line


def test_query_string_is_not_logged(client: TestClient, capture) -> None:
    client.get("/api/health?password=super-secret&token=abc")
    line = request_lines(capture.records)[0]
    assert "password=super-secret" not in line
    assert "token=abc" not in line
    assert "/api/health -> 200" in line


def test_request_body_is_never_logged(
    client: TestClient, session: Session, capture
) -> None:
    client.post(
        "/api/auth/login",
        json={"username": "someone", "password": "hunter2-super-secret"},
    )
    for record in capture.records:
        assert "hunter2-super-secret" not in record.getMessage()


# --- the correlation / request id --------------------------------------------------


def test_response_carries_request_id_header(client: TestClient) -> None:
    response = client.get("/api/health")
    request_id = response.headers["X-Request-ID"]
    assert re.fullmatch(r"[0-9a-f]{32}", request_id)  # generated uuid4 hex


def test_safe_incoming_request_id_is_accepted_and_echoed(
    client: TestClient, capture
) -> None:
    response = client.get("/api/health", headers={"X-Request-ID": "web-42"})
    assert response.headers["X-Request-ID"] == "web-42"
    assert "request_id=web-42" in request_lines(capture.records)[0]


@pytest.mark.parametrize(
    "hostile",
    [
        "x" * 300,                    # oversized
        "inject\nHost: evil",         # header injection
        "spaces in it",
        "weird;chars$here",
    ],
)
def test_hostile_incoming_request_ids_are_replaced(
    client: TestClient, hostile: str, capture
) -> None:
    response = client.get(
        "/api/health",
        headers={"X-Request-ID": hostile},
    )
    echoed = response.headers["X-Request-ID"]
    assert hostile not in echoed
    assert "\n" not in echoed
    assert len(echoed) <= 64
    line = request_lines(capture.records)[0]
    assert hostile not in line


def test_handler_can_see_request_id_on_state(client: TestClient, capture) -> None:
    # get_current_user logs the request id set by the middleware — proving
    # request.state.request_id is visible to handlers/dependencies.
    client.get("/api/persons")  # 401: no credentials
    records = security_records(capture.records)
    assert len(records) == 1
    assert "request_id=" in records[0].getMessage()
    assert "request_id=-" not in records[0].getMessage()


# --- security logging: authentication failures -------------------------------------


def test_login_failure_logs_warning_without_credentials(
    client: TestClient, session: Session, capture
) -> None:
    auth_service.create_user(session, username="victim", password="good-pass-123")
    client.post(
        "/api/auth/login",
        json={"username": "victim", "password": "wrong-password"},
    )

    records = security_records(capture.records)
    assert len(records) == 1
    record = records[0]
    assert record.levelno == logging.WARNING
    assert "username='victim'" in record.getMessage()
    # Never the attempted (or real) password, never any token.
    assert "wrong-password" not in record.getMessage()
    assert "good-pass-123" not in record.getMessage()


def test_login_failure_response_stays_generic(
    client: TestClient, session: Session, capture
) -> None:
    # The log records the reason; the API response must not change.
    response = client.post(
        "/api/auth/login",
        json={"username": "ghost", "password": "whatever"},
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid username or password"}
    assert len(security_records(capture.records)) == 1


def test_oversized_username_is_truncated_not_flooding_the_log(
    client: TestClient, capture
) -> None:
    huge = "a" * 5000
    client.post("/api/auth/login", json={"username": huge, "password": "x" * 9})

    records = security_records(capture.records)
    assert len(records) == 1
    message = records[0].getMessage()
    assert len(message) < 200  # bounded, not a 5 KB log line
    assert "aaaa" not in message[:70] or len(message) < 200
    assert message.count("a") < 100  # the 5000-char body was truncated


def test_invalid_token_failure_is_logged_without_token_value(
    client: TestClient, capture
) -> None:
    client.headers["Authorization"] = "Bearer not.a.real.jwt"
    client.get("/api/auth/me")

    records = security_records(capture.records)
    assert len(records) == 1
    message = records[0].getMessage()
    assert "invalid or expired token" in message
    assert "not.a.real.jwt" not in message  # the token value itself


def test_valid_token_but_unknown_user_is_logged(
    client: TestClient, session: Session, capture
) -> None:
    # A signed token whose user was deleted: worth a warning naming the
    # user id (investigating a possibly stolen token).
    user = auth_service.create_user(session, username="gone", password="x-pass-12345")
    token, _ = auth_service.issue_access_token(user)
    session.delete(user)
    session.commit()

    client.headers["Authorization"] = f"Bearer {token}"
    client.get("/api/auth/me")

    records = security_records(capture.records)
    assert len(records) == 1
    assert "no active user" in records[0].getMessage()
    assert str(user.id) in records[0].getMessage()
    client.headers.pop("Authorization", None)


# --- security logging: authorization failures ---------------------------------------


def test_permission_denial_is_logged_with_user_and_permission(
    client: TestClient, session: Session, authz_seeded, capture
) -> None:
    from tests.conftest import make_user_with_roles

    user = make_user_with_roles(session, "plain-operator", role_codes=())
    token, _ = auth_service.issue_access_token(user)
    client.headers["Authorization"] = f"Bearer {token}"
    response = client.get("/api/persons")
    client.headers.pop("Authorization", None)

    assert response.status_code == 403
    assert response.json() == {"detail": "Not authorized"}

    records = security_records(capture.records)
    assert len(records) == 1
    message = records[0].getMessage()
    assert "lacks permission=" in message
    assert "people:read" in message
    assert str(user.id) in message
    assert response.json()["detail"] == "Not authorized"  # unchanged contract


def test_successful_login_logs_info_not_warning(
    client: TestClient, session: Session, capture
) -> None:
    auth_service.create_user(session, username="okuser", password="fine-pass-123")
    response = client.post(
        "/api/auth/login", json={"username": "okuser", "password": "fine-pass-123"}
    )
    assert response.status_code == 200

    records = security_records(capture.records)
    assert len(records) == 1
    assert records[0].levelno == logging.INFO
    assert "auth success" in records[0].getMessage()
