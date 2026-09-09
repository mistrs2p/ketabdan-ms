"""Person service — creation logic for the first write endpoint (docs/06 §4a).

Until now the API layer was read-only and its routers issued trivial queries
directly. Person creation is the first operation with real logic — resolving
role codes against the seeded reference data and writing the person plus its
memberships atomically — so it lives here, behind a small HTTP-free interface
the router calls.
"""

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Person, Role
from app.schemas.person import PersonCreate


class UnknownRoleError(ValueError):
    """A requested role code does not exist in the reference data."""

    def __init__(self, codes: Sequence[str]) -> None:
        self.codes = list(codes)
        super().__init__(f"Unknown role code(s): {', '.join(self.codes)}")


def create_person(db: Session, payload: PersonCreate) -> Person:
    """Create a Person together with its role memberships in one transaction.

    Roles are identified by their stable machine codes (docs/03 §5.2).
    Duplicate codes in the input are collapsed — a person holds a *set* of
    roles (D-001), so `["supporter", "supporter"]` means one membership.
    Raises ``UnknownRoleError`` when a code has no matching reference row;
    nothing is written in that case (atomicity, docs/06 §4a).
    """
    # dict.fromkeys: preserve input order while collapsing duplicates.
    codes = list(dict.fromkeys(payload.roles))

    roles: list[Role] = []
    if codes:
        found = {
            role.code: role
            for role in db.scalars(select(Role).where(Role.code.in_(codes)))
        }
        missing = [code for code in codes if code not in found]
        if missing:
            raise UnknownRoleError(missing)
        roles = [found[code] for code in codes]

    person = Person(
        name=payload.name,
        phone=payload.phone,
        active=payload.active,
        roles=roles,
    )
    db.add(person)
    db.commit()
    return person
