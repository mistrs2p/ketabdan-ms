"""Assign an application role to an existing user (CLI, docs/06 §4g).

The explicit, safe mechanism for granting authorization after a user
already exists (users are created via ``python -m app.create_user``,
which can also grant a role at creation with ``--role``):

    python -m app.assign_role <username> <role_code>   # grant
    python -m app.assign_role --list                   # list roles/users

This is the only supported way to change a user's application roles —
there is no HTTP endpoint for it (an admin API is future work). The
command is deliberately loud: unknown usernames and unknown roles fail
with a clear message, and an already-held role is reported as an error
rather than silently ignored, so the operator always sees the true
state. It never touches passwords.
"""

import argparse
import sys

from sqlalchemy import select

from app.db.session import get_session_factory
from app.models import ApplicationRole, User, UserApplicationRole
from app.services import authz


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m app.assign_role",
        description="Grant an application role to an existing user.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="list application roles and each user's granted roles, then exit",
    )
    parser.add_argument("username", nargs="?", help="existing login username")
    parser.add_argument("role_code", nargs="?", help="application role code")
    return parser.parse_args(argv)


def print_state(db) -> None:
    """List application roles and who currently holds them."""
    for role in authz.list_application_roles(db):
        holders = db.scalars(
            select(User.username)
            .join(UserApplicationRole, UserApplicationRole.user_id == User.id)
            .where(UserApplicationRole.application_role_id == role.id)
            .order_by(User.username)
        ).all()
        who = ", ".join(holders) if holders else "(nobody)"
        print(f"{role.code:10} {role.name:14} {who}")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])

    db = get_session_factory()()
    try:
        if args.list:
            print_state(db)
            return 0

        if not args.username or not args.role_code:
            print(
                "Usage: python -m app.assign_role <username> <role_code> "
                "(or --list)",
                file=sys.stderr,
            )
            return 2

        user = authz.assign_application_role(
            db, username=args.username, role_code=args.role_code
        )
        # Collected before the session closes (below) — the message must
        # reflect the full grant set, not just the one just added.
        granted = db.scalars(
            select(ApplicationRole.code)
            .join(
                UserApplicationRole,
                UserApplicationRole.application_role_id == ApplicationRole.id,
            )
            .where(UserApplicationRole.user_id == user.id)
            .order_by(ApplicationRole.code)
        ).all()
    except authz.UserNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except authz.UnknownApplicationRoleError:
        codes = ", ".join(r.code for r in authz.list_application_roles(db))
        print(
            f"Unknown application role: {args.role_code}. "
            f"Available roles: {codes}",
            file=sys.stderr,
        )
        return 1
    except authz.RoleAlreadyGrantedError as exc:
        print(f"Nothing to do — {exc.username} already has role {exc.role_code}.")
        return 0
    finally:
        db.close()

    print(f"{user.username!r} now holds: {', '.join(granted)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
