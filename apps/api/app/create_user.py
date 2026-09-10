"""Controlled bootstrap: create the first authentication user (CLI).

There is no public registration endpoint in this application — it is an
internal, manager-operated system (docs/06 §4f). The only supported way
to create a User is this command, run deliberately by a developer/admin:

    python -m app.create_user <username>

The password is read interactively (getpass) — it is never accepted as a
command-line argument (visible in shell history / process lists) and is
never written to source, logs, or output. Re-running the command with an
existing username fails cleanly; it never resets or overwrites an
existing account.

Users are created *active* by default; no default or well-known password
exists anywhere in the codebase.
"""

import getpass
import sys

from app.db.session import get_session_factory
from app.services import auth as auth_service


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python -m app.create_user <username>", file=sys.stderr)
        return 2

    username = sys.argv[1]
    password = getpass.getpass(f"Password for {username!r}: ")
    confirm = getpass.getpass("Confirm password: ")

    if password != confirm:
        print("Passwords do not match.", file=sys.stderr)
        return 1

    db = get_session_factory()()
    try:
        user = auth_service.create_user(db, username=username, password=password)
    except auth_service.PasswordPolicyError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except auth_service.UsernameTakenError as exc:
        print(f"Username already exists: {exc.username}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    finally:
        db.close()

    # Print identity only — never the password or its hash.
    print(f"Created user {user.username!r} (id={user.id}, active={user.active})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
