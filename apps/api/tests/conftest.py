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
import importlib.util
from pathlib import Path

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
from app.models import ApplicationRole, ApplicationRolePermission, Permission
from app.models.user import User
from app.services import auth as auth_service

APPS_API_DIR = Path(__file__).resolve().parents[1]
AUTHZ_MIGRATION_PATH = APPS_API_DIR / "alembic" / "versions" / "0005_add_application_authorization_tables.py"


def _load_authz_migration_module() -> object:
    """Import the 0005 migration file directly (alembic/versions is not a package)."""
    spec = importlib.util.spec_from_file_location(
        "authz_seed_migration", AUTHZ_MIGRATION_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


# --- Authorization fixtures (docs/06 §4g) ------------------------------------
#
# The API tests mirror the migration-seeded reference data the way
# test_api_persons mirrors the 0002 role seeds: the constants are loaded
# from the 0005 migration module itself, so tests and the real database
# can never drift apart.


@pytest.fixture()
def authz_seeded(session: Session) -> None:
    """Insert the 0005 authorization reference rows into the SQLite session.

    Same data as migration 0005 seeds on PostgreSQL: three application
    roles (admin/manager/operator), seven permissions, and the role→
    permission matrix. Business endpoints require these rows because
    every permission check resolves through them.
    """
    migration = _load_authz_migration_module()

    roles = {
        row["id"]: ApplicationRole(id=row["id"], code=row["code"], name=row["name"])
        for row in migration.SEED_APPLICATION_ROLES
    }
    permissions = {
        row["id"]: Permission(id=row["id"], code=row["code"], name=row["name"])
        for row in migration.SEED_PERMISSIONS
    }
    session.add_all(roles.values())
    session.add_all(permissions.values())
    # The matrix comes straight from the migration's own rows — the
    # fixture cannot drift from what PostgreSQL gets.
    session.add_all(
        ApplicationRolePermission(
            application_role_id=row["application_role_id"],
            permission_id=row["permission_id"],
        )
        for row in migration.SEED_APPLICATION_ROLE_PERMISSIONS
    )
    session.commit()


def make_user_with_roles(
    session: Session, username: str, *, role_codes: tuple[str, ...] = ()
) -> User:
    """Create a user through the real service, then grant the given
    application role codes through the real assignment service."""
    from app.services import authz

    user = auth_service.create_user(
        session, username=username, password="test-pass-12345"
    )
    for code in role_codes:
        authz.assign_application_role(session, username=username, role_code=code)
    return user


@pytest.fixture()
def authed_client(
    client: TestClient, session: Session, authz_seeded: None
) -> Iterator[TestClient]:
    """The shared TestClient authenticated as an admin-privileged user.

    Business routes require a permission (docs/06 §4g); this fixture
    sends a valid admin token as the default Authorization header. Tests
    that need other users build their own tokens via
    ``make_user_with_roles`` + ``auth_service.issue_access_token``.
    """
    user = make_user_with_roles(session, "test-admin", role_codes=("admin",))
    token, _ = auth_service.issue_access_token(user)
    client.headers["Authorization"] = f"Bearer {token}"
    yield client
    client.headers.pop("Authorization", None)
