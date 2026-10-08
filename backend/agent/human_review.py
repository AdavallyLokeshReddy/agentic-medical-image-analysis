from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class ReviewDecision(str, Enum):
    ACCEPT = "accept"
    MODIFY = "modify"
    REJECT = "reject"


class ReviewStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"


@dataclass
class HumanReview:
    review_id: str
    case_id: str
    report_id: str

    status: ReviewStatus = ReviewStatus.PENDING
    decision: Optional[ReviewDecision] = None

    reviewer_id: Optional[str] = None

    reviewer_comments: list[str] = field(default_factory=list)

    modified_observations: list[dict[str, Any]] = field(
        default_factory=list
    )

    reviewed_evidence_ids: list[str] = field(
        default_factory=list
    )

    reviewed_verification_ids: list[str] = field(
        default_factory=list
    )

    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    intervention_reason: Optional[str] = None

    def start(self) -> None:
        if self.status != ReviewStatus.PENDING:
            raise ValueError("Review has already been completed.")

        self.started_at = datetime.now(timezone.utc).isoformat()

    def accept(
        self,
        reviewer_id: str,
        comments: Optional[list[str]] = None,
    ) -> None:
        self._complete(
            reviewer_id=reviewer_id,
            decision=ReviewDecision.ACCEPT,
            comments=comments,
        )

    def modify(
        self,
        reviewer_id: str,
        modified_observations: list[dict[str, Any]],
        reason: str,
        comments: Optional[list[str]] = None,
    ) -> None:

        if not reason.strip():
            raise ValueError(
                "A reason is required when modifying a report."
            )

        self.modified_observations = modified_observations
        self.intervention_reason = reason

        self._complete(
            reviewer_id=reviewer_id,
            decision=ReviewDecision.MODIFY,
            comments=comments,
        )

    def reject(
        self,
        reviewer_id: str,
        reason: str,
        comments: Optional[list[str]] = None,
    ) -> None:

        if not reason.strip():
            raise ValueError(
                "A reason is required when rejecting a report."
            )

        self.intervention_reason = reason

        self._complete(
            reviewer_id=reviewer_id,
            decision=ReviewDecision.REJECT,
            comments=comments,
        )

    def _complete(
        self,
        reviewer_id: str,
        decision: ReviewDecision,
        comments: Optional[list[str]],
    ) -> None:

        if self.status != ReviewStatus.PENDING:
            raise ValueError(
        "Review has already been completed and cannot be changed."
    )

        if not reviewer_id.strip():
            raise ValueError(
                "Reviewer ID is required."
            )

        self.reviewer_id = reviewer_id
        self.decision = decision
        self.status = ReviewStatus.COMPLETED

        if comments:
            self.reviewer_comments.extend(comments)

        self.completed_at = datetime.now(
            timezone.utc
        ).isoformat()

    def record_reviewed_evidence(
        self,
        evidence_ids: list[str],
    ) -> None:

        self.reviewed_evidence_ids = list(
            dict.fromkeys(evidence_ids)
        )

    def record_reviewed_verifications(
        self,
        verification_ids: list[str],
    ) -> None:

        self.reviewed_verification_ids = list(
            dict.fromkeys(verification_ids)
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "review_id": self.review_id,
            "case_id": self.case_id,
            "report_id": self.report_id,
            "status": self.status.value,
            "decision": (
                self.decision.value
                if self.decision
                else None
            ),
            "reviewer_id": self.reviewer_id,
            "reviewer_comments": self.reviewer_comments,
            "modified_observations": (
                self.modified_observations
            ),
            "reviewed_evidence_ids": (
                self.reviewed_evidence_ids
            ),
            "reviewed_verification_ids": (
                self.reviewed_verification_ids
            ),
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "intervention_reason": (
                self.intervention_reason
            ),
        }