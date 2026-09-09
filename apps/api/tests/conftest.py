"""Shared pytest fixtures.

Unit-level model/metadata tests use an isolated in-memory SQLite database
(no PostgreSQL required). SQLite enforces CHECK/UNIQUE/PK constraints and
(with `PRAGMA foreign_keys=ON`, enabled below) FK delete behaviors, so the
ORM wiring can be exercised end-to-end there; API tests reuse the same
session through FastAPI's dependency override. PostgreSQL-specific behavior
is additionally covered by running the application against the real database
(see docs/04-BACKEND-PERSISTENCE.md and docs/06-BACKEND-API.md, Validation).
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 — register all models on Base.metadata
from app.db.base import Base
from app.db.session import get_db
from app.main import app


@pytest.fixture()
def engine() -> Engine:
    # StaticPool + check_same_thread=False: FastAPI's TestClient runs the
    # application in a worker thread, so the in-memory database must be one
    # shared connection visible across threads (the default per-thread pool
    # would hand the app thread a fresh, empty database).
    engine = create_engine(
        "sqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def session(engine: Engine) -> Session:
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    session = factory()
    yield session
    session.close()


@pytest.fixture()
def client(session: Session) -> Iterator[TestClient]:
    """TestClient wired to the isolated SQLite session via dependency override."""

    def override_get_db() -> Iterator[Session]:
        yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_db, None)
