"""Authorization dependencies (docs/06 §4g) — route protection building blocks.

``require_permission(code)`` is the single factory every protected route
uses. Semantics (§4g):

- authentication failures (missing/invalid/expired token, inactive user)
  are raised by ``get_current_user`` → **401**;
- an authenticated user whose effective permissions do not include the
  required code → **403**, with a generic detail that does not reveal
  which permission was missing.

The check itself is server-side only: permissions come from the
database (services.authz), never from the token payload or any
client-provided value. Route handlers stay untouched — the dependency
is declared once per route decorator.
"""

from collections.abc import Callable

import logging
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.db.session import get_db
from app.models import User
from app.services import authz

# §4g: one generic message — never which permission was required.
GENERIC_403_DETAIL = "Not authorized"

# Security logging (Task 5.8): an authenticated user denied a permission
# is a WARNING worth investigating (role misconfiguration, probing), but
# still a correctly-handled outcome. User id and the missing permission
# code are the minimum needed to diagnose; nothing about the request
# body or headers.
_security_log = logging.getLogger("app.api.security")


def require_permission(permission: str) -> Callable[..., User]:
    """Build a route dependency enforcing ``permission`` (docs/06 §4g).

    Usage::

        @router.get(
            "/events",
            dependencies=[Depends(require_permission(authz.EVENTS_READ))],
        )
    """

    def checker(
        request: Request,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        # get_current_user has already run: past this point the caller is
        # authenticated and active — only the permission question remains.
        if not authz.user_has_permission(db, user=current_user, permission=permission):
            _security_log.warning(
                "authorization failure: user_id=%s lacks permission=%s "
                "request_id=%s",
                current_user.id,
                permission,
                getattr(request.state, "request_id", "-"),
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=GENERIC_403_DETAIL,
            )
        return current_user

    return checker
