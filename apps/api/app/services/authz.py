"""Authorization service — HTTP-free permission logic (docs/06 §4g).

The whole model in one place:

- a **User** (who can authenticate) may hold any number of
  **ApplicationRole**s (authorization roles — *not* the business-domain
  ``roles`` of a Person);
- an ApplicationRole holds any number of **Permission**s (stable machine
  codes, one per capability the API actually offers);
- a user's effective permissions are the **union** across all their
  roles, resolved server-side from the database on every check — never
  from the token, never from client-provided data.

Permission codes are defined here as constants so route modules never
carry scattered string literals; the seeded database rows (migration
``0005``) use exactly these codes.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    ApplicationRole,
    ApplicationRolePermission,
    Permission,
    User,
    UserApplicationRole,
)

# --- Permission codes (one per current API capability; docs/06 §4g) ---------

ROLES_READ = "roles:read"
PEOPLE_READ = "people:read"
PEOPLE_CREATE = "people:create"
EVENTS_READ = "events:read"
EVENTS_CREATE = "events:create"
ASSIGNMENTS_READ = "assignments:read"
ASSIGNMENTS_CREATE = "assignments:create"

ALL_PERMISSION_CODES: frozenset[str] = frozenset(
    {
        ROLES_READ,
        PEOPLE_READ,
        PEOPLE_CREATE,
        EVENTS_READ,
        EVENTS_CREATE,
        ASSIGNMENTS_READ,
        ASSIGNMENTS_CREATE,
    }
)


# --- Domain exceptions (routers/CLIs translate; never raised over HTTP) ------


class UnknownApplicationRoleError(ValueError):
    """No application role with the given code exists."""

    def __init__(self, code: str) -> None:
        super().__init__(f"Unknown application role: {code}")
        self.code = code


class UserNotFoundError(ValueError):
    """No user with the given canonical username exists (CLI paths only)."""

    def __init__(self, username: str) -> None:
        super().__init__(f"User not found: {username}")
        self.username = username


class RoleAlreadyGrantedError(ValueError):
    """The user already holds this application role."""

    def __init__(self, username: str, role_code: str) -> None:
        super().__init__(f"User {username} already has role {role_code}")
        self.username = username
        self.role_code = role_code


# --- Permission resolution (server-side, per check) --------------------------


def user_permission_codes(db: Session, *, user: User) -> set[str]:
    """The user's effective permission codes — the union across all their
    application roles. Resolved from the database, never from the token."""
    return set(
        db.scalars(
            select(Permission.code)
            .join(
                ApplicationRolePermission,
                ApplicationRolePermission.permission_id == Permission.id,
            )
            .join(
                UserApplicationRole,
                UserApplicationRole.application_role_id
                == ApplicationRolePermission.application_role_id,
            )
            .where(UserApplicationRole.user_id == user.id)
        ).all()
    )


def user_has_permission(db: Session, *, user: User, permission: str) -> bool:
    """True when the user's effective permissions include ``permission``.

    A user with no application roles has no permissions at all — the
    authorization denial is the caller's to translate (403 over HTTP).
    """
    return permission in user_permission_codes(db, user=user)


# --- Role assignment (bootstrap CLI / explicit operator flows) ----------------


def list_application_roles(db: Session) -> list[ApplicationRole]:
    """All application roles, ordered by code (for CLI listing/docs)."""
    return list(
        db.scalars(select(ApplicationRole).order_by(ApplicationRole.code)).all()
    )


def get_application_role_by_code(
    db: Session, *, code: str
) -> ApplicationRole | None:
    return db.scalar(select(ApplicationRole).where(ApplicationRole.code == code))


def assign_application_role(
    db: Session, *, username: str, role_code: str
) -> User:
    """Grant an application role to an existing user (by canonical username).

    Explicit and idempotence-refusing: an unknown role or an already-held
    role raises, so operators see the true state instead of a silent
    no-op. Used by the CLI (``python -m app.assign_role``); there is no
    HTTP endpoint for role assignment in this task.
    """
    from app.services.auth import normalize_username

    canonical = normalize_username(username)
    user = db.scalar(select(User).where(User.username == canonical))
    if user is None:
        raise UserNotFoundError(username)

    role = get_application_role_by_code(db, code=role_code)
    if role is None:
        raise UnknownApplicationRoleError(role_code)

    already = db.scalar(
        select(UserApplicationRole).where(
            UserApplicationRole.user_id == user.id,
            UserApplicationRole.application_role_id == role.id,
        )
    )
    if already is not None:
        raise RoleAlreadyGrantedError(canonical, role_code)

    db.add(UserApplicationRole(user=user, application_role=role))
    db.commit()
    return user
