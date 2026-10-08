from dataclasses import dataclass
from typing import Any, Optional

from agent.case_state import CaseState
from agent.human_review import HumanReview, ReviewDecision, ReviewStatus
from reporting.structured_report import StructuredDraftReport


@dataclass
class ReviewLifecycle:
    """
    Coordinates the lifecycle between a structured draft report
    and a human review.

    This class does not overwrite AI-generated evidence or report
    content. Human intervention is recorded separately through
    HumanReview.
    """

    case: CaseState
    report: StructuredDraftReport
    review: HumanReview

    def __post_init__(self) -> None:
        if self.report.case_id != self.case.case_id:
            raise ValueError(
                "Report case ID does not match CaseState."
            )

        if self.review.case_id != self.case.case_id:
            raise ValueError(
                "Review case ID does not match CaseState."
            )

        if self.review.report_id != self.report.report_id:
            raise ValueError(
                "Review report ID does not match StructuredDraftReport."
            )

    def start_review(self) -> HumanReview:
        """Start the pending human review."""

        if self.review.status != ReviewStatus.PENDING:
            raise ValueError(
                "Review has already been completed and cannot be started."
            )

        self.review.start()
        return self.review

    def record_review_context(
        self,
        evidence_ids: list[str],
        verification_ids: list[str],
    ) -> HumanReview:
        """
        Record the evidence and verification context examined
        by the reviewer.
        """

        self._validate_evidence_ids(evidence_ids)
        self._validate_verification_ids(verification_ids)

        self.review.record_reviewed_evidence(evidence_ids)
        self.review.record_reviewed_verifications(verification_ids)

        return self.review

    def accept(
        self,
        reviewer_id: str,
        comments: Optional[list[str]] = None,
    ) -> HumanReview:
        """Accept the generated report after human review."""

        self._require_pending_review()

        self.review.accept(
            reviewer_id=reviewer_id,
            comments=comments,
        )

        return self.review

    def modify(
        self,
        reviewer_id: str,
        modified_observations: list[dict[str, Any]],
        reason: str,
        comments: Optional[list[str]] = None,
    ) -> HumanReview:
        """
        Record a human modification without overwriting
        the original AI-generated report.
        """

        self._require_pending_review()

        self.review.modify(
            reviewer_id=reviewer_id,
            modified_observations=modified_observations,
            reason=reason,
            comments=comments,
        )

        return self.review

    def reject(
        self,
        reviewer_id: str,
        reason: str,
        comments: Optional[list[str]] = None,
    ) -> HumanReview:
        """Reject the generated report after human review."""

        self._require_pending_review()

        self.review.reject(
            reviewer_id=reviewer_id,
            reason=reason,
            comments=comments,
        )

        return self.review

    def _require_pending_review(self) -> None:
        if self.review.status != ReviewStatus.PENDING:
            raise ValueError(
                "Review has already been completed and cannot be changed."
            )

    def _validate_evidence_ids(
        self,
        evidence_ids: list[str],
    ) -> None:
        """Validate evidence references against the current case."""

        known_ids = {
            evidence.evidence_id
            for evidence in self.case.evidence
        }

        unknown_ids = [
            evidence_id
            for evidence_id in evidence_ids
            if evidence_id not in known_ids
        ]

        if unknown_ids:
            raise ValueError(
                f"Unknown evidence IDs: {unknown_ids}"
            )

    def _validate_verification_ids(
        self,
        verification_ids: list[str],
    ) -> None:
        """
        Validate references against the case-level verification state.

        CaseState currently stores one VerificationState object rather
        than a collection of individually identified verification
        objects. Therefore, the lifecycle records a logical reference
        to the available verification state.
        """

        if not verification_ids:
            return

        if self.case.verification is None:
            raise ValueError(
                "Unknown verification IDs: "
                f"{verification_ids}"
            )

        allowed_reference = "verification_passed"

        unknown_ids = [
            verification_id
            for verification_id in verification_ids
            if verification_id != allowed_reference
        ]

        if unknown_ids:
            raise ValueError(
                f"Unknown verification IDs: {unknown_ids}"
            )

    def is_completed(self) -> bool:
        """Return whether the review lifecycle is complete."""

        return self.review.status == ReviewStatus.COMPLETED

    def decision(self) -> Optional[ReviewDecision]:
        """Return the current review decision."""

        return self.review.decision