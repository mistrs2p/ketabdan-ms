"""API tests for the health endpoint.

`GET /api/health` is the liveness contract (docs/06 §4): it answers
`{"status": "ok"}` and involves **no database** — it must work even when
`DATABASE_URL` is not configured. The test pins that shape so a refactor
cannot accidentally couple startup liveness to the database.
"""

from fastapi.testclient import TestClient


def test_health_returns_ok_without_database(client: TestClient) -> None:
    # The client fixture's get_db override is irrelevant here: the health
    # route takes no session dependency at all — that absence is the point.
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
