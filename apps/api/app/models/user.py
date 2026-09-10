"""User — an authenticated application identity (Phase 5 auth foundation).

Deliberately separate from ``Person`` (docs/00 §3): Person is a business
entity (a branch member), User is *who is logged in*. A future task may link
them; no relationship is forced here. Login identifier: username — the
project's reference data uses machine-style codes, no email exists anywhere
in the domain, and the internal manager-operated application has no mail
flow, so email would be an invented requirement (documented in docs/06 §4f).
"""

from uuid import UUID

from sqlalchemy import Boolean, Text, true
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, uuid_pk


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[UUID] = uuid_pk()

    # Unique login identifier. Stored exactly as provided except for the
    # casefold normalization applied at creation/lookup (see services.auth)
    # — one canonical form, no silent per-request transformations.
    username: Mapped[str] = mapped_column(Text, nullable=False, unique=True)

    # Argon2id hash (app.core.security) — never plaintext, never reversible.
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)

    # Account switch. Inactive users fail authentication with the same
    # generic 401 as everyone else (docs/06 §4f — no enumeration).
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=true()
    )
