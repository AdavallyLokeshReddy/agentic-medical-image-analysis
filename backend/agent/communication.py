from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class TriageLevel(str, Enum):
    """
    Governed workflow urgency assigned to a case.

    Triage is a workflow proposal, not an autonomous clinical
    diagnosis or treatment decision.
    """

    ROUTINE = "routine"
    PRIORITY = "priority"
    URGENT = "urgent"
    ESCALATE = "escalate"


class CommunicationStatus(str, Enum):
    """
    Lifecycle state of a governed workflow communication.
    """

    PENDING = "pending"
    ACKNOWLEDGED = "acknowledged"
    ESCALATED = "escalated"
    FALLBACK = "fallback"
    CLOSED = "closed"


@dataclass
class TriageRecord:
    """
    Auditable triage proposal for a medical-imaging case.

    The record describes workflow urgency and its supporting
    evidence. It does not independently establish a diagnosis,
    treatment decision, or clinical disposition.
    """

    triage_id: str
    case_id: str
    level: TriageLevel

    reason: str

    evidence_ids: list[str] = field(default_factory=list)

    verification_status: str = "not_verified"

    requires_human_approval: bool = True

    created_at: str = field(
        default_factory=lambda: datetime.now(
            timezone.utc
        ).isoformat()
    )

    approved_by: Optional[str] = None
    approved_at: Optional[str] = None

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def approve(self, reviewer_id: str) -> None:
        """
        Record human approval of the triage proposal.
        """

        if not reviewer_id.strip():
            raise ValueError(
                "Reviewer ID is required."
            )

        if self.approved_by is not None:
            raise ValueError(
                "Triage has already been approved."
            )

        self.approved_by = reviewer_id
        self.approved_at = datetime.now(
            timezone.utc
        ).isoformat()

    def to_dict(self) -> dict[str, Any]:
        """
        Convert the triage record to a serializable dictionary.
        """

        return {
            "triage_id": self.triage_id,
            "case_id": self.case_id,
            "level": self.level.value,
            "reason": self.reason,
            "evidence_ids": self.evidence_ids,
            "verification_status": (
                self.verification_status
            ),
            "requires_human_approval": (
                self.requires_human_approval
            ),
            "created_at": self.created_at,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at,
            "metadata": self.metadata,
        }


@dataclass
class CommunicationRecord:
    """
    Auditable communication and closure state for a case.

    Communication does not itself authorize clinical action.
    """

    communication_id: str
    case_id: str

    message: str

    status: CommunicationStatus = (
        CommunicationStatus.PENDING
    )

    triage_id: Optional[str] = None

    recipient_role: Optional[str] = None

    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[str] = None

    reason: Optional[str] = None

    created_at: str = field(
        default_factory=lambda: datetime.now(
            timezone.utc
        ).isoformat()
    )

    closed_at: Optional[str] = None

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def acknowledge(self, reviewer_id: str) -> None:
        """
        Record acknowledgement of the communication.
        """

        self._require_pending()

        if not reviewer_id.strip():
            raise ValueError(
                "Reviewer ID is required."
            )

        self.status = (
            CommunicationStatus.ACKNOWLEDGED
        )

        self.acknowledged_by = reviewer_id
        self.acknowledged_at = datetime.now(
            timezone.utc
        ).isoformat()

    def escalate(self, reason: str) -> None:
        """
        Escalate the communication when acknowledgement
        or workflow completion requires further handling.
        """

        self._require_pending_or_acknowledged()

        if not reason.strip():
            raise ValueError(
                "Escalation reason is required."
            )

        self.status = (
            CommunicationStatus.ESCALATED
        )

        self.reason = reason

    def fallback(self, reason: str) -> None:
        """
        Record a governed fallback path.
        """

        if self.status == CommunicationStatus.CLOSED:
            raise ValueError(
                "Closed communication cannot enter fallback."
            )

        if not reason.strip():
            raise ValueError(
                "Fallback reason is required."
            )

        self.status = (
            CommunicationStatus.FALLBACK
        )

        self.reason = reason

    def close(self) -> None:
        """
        Close the communication after the governed
        workflow has reached an appropriate endpoint.
        """

        if self.status != CommunicationStatus.ACKNOWLEDGED:
            raise ValueError(
                "Communication must be acknowledged before closure."
            )

        self.status = CommunicationStatus.CLOSED

        self.closed_at = datetime.now(
            timezone.utc
        ).isoformat()

    def _require_pending(self) -> None:
        if self.status != CommunicationStatus.PENDING:
            raise ValueError(
                "Communication is no longer pending."
            )

    def _require_pending_or_acknowledged(self) -> None:
        if self.status not in {
            CommunicationStatus.PENDING,
            CommunicationStatus.ACKNOWLEDGED,
        }:
            raise ValueError(
                "Communication cannot be escalated from its current state."
            )

    def to_dict(self) -> dict[str, Any]:
        """
        Convert the communication record to a serializable dictionary.
        """

        return {
            "communication_id": (
                self.communication_id
            ),
            "case_id": self.case_id,
            "message": self.message,
            "status": self.status.value,
            "triage_id": self.triage_id,
            "recipient_role": self.recipient_role,
            "acknowledged_by": self.acknowledged_by,
            "acknowledged_at": self.acknowledged_at,
            "reason": self.reason,
            "created_at": self.created_at,
            "closed_at": self.closed_at,
            "metadata": self.metadata,
        }