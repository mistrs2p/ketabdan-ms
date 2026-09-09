"""Development-only database connectivity verification.

Run from `apps/api`:

    python -m app.db.check

Exits 0 when the configured database answers `SELECT 1`, 1 otherwise
(including when DATABASE_URL is not configured). This is intentionally a
separate CLI entry point — application startup never depends on it and no
public API endpoint is added.
"""

import sys

from sqlalchemy import text

from app.db.session import DatabaseNotConfiguredError, get_engine


def main() -> int:
    try:
        engine = get_engine()
    except DatabaseNotConfiguredError as exc:
        print(f"FAIL: {exc}")
        return 1

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 — report any driver-level failure
        print(f"FAIL: could not connect to the database: {exc}")
        return 1

    print(f"OK: database connection verified ({engine.url.render_as_string(hide_password=True)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
