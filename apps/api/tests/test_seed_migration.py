"""PostgreSQL-backed tests for the 0002 seed-initial-roles migration.

These tests run the real Alembic migration chain (0001 + 0002) against a
**disposable database** created on the configured PostgreSQL server and
dropped afterwards — the persistent development database is never modified.
They verify the migration lifecycle itself (upgrade / downgrade / re-upgrade)
plus idempotency of the seed insert, against actual PostgreSQL behavior.

If no PostgreSQL server is reachable, the tests skip with an explicit reason
(the SQLite-based model tests remain the always-available baseline).
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
MIGRATION_PATH = APPS_API_DIR / "alembic" / "versions" / "0002_seed_initial_roles.py"

EXPECTED_ROLES: dict[str, str] = {
    "learner": "Learner / Student",
    "supporter": "Supporter",
    "coach": "Coach",
    "teacher": "Teacher",
    "referrer": "Referrer",
    "manager": "Manager",
}

DISPOSABLE_DB_NAME = "ketabdaneh_seed_test"


def _load_migration_module() -> object:
    """Import the 0002 migration file directly (alembic/versions is not a package)."""
    spec = importlib.util.spec_from_file_location("seed_initial_roles", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _fetch_roles(engine: Engine) -> list[dict]:
    with engine.connect() as connection:
        rows = connection.execute(
            text("SELECT id, code, name, created_at, updated_at FROM roles")
        ).mappings()
        return [dict(row) for row in rows]


@pytest.fixture()
def disposable_db_engine():
    """A throwaway database on the configured PostgreSQL server.

    Connects to the configured development database only to issue
    CREATE/DROP DATABASE statements on the same server; the development
    database itself is never migrated or modified by these tests.
    """
    database_url = get_settings().database_url
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
    disposable_url = str(disposable_db_engine.url.render_as_string(hide_password=False))
    monkeypatch.setenv("DATABASE_URL", disposable_url)
    get_settings.cache_clear()

    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(APPS_API_DIR / "alembic"))
    try:
        yield config
    finally:
        get_settings.cache_clear()


def test_upgrade_seeds_exactly_the_six_confirmed_roles(
    alembic_config, disposable_db_engine
) -> None:
    command.upgrade(alembic_config, "head")

    rows = _fetch_roles(disposable_db_engine)
    # Exactly six rows; every code present; every name exact.
    assert {row["code"]: row["name"] for row in rows} == EXPECTED_ROLES
    # Stable migration-owned identities.
    migration = _load_migration_module()
    assert {row["id"] for row in rows} == set(migration.SEED_ROLE_IDS)
    # Audit timestamps filled by the existing database defaults (docs/03 §4).
    assert all(row["created_at"] is not None for row in rows)
    assert all(row["updated_at"] is not None for row in rows)


def test_reapplied_seed_insert_creates_no_duplicates(
    alembic_config, disposable_db_engine
) -> None:
    command.upgrade(alembic_config, "head")
    # Running `upgrade head` again is a no-op in the migration lifecycle...
    command.upgrade(alembic_config, "head")

    # ...and re-executing the seed insert itself (ON CONFLICT DO NOTHING)
    # against the already-seeded database must not duplicate or clobber rows.
    migration = _load_migration_module()
    with disposable_db_engine.begin() as connection:
        migration.insert_seed_roles(connection)

    rows = _fetch_roles(disposable_db_engine)
    assert len(rows) == len(EXPECTED_ROLES)
    assert {row["code"]: row["name"] for row in rows} == EXPECTED_ROLES
    assert {row["id"] for row in rows} == set(migration.SEED_ROLE_IDS)


def test_downgrade_removes_only_seeded_roles_and_reupgrade_recreates(
    alembic_config, disposable_db_engine
) -> None:
    migration = _load_migration_module()
    command.upgrade(alembic_config, "head")

    # An unrelated role the migration must not touch on downgrade.
    unrelated_id = UUID("12345678-1234-4123-8123-123456789abc")
    with disposable_db_engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO roles (id, code, name) "
                "VALUES (:id, 'unrelated', 'Unrelated')"
            ),
            {"id": str(unrelated_id)},
        )

    command.downgrade(alembic_config, "0001")

    rows = _fetch_roles(disposable_db_engine)
    assert [(row["id"], row["code"]) for row in rows] == [
        (unrelated_id, "unrelated")
    ], "downgrade must remove only the six seeded rows"

    # Upgrade after downgrade recreates exactly the six seeded roles.
    command.upgrade(alembic_config, "head")

    rows = _fetch_roles(disposable_db_engine)
    assert {row["code"]: row["name"] for row in rows} == {
        **EXPECTED_ROLES,
        "unrelated": "Unrelated",
    }
    assert {row["id"] for row in rows if row["code"] in EXPECTED_ROLES} == set(
        migration.SEED_ROLE_IDS
    )
