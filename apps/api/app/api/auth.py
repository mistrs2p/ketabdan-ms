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
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import User
from app.schemas.auth import LoginRequest, TokenResponse, UserRead
from app.services import auth as auth_service

router = APIRouter(prefix="/api/auth", tags=["auth"])

# auto_error=False: a missing Authorization header must become our own
# generic 401, not FastAPI's 403-flavored "Not authenticated" default.
_bearer_scheme = HTTPBearer(auto_error=False)

# §4f: one message for every auth failure — nothing about which check.
GENERIC_401_DETAIL = "Not authenticated"


def get_current_user(
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
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=GENERIC_401_DETAIL,
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        subject = auth_service.resolve_token_subject(token=credentials.credentials)
    except auth_service.InvalidTokenError as exc:
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
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=GENERIC_401_DETAIL,
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    user = db.get(User, user_id)
    if user is None or not user.active:
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
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
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
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=auth_service.GENERIC_AUTH_FAILURE,
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    return TokenResponse(access_token=token, expires_in=expires_in)


@router.get(
    "/me",
    response_model=UserRead,
    status_code=status.HTTP_200_OK,
)
def read_current_user(current_user: User = Depends(get_current_user)) -> User:
    """The authenticated identity — public projection only, no hash."""
    return current_user
