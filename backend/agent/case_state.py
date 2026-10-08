from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from .safety_contract import SafetyContract
from .task_graph import TaskGraph, TaskNode
from .human_review import HumanReview
from .communication import TriageRecord, CommunicationRecord


class CaseModality(str, Enum):
    """
    Supported medical imaging modalities.
    """

    CT = "CT"
    MRI = "MRI"
    XRAY = "X-RAY"
    UNKNOWN = "UNKNOWN"


class CaseStatus(str, Enum):
    """
    Overall lifecycle state of a case.
    """

    CREATED = "created"
    INTAKE = "intake"
    ANALYZING = "analyzing"
    VERIFICATION = "verification"
    REQUIRES_REVIEW = "requires_review"
    COMPLETED = "completed"
    ABSTAINED = "abstained"
    FAILED = "failed"


class EvidenceStatus(str, Enum):
    """
    Status of an individual evidence object.
    """

    PROPOSED = "proposed"
    VALID = "valid"
    INVALID = "invalid"
    REQUIRES_REVIEW = "requires_review"


class VerificationStatus(str, Enum):
    """
    Verification state of the accumulated case evidence.
    """

    NOT_STARTED = "not_started"
    PASSED = "passed"
    REQUIRES_REVIEW = "requires_review"
    FAILED = "failed"


class ActionStatus(str, Enum):
    """
    Lifecycle state of an action proposed or performed by the agent.
    """

    PROPOSED = "proposed"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass
class EvidenceProvenance:
    """
    Provenance information describing how an evidence object
    was produced.
    """

    tool_name: Optional[str] = None
    tool_version: Optional[str] = None
    model_name: Optional[str] = None
    model_version: Optional[str] = None
    runtime: Optional[str] = None

    input_references: List[str] = field(
        default_factory=list
    )

    created_at: str = field(
        default_factory=lambda: datetime.now(
            timezone.utc
        ).isoformat()
    )

    metadata: Dict[str, Any] = field(
        default_factory=dict
    )


@dataclass
class EvidenceItem:
    """
    A traceable piece of evidence produced during case processing.

    Evidence can represent:
    - model output
    - measurement
    - observation
    - retrieval result
    - intermediate analytical result

    Evidence is not automatically a clinical diagnosis.
    """

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    evidence_id: str
    case_id: Optional[str] = None

    # ------------------------------------------------------------------
    # Evidence content
    # ------------------------------------------------------------------

    evidence_type: str = ""
    source: str = ""
    claim: Optional[str] = None
    output: Any = None

    # ------------------------------------------------------------------
    # Evidence status
    # ------------------------------------------------------------------

    status: EvidenceStatus = EvidenceStatus.PROPOSED
    confidence: Optional[float] = None
    applicable: Optional[bool] = None

    # ------------------------------------------------------------------
    # Image / series references
    # ------------------------------------------------------------------

    image_ids: List[str] = field(
        default_factory=list
    )

    series_uid: Optional[str] = None

    supporting_slices: List[int] = field(
        default_factory=list
    )

    supporting_regions: List[Dict[str, Any]] = field(
        default_factory=list
    )

    # ------------------------------------------------------------------
    # Provenance
    # ------------------------------------------------------------------

    provenance: EvidenceProvenance = field(
        default_factory=EvidenceProvenance
    )

    # ------------------------------------------------------------------
    # Verification traceability
    # ------------------------------------------------------------------

    verification_ids: List[str] = field(
        default_factory=list
    )

    # ------------------------------------------------------------------
    # Task / dependency traceability
    # ------------------------------------------------------------------

    task_id: Optional[str] = None

    dependencies: List[str] = field(
        default_factory=list
    )

    # ------------------------------------------------------------------
    # Warnings / metadata
    # ------------------------------------------------------------------

    warnings: List[str] = field(
        default_factory=list
    )

    metadata: Dict[str, Any] = field(
        default_factory=dict
    )

    # ==================================================================
    # EVIDENCE LIFECYCLE
    # ==================================================================

    def mark_valid(
        self,
        verification_id: Optional[str] = None,
    ) -> None:
        """
        Mark evidence as valid after successful verification.

        Valid means that the evidence passed its applicable
        verification process.

        It does NOT mean that the evidence itself is a diagnosis.
        """

        self.status = EvidenceStatus.VALID
        self.applicable = True

        if verification_id:
            if verification_id not in self.verification_ids:
                self.verification_ids.append(
                    verification_id
                )

    def mark_requires_review(
        self,
        verification_id: Optional[str] = None,
    ) -> None:
        """
        Mark evidence as requiring human review.

        Applicability remains unresolved until review.
        """

        self.status = EvidenceStatus.REQUIRES_REVIEW
        self.applicable = None

        if verification_id:
            if verification_id not in self.verification_ids:
                self.verification_ids.append(
                    verification_id
                )

    def invalidate(
        self,
        reason: str,
        verification_id: Optional[str] = None,
    ) -> None:
        """
        Explicitly invalidate this evidence object.

        The original output and provenance are preserved so that
        the invalidation remains auditable.
        """

        if not reason:
            raise ValueError(
                "Invalidation reason cannot be empty."
            )

        self.status = EvidenceStatus.INVALID
        self.applicable = False

        # Store the exact invalidation reason so it can be
        # directly inspected by downstream verification,
        # audit, and testing components.
        self.warnings.append(reason)

        if verification_id:
            if verification_id not in self.verification_ids:
                self.verification_ids.append(
                    verification_id
                )


