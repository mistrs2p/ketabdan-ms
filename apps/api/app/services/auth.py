"""Authentication service — HTTP-free domain logic for login and tokens.

Follows the established service pattern (app/services/persons.py): the
router translates exceptions into HTTP; this module never imports FastAPI.

User-enumeration protection (docs/06 §4f): every failure — unknown user,
wrong password, inactive account — raises the same ``AuthenticationError``
with one generic message. No code path may distinguish the causes.
"""

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import AUTH_SECRET_PLACEHOLDER, get_settings
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    password_needs_rehash,
    verify_password,
)
from app.models import User

# One canonical login-failure message — never reveals which check failed.
GENERIC_AUTH_FAILURE = "Invalid username or password"

# Canonical username form: casefold once, here, at every boundary (creation
# and lookup) — so "Ali" and "ALI" are the same account but no per-request
# silent transformation happens inside the database layer.
MIN_PASSWORD_LENGTH = 8


class AuthenticationError(Exception):
    """Credentials rejected — unknown user, wrong password, or inactive."""

    def __init__(self) -> None:
        super().__init__(GENERIC_AUTH_FAILURE)


class InvalidTokenError(Exception):
    """The presented token is invalid, expired, or not an access token."""


class PasswordPolicyError(ValueError):
    """The supplied password does not satisfy the minimal policy (§4f)."""

    def __init__(self) -> None:
        super().__init__(
            f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
        )


class UsernameTakenError(ValueError):
    """The username (in canonical form) already exists."""

    def __init__(self, username: str) -> None:
        super().__init__(f"Username already exists: {username}")
        self.username = username


def normalize_username(username: str) -> str:
    """Canonical form of a login identifier: trimmed + casefolded."""
    return username.strip().casefold()


def validate_password_policy(password: str) -> str:
    """Minimal policy (docs/06 §4f): non-empty and >= 8 characters.

    No complexity rules — the project is internal and small; inventing
    enterprise rules is out of scope. The password is returned opaque.
    """
    if len(password) < MIN_PASSWORD_LENGTH:
        raise PasswordPolicyError()
    return password


class InsecureSecretError(RuntimeError):
    """AUTH_SECRET_KEY is the known placeholder and not explicitly allowed.

    Raised by authentication paths in production contexts so the system can
    never silently sign tokens with a publicly-known secret.
    """


def ensure_secure_auth_secret() -> None:
    """Refuse the known placeholder secret unless explicitly allowed.

    The placeholder default in ``app.core.config`` exists only so the app
    can start for local development; anything that actually *issues or
    verifies* tokens must pass this check. Production sets
    ``AUTH_ALLOW_INSECURE_DEV_SECRET=0`` (or simply a real secret) — and
    production Settings validation rejects the placeholder (and the flag
    itself) at startup, so this guard is the belt to that suspenders.
    """
    settings = get_settings()
    if (
        settings.auth_secret_key.get_secret_value() == AUTH_SECRET_PLACEHOLDER
        and not settings.auth_allow_insecure_dev_secret
    ):
        raise InsecureSecretError(
            "AUTH_SECRET_KEY is the insecure placeholder. Set a real secret "
            "in the environment (see .env.example)."
        )


def authenticate(db: Session, *, username: str, password: str) -> User:
    """Verify credentials and return the User; raise AuthenticationError.

    All three failure modes (unknown user / wrong password / inactive)
    raise the identical exception — timing differences are mitigated by
    always performing one Argon2 verification against a dummy hash when
    the user does not exist, so response time does not leak existence.
    """
    ensure_secure_auth_secret()
    canonical = normalize_username(username)
    user = db.scalar(select(User).where(User.username == canonical))

    if user is None:
        # Dummy verification keeps the timing profile of a real attempt.
        verify_password("$argon2id$v=19$m=65536,t=3,p=4$dGVzdA$dGVzdA", password)
        raise AuthenticationError()

    if not verify_password(user.password_hash, password):
        raise AuthenticationError()

    if not user.active:
        raise AuthenticationError()

    # Transparent upgrade if Argon2 parameters changed since the hash was
    # made (never on a failed login — only a proven-correct password).
    if password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
        db.commit()

    return user


def issue_access_token(user: User) -> tuple[str, int]:
    """Create a signed access token for an authenticated user.

    Returns ``(token, expires_in_seconds)``.
    """
    settings = get_settings()
    return create_access_token(
        subject=str(user.id),
        secret_key=settings.auth_secret_key.get_secret_value(),
        algorithm=settings.auth_algorithm,
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
    )


def resolve_token_subject(*, token: str) -> str:
    """Verify a bearer token and return its subject (user id string).

    Raises InvalidTokenError for any malformed/expired/wrongly-signed or
    wrongly-typed token (app.core.security).
    """
    from app.core.security import InvalidTokenError as CoreInvalidTokenError

    ensure_secure_auth_secret()
    settings = get_settings()
    try:
        return decode_access_token(
            token=token,
            secret_key=settings.auth_secret_key.get_secret_value(),
            algorithm=settings.auth_algorithm,
        )
    except CoreInvalidTokenError as exc:
        raise InvalidTokenError() from exc


def create_user(
    db: Session, *, username: str, password: str, active: bool = True
) -> User:
    """Create an authentication user (bootstrap / future admin flows).

    Password policy is enforced; usernames are stored in canonical form;
    a duplicate canonical username raises UsernameTakenError (atomic —
    nothing is written).
    """
    canonical = normalize_username(username)
    if not canonical:
        raise ValueError("Username must not be empty.")
    validate_password_policy(password)

    existing = db.scalar(select(User).where(User.username == canonical))
    if existing is not None:
        raise UsernameTakenError(canonical)

    user = User(
        username=canonical,
        password_hash=hash_password(password),
        active=active,
    )
    db.add(user)
    db.commit()
    return user
