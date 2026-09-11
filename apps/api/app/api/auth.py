"""Authentication endpoints (docs/06 §4f).

``POST /api/auth/login``  — verify credentials, issue an access token.
``GET  /api/auth/me``     — return the authenticated user (no hash).

Error semantics (§4b/§4f): every authentication failure is a single
generic 401 — unknown user, wrong password, inactive account, missing,
malformed, invalid, or expired token are indistinguishable to callers.
403 is authorization's status (docs/06 §4g, Task 5.2) and never appears
on these endpoints. No auth failure path may produce a 500 or leak
internal details.

``get_current_user`` is the authentication half every protected route
builds on (via ``app.api.deps.require_permission``, §4g) — it does no
role/permission checks by design.

Security logging (Task 5.8): every authentication failure is logged at
WARNING on ``app.api.security`` with the failure reason, the request id,
and the minimum user reference needed to investigate (username on login
failures — never the password, never the token, never the Authorization
header value). The API response stays generic: the log is the only place
the reason is recorded.
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import User
from app.schemas.auth import LoginRequest, TokenResponse, UserRead
from app.services import auth as auth_service

router = APIRouter(prefix="/api/auth", tags=["auth"])

_security_log = logging.getLogger("app.api.security")

# auto_error=False: a missing Authorization header must become our own
# generic 401, not FastAPI's 403-flavored "Not authenticated" default.
_bearer_scheme = HTTPBearer(auto_error=False)

# §4f: one message for every auth failure — nothing about which check.
GENERIC_401_DETAIL = "Not authenticated"


def _request_id(request: Request) -> str:
    """The request's correlation id (set by RequestLoggingMiddleware)."""
    return getattr(request.state, "request_id", "-")


def _loggable_username(username: str) -> str:
    """The username for security logs, length-bounded.

    The request body is attacker-controlled: an oversized "username"
    must not be echoed verbatim into the log (flooding), so anything
    past a sane bound is truncated with an explicit marker.
    """
    max_len = 64
    return username if len(username) <= max_len else username[:max_len] + "…"


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Resolve the Bearer token to a live, active User (401 otherwise).

    Read Authorization header → validate the Bearer scheme → verify the
    JWT signature and expiration → extract the subject → load the user →
    reject nonexistent or inactive accounts. Role/permission checks are
    deliberately absent — they live in app.api.deps (docs/06 §4g).
    """
    if credentials is None or credentials.scheme.lower() != "bearer":
        _security_log.warning(
            "auth failure: missing or non-bearer authorization header "
            "request_id=%s",
            _request_id(request),
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=GENERIC_401_DETAIL,
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        subject = auth_service.resolve_token_subject(token=credentials.credentials)
    except auth_service.InvalidTokenError as exc:
        # Never the token value itself — only that it failed validation.
        _security_log.warning(
            "auth failure: invalid or expired token request_id=%s",
            _request_id(request),
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=GENERIC_401_DETAIL,
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    # A syntactically non-UUID subject (possible in a forged token) is
    # just another invalid token — generic 401, never a 500.
    try:
        user_id = UUID(subject)
    except ValueError as exc:
        _security_log.warning(
            "auth failure: token subject is not a user id request_id=%s",
            _request_id(request),
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=GENERIC_401_DETAIL,
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    user = db.get(User, user_id)
    if user is None or not user.active:
        # The token itself was valid — a nonexistent or deactivated user
        # here is worth investigating (stolen token of a removed account).
        _security_log.warning(
            "auth failure: token subject has no active user user_id=%s "
            "request_id=%s",
            user_id,
            _request_id(request),
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=GENERIC_401_DETAIL,
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
)
def login(
    payload: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Verify credentials and return a signed access token (docs/06 §4f).

    Failures return a generic 401 with the same body for unknown user,
    wrong password, and inactive account — no user enumeration.
    """
    try:
        user = auth_service.authenticate(
            db, username=payload.username, password=payload.password
        )
        token, expires_in = auth_service.issue_access_token(user)
    except auth_service.AuthenticationError as exc:
        # The username is the minimum needed to spot brute-force attempts;
        # the password is never logged, and the failure reason stays out
        # of the response.
        _security_log.warning(
            "auth failure: login rejected username=%r request_id=%s",
            _loggable_username(payload.username),
            _request_id(request),
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=auth_service.GENERIC_AUTH_FAILURE,
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    _security_log.info(
        "auth success: login user_id=%s request_id=%s",
        user.id,
        _request_id(request),
    )
    return TokenResponse(access_token=token, expires_in=expires_in)


@router.get(
    "/me",
    response_model=UserRead,
    status_code=status.HTTP_200_OK,
)
def read_current_user(current_user: User = Depends(get_current_user)) -> User:
    """The authenticated identity — public projection only, no hash."""
    return current_user