@dataclass
class CaseAction:
    """
    An action proposed or performed as part of the case workflow.

    Actions are tracked separately from evidence because analytical
    evidence and operational authority are different concepts.
    """

    action_id: str
    action_type: str
    description: str

    status: ActionStatus = ActionStatus.PROPOSED

    permission_tier: Optional[str] = None
    requires_human_approval: bool = False

    evidence_ids: List[str] = field(
        default_factory=list
    )

    proposed_at: str = field(
        default_factory=lambda: datetime.now(
            timezone.utc
        ).isoformat()
    )

    completed_at: Optional[str] = None

    reason: Optional[str] = None
    result: Optional[Any] = None

    metadata: Dict[str, Any] = field(
        default_factory=dict
    )


@dataclass
class VerificationState:
    """
    Current verification state for the case.
    """

    status: VerificationStatus = (
        VerificationStatus.NOT_STARTED
    )

    checks: List[Dict[str, Any]] = field(
        default_factory=list
    )

    warnings: List[str] = field(
        default_factory=list
    )

    failed_checks: List[str] = field(
        default_factory=list
    )

    human_review_required: bool = False

    last_verified_at: Optional[str] = None

    metadata: Dict[str, Any] = field(
        default_factory=dict
    )


@dataclass
class CaseState:
    """
    Central state object for one medical-imaging case.

    Conceptually:

        S_t = (I, M, H, Q, T_t, E_t, X_t)

    where:

        I   = images
        M   = acquisition metadata
        H   = selected clinical history
        Q   = clinical question
        T_t = active task graph
        E_t = accumulated evidence
        X_t = proposed/completed actions
    """

    # ------------------------------------------------------------------
    # Case identity
    # ------------------------------------------------------------------

    case_id: str

    # ------------------------------------------------------------------
    # Modality / clinical question
    # ------------------------------------------------------------------

    modality: CaseModality = CaseModality.UNKNOWN

    body_region: Optional[str] = None

    clinical_question: Optional[str] = None

    # ------------------------------------------------------------------
    # I = Images
    # ------------------------------------------------------------------

    images: List[Dict[str, Any]] = field(
        default_factory=list
    )

    # ------------------------------------------------------------------
    # M = Acquisition metadata
    # ------------------------------------------------------------------

    metadata: Dict[str, Any] = field(
        default_factory=dict
    )

    # ------------------------------------------------------------------
    # H = Selected clinical history
    # ------------------------------------------------------------------

    clinical_history: Dict[str, Any] = field(
        default_factory=dict
    )

    # ------------------------------------------------------------------
    # T_t = Active task graph
    # ------------------------------------------------------------------

    task_graph: TaskGraph = field(
        default_factory=TaskGraph
    )

    # ------------------------------------------------------------------
    # E_t = Accumulated evidence
    # ------------------------------------------------------------------

    evidence: List[EvidenceItem] = field(
        default_factory=list
    )

    # ------------------------------------------------------------------
    # X_t = Proposed/completed actions
    # ------------------------------------------------------------------

    actions: List[CaseAction] = field(
        default_factory=list
    )

    # ------------------------------------------------------------------
    # Human Review
    # ------------------------------------------------------------------

    human_reviews: List[HumanReview] = field(
        default_factory=list
    )
    # ------------------------------------------------------------------
# Governed Triage
# ------------------------------------------------------------------

    triage_records: List[TriageRecord] = field(
        default_factory=list
)

# ------------------------------------------------------------------
# Communication / Closure
# ------------------------------------------------------------------

    communications: List[CommunicationRecord] = field(
    default_factory=list
)
    # ------------------------------------------------------------------
    # Tool information
    # ------------------------------------------------------------------

    available_tools: List[str] = field(
        default_factory=list
    )

    selected_tools: List[str] = field(
        default_factory=list
    )

    # ------------------------------------------------------------------
    # Verification
    # ------------------------------------------------------------------

    verification: VerificationState = field(
        default_factory=VerificationState
    )

    # ------------------------------------------------------------------
    # Safety Contract
    # ------------------------------------------------------------------

    safety_contract: Optional[SafetyContract] = None

    # ------------------------------------------------------------------
    # Overall case lifecycle
    # ------------------------------------------------------------------

    status: CaseStatus = CaseStatus.CREATED

    # ------------------------------------------------------------------
    # Timestamps
    # ------------------------------------------------------------------

    created_at: str = field(
        default_factory=lambda: datetime.now(
            timezone.utc
        ).isoformat()
    )

    updated_at: str = field(
        default_factory=lambda: datetime.now(
            timezone.utc
        ).isoformat()
    )

    # ------------------------------------------------------------------
    # Warnings / notes
    # ------------------------------------------------------------------

    warnings: List[str] = field(
        default_factory=list
    )

    notes: List[str] = field(
        default_factory=list
    )

    # ==================================================================
    # CASE STATE METHODS
    # ==================================================================

    def touch(self) -> None:
        """
        Update the modification timestamp.
        """

        self.updated_at = datetime.now(
            timezone.utc
        ).isoformat()

    # ------------------------------------------------------------------
    # Images
    # ------------------------------------------------------------------

    def add_image(
        self,
        image: Dict[str, Any],
    ) -> None:
        """
        Add an image reference to the case.
        """

        if not isinstance(image, dict):
            raise TypeError(
                "image must be a dictionary."
            )

        self.images.append(image)
        self.touch()

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------

    def update_metadata(
        self,
        key: str,
        value: Any,
    ) -> None:
        """
        Add or update acquisition metadata.
        """

        if not key:
            raise ValueError(
                "Metadata key cannot be empty."
            )

        self.metadata[key] = value
        self.touch()

    # ------------------------------------------------------------------
    # Clinical history
    # ------------------------------------------------------------------

    def update_clinical_history(
        self,
        key: str,
        value: Any,
    ) -> None:
        """
        Add or update selected clinical history.
        """

        if not key:
            raise ValueError(
                "Clinical history key cannot be empty."
            )

        self.clinical_history[key] = value
        self.touch()

    # ------------------------------------------------------------------
    # Tasks
    # ------------------------------------------------------------------

    def add_task(
        self,
        task: TaskNode,
    ) -> None:
        """
        Add a task to the active task graph.
        """

        if not isinstance(task, TaskNode):
            raise TypeError(
                "task must be a TaskNode instance."
            )

        self.task_graph.add_task(task)
        self.touch()

    # ------------------------------------------------------------------
    # Tools
    # ------------------------------------------------------------------

    def set_available_tools(
        self,
        tools: List[str],
    ) -> None:
        """
        Store tools available for this case.
        """

        if not isinstance(tools, list):
            raise TypeError(
                "tools must be a list."
            )

        self.available_tools = tools
        self.touch()

    def discover_available_tools(
        self,
        registry,
    ) -> List[dict]:
        """
        Discover tools from the registry that match this case.

        This method only discovers compatible tools.
        It does not execute any medical AI tool.
        """

        modality = self.modality.value

        if modality == CaseModality.UNKNOWN.value:
            self.set_available_tools([])
            return []

        tools = registry.find_tools(
            modality=modality,
            body_region=self.body_region,
        )

        self.set_available_tools(
            [
                tool["name"]
                for tool in tools
            ]
        )

        return tools

    def select_tool(
        self,
        tool_name: str,
    ) -> None:
        """
        Mark a registered tool as selected for this case.
        """

        if not tool_name:
            raise ValueError(
                "tool_name cannot be empty."
            )

        if tool_name not in self.available_tools:
            raise ValueError(
                f"Tool '{tool_name}' is not available "
                f"for case '{self.case_id}'."
            )

        if tool_name not in self.selected_tools:
            self.selected_tools.append(
                tool_name
            )

        self.touch()

    # ------------------------------------------------------------------
    # Evidence
    # ------------------------------------------------------------------

    def add_evidence(
        self,
        evidence: EvidenceItem,
    ) -> None:
        """
        Add an evidence object to the case.
        """

        if not isinstance(evidence, EvidenceItem):
            raise TypeError(
                "evidence must be an EvidenceItem instance."
            )

        self.evidence.append(evidence)
        self.touch()

    def get_evidence(
        self,
        evidence_id: str,
    ) -> EvidenceItem:
        """
        Retrieve an evidence object by ID.
        """

        for item in self.evidence:
            if item.evidence_id == evidence_id:
                return item

        raise KeyError(
            f"Evidence not found: {evidence_id}"
        )

    def invalidate_evidence(
        self,
        evidence_id: str,
        reason: str,
        verification_id: Optional[str] = None,
    ) -> None:
        """
        Invalidate one evidence object while preserving provenance.

        This supports selective invalidation.
        """

        evidence = self.get_evidence(
            evidence_id
        )

        evidence.invalidate(
            reason=reason,
            verification_id=verification_id,
        )

        self.touch()

    def get_valid_evidence(
        self,
    ) -> List[EvidenceItem]:
        """
        Return evidence that has passed verification.
        """

        return [
            evidence
            for evidence in self.evidence
            if evidence.status == EvidenceStatus.VALID
        ]

    def get_review_required_evidence(
        self,
    ) -> List[EvidenceItem]:
        """
        Return evidence objects that require human review.
        """

        return [
            evidence
            for evidence in self.evidence
            if evidence.status
            == EvidenceStatus.REQUIRES_REVIEW
        ]

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def add_action(
        self,
        action: CaseAction,
    ) -> None:
        """
        Add an action proposed by the workflow.
        """

        if not isinstance(action, CaseAction):
            raise TypeError(
                "action must be a CaseAction instance."
            )

        self.actions.append(action)
        self.touch()

    def get_action(
        self,
        action_id: str,
    ) -> CaseAction:
        """
        Retrieve an action by ID.
        """

        for action in self.actions:
            if action.action_id == action_id:
                return action

        raise KeyError(
            f"Action not found: {action_id}"
        )

    # ------------------------------------------------------------------
    # Human Review
    # ------------------------------------------------------------------

    def add_human_review(
        self,
        review: HumanReview,
    ) -> None:
        """
        Add a human review to the case.

        The review must belong to the same case.
        """

        if not isinstance(review, HumanReview):
            raise TypeError(
                "review must be a HumanReview instance."
            )

        if review.case_id != self.case_id:
            raise ValueError(
                "Human review case ID does not match CaseState."
            )

        self.human_reviews.append(review)
        self.touch()

    def get_human_review(
        self,
        review_id: str,
    ) -> HumanReview:
        """
        Retrieve a human review by ID.
        """

        for review in self.human_reviews:
            if review.review_id == review_id:
                return review

        raise KeyError(
            f"Human review '{review_id}' not found."
        )

    def get_completed_human_reviews(
        self,
    ) -> List[HumanReview]:
        """
        Return all completed human reviews for this case.
        """

        return [
            review
            for review in self.human_reviews
            if review.status.value == "completed"
        ]
        # ------------------------------------------------------------------
    # Governed Triage
    # ------------------------------------------------------------------

    def add_triage(
        self,
        triage: TriageRecord,
    ) -> None:
        """
        Add a governed triage record to the case.

        The triage record must belong to the same case.
        """

        if not isinstance(triage, TriageRecord):
            raise TypeError(
                "triage must be a TriageRecord instance."
            )

        if triage.case_id != self.case_id:
            raise ValueError(
                "Triage case ID does not match CaseState."
            )

        self.triage_records.append(triage)
        self.touch()

    def get_triage(
        self,
        triage_id: str,
    ) -> TriageRecord:
        """
        Retrieve a triage record by ID.
        """

        for triage in self.triage_records:
            if triage.triage_id == triage_id:
                return triage

        raise KeyError(
            f"Triage record '{triage_id}' not found."
        )

    # ------------------------------------------------------------------
    # Communication / Closure
    # ------------------------------------------------------------------

    def add_communication(
        self,
        communication: CommunicationRecord,
    ) -> None:
        """
        Add a communication record to the case.

        The communication must belong to the same case.
        """

        if not isinstance(
            communication,
            CommunicationRecord,
        ):
            raise TypeError(
                "communication must be a CommunicationRecord instance."
            )

        if communication.case_id != self.case_id:
            raise ValueError(
                "Communication case ID does not match CaseState."
            )

        self.communications.append(communication)
        self.touch()

    def get_communication(
        self,
        communication_id: str,
    ) -> CommunicationRecord:
        """
        Retrieve a communication record by ID.
        """

        for communication in self.communications:
            if communication.communication_id == communication_id:
                return communication

        raise KeyError(
            f"Communication '{communication_id}' not found."
        )
    # ------------------------------------------------------------------
    # Verification
    # ------------------------------------------------------------------

    def set_verification(
        self,
        status: VerificationStatus,
        checks: Optional[
            List[Dict[str, Any]]
        ] = None,
        warnings: Optional[
            List[str]
        ] = None,
        failed_checks: Optional[
            List[str]
        ] = None,
        human_review_required: bool = False,
    ) -> None:
        """
        Update the case verification state.
        """

        self.verification.status = status

        if checks is not None:
            self.verification.checks = checks

        if warnings is not None:
            self.verification.warnings = warnings

        if failed_checks is not None:
            self.verification.failed_checks = (
                failed_checks
            )

        self.verification.human_review_required = (
            human_review_required
        )

        self.verification.last_verified_at = (
            datetime.now(
                timezone.utc
            ).isoformat()
        )

        self.touch()

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def set_status(
        self,
        status: CaseStatus,
    ) -> None:
        """
        Change the overall case lifecycle status.
        """

        if not isinstance(status, CaseStatus):
            raise TypeError(
                "status must be a CaseStatus value."
            )

        self.status = status
        self.touch()

    # ------------------------------------------------------------------
    # Warnings
    # ------------------------------------------------------------------

    def add_warning(
        self,
        warning: str,
    ) -> None:
        """
        Add a case-level warning.
        """

        if not warning:
            raise ValueError(
                "warning cannot be empty."
            )

        self.warnings.append(warning)
        self.touch()

    # ------------------------------------------------------------------
    # Notes
    # ------------------------------------------------------------------

    def add_note(
        self,
        note: str,
    ) -> None:
        """
        Add a case-level note.
        """

        if not note:
            raise ValueError(
                "note cannot be empty."
            )

        self.notes.append(note)
        self.touch()

    # ==================================================================
    # SERIALIZATION
    # ==================================================================

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the complete case state into a dictionary.

        Useful for:
        - FastAPI responses
        - logging
        - audit records
        - future PostgreSQL persistence
        """

        data = asdict(self)

        # TaskGraph has its own serialization method.
        data["task_graph"] = (
            self.task_graph.to_dict()
        )

        return data

    # ==================================================================
    # SUMMARY
    # ==================================================================

    def summary(self) -> Dict[str, Any]:
        """
        Return a compact summary of the current case state.
        """

        return {
            "case_id": self.case_id,
            "modality": self.modality.value,
            "body_region": self.body_region,
            "clinical_question": (
                self.clinical_question
            ),
            "status": self.status.value,
            "image_count": len(
                self.images
            ),
            "task_count": (
                self.task_graph.summary()[
                    "task_count"
                ]
            ),
            "evidence_count": len(
                self.evidence
            ),
            "valid_evidence_count": len(
                self.get_valid_evidence()
            ),
            "review_required_evidence_count": len(
                self.get_review_required_evidence()
            ),
            "action_count": len(
                self.actions
            ),
            "available_tools": (
                self.available_tools
            ),
            "selected_tools": (
                self.selected_tools
            ),
            "verification_status": (
                self.verification.status.value
            ),
            "human_review_required": (
                self.verification
                .human_review_required
            ),
            "safety_contract_id": (
                self.safety_contract.contract_id
                if self.safety_contract is not None
                else None
            ),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }