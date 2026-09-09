"""Round-trip persistence tests against an in-memory SQLite database.

Exercises the ORM wiring (relationships, defaults, constraints, delete
behaviors) without requiring the production PostgreSQL instance.
"""

from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import (
    Event,
    EventAssignment,
    EventReport,
    EventResponsibility,
    Person,
    PersonRole,
    Role,
)


def make_role(code: str, name: str) -> Role:
    return Role(code=code, name=name)


def make_person(name: str = "Seyed", **roles: Role) -> Person:
    person = Person(name=name, phone="09120000000")
    person.roles.extend(roles.values())
    return person


class TestPersonRoles:
    def test_person_can_hold_multiple_simultaneous_roles(self, session) -> None:
        learner = make_role("learner", "Learner / Student")
        supporter = make_role("supporter", "Supporter")
        person = make_person(learner=learner, supporter=supporter)
        session.add_all([learner, supporter, person])
        session.commit()

        assert {role.code for role in person.roles} == {"learner", "supporter"}

    def test_same_person_cannot_hold_same_role_twice(self, session) -> None:
        role = make_role("coach", "Coach")
        person = Person(name="Seyed")
        session.add_all([role, person])
        session.flush()

        session.add(PersonRole(person_id=person.id, role_id=role.id))
        session.add(PersonRole(person_id=person.id, role_id=role.id))
        with pytest.raises(IntegrityError):
            session.commit()


class TestEvent:
    def test_defaults_match_schema(self, session) -> None:
        event = Event(
            title="Introduction session",
            type="introduction_session",
            planned_at=datetime(2026, 9, 12, 17, 0, tzinfo=UTC),
        )
        session.add(event)
        session.commit()

        assert event.status == "DRAFT"
        assert event.created_at is not None
        assert event.updated_at is not None

    def test_status_check_rejects_unknown_value(self, session) -> None:
        event = Event(
            title="X",
            type="gathering",
            planned_at=datetime(2026, 9, 12, 17, 0, tzinfo=UTC),
            status="REPORTED",  # rejected with D-002
        )
        session.add(event)
        with pytest.raises(IntegrityError):
            session.commit()


class TestEventAssignment:
    def test_assignment_relationships_wired(self, session) -> None:
        person = Person(name="Seyed")
        responsibility = EventResponsibility(code="registration", name="Registration")
        event = Event(
            title="Introduction session",
            type="introduction_session",
            planned_at=datetime(2026, 9, 12, 17, 0, tzinfo=UTC),
        )
        session.add_all([person, responsibility, event])
        session.flush()

        assignment = EventAssignment(
            event_id=event.id,
            person_id=person.id,
            responsibility_id=responsibility.id,
        )
        session.add(assignment)
        session.commit()

        assert assignment.approval_status == "PENDING"  # provisional default
        assert event.assignments == [assignment]
        assert person.assignments == [assignment]
        assert responsibility.assignments == [assignment]
        assert assignment.event is event
        assert assignment.person is person
        assert assignment.responsibility is responsibility

    def test_approval_status_check_rejects_unknown_value(self, session) -> None:
        person = Person(name="Seyed")
        responsibility = EventResponsibility(code="follow_up", name="Follow-up")
        event = Event(
            title="X",
            type="class",
            planned_at=datetime(2026, 9, 12, 17, 0, tzinfo=UTC),
        )
        session.add_all([person, responsibility, event])
        session.flush()

        session.add(
            EventAssignment(
                event_id=event.id,
                person_id=person.id,
                responsibility_id=responsibility.id,
                approval_status="REJECTED",  # not in the provisional set
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()

    def test_two_people_may_hold_same_responsibility(self, session) -> None:
        """Exclusivity is TBD-D11 — the schema must allow sharing."""
        person_a = Person(name="A")
        person_b = Person(name="B")
        responsibility = EventResponsibility(code="registration", name="Registration")
        event = Event(
            title="X",
            type="gathering",
            planned_at=datetime(2026, 9, 12, 17, 0, tzinfo=UTC),
        )
        session.add_all([person_a, person_b, responsibility, event])
        session.flush()

        session.add_all(
            [
                EventAssignment(
                    event_id=event.id,
                    person_id=person_a.id,
                    responsibility_id=responsibility.id,
                ),
                EventAssignment(
                    event_id=event.id,
                    person_id=person_b.id,
                    responsibility_id=responsibility.id,
                ),
            ]
        )
        session.commit()  # must not raise
        assert len(event.assignments) == 2


class TestEventReport:
    def test_report_is_optional_and_unique_per_event(self, session) -> None:
        author = Person(name="Seyed")
        event = Event(
            title="X",
            type="class",
            planned_at=datetime(2026, 9, 12, 17, 0, tzinfo=UTC),
        )
        session.add_all([author, event])
        session.flush()

        assert event.report is None  # D-003: optional

        report = EventReport(event_id=event.id, author_id=author.id, content="ok")
        session.add(report)
        session.commit()

        # Re-load from the database: the in-memory `event.report` attribute
        # was already (lazily) loaded as None before the insert.
        session.expire(event)
        assert event.report is not None
        assert event.report.content == "ok"
        assert event.report.event_id == event.id
        assert event.report.event is event

        # A second report for the same event violates D-003.
        session.add(
            EventReport(event_id=event.id, author_id=author.id, content="again")
        )
        with pytest.raises(IntegrityError):
            session.commit()


class TestDeleteBehaviors:
    def test_deleting_event_cascades_assignments_and_report(self, session) -> None:
        person = Person(name="Seyed")
        responsibility = EventResponsibility(code="registration", name="Registration")
        event = Event(
            title="X",
            type="gathering",
            planned_at=datetime(2026, 9, 12, 17, 0, tzinfo=UTC),
        )
        session.add_all([person, responsibility, event])
        session.flush()
        session.add(
            EventAssignment(
                event_id=event.id,
                person_id=person.id,
                responsibility_id=responsibility.id,
            )
        )
        session.add(EventReport(event_id=event.id, author_id=person.id, content="ok"))
        session.commit()

        session.delete(event)
        session.commit()

        assert session.query(EventAssignment).count() == 0
        assert session.query(EventReport).count() == 0

    def test_deleting_report_author_is_restricted(self, session) -> None:
        author = Person(name="Seyed")
        event = Event(
            title="X",
            type="class",
            planned_at=datetime(2026, 9, 12, 17, 0, tzinfo=UTC),
        )
        session.add_all([author, event])
        session.flush()
        session.add(EventReport(event_id=event.id, author_id=author.id, content="ok"))
        session.commit()

        session.delete(author)
        with pytest.raises(IntegrityError):
            session.commit()

    def test_deleting_role_in_use_is_restricted(self, session) -> None:
        """RESTRICT on person_roles.role_id (schema doc §7).

        A core-level DELETE is used because the ORM would first remove the
        association rows itself; the database-level delete behavior is what
        this test verifies.
        """
        from sqlalchemy import delete

        role = make_role("supporter", "Supporter")
        person = Person(name="Seyed")
        person.roles.append(role)
        session.add_all([role, person])
        session.commit()

        with pytest.raises(IntegrityError):
            session.execute(delete(Role).where(Role.id == role.id))
