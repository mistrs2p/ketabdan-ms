"""ORM models for the Ketabdaneh MVP schema (docs/03-DATABASE-SCHEMA.md).

Importing this package registers every model against `Base.metadata`, which
is what future Alembic migrations will target. Task and Availability are
deliberately absent — deferred per schema doc §13.

The Phase 5 authorization tables (ApplicationRole, Permission and their
join tables, docs/06 §4g) live alongside the business schema — separate
from the business-domain Role/PersonRole pair by design.
"""

from app.models.application_role import ApplicationRole
from app.models.application_role_permission import ApplicationRolePermission
from app.models.event import Event, EventStatus
from app.models.event_assignment import ApprovalStatus, EventAssignment
from app.models.event_report import EventReport
from app.models.event_responsibility import EventResponsibility
from app.models.permission import Permission
from app.models.person import Person
from app.models.person_role import PersonRole
from app.models.role import Role
from app.models.user import User
from app.models.user_application_role import UserApplicationRole

__all__ = [
    "ApplicationRole",
    "ApplicationRolePermission",
    "ApprovalStatus",
    "Event",
    "EventAssignment",
    "EventReport",
    "EventResponsibility",
    "EventStatus",
    "Permission",
    "Person",
    "PersonRole",
    "Role",
    "User",
    "UserApplicationRole",
]
