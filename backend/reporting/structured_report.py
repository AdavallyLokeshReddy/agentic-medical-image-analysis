from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from agent.case_state import (
    CaseState,
    EvidenceItem,
    EvidenceStatus,
)


class ReportStatus(str, Enum):
    DRAFT = "draft"
    REQUIRES_REVIEW = "requires_review"
    BLOCKED = "blocked"


@dataclass
class ReportObservation:
    evidence_id: str
    claim: str
    confidence: Optional[float] = None
    supporting_slices: list[int] = field(default_factory=list)
    verification_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "claim": self.claim,
            "confidence": self.confidence,
            "supporting_slices": self.supporting_slices,
            "verification_ids": self.verification_ids,
        }


@dataclass
class StructuredDraftReport:
    report_id: str
    case_id: str
    generated_at: str

    status: ReportStatus

    clinical_question: str
    modality: str
    body_region: str

    observations: list[ReportObservation] = field(default_factory=list)

    uncertainty: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)

    evidence_references: list[str] = field(default_factory=list)
    verification_status: str = "not_verified"

    human_review_required: bool = True

    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "case_id": self.case_id,
            "generated_at": self.generated_at,
            "status": self.status.value,
            "clinical_question": self.clinical_question,
            "modality": self.modality,
            "body_region": self.body_region,
            "observations": [
                observation.to_dict()
                for observation in self.observations
            ],
            "uncertainty": self.uncertainty,
            "limitations": self.limitations,
            "evidence_references": self.evidence_references,
            "verification_status": self.verification_status,
            "human_review_required": self.human_review_required,
            "provenance": self.provenance,
        }


def create_structured_draft_report(
    case: CaseState,
    report_id: str,
) -> StructuredDraftReport:
    """
    Create a governed structured draft report from CaseState.

    Only VALID evidence can become report observations.
    Evidence requiring review is surfaced as uncertainty.
    INVALID evidence is excluded from observations.
    """

    valid_evidence = case.get_valid_evidence()
    review_evidence = case.get_review_required_evidence()

    observations: list[ReportObservation] = []
    evidence_references: list[str] = []
    uncertainty: list[str] = []
    limitations: list[str] = []

    # ---------------------------------------------------------
    # VALID evidence
    # ---------------------------------------------------------
    for evidence in valid_evidence:
        observations.append(
            ReportObservation(
                evidence_id=evidence.evidence_id,
                claim=evidence.claim,
                confidence=evidence.confidence,
                supporting_slices=evidence.supporting_slices,
                verification_ids=evidence.verification_ids,
            )
        )

        evidence_references.append(evidence.evidence_id)

    # ---------------------------------------------------------
    # Evidence requiring human review
    # ---------------------------------------------------------
    for evidence in review_evidence:
        uncertainty.append(
            f"Evidence {evidence.evidence_id} requires review "
            f"before it can support a report finding."
        )

        evidence_references.append(evidence.evidence_id)

    # ---------------------------------------------------------
    # Case-level warnings and limitations
    # ---------------------------------------------------------
    limitations.extend(case.warnings)

    # ---------------------------------------------------------
    # Determine report status
    # ---------------------------------------------------------
    if not valid_evidence and not review_evidence:
        status = ReportStatus.BLOCKED
        verification_status = "no_eligible_evidence"
    elif review_evidence:
        status = ReportStatus.REQUIRES_REVIEW
        verification_status = "review_required"
    else:
        status = ReportStatus.DRAFT
        verification_status = "verified_evidence_available"

    return StructuredDraftReport(
        report_id=report_id,
        case_id=case.case_id,
        generated_at=datetime.now(timezone.utc).isoformat(),

        status=status,

        clinical_question=case.clinical_question,
        modality=case.modality.value,
        body_region=case.body_region,

        observations=observations,

        uncertainty=uncertainty,
        limitations=limitations,

        evidence_references=evidence_references,
        verification_status=verification_status,

        # The report is always subject to human clinical review.
        human_review_required=True,

        provenance={
            "generator": "governed_medical_imaging_agent",
            "case_id": case.case_id,
            "evidence_ids": evidence_references,
        },
    )