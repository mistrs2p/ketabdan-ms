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

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "username": "admin",
                    "password": "example-password",
                }
            ]
        }
    )

    username: str = Field(
        min_length=1,
        description="Login identifier. Matched case-insensitively "
        "(normalized to casefold); example value — not a real account.",
    )
    password: str = Field(
        min_length=1,
        description="The account password, sent as an opaque secret. "
        "Example value only.",
    )


class TokenResponse(BaseModel):
    """Successful login response (docs/06 §4f)."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                    "token_type": "bearer",
                    "expires_in": 30,
                }
            ]
        }
    )

    access_token: str = Field(
        description="Signed JWT access token; send it as "
        '`Authorization: Bearer <access_token>`. Example value only.'
    )
    token_type: str = Field(default="bearer", description='Always "bearer".')
    expires_in: int = Field(description="Token lifetime in seconds.")


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

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                    "username": "admin",
                    "active": True,
                }
            ]
        },
    )

    id: UUID = Field(description="The user's stable identifier (token subject).")
    username: str = Field(description="Canonical (casefolded) login identifier.")
    active: bool = Field(
        description="Whether the account may log in and hold valid tokens."
    )


__all__ = [
    "MIN_PASSWORD_LENGTH",
    "LoginRequest",
    "TokenResponse",
    "UserCreate",
    "UserRead",
]
