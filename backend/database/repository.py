from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import (
    AuditEventModel,
    CaseModel,
    CommunicationModel,
    EvidenceModel,
    HumanReviewModel,
    TriageModel,
    VerificationModel,
)


class MedicalCaseRepository:
    """
    Repository layer for persistent medical-AI case data.

    This class keeps database operations separate from:
    - CaseState
    - agent orchestration
    - model inference
    - verification
    - FastAPI routes
    """

    def __init__(self, session: Session):
        self.session = session

    # ------------------------------------------------------------------
    # Cases
    # ------------------------------------------------------------------

    def create_case(
        self,
        case_id: str,
        modality: str,
        body_region: str,
        clinical_question: str,
        status: str,
    ) -> CaseModel:
        case = CaseModel(
            case_id=case_id,
            modality=modality,
            body_region=body_region,
            clinical_question=clinical_question,
            status=status,
        )

        self.session.add(case)
        self.session.flush()

        return case

    def get_case(self, case_id: str) -> CaseModel | None:
        statement = select(CaseModel).where(
            CaseModel.case_id == case_id
        )

        return self.session.scalar(statement)

    # ------------------------------------------------------------------
    # Evidence
    # ------------------------------------------------------------------

    def add_evidence(
        self,
        evidence_id: str,
        case_id: str,
        source_type: str,
        source_reference: str,
        status: str,
        metadata: dict[str, Any] | None = None,
    ) -> EvidenceModel:
        evidence = EvidenceModel(
            evidence_id=evidence_id,
            case_id=case_id,
            source_type=source_type,
            source_reference=source_reference,
            status=status,
            metadata_json=metadata,
        )

        self.session.add(evidence)
        self.session.flush()

        return evidence

    def get_evidence(self, evidence_id: str) -> EvidenceModel | None:
        statement = select(EvidenceModel).where(
            EvidenceModel.evidence_id == evidence_id
        )

        return self.session.scalar(statement)

    def list_evidence(self, case_id: str) -> list[EvidenceModel]:
        statement = (
            select(EvidenceModel)
            .where(EvidenceModel.case_id == case_id)
            .order_by(EvidenceModel.created_at)
        )

        return list(self.session.scalars(statement).all())

    # ------------------------------------------------------------------
    # Human reviews
    # ------------------------------------------------------------------

    def add_human_review(
        self,
        review_id: str,
        case_id: str,
        reviewer_id: str,
        decision: str,
        status: str,
        reason: str | None = None,
        evidence_ids: list[str] | None = None,
        verification_ids: list[str] | None = None,
    ) -> HumanReviewModel:
        review = HumanReviewModel(
            review_id=review_id,
            case_id=case_id,
            reviewer_id=reviewer_id,
            decision=decision,
            status=status,
            reason=reason,
            evidence_ids=evidence_ids,
            verification_ids=verification_ids,
        )

        self.session.add(review)
        self.session.flush()

        return review

    def get_human_review(
        self,
        review_id: str,
    ) -> HumanReviewModel | None:
        statement = select(HumanReviewModel).where(
            HumanReviewModel.review_id == review_id
        )

        return self.session.scalar(statement)

    def list_human_reviews(
        self,
        case_id: str,
    ) -> list[HumanReviewModel]:
        statement = (
            select(HumanReviewModel)
            .where(HumanReviewModel.case_id == case_id)
            .order_by(HumanReviewModel.created_at)
        )

        return list(self.session.scalars(statement).all())

    # ------------------------------------------------------------------
    # Verifications
    # ------------------------------------------------------------------

    def add_verification(
        self,
        verification_id: str,
        case_id: str,
        status: str,
        categories: list[str] | None = None,
        findings: dict[str, Any] | None = None,
        reason: str | None = None,
    ) -> VerificationModel:
        verification = VerificationModel(
            verification_id=verification_id,
            case_id=case_id,
            status=status,
            categories=categories,
            findings=findings,
            reason=reason,
        )

        self.session.add(verification)
        self.session.flush()

        return verification

    def get_verification(
        self,
        verification_id: str,
    ) -> VerificationModel | None:
        statement = select(VerificationModel).where(
            VerificationModel.verification_id == verification_id
        )

        return self.session.scalar(statement)

    def list_verifications(
        self,
        case_id: str,
    ) -> list[VerificationModel]:
        statement = (
            select(VerificationModel)
            .where(VerificationModel.case_id == case_id)
            .order_by(VerificationModel.created_at)
        )

        return list(self.session.scalars(statement).all())

    # ------------------------------------------------------------------
    # Triage
    # ------------------------------------------------------------------

    def add_triage(
        self,
        triage_id: str,
        case_id: str,
        level: str,
        reason: str,
        verification_status: str,
        evidence_ids: list[str] | None = None,
        requires_human_approval: bool = True,
        approved_by: str | None = None,
        approved_at=None,
    ) -> TriageModel:
        triage = TriageModel(
            triage_id=triage_id,
            case_id=case_id,
            level=level,
            reason=reason,
            evidence_ids=evidence_ids,
            verification_status=verification_status,
            requires_human_approval=requires_human_approval,
            approved_by=approved_by,
            approved_at=approved_at,
        )

        self.session.add(triage)
        self.session.flush()

        return triage

    def get_triage(
        self,
        triage_id: str,
    ) -> TriageModel | None:
        statement = select(TriageModel).where(
            TriageModel.triage_id == triage_id
        )

        return self.session.scalar(statement)

    def list_triage(
        self,
        case_id: str,
    ) -> list[TriageModel]:
        statement = (
            select(TriageModel)
            .where(TriageModel.case_id == case_id)
            .order_by(TriageModel.created_at)
        )

        return list(self.session.scalars(statement).all())

    # ------------------------------------------------------------------
    # Communications
    # ------------------------------------------------------------------

    def add_communication(
        self,
        communication_id: str,
        case_id: str,
        message: str,
        status: str,
        triage_id: str | None = None,
        recipient_role: str | None = None,
        reason: str | None = None,
    ) -> CommunicationModel:
        communication = CommunicationModel(
            communication_id=communication_id,
            case_id=case_id,
            triage_id=triage_id,
            message=message,
            status=status,
            recipient_role=recipient_role,
            reason=reason,
        )

        self.session.add(communication)
        self.session.flush()

        return communication

    def get_communication(
        self,
        communication_id: str,
    ) -> CommunicationModel | None:
        statement = select(CommunicationModel).where(
            CommunicationModel.communication_id == communication_id
        )

        return self.session.scalar(statement)

    def list_communications(
        self,
        case_id: str,
    ) -> list[CommunicationModel]:
        statement = (
            select(CommunicationModel)
            .where(CommunicationModel.case_id == case_id)
            .order_by(CommunicationModel.created_at)
        )

        return list(self.session.scalars(statement).all())

    # ------------------------------------------------------------------
    # Audit events
    # ------------------------------------------------------------------

    def add_audit_event(
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
        event = AuditEventModel(
            event_id=event_id,
            case_id=case_id,
            actor_type=actor_type,
            actor_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            metadata_json=metadata,
        )

        self.session.add(event)
        self.session.flush()

        return event

    def get_audit_event(
        self,
        event_id: str,
    ) -> AuditEventModel | None:
        statement = select(AuditEventModel).where(
            AuditEventModel.event_id == event_id
        )

        return self.session.scalar(statement)

    def list_audit_events(
        self,
        case_id: str,
    ) -> list[AuditEventModel]:
        statement = (
            select(AuditEventModel)
            .where(AuditEventModel.case_id == case_id)
            .order_by(AuditEventModel.timestamp)
        )

        return list(self.session.scalars(statement).all())