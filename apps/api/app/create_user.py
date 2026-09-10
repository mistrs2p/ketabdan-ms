"""Controlled bootstrap: create the first authentication user (CLI).

There is no public registration endpoint in this application — it is an
internal, manager-operated system (docs/06 §4f). The only supported way
to create a User is this command, run deliberately by a developer/admin:

    python -m app.create_user <username> [--role admin]

The password is read interactively (getpass) — it is never accepted as a
command-line argument (visible in shell history / process lists) and is
never written to source, logs, or output. Re-running the command with an
existing username fails cleanly; it never resets or overwrites an
existing account.

``--role`` (docs/06 §4g) optionally assigns an *application* role at
creation — the usual bootstrap flow for the first user is
``--role admin``. It defaults to no role: a new user without ``--role``
can authenticate but has no permissions (403 on business routes) until a
role is explicitly granted via ``python -m app.assign_role``. The role
code is validated against the database *before* the password prompt, so
a typo fails fast. No user is ever granted a role silently.

Users are created *active* by default; no default or well-known password
exists anywhere in the codebase.
"""

import argparse
import getpass
import sys

from app.db.session import get_session_factory
from app.services import auth as auth_service
from app.services import authz


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m app.create_user",
        description="Create an authentication user (interactive).",
    )
    parser.add_argument("username", help="login username")
    parser.add_argument(
        "--role",
        default=None,
        help="application role code to grant at creation "
        "(e.g. admin, manager, operator; see python -m app.assign_role "
        "to list/grant roles later)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])

    db = get_session_factory()()
    try:
        # Validate the role code against the database BEFORE the password
        # prompt, so a typo exits immediately (and non-interactively).
        role = None
        if args.role is not None:
            role = authz.get_application_role_by_code(db, code=args.role)
            if role is None:
                codes = ", ".join(r.code for r in authz.list_application_roles(db))
                print(
                    f"Unknown application role: {args.role}. "
                    f"Available roles: {codes}",
                    file=sys.stderr,
                )
                return 1

        password = getpass.getpass(f"Password for {args.username!r}: ")
        confirm = getpass.getpass("Confirm password: ")

        if password != confirm:
            print("Passwords do not match.", file=sys.stderr)
            return 1

        user = auth_service.create_user(
            db, username=args.username, password=password
        )
        if role is not None:
            authz.assign_application_role(
                db, username=args.username, role_code=role.code
            )
    except auth_service.PasswordPolicyError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except auth_service.UsernameTakenError as exc:
        print(f"Username already exists: {exc.username}", file=sys.stderr)
        return 1
    except (authz.RoleAlreadyGrantedError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    finally:
        db.close()

    # Print identity only — never the password or its hash.
    suffix = f" (role: {role.code})" if role is not None else ""
    print(
        f"Created user {user.username!r} (id={user.id}, active={user.active})"
        f"{suffix}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
