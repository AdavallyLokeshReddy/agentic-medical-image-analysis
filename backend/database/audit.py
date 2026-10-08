from typing import Any

from sqlalchemy.orm import Session

from database.models import AuditEventModel
from database.repository import MedicalCaseRepository


class AuditService:
    """
    Append-oriented audit service for governed medical-AI actions.

    Audit events are created through this service and persisted through
    the repository layer.

    Historical audit events are never updated or deleted by this service.
    """

    def __init__(self, session: Session):
        self.session = session
        self.repository = MedicalCaseRepository(session)

    def record_event(
        self,
        event_id: str,
        case_id: str,
        actor_type: str,
        action: str,
        entity_type: str,
        actor_id: str | None = None,
        entity_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditEventModel:
        """
        Record one governed audit event.

        The event is added to the current database transaction.
        The caller controls the final commit.
        """

        if not event_id:
            raise ValueError("event_id must not be empty.")

        if not case_id:
            raise ValueError("case_id must not be empty.")

        if not actor_type:
            raise ValueError("actor_type must not be empty.")

        if not action:
            raise ValueError("action must not be empty.")

        if not entity_type:
            raise ValueError("entity_type must not be empty.")

        event = self.repository.add_audit_event(
            event_id=event_id,
            case_id=case_id,
            actor_type=actor_type,
            actor_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            metadata=metadata,
        )

        return event

    def get_event(
        self,
        event_id: str,
    ) -> AuditEventModel | None:
        """
        Retrieve one audit event.
        """

        return self.repository.get_audit_event(event_id)

    def list_case_events(
        self,
        case_id: str,
    ) -> list[AuditEventModel]:
        """
        Retrieve audit history for one case in chronological order.
        """

        return self.repository.list_audit_events(case_id)