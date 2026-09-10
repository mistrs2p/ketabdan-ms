"""Authentication API schemas (docs/06 §4f).

``LoginRequest`` is the contract for ``POST /api/auth/login``;
``TokenResponse`` mirrors the OAuth2-style login body
(``access_token`` / ``token_type: "bearer"`` / ``expires_in``);
``UserRead`` is what ``GET /api/auth/me`` returns — and deliberately
contains no ``password_hash``: hashes never leave the server (§4f
security rule).
"""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.services.auth import MIN_PASSWORD_LENGTH


class LoginRequest(BaseModel):
    """Request body for ``POST /api/auth/login`` (docs/06 §4f).

    Only presence/type validation: the identifier is normalized
    casefold in the service, and the password is treated as an opaque
    secret (minimal policy checked at *creation* time, not login time).
    """

    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class TokenResponse(BaseModel):
    """Successful login response (docs/06 §4f)."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class UserCreate(BaseModel):
    """Request contract for the bootstrap user-creation path (docs/06 §4f).

    Used only by the controlled bootstrap mechanism (CLI), never by a
    public endpoint — there is no registration API in this application.
    """

    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class UserRead(BaseModel):
    """An authenticated identity, as returned by ``GET /api/auth/me``.

    No hash, no secret material — the public projection of a User.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str
    active: bool


__all__ = [
    "MIN_PASSWORD_LENGTH",
    "LoginRequest",
    "TokenResponse",
    "UserCreate",
    "UserRead",
]
