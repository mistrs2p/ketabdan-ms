"""Metadata-level tests: the ORM matches docs/03-DATABASE-SCHEMA.md.

These tests inspect `Base.metadata` directly and need no database.
"""

import app.models  # noqa: F401 — register all models
from app.db.base import Base
from sqlalchemy import Uuid, DateTime
from sqlalchemy.schema import CheckConstraint, UniqueConstraint

MVP_TABLES = {
    "persons",
    "roles",
    "person_roles",
    "events",
    "event_responsibilities",
    "event_assignments",
    "event_reports",
}

# The authentication identity table (Phase 5, docs/06 §4f) sits alongside
# the seven MVP business tables — deliberately not part of MVP_TABLES,
# which the tests below use to assert the *business* schema of docs/03.
AUTH_TABLES = {"users"}


def unique_column_names(table_name: str) -> set[str]:
    """Names of columns covered by a single-column UNIQUE constraint."""
    table = Base.metadata.tables[table_name]
    names = {column.name for column in table.columns if column.unique}
    for constraint in table.constraints:
        if isinstance(constraint, UniqueConstraint) and len(constraint.columns) == 1:
            names.add(next(iter(constraint.columns)).name)
    return names


def check_constraints(table_name: str) -> list[str]:
    return [
        str(constraint.sqltext.compile())
        for constraint in Base.metadata.tables[table_name].constraints
        if isinstance(constraint, CheckConstraint)
    ]


def test_exactly_the_seven_mvp_tables_registered() -> None:
    # Business schema (docs/03 §5) plus the Phase 5 auth table — nothing
    # else may register: no invented tables, no tasks/availability.
    assert set(Base.metadata.tables) == MVP_TABLES | AUTH_TABLES


def test_users_table_shape() -> None:
    # docs/06 §4f: login identity — unique username, opaque hash, switch.
    table = Base.metadata.tables["users"]
    assert unique_column_names("users") == {"username"}
    assert set(table.columns.keys()) >= {"id", "username", "password_hash", "active"}


def test_uuid_primary_keys_on_all_tables() -> None:
    for table_name in MVP_TABLES:
        table = Base.metadata.tables[table_name]
        pk_columns = list(table.primary_key.columns)
        assert pk_columns, f"{table_name} has no primary key"
        for column in pk_columns:
            assert isinstance(column.type, Uuid), (
                f"{table_name}.{column.name} is not a UUID primary key"
            )


def test_person_roles_composite_pk() -> None:
    pk_columns = {
        column.name
        for column in Base.metadata.tables["person_roles"].primary_key.columns
    }
    assert pk_columns == {"person_id", "role_id"}


def test_fk_ondelete_behaviors_match_schema_doc() -> None:
    expected = {
        ("person_roles", "person_id"): ("persons", "CASCADE"),
        ("person_roles", "role_id"): ("roles", "RESTRICT"),
        ("event_assignments", "event_id"): ("events", "CASCADE"),
        ("event_assignments", "person_id"): ("persons", "CASCADE"),
        ("event_assignments", "responsibility_id"): (
            "event_responsibilities",
            "RESTRICT",
        ),
        ("event_reports", "event_id"): ("events", "CASCADE"),
        ("event_reports", "author_id"): ("persons", "RESTRICT"),
    }
    actual: dict[tuple[str, str], tuple[str, str]] = {}
    for table_name, table in Base.metadata.tables.items():
        for fk in table.foreign_keys:
            actual[(table_name, fk.parent.name)] = (
                fk.column.table.name,
                fk.ondelete or "",
            )
    for key, value in expected.items():
        assert actual.get(key) == value, (
            f"FK {key}: expected {value}, got {actual.get(key)}"
        )


def test_event_status_check_constraint_exact_d002_set() -> None:
    checks = check_constraints("events")
    assert len(checks) == 1
    sql_text = checks[0]
    for value in ("DRAFT", "SCHEDULED", "IN_PROGRESS", "COMPLETED", "CANCELLED"):
        assert f"'{value}'" in sql_text
    assert "REPORTED" not in sql_text


