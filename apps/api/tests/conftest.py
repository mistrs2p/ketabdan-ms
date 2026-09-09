"""Shared pytest fixtures: an isolated in-memory SQLite database.

Unit-level model/metadata tests must not require the production PostgreSQL
instance. SQLite enforces CHECK/UNIQUE/PK constraints and (with
`PRAGMA foreign_keys=ON`, enabled below) FK delete behaviors, so the ORM
wiring can be exercised end-to-end here. PostgreSQL-specific behavior is
additionally covered by running the application against the real database
(see docs/04-BACKEND-PERSISTENCE.md, Validation).
"""

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 — register all models on Base.metadata
from app.db.base import Base


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
