"""Database engine, session factory, and FastAPI session dependency.

The engine is created lazily on first use: importing this module (and
therefore starting the application) never requires `DATABASE_URL` to be
set. Anything that actually opens a session without configuration gets a
clear error at that point instead.
"""

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


class DatabaseNotConfiguredError(RuntimeError):
    """Raised when a database session is requested without DATABASE_URL."""


@lru_cache
def get_engine() -> Engine:
    """Create (once) and return the SQLAlchemy engine.

    Raises:
        DatabaseNotConfiguredError: if `DATABASE_URL` is not configured.
    """
    database_url = get_settings().database_url
    if not database_url:
        raise DatabaseNotConfiguredError(
            "DATABASE_URL is not set; configure it (see apps/api/.env.example) "
            "before using database features."
        )
    return create_engine(database_url, pool_pre_ping=True)


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    """Create (once) and return the session factory bound to the engine."""
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """FastAPI dependency yielding a database session.

    Use with `Depends(get_db)`. The session is always closed, even on error.
    """
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()
