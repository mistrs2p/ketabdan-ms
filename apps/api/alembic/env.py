"""Alembic migration environment.

The database URL comes from the application's pydantic-settings
configuration (DATABASE_URL environment variable / apps/api/.env) — the same
configuration that drives the application at runtime. Nothing is hard-coded
here or in alembic.ini.

Schema structure is derived from the SQLAlchemy models: importing
``app.models`` registers all ORM models on ``Base.metadata``, which is the
single ``target_metadata`` used by autogenerate and ``alembic check``. No
table definitions are duplicated in this file.

Logging: deliberately NOT configured here. The template's
``fileConfig(alembic.ini)`` REPLACES the root logger's handlers and (with
``disable_existing_loggers``, the stdlib default) silently disables
already-configured loggers — clobbering the application's central logging
(Task 5.8, app/core/logging.py) whenever migrations run in-process. The
alembic.ini logging sections are inert leftovers; keep logging owned by
one place.
"""

from alembic import context
from sqlalchemy import engine_from_config, pool

import app.models  # noqa: F401 — registers all ORM models on Base.metadata
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.base import Base

# Alembic Config object (provides access to values in alembic.ini).
config = context.config

# Same central logging as the application — idempotent, so importing this
# module twice (or running migrations in an already-configured process)
# never duplicates handlers or resets them.
configure_logging(level=get_settings().log_level)

# Resolve the URL from the application settings. Failing early with a clear
# message is better than a confusing "could not parse URL" deep inside
# SQLAlchemy.
database_url = get_settings().database_url
if not database_url:
    raise RuntimeError(
        "DATABASE_URL is not set; configure it (see apps/api/.env.example) "
        "before running migrations."
    )
config.set_main_option("sqlalchemy.url", database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (emit SQL to stdout, no DB needed)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (connect to the database)."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