def test_approval_status_check_constraint_provisional_values() -> None:
    checks = check_constraints("event_assignments")
    assert len(checks) == 1
    sql_text = checks[0]
    assert "'PENDING'" in sql_text
    assert "'APPROVED'" in sql_text


def test_unique_constraints_match_schema_doc() -> None:
    assert unique_column_names("roles") == {"code", "name"}
    assert unique_column_names("event_responsibilities") == {"code", "name"}
    # D-003: at most one report per event.
    assert unique_column_names("event_reports") == {"event_id"}


def test_deliberately_absent_uniqueness() -> None:
    # Exclusivity is TBD-D11 — no UNIQUE(event_id, responsibility_id).
    assignment_table = Base.metadata.tables["event_assignments"]
    for constraint in assignment_table.constraints:
        if isinstance(constraint, UniqueConstraint):
            column_names = {column.name for column in constraint.columns}
            assert column_names != {"event_id", "responsibility_id"}
    for index in assignment_table.indexes:
        if index.unique:
            column_names = {column.name for column in index.columns}
            assert column_names != {"event_id", "responsibility_id"}
    # Phone uniqueness is TBD-D2 — persons.phone must not be unique.
    assert "phone" not in unique_column_names("persons")


def test_justified_indexes_present() -> None:
    def indexed_columns(table_name: str) -> set[str]:
        table = Base.metadata.tables[table_name]
        # Explicit secondary indexes only (PKs are implicitly indexed).
        return {column.name for index in table.indexes for column in index.columns}

    assert "planned_at" in indexed_columns("events")
    assert "status" in indexed_columns("events")
    assert {"event_id", "person_id", "responsibility_id"} <= indexed_columns(
        "event_assignments"
    )
    assert "role_id" in indexed_columns("person_roles")
    assert "author_id" in indexed_columns("event_reports")


def test_audit_timestamps_policy() -> None:
    for table_name in MVP_TABLES:
        columns = Base.metadata.tables[table_name].columns
        assert "created_at" in columns, f"{table_name} missing created_at"
        assert isinstance(columns["created_at"].type, DateTime)
        assert columns["created_at"].type.timezone is True

    for table_name in MVP_TABLES - {"person_roles"}:
        assert "updated_at" in Base.metadata.tables[table_name].columns
    # person_roles is intentionally immutable (schema doc §5.3).
    assert "updated_at" not in Base.metadata.tables["person_roles"].columns


def test_no_invented_audit_fields() -> None:
    forbidden = {
        "deleted_at",
        "is_deleted",
        "created_by",
        "approved_by",
        "approved_at",
        "cancelled_by",
        "reported_at",
    }
    for table_name in MVP_TABLES:
        column_names = set(Base.metadata.tables[table_name].columns)
        invented = column_names & forbidden
        assert not invented, f"{table_name} contains invented audit fields: {invented}"


def test_task_and_availability_tables_absent() -> None:
    all_tables = set(Base.metadata.tables)
    assert "tasks" not in all_tables
    assert "availabilities" not in all_tables
    assert "availability" not in all_tables


def test_ddl_compiles_for_postgresql_dialect() -> None:
    """The full schema renders as valid PostgreSQL DDL (not executed)."""
    from sqlalchemy.dialects import postgresql
    from sqlalchemy.schema import CreateTable

    dialect = postgresql.dialect()
    ddl = "\n".join(
        str(CreateTable(Base.metadata.tables[name]).compile(dialect=dialect))
        for name in sorted(MVP_TABLES)
    )
    # UUID primary keys and timezone-aware timestamps (schema doc §3/§4).
    assert ddl.count("UUID") >= len(MVP_TABLES)
    assert "TIMESTAMP WITH TIME ZONE" in ddl
    # CHECK constraints for status (D-002) and provisional approval values.
    assert "CHECK (status IN" in ddl
    assert "CHECK (approval_status IN" in ddl
    # UNIQUE(event_id) on event_reports enforces D-003.
    assert "UNIQUE (event_id)" in ddl
