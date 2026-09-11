"""PostgreSQL-backed tests for the 0005 authorization-seed migration.

Runs the real Alembic migration chain (0001 â†’ 0005) against a **disposable
database** created on the configured PostgreSQL server and dropped
afterwards â€” the persistent development database is never modified. Verifies
the migration lifecycle (upgrade / downgrade / re-upgrade), the exact seeded
matrix, and idempotency of the seed inserts, against actual PostgreSQL
behavior. The test_seed_migration.py pattern, applied to the authorization
tables.

If no PostgreSQL server is reachable, the tests skip with an explicit reason
(the SQLite-based authz tests remain the always-available baseline).
"""

import importlib.util
from pathlib import Path
from uuid import UUID

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError

from app.core.config import get_settings

APPS_API_DIR = Path(__file__).resolve().parents[1]
ALEMBIC_INI = APPS_API_DIR / "alembic.ini"
MIGRATION_PATH = (
    APPS_API_DIR / "alembic" / "versions" / "0005_add_application_authorization_tables.py"
)

EXPECTED_ROLES: dict[str, str] = {
    "admin": "Administrator",
    "manager": "Manager",
    "operator": "Operator",
}

# The seeded matrix (docs/06 Â§4g): operator is everything but people:create.
OPERATOR_MISSING = "people:create"
ALL_CODES = {
    "roles:read",
    "people:read",
    "people:create",
    "events:read",
    "events:create",
    "assignments:read",
    "assignments:create",
}

AUTHZ_TABLES = (
    "application_roles",
    "permissions",
    "user_application_roles",
    "application_role_permissions",
)

DISPOSABLE_DB_NAME = "ketabdaneh_authz_seed_test"


def _load_migration_module() -> object:
    """Import the 0005 migration file directly (alembic/versions is not a package)."""
    spec = importlib.util.spec_from_file_location("authz_migration", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _fetch_rows(engine: Engine, sql: str) -> list[dict]:
    with engine.connect() as connection:
        return [dict(row) for row in connection.execute(text(sql)).mappings()]


def _fetch_matrix(engine: Engine) -> set[tuple[str, str]]:
    rows = _fetch_rows(
        engine,
        "SELECT r.code AS role_code, p.code AS permission_code "
        "FROM application_role_permissions arp "
        "JOIN application_roles r ON r.id = arp.application_role_id "
        "JOIN permissions p ON p.id = arp.permission_id",
    )
    return {(row["role_code"], row["permission_code"]) for row in rows}


@pytest.fixture()
def disposable_db_engine():
    """A throwaway database on the configured PostgreSQL server.

    Connects to the configured development database only to issue
    CREATE/DROP DATABASE statements on the same server; the development
    database itself is never migrated or modified by these tests.
    """
    database_url = get_settings().database_url.get_secret_value()
    if not database_url:
        pytest.skip("DATABASE_URL is not configured")

    admin_engine = create_engine(database_url, isolation_level="AUTOCOMMIT")
    try:
        try:
            with admin_engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        except OperationalError as exc:
            pytest.skip(f"PostgreSQL server not reachable: {exc}")

        with admin_engine.connect() as connection:
            connection.execute(
                text(f'DROP DATABASE IF EXISTS "{DISPOSABLE_DB_NAME}"')
            )
            connection.execute(text(f'CREATE DATABASE "{DISPOSABLE_DB_NAME}"'))
    finally:
        admin_engine.dispose()

    url = database_url.rsplit("/", 1)[0] + "/" + DISPOSABLE_DB_NAME
    engine = create_engine(url)
    try:
        yield engine
    finally:
        engine.dispose()
        cleanup_engine = create_engine(database_url, isolation_level="AUTOCOMMIT")
        try:
            with cleanup_engine.connect() as connection:
                connection.execute(
                    text(f'DROP DATABASE IF EXISTS "{DISPOSABLE_DB_NAME}"')
                )
        finally:
            cleanup_engine.dispose()


@pytest.fixture()
def alembic_config(disposable_db_engine: Engine, monkeypatch):
    """Alembic configuration pointed at the disposable database.

    env.py resolves the URL through the application settings, so the
    DATABASE_URL environment variable is overridden (env vars take priority
    over the .env file) and the settings cache is cleared around the run.
    """
    disposable_url = str(
        disposable_db_engine.url.render_as_string(hide_password=False)
    )
    monkeypatch.setenv("DATABASE_URL", disposable_url)
    get_settings.cache_clear()

    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(APPS_API_DIR / "alembic"))
    try:
        yield config
    finally:
        get_settings.cache_clear()


