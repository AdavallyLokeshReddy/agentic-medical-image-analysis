from sqlalchemy.orm import Session

from agent.case_state import CaseState
from database.repository import MedicalCaseRepository


class CaseStatePersistence:
    """
    Persistence bridge between the runtime CaseState and PostgreSQL.

    CaseState remains the runtime representation of the governed case.
    PostgreSQL stores persistent case and workflow records.

    This class intentionally does not replace CaseState with ORM models.
    """

    def __init__(self, session: Session):
        self.session = session
        self.repository = MedicalCaseRepository(session)

    def save_case(self, case_state: CaseState):
        """
        Persist the core case information.

        If the case already exists, its fields are updated.
        """

        existing_case = self.repository.get_case(
            case_state.case_id
        )

        if existing_case is None:
            self.repository.create_case(
                case_id=case_state.case_id,
                modality=case_state.modality.value,
                body_region=case_state.body_region or "",
                clinical_question=(
                    case_state.clinical_question or ""
                ),
                status=case_state.status.value,
            )
        else:
            existing_case.modality = (
                case_state.modality.value
            )
            existing_case.body_region = (
                case_state.body_region or ""
            )
            existing_case.clinical_question = (
                case_state.clinical_question or ""
            )
            existing_case.status = (
                case_state.status.value
            )

        self.session.flush()

    def save_evidence(self, case_state: CaseState):
        """
        Persist evidence objects that do not already exist.
        """

        for evidence in case_state.evidence:
            existing = self.repository.get_evidence(
                evidence.evidence_id
            )

            if existing is not None:
                continue

            self.repository.add_evidence(
                evidence_id=evidence.evidence_id,
                case_id=case_state.case_id,
                source_type=evidence.evidence_type,
                source_reference=evidence.source,
                status=evidence.status.value,
                metadata={
                    "claim": evidence.claim,
                    "output": evidence.output,
                    "confidence": evidence.confidence,
                    "applicable": evidence.applicable,
                    "image_ids": evidence.image_ids,
                    "series_uid": evidence.series_uid,
                    "supporting_slices": (
                        evidence.supporting_slices
                    ),
                    "supporting_regions": (
                        evidence.supporting_regions
                    ),
                    "verification_ids": (
                        evidence.verification_ids
                    ),
                    "task_id": evidence.task_id,
                    "dependencies": evidence.dependencies,
                    "warnings": evidence.warnings,
                    "provenance": {
                        "tool_name": (
                            evidence.provenance.tool_name
                        ),
                        "tool_version": (
                            evidence.provenance.tool_version
                        ),
                        "model_name": (
                            evidence.provenance.model_name
                        ),
                        "model_version": (
                            evidence.provenance.model_version
                        ),
                        "runtime": (
                            evidence.provenance.runtime
                        ),
                        "input_references": (
                            evidence.provenance.input_references
                        ),
                        "created_at": (
                            evidence.provenance.created_at
                        ),
                        "metadata": (
                            evidence.provenance.metadata
                        ),
                    },
                    "metadata": evidence.metadata,
                },
            )

        self.session.flush()

    def save_human_reviews(self, case_state: CaseState):
        """
        Persist human reviews that do not already exist.
        """

        for review in case_state.human_reviews:
            existing = self.repository.get_human_review(
                review.review_id
            )

            if existing is not None:
                continue

            self.repository.add_human_review(
                review_id=review.review_id,
                case_id=case_state.case_id,
                reviewer_id=review.reviewer_id,
                decision=(
                    review.decision.value
                    if review.decision is not None
                    else None
                ),
                status=review.status.value,
                reason=review.intervention_reason,
                evidence_ids=review.reviewed_evidence_ids,
                verification_ids=(
                    review.reviewed_verification_ids
                ),
            )

        self.session.flush()

    def save_verification(self, case_state: CaseState):
        """
        Persist the current verification state.

        The verification record represents the current
        verification snapshot for the case.
        """

        verification_id = (
            f"{case_state.case_id}-verification"
        )

        existing = self.repository.get_verification(
            verification_id
        )

        findings = {
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
        }

        if existing is None:
            self.repository.add_verification(
                verification_id=verification_id,
                case_id=case_state.case_id,
                status=case_state.verification.status.value,
                categories=[],
                findings=findings,
                reason=None,
            )
        else:
            existing.status = (
                case_state.verification.status.value
            )
            existing.categories = []
            existing.findings = findings
            existing.reason = None

        self.session.flush()

    def save_triage(self, case_state: CaseState):
        """
        Persist governed triage records.
        """

        for triage in case_state.triage_records:
            existing = self.repository.get_triage(
                triage.triage_id
            )

            if existing is not None:
                continue

            self.repository.add_triage(
                triage_id=triage.triage_id,
                case_id=case_state.case_id,
                level=triage.level.value,
                reason=triage.reason,
                verification_status=(
                    triage.verification_status.value
                ),
                evidence_ids=triage.evidence_ids,
                requires_human_approval=(
                    triage.requires_human_approval
                ),
                approved_by=triage.approved_by,
                approved_at=triage.approved_at,
            )

        self.session.flush()

    def save_communications(self, case_state: CaseState):
        """
        Persist communication records.
        """

        for communication in case_state.communications:
            existing = self.repository.get_communication(
                communication.communication_id
            )

            if existing is not None:
                continue

            self.repository.add_communication(
                communication_id=(
                    communication.communication_id
                ),
                case_id=case_state.case_id,
                message=communication.message,
                status=communication.status.value,
                triage_id=communication.triage_id,
                recipient_role=(
                    communication.recipient_role
                ),
                reason=communication.reason,
            )

        self.session.flush()

    def save(self, case_state: CaseState):
        """
        Persist the current CaseState snapshot.

        The caller controls the transaction commit.
        """

        if not isinstance(case_state, CaseState):
            raise TypeError(
                "case_state must be a CaseState instance."
            )

        self.save_case(case_state)
        self.save_evidence(case_state)
        self.save_human_reviews(case_state)
        self.save_verification(case_state)
        self.save_triage(case_state)
        self.save_communications(case_state)

        self.session.commit()