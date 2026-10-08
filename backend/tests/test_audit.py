import pytest

from database.audit import AuditService
from database.connection import SessionLocal, engine
from database.models import Base


def test_audit_event_creation_and_retrieval():
    Base.metadata.create_all(bind=engine)

    session = SessionLocal()

    try:
        audit = AuditService(session)

        event = audit.record_event(
            event_id="audit-test-1",
            case_id="audit-case-1",
            actor_type="system",
            actor_id="orchestrator",
            action="task_completed",
            entity_type="task",
            entity_id="task-1",
            metadata={
                "task_type": "verification",
                "result": "completed",
            },
        )

        session.commit()

        assert event.event_id == "audit-test-1"
        assert event.case_id == "audit-case-1"
        assert event.actor_type == "system"
        assert event.actor_id == "orchestrator"
        assert event.action == "task_completed"
        assert event.entity_type == "task"
        assert event.entity_id == "task-1"
        assert event.metadata_json["result"] == "completed"

        retrieved = audit.get_event("audit-test-1")

        assert retrieved is not None
        assert retrieved.event_id == "audit-test-1"
        assert retrieved.action == "task_completed"

    finally:
        session.close()


def test_audit_case_history():
    session = SessionLocal()

    try:
        audit = AuditService(session)

        audit.record_event(
            event_id="audit-history-1",
            case_id="audit-history-case",
            actor_type="system",
            action="case_created",
            entity_type="case",
            entity_id="audit-history-case",
        )

        audit.record_event(
            event_id="audit-history-2",
            case_id="audit-history-case",
            actor_type="agent",
            action="task_started",
            entity_type="task",
            entity_id="task-2",
        )

        audit.record_event(
            event_id="audit-history-3",
            case_id="audit-history-case",
            actor_type="human",
            actor_id="reviewer-1",
            action="review_completed",
            entity_type="human_review",
            entity_id="review-1",
        )

        session.commit()

        events = audit.list_case_events("audit-history-case")

        assert len(events) == 3
        assert [event.event_id for event in events] == [
            "audit-history-1",
            "audit-history-2",
            "audit-history-3",
        ]

    finally:
        session.close()


@pytest.mark.parametrize(
    "field,value",
    [
        ("event_id", ""),
        ("case_id", ""),
        ("actor_type", ""),
        ("action", ""),
        ("entity_type", ""),
    ],
)
def test_audit_event_required_fields(field, value):
    session = SessionLocal()

    try:
        audit = AuditService(session)

        kwargs = {
            "event_id": "audit-validation-test",
            "case_id": "audit-validation-case",
            "actor_type": "system",
            "action": "test_action",
            "entity_type": "case",
        }

        kwargs[field] = value

        with pytest.raises(ValueError):
            audit.record_event(**kwargs)

    finally:
        session.close()


def test_audit_event_is_persisted_only_after_commit():
    session = SessionLocal()

    try:
        audit = AuditService(session)

        audit.record_event(
            event_id="audit-transaction-test",
            case_id="audit-transaction-case",
            actor_type="system",
            action="transaction_test",
            entity_type="case",
        )

        # The event is part of the current transaction but has not
        # been committed yet.
        session.rollback()

    finally:
        session.close()

    verification_session = SessionLocal()

    try:
        audit = AuditService(verification_session)

        retrieved = audit.get_event("audit-transaction-test")

        assert retrieved is None

    finally:
        verification_session.close()