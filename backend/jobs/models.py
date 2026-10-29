"""Job state. Pure data: no framework, no model, no I/O."""
from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class JobStatus(str, Enum):
    QUEUED = "queued"
    VALIDATING = "validating"            # case state, safety contract, task graph, tool authorization
    PREPROCESSING = "preprocessing"      # DICOM validation, HU volume
    RUNNING = "running"                  # the authorized tool is executing
    VERIFYING = "verifying"              # verifier checks the tool output
    EVIDENCE_CREATED = "evidence_created"
    REQUIRES_REVIEW = "requires_review"  # worker finished; a human must review. Resting state.
    COMPLETED = "completed"              # a human review decision has been recorded
    FAILED = "failed"                    # an unexpected error; reason recorded
    BLOCKED = "blocked"                  # the series failed technical validation, or the verifier blocked the result
    ABSTAINED = "abstained"              # governance found no authorized, executable tool for this case: the system declines to analyse


#: statuses in which the worker thread is (or will be) working on the job
WORKING = frozenset({
    JobStatus.QUEUED, JobStatus.VALIDATING, JobStatus.PREPROCESSING, JobStatus.RUNNING,
    JobStatus.VERIFYING, JobStatus.EVIDENCE_CREATED,
})
#: statuses that will not change any more
FINAL = frozenset({JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.BLOCKED, JobStatus.ABSTAINED})


def new_job_id() -> str:
    return f"JOB-{uuid.uuid4().hex[:12].upper()}"


@dataclass
class JobArtifacts:
    """Objects produced by the governed workflow. Kept server-side; the status view never exposes them."""

    case: Any = None            # agent.case_state.CaseState
    plan: Optional[dict] = None
    tool_result: Optional[dict] = None
    verification_outcome: Optional[dict] = None
    evidence_id: Optional[str] = None
    report: Any = None          # reporting.structured_report.StructuredDraftReport
    review: Any = None          # agent.human_review.HumanReview
    lifecycle: Any = None       # agent.review_lifecycle.ReviewLifecycle
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    #: Set once the worker has written the job's final state. A review waits for it, so a review's
    #: write can never be overtaken (and overwritten) by the worker's final write.
    persisted: threading.Event = field(default_factory=threading.Event, repr=False)


@dataclass
class JobRecord:
    job_id: str
    case_id: str
    body_region: str
    clinical_question: Optional[str]
    status: JobStatus = JobStatus.QUEUED
    tool_name: Optional[str] = None
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    steps: list[dict[str, Any]] = field(default_factory=list)
    timings_seconds: dict[str, float] = field(default_factory=dict)
    error: Optional[dict[str, str]] = None
    note: Optional[str] = None
    outcome: Optional[dict[str, Any]] = None
    artifacts: JobArtifacts = field(default_factory=JobArtifacts, repr=False)
    #: True when this record was read back from the database rather than produced by this process.
    #: Its stored status and result are readable, but the live governance objects (CaseState,
    #: report, review lifecycle) do not exist, so a pending human review cannot be completed.
    restored: bool = False

    @property
    def accepted_status(self) -> str:
        """Status at the moment the job was accepted (always 'queued'). The 202 response describes this,
        not the live status: the worker thread may already be running by the time the response is built."""
        return self.steps[0]["status"] if self.steps else JobStatus.QUEUED.value

    def transition(self, status: JobStatus, detail: Optional[str] = None) -> None:
        now = utc_now()
        if self.started_at is None and status != JobStatus.QUEUED:
            self.started_at = now
        self.status = status
        self.updated_at = now
        self.steps.append({"status": status.value, "at": now, "detail": detail})
        if status in FINAL or status == JobStatus.REQUIRES_REVIEW:
            self.finished_at = now

    def to_row(self) -> dict[str, Any]:
        """Column values for persistence. Plain JSON types only; contains no artifacts."""
        return {
            "job_id": self.job_id, "case_id": self.case_id, "body_region": self.body_region,
            "clinical_question": self.clinical_question, "status": self.status.value,
            "tool_name": self.tool_name, "created_at": self.created_at, "updated_at": self.updated_at,
            "started_at": self.started_at, "finished_at": self.finished_at,
            "steps": list(self.steps), "timings_seconds": dict(self.timings_seconds),
            "error": self.error, "note": self.note, "outcome": self.outcome,
        }

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "JobRecord":
        return cls(
            job_id=row["job_id"], case_id=row["case_id"], body_region=row["body_region"],
            clinical_question=row["clinical_question"], status=JobStatus(row["status"]),
            tool_name=row["tool_name"], created_at=row["created_at"], updated_at=row["updated_at"],
            started_at=row["started_at"], finished_at=row["finished_at"],
            steps=list(row["steps"] or []), timings_seconds=dict(row["timings_seconds"] or {}),
            error=row["error"], note=row["note"], outcome=row["outcome"], restored=True,
        )

    def to_dict(self) -> dict[str, Any]:
        """Status view. Contains no model output, no probabilities and no report text."""
        return {
            "job_id": self.job_id,
            "case_id": self.case_id,
            "status": self.status.value,
            "tool_name": self.tool_name,
            "body_region": self.body_region,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "steps": list(self.steps),
            "timings_seconds": dict(self.timings_seconds),
            "error": self.error,
            "note": self.note,
            "outcome": self.outcome,
            "restored_after_restart": self.restored,
        }
