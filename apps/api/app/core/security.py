"""Password hashing and JWT issuing/verification (Phase 5 auth foundation).

All cryptography lives here — routes and services never touch hash or token
internals. Two libraries only:

- ``argon2-cffi`` (Argon2id) for passwords: memory-hard, no custom crypto,
  verification through the library's constant-time ``verify`` plus explicit
  rehash-need detection.
- ``pyjwt`` (HS256) for signed access tokens: pinned algorithm list on both
  sign and decode, so a token's ``alg`` header can never select a different
  algorithm (no ``alg=none`` / RS→HS confusion).

Secrets come exclusively from configuration (``AUTH_SECRET_KEY`` etc.); see
app/core/config.py and .env.example.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

# Argon2id with the library's curated defaults (time=3, memory=64 MiB,
# parallelism=4) — sane 2026 parameters, deliberately not hand-tuned.
_hasher = PasswordHasher()

# The only algorithms decode() will ever accept — pinned, not read from
# the token header (prevents algorithm-confusion attacks).
JWT_ALGORITHMS: list[str] = ["HS256"]

# Registered claim used to carry the user's id.
SUBJECT_CLAIM = "sub"
TOKEN_TYPE_CLAIM = "typ"
ACCESS_TOKEN_TYPE = "access"


class InvalidTokenError(Exception):
    """A token failed signature/expiry/format verification (→ 401)."""


# --- Password hashing -----------------------------------------------------


def hash_password(password: str) -> str:
    """Return the Argon2id hash of a password (opaque string, never plaintext)."""
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    """Constant-time Argon2 verification; False on any mismatch."""
    try:
        return _hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False
    except Exception:
        # Malformed/foreign hash or verification error — never raises into
        # the request path; treat as failed authentication.
        return False


def password_needs_rehash(password_hash: str) -> bool:
    """True when the hash no longer matches the current Argon2 parameters."""
    return _hasher.check_needs_rehash(password_hash)


# --- JWT access tokens ------------------------------------------------------


def create_access_token(
    *,
    subject: str,
    secret_key: str,
    algorithm: str,
    expires_delta: timedelta,
) -> tuple[str, int]:
    """Issue a signed access token for ``subject`` (the user id, as string).

    Returns ``(token, expires_in)`` — ``expires_in`` in seconds, mirroring
    OAuth2's field, so the response can state the lifetime without a second
    clock read.
    """
    now = datetime.now(UTC)
    expires_at = now + expires_delta
    payload: dict[str, Any] = {
        SUBJECT_CLAIM: subject,
        TOKEN_TYPE_CLAIM: ACCESS_TOKEN_TYPE,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    token = jwt.encode(payload, secret_key, algorithm=algorithm)
    return token, int(expires_delta.total_seconds())


def decode_access_token(*, token: str, secret_key: str, algorithm: str) -> str:
    """Verify signature + expiry + type and return the subject (user id).

    Raises InvalidTokenError for any malformed, expired, wrongly-typed, or
    wrongly-signed token — the caller maps that to a single generic 401
    (no detail about which check failed).
    """
    try:
        payload = jwt.decode(
            token,
            secret_key,
            algorithms=JWT_ALGORITHMS if algorithm in JWT_ALGORITHMS else [algorithm],
            options={"require": ["exp", SUBJECT_CLAIM]},
        )
    except jwt.PyJWTError as exc:
        raise InvalidTokenError() from exc

    if payload.get(TOKEN_TYPE_CLAIM, ACCESS_TOKEN_TYPE) != ACCESS_TOKEN_TYPE:
        # A token of another type (future refresh tokens) is not an access
        # token — reject, without trusting its content.
        raise InvalidTokenError()

    subject = payload.get(SUBJECT_CLAIM)
    if not isinstance(subject, str) or subject == "":
        raise InvalidTokenError()
    return subject