def test_upgrade_seeds_the_exact_authorization_matrix(
    alembic_config, disposable_db_engine: Engine
) -> None:
    command.upgrade(alembic_config, "head")

    roles = _fetch_rows(
        disposable_db_engine,
        "SELECT id, code, name, created_at, updated_at FROM application_roles",
    )
    assert {row["code"]: row["name"] for row in roles} == EXPECTED_ROLES
    migration = _load_migration_module()
    assert {row["id"] for row in roles} == set(migration.SEED_APPLICATION_ROLE_IDS)

    permissions = _fetch_rows(
        disposable_db_engine,
        "SELECT id, code, name FROM permissions",
    )
    assert {row["code"] for row in permissions} == ALL_CODES
    assert {row["id"] for row in permissions} == set(migration.SEED_PERMISSION_IDS)

    matrix = _fetch_matrix(disposable_db_engine)
    expected_matrix = {
        (role_code, permission_code)
        for role_code in ("admin", "manager")
        for permission_code in ALL_CODES
    } | {
        ("operator", permission_code)
        for permission_code in ALL_CODES - {OPERATOR_MISSING}
    }
    assert matrix == expected_matrix

    # Audit timestamps filled by the database defaults (docs/03 Â§4).
    assert all(row["created_at"] is not None for row in roles)
    assert all(row["updated_at"] is not None for row in roles)


def test_reapplied_seed_insert_creates_no_duplicates(
    alembic_config, disposable_db_engine: Engine
) -> None:
    command.upgrade(alembic_config, "head")
    command.upgrade(alembic_config, "head")  # no-op in the lifecycle

    # Re-executing the seed insert itself (ON CONFLICT DO NOTHING) against
    # the already-seeded database must not duplicate or clobber rows.
    migration = _load_migration_module()
    with disposable_db_engine.begin() as connection:
        migration.insert_seed_authorization_data(connection)

    roles = _fetch_rows(
        disposable_db_engine,
        "SELECT id, code FROM application_roles",
    )
    assert len(roles) == 3
    assert {row["id"] for row in roles} == set(migration.SEED_APPLICATION_ROLE_IDS)
    assert len(_fetch_matrix(disposable_db_engine)) == 20


def test_downgrade_drops_authorization_tables_users_intact_reupgrade_reseeds(
    alembic_config, disposable_db_engine: Engine
) -> None:
    command.upgrade(alembic_config, "head")

    # A user row the downgrade must not touch (0004 owns the users table).
    user_id = UUID("12345678-1234-4123-8123-123456789abc")
    with disposable_db_engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO users (id, username, password_hash) "
                "VALUES (:id, 'survivor', 'x')"
            ),
            {"id": str(user_id)},
        )

    command.downgrade(alembic_config, "0004")

    # The three authorization tables are gone; users survives untouched.
    for table_name in AUTHZ_TABLES:
        exists = disposable_db_engine.connect()
        with exists as connection:
            regclass = connection.execute(
                text(f"SELECT to_regclass('public.{table_name}')")
            ).scalar()
        assert regclass is None, f"{table_name} must be dropped on downgrade"
    surviving = _fetch_rows(
        disposable_db_engine, "SELECT id, username FROM users"
    )
    assert [(row["id"], row["username"]) for row in surviving] == [
        (user_id, "survivor")
    ]

    # Upgrade after downgrade recreates and reseeds exactly.
    command.upgrade(alembic_config, "head")

    migration = _load_migration_module()
    roles = _fetch_rows(
        disposable_db_engine, "SELECT id, code FROM application_roles"
    )
    assert {row["code"] for row in roles} == set(EXPECTED_ROLES)
    assert {row["id"] for row in roles} == set(migration.SEED_APPLICATION_ROLE_IDS)
    assert len(_fetch_matrix(disposable_db_engine)) == 20
