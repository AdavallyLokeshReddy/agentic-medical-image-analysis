from typing import Any

from sqlalchemy.orm import Session

from agent.case_state import CaseState
from database.audit import AuditService


class CaseAudit:
    """
    Audit integration bridge for the runtime CaseState.

    CaseState remains independent of the database layer.
    This class translates governed workflow events into
    append-only audit records.
    """

    def __init__(self, session: Session):
        self.session = session
        self.audit_service = AuditService(session)

    def record_case_created(
        self,
        case_state: CaseState,
        actor_type: str = "system",
        actor_id: str | None = None,
    ):
        """
        Record creation of a case.
        """

        return self.audit_service.record_event(
            event_id=f"{case_state.case_id}-created",
            case_id=case_state.case_id,
            actor_type=actor_type,
            actor_id=actor_id,
            action="case_created",
            entity_type="case",
            entity_id=case_state.case_id,
            metadata={
                "modality": case_state.modality.value,
                "body_region": case_state.body_region,
                "clinical_question": (
                    case_state.clinical_question
                ),
            },
        )

    def record_evidence_added(
        self,
        case_state: CaseState,
        evidence_id: str,
        actor_type: str = "system",
        actor_id: str | None = None,
    ):
        """
        Record creation of an evidence object.
        """

        evidence = case_state.get_evidence(evidence_id)

        if evidence is None:
            raise ValueError(
                f"Evidence '{evidence_id}' does not exist "
                "in CaseState."
            )

        return self.audit_service.record_event(
            event_id=f"{case_state.case_id}-evidence-{evidence_id}",
            case_id=case_state.case_id,
            actor_type=actor_type,
            actor_id=actor_id,
            action="evidence_added",
            entity_type="evidence",
            entity_id=evidence_id,
            metadata={
                "evidence_type": evidence.evidence_type,
                "source": evidence.source,
                "status": evidence.status.value,
                "task_id": evidence.task_id,
            },
        )

    def record_verification(
        self,
        case_state: CaseState,
        actor_type: str = "system",
        actor_id: str | None = None,
    ):
        """
        Record a verification state change.
        """

        return self.audit_service.record_event(
            event_id=(
                f"{case_state.case_id}-verification-"
                f"{case_state.verification.status.value}"
            ),
            case_id=case_state.case_id,
            actor_type=actor_type,
            actor_id=actor_id,
            action="verification_completed",
            entity_type="verification",
            entity_id=(
                f"{case_state.case_id}-verification"
            ),
            metadata={
                "status": (
                    case_state.verification.status.value
                ),
                "checks": case_state.verification.checks,
                "warnings": (
                    case_state.verification.warnings
                ),
                "failed_checks": (
                    case_state.verification.failed_checks
                ),
                "human_review_required": (
                    case_state.verification
                    .human_review_required
                ),
            },
        )

    def record_human_review(
        self,
        case_state: CaseState,
        review_id: str,
        actor_type: str = "human",
        actor_id: str | None = None,
    ):
        """
        Record completion of a human review.
        """

        review = case_state.get_human_review(review_id)

        if review is None:
            raise ValueError(
                f"Human review '{review_id}' does not exist "
                "in CaseState."
            )

        return self.audit_service.record_event(
            event_id=f"{case_state.case_id}-review-{review_id}",
            case_id=case_state.case_id,
            actor_type=actor_type,
            actor_id=(
                actor_id
                if actor_id is not None
                else review.reviewer_id
            ),
            action="human_review_completed",
            entity_type="human_review",
            entity_id=review_id,
            metadata={
                "report_id": review.report_id,
                "status": review.status.value,
                "decision": (
                    review.decision.value
                    if review.decision is not None
                    else None
                ),
                "reviewer_id": review.reviewer_id,
                "reviewed_evidence_ids": (
                    review.reviewed_evidence_ids
                ),
                "reviewed_verification_ids": (
                    review.reviewed_verification_ids
                ),
                "intervention_reason": (
                    review.intervention_reason
                ),
            },
        )

    def record_triage(
        self,
        case_state: CaseState,
        triage_id: str,
        actor_type: str = "human",
        actor_id: str | None = None,
    ):
        """
        Record a triage decision.
        """

        triage = case_state.get_triage(triage_id)

        if triage is None:
            raise ValueError(
                f"Triage '{triage_id}' does not exist "
                "in CaseState."
            )

        return self.audit_service.record_event(
            event_id=f"{case_state.case_id}-triage-{triage_id}",
            case_id=case_state.case_id,
            actor_type=actor_type,
            actor_id=(
                actor_id
                if actor_id is not None
                else triage.approved_by
            ),
            action="triage_approved",
            entity_type="triage",
            entity_id=triage_id,
            metadata={
                "level": triage.level.value,
                "reason": triage.reason,
                "verification_status": (
                    triage.verification_status.value
                ),
                "requires_human_approval": (
                    triage.requires_human_approval
                ),
                "approved_by": triage.approved_by,
            },
        )

    def record_communication(
        self,
        case_state: CaseState,
        communication_id: str,
        actor_type: str = "system",
        actor_id: str | None = None,
    ):
        """
        Record creation of a communication event.
        """

        communication = case_state.get_communication(
            communication_id
        )

        if communication is None:
            raise ValueError(
                f"Communication '{communication_id}' "
                "does not exist in CaseState."
            )

        return self.audit_service.record_event(
            event_id=(
                f"{case_state.case_id}-communication-"
                f"{communication_id}"
            ),
            case_id=case_state.case_id,
            actor_type=actor_type,
            actor_id=actor_id,
            action="communication_created",
            entity_type="communication",
            entity_id=communication_id,
            metadata={
                "triage_id": communication.triage_id,
                "status": communication.status.value,
                "recipient_role": (
                    communication.recipient_role
                ),
                "reason": communication.reason,
            },
        )

    def list_case_events(
        self,
        case_state: CaseState,
    ):
        """
        Retrieve the append-only audit history for a case.
        """

        return self.audit_service.list_case_events(
            case_state.case_id
        )