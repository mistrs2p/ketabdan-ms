"""ORM models for the Ketabdaneh MVP schema (docs/03-DATABASE-SCHEMA.md).

Importing this package registers every model against `Base.metadata`, which
is what future Alembic migrations will target. Task and Availability are
deliberately absent — deferred per schema doc §13.
"""

from app.models.event import Event, EventStatus
from app.models.event_assignment import ApprovalStatus, EventAssignment
from app.models.event_report import EventReport
from app.models.event_responsibility import EventResponsibility
from app.models.person import Person
from app.models.person_role import PersonRole
from app.models.role import Role
from app.models.user import User

__all__ = [
    "ApprovalStatus",
    "Event",
    "EventAssignment",
    "EventReport",
    "EventResponsibility",
    "EventStatus",
    "Person",
    "PersonRole",
    "Role",
    "User",
]
