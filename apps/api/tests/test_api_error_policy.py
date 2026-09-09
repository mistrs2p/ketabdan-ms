"""Error-policy tests — lock the behavior documented in docs/06 §4b.

These tests are deliberately behavioral locks, not feature tests: they
assert the status codes and body shapes of every error class the API can
currently produce, so a future refactor (or a FastAPI upgrade) cannot
silently change the error contract the frontend builds against.
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.main import app
from app.models import Role


def test_validation_error_keeps_fastapi_default_shape(
    client: TestClient,
) -> None:
    # §4b rule 2: missing required field -> 422, detail is Pydantic's
    # structured list (type/loc/msg per item), never reformatted by us.
    response = client.post("/api/persons", json={})

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert isinstance(detail, list)
    (item,) = detail
    assert item["type"] == "missing"
    assert item["loc"] == ["body", "name"]
    assert item["msg"] == "Field required"


def test_malformed_json_is_also_a_validation_error(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/persons",
        content=b'{"name": ',  # truncated JSON
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)


def test_domain_error_uses_422_with_human_readable_detail(
    client: TestClient, session: Session
) -> None:
    # §4b rule 3: request content that violates domain reference data
    # shares the validation status family, with a plain string detail.
    session.add(Role(code="supporter", name="Supporter"))
    session.commit()

    response = client.post(
        "/api/persons", json={"name": "Reza", "roles": ["ghost"]}
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Unknown role code(s): ghost"


def test_unknown_path_is_404_with_detail_string(client: TestClient) -> None:
    response = client.get("/api/nope")

    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}


def test_unsupported_method_is_405_with_detail_string(
    client: TestClient,
) -> None:
    # /api/roles only supports GET; roles have no write endpoints (§4).
    response = client.delete("/api/roles")

    assert response.status_code == 405
    assert response.json() == {"detail": "Method Not Allowed"}


def test_unexpected_exception_is_starlette_default_500_plain_text() -> None:
    # §4b rule 5: no global handler exists; an unexpected exception must
    # produce starlette's default 500 — plain text, no stack trace leaked.
    def boom() -> Iterator[Session]:
        raise RuntimeError("kaboom")
        yield  # pragma: no cover

    app.dependency_overrides[get_db] = boom
    try:
        # raise_server_exceptions=False: observe the 500 the client gets
        # instead of letting TestClient re-raise the RuntimeError.
        raw_client = TestClient(app, raise_server_exceptions=False)
        response = raw_client.get("/api/persons")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 500
    assert response.headers["content-type"].startswith("text/plain")
    assert response.text == "Internal Server Error"
