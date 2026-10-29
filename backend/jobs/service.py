"""
AnalysisJobService: runs the existing governed workflow for one case as a background job.

  validating     CaseState, orchestrator.plan (Safety Contract + Task Graph), authorized tool selection
  preprocessing  DICOM validation and HU volume  (technical_validation task)
  running        adapter.execute(tool, {"volume": ...})                              (ich_analysis task)
  verifying      orchestrator.verify_analysis                                         (verification task)
  evidence_created  EvidenceItem + provenance, status set from the verifier decision
  requires_review   structured draft report + pending HumanReview; a human decides next

Everything that decides something (authorization, verification, evidence status, report, review rules)
is the existing governance code. This module only sequences it and records what happened.

One worker thread: the model runs one case at a time, and job state is in process memory until
persistence (PostgreSQL / object storage) is added. A restart loses job state: that is stated, not hidden.

Research & Engineering Prototype - Not for clinical diagnosis or treatment.
"""
from __future__ import annotations

import dataclasses
import enum
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator, Optional

from agent.case_state import (
    CaseModality,
    CaseState,
    CaseStatus,
    EvidenceItem,
    EvidenceProvenance,
    VerificationStatus,
)
from agent.human_review import HumanReview
from agent.orchestrator import AgentOrchestrator
from agent.review_lifecycle import ReviewLifecycle
from reporting.structured_report import create_structured_draft_report

from .execution import ExecutionAdapter
from .models import FINAL, WORKING, JobRecord, JobStatus, new_job_id

log = logging.getLogger("jobs")

NOTICE = "Research & Engineering Prototype - Not for clinical diagnosis or treatment."
DEFAULT_QUESTION = "Research workflow analysis of the uploaded series (not a diagnosis)"
MAX_STORED_JOBS = 200


class JobRejected(Exception):
    """A request the service refuses. `kind` maps to an HTTP status in routes.py."""

    def __init__(self, kind: str, reason: str):
        super().__init__(reason)
        self.kind = kind  # not_found | not_ready | conflict | busy | unavailable | invalid
        self.reason = reason


class _Stop(Exception):
    """Internal: the job reached a final state on purpose (blocked/abstained); stop the pipeline."""


# --------------------------------------------------------------------------------------------
# default readers (heavy imports stay lazy so this module imports without pydicom)
# --------------------------------------------------------------------------------------------
def _read_header(path: Path) -> dict[str, str]:
    import pydicom

    ds = pydicom.dcmread(str(path), stop_before_pixels=True)
    return {
        "modality": str(getattr(ds, "Modality", "")).upper(),
        "study_uid": str(getattr(ds, "StudyInstanceUID", "")),
        "series_uid": str(getattr(ds, "SeriesInstanceUID", "")),
    }


def _load_series(paths: list[str]) -> dict[str, Any]:
    from preprocessing.ct_preprocessing import preprocess_ct_series

    return preprocess_ct_series(paths)


def to_jsonable(value: Any) -> Any:
    """Convert dataclasses, enums, numpy values and paths into plain JSON types."""
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return to_jsonable(dataclasses.asdict(value))
    if isinstance(value, enum.Enum):
        return value.value
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [to_jsonable(v) for v in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if hasattr(value, "tolist"):
        return value.tolist()
    if hasattr(value, "item"):
        return value.item()
    return str(value)


def _slice_indices(result: dict[str, Any]) -> list[int]:
    """The tool reports {subtype: [{slice_index, probability}, ...]}; evidence wants plain slice numbers."""
    found: set[int] = set()
    supporting = (result.get("series") or {}).get("supporting_slices") or {}
    if isinstance(supporting, dict):
        for entries in supporting.values():
            for entry in entries or []:
                if isinstance(entry, dict) and isinstance(entry.get("slice_index"), int):
                    found.add(entry["slice_index"])
    elif isinstance(supporting, list):
        found.update(v for v in supporting if isinstance(v, int))
    return sorted(found)


class JobStore:
    """In-memory job registry behind a lock. Replace with a database-backed store later."""

    def __init__(self, cap: int = MAX_STORED_JOBS):
        self._jobs: dict[str, JobRecord] = {}
        self._lock = threading.RLock()
        self._cap = cap

    def add(self, job: JobRecord) -> None:
        with self._lock:
            self._jobs[job.job_id] = job
            if len(self._jobs) > self._cap:
                for job_id, old in list(self._jobs.items()):
                    if old.status in FINAL and len(self._jobs) > self._cap:
                        del self._jobs[job_id]

    def get(self, job_id: str) -> Optional[JobRecord]:
        with self._lock:
            return self._jobs.get(job_id)

    def for_case(self, case_id: str) -> list[JobRecord]:
        with self._lock:
            return [j for j in self._jobs.values() if j.case_id == case_id]

    def count_working(self) -> int:
        with self._lock:
            return sum(1 for j in self._jobs.values() if j.status in WORKING)

    # ---- persistence hooks: no-ops here, implemented by jobs.persistence.PersistentJobStore ----
    def save(self, job: JobRecord, snapshot: Any = None, *, write_snapshot: bool = False) -> None:
        """Record the job's current state. `snapshot` is the /result payload (without the job view)."""

    def snapshot(self, job_id: str) -> Optional[dict[str, Any]]:
        """The stored /result snapshot for a restored job, if any."""
        return None

    def persist_case_state(self, case: Any, *, reviews: bool) -> None:
        """Write the normalized case / evidence / verification rows (and completed reviews if asked)."""

    def recover_interrupted(self) -> list[str]:
        """Mark jobs left in a working state by a previous process as failed. Returns their ids."""
        return []

    def describe(self) -> dict[str, Any]:
        return {"state_storage": "in-process memory (lost on restart)"}


class AnalysisJobService:
    def __init__(
        self,
        adapter: ExecutionAdapter,
        series_locator: Callable[[str], tuple[str, list[Path]]],
        series_loader: Optional[Callable[[list[str]], dict[str, Any]]] = None,
        header_reader: Optional[Callable[[Path], dict[str, str]]] = None,
        max_pending: int = 3,
        store: Optional[JobStore] = None,
    ):
        self.adapter = adapter
        self.series_locator = series_locator
        self.series_loader = series_loader or _load_series
        self.header_reader = header_reader or _read_header
        self.max_pending = max_pending
        self.store = store or JobStore()
        self._submit_lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="analysis-job")

    # ----------------------------------------------------------------------------------------
    # public API
    # ----------------------------------------------------------------------------------------
    def runtime_status(self) -> dict[str, Any]:
        status = dict(self.adapter.runtime_status())
        status["jobs_working"] = self.store.count_working()
        status["max_pending"] = self.max_pending
        status.update(self.store.describe())
        return status

    def submit(self, case_id: str, body_region: str = "head", clinical_question: Optional[str] = None) -> JobRecord:
        runtime = self.adapter.runtime_status()
        if not runtime.get("available"):
            raise JobRejected("unavailable", f"Model runtime is not available: {runtime.get('reason')}")

        series_uid, files = self.series_locator(case_id)  # raises JobRejected(not_found | not_ready)

        with self._submit_lock:
            for other in self.store.for_case(case_id):
                if other.restored:
                    continue  # read back from the database: no live worker or review context exists for it
                if other.status in WORKING or other.status == JobStatus.REQUIRES_REVIEW:
                    raise JobRejected(
                        "conflict",
                        f"Case {case_id} already has job {other.job_id} in state '{other.status.value}'. "
                        "Wait for it, or record the human review first.",
                    )
            if self.store.count_working() >= self.max_pending:
                raise JobRejected("busy", "The analysis queue is full. Try again shortly.")
            job = JobRecord(
                job_id=new_job_id(),
                case_id=case_id,
                body_region=body_region.strip().lower(),
                clinical_question=clinical_question,
            )
            job.steps.append({"status": JobStatus.QUEUED.value, "at": job.created_at, "detail": "accepted"})
            self.store.add(job)

        self._executor.submit(self._run_job, job.job_id, series_uid, list(files))
        return job

    def get(self, job_id: str) -> JobRecord:
        job = self.store.get(job_id)
        if job is None:
            raise JobRejected("not_found", f"Job not found: {job_id}")
        return job

    def list_for_case(self, case_id: str) -> list[JobRecord]:
        return sorted(self.store.for_case(case_id), key=lambda j: j.created_at, reverse=True)

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)

    # ----------------------------------------------------------------------------------------
    # worker
    # ----------------------------------------------------------------------------------------
    @contextmanager
    def _stage(self, job: JobRecord, status: JobStatus, detail: Optional[str] = None) -> Iterator[None]:
        job.transition(status, detail)
        self.store.save(job)
        started = time.perf_counter()
        try:
            yield
        finally:
            job.timings_seconds[status.value] = round(time.perf_counter() - started, 3)

    def _run_job(self, job_id: str, series_uid: str, files: list[Path]) -> None:
        job = self.store.get(job_id)
        if job is None:
            return
        try:
            self._execute(job, series_uid, files)
        except _Stop:
            pass
        except Exception as error:  # noqa: BLE001 - recorded on the job, never swallowed silently
            log.exception("job %s failed in stage %s", job.job_id, job.status.value)
            self._fail(job, error)
        finally:
            self._persist_final(job)

    def _persist_final(self, job: JobRecord) -> None:
        """Write the finished job, its /result snapshot and the normalized governance rows."""
        case = job.artifacts.case
        try:
            self.store.save(job, self._snapshot(job), write_snapshot=True)
            if case is not None:
                # Pending reviews are deliberately not written: human_reviews holds completed reviews only.
                self.store.persist_case_state(case, reviews=False)
        finally:
            job.artifacts.persisted.set()

    def _end(self, job: JobRecord, status: JobStatus, note: str, case_status: CaseStatus) -> None:
        job.note = note
        case = job.artifacts.case
        if case is not None:
            case.set_status(case_status)
        job.transition(status, note)
        raise _Stop()

    def _fail(self, job: JobRecord, error: Exception) -> None:
        stage = job.status.value
        job.error = {"stage": stage, "type": type(error).__name__, "message": str(error)[:400]}
        case = job.artifacts.case
        if case is not None:
            case.set_status(CaseStatus.FAILED)
            task_id = {"running": f"{case.case_id}-ANALYSIS", "preprocessing": f"{case.case_id}-TECHNICAL"}.get(stage)
            if task_id and case.task_graph.has_task(task_id):
                case.task_graph.mark_failed(task_id)
        job.transition(JobStatus.FAILED, f"{type(error).__name__} during {stage}")

    def _execute(self, job: JobRecord, series_uid: str, files: list[Path]) -> None:
        art = job.artifacts

        # ---- validating: governance planning -------------------------------------------------
        with self._stage(job, JobStatus.VALIDATING, "case state, safety contract, task graph, tool authorization"):
            header = self.header_reader(files[0])
            try:
                modality = CaseModality(header["modality"])
            except ValueError:
                modality = CaseModality.UNKNOWN
            case = CaseState(
                case_id=job.case_id,
                modality=modality,
                body_region=job.body_region,
                clinical_question=job.clinical_question or DEFAULT_QUESTION,
            )
            case.add_image(
                {
                    "series_instance_uid": series_uid,
                    "study_instance_uid": header["study_uid"],
                    "slice_count": len(files),
                }
            )
            art.case = case
            orchestrator = AgentOrchestrator(self.adapter.registry())
            art.plan = orchestrator.plan(case)

            executable = self.adapter.executable_tools()
            candidates = sorted(t["name"] for t in art.plan["available_tools"] if t["name"] in executable)
            if not candidates:
                self._end(
                    job,
                    JobStatus.ABSTAINED,
                    f"No authorized, executable tool for modality {modality.value} / region '{job.body_region}'. "
                    "The system declines to analyse this case.",
                    CaseStatus.ABSTAINED,
                )
            tool_name = candidates[0]
            try:
                orchestrator.select_tool(case, tool_name)  # Safety Contract must approve it
            except (PermissionError, ValueError) as error:
                self._end(job, JobStatus.ABSTAINED, f"Tool selection refused: {error}", CaseStatus.ABSTAINED)
            job.tool_name = tool_name
            if case.task_graph.has_task(f"{case.case_id}-INTAKE"):
                case.task_graph.mark_completed(f"{case.case_id}-INTAKE")

        # ---- preprocessing: technical validation + HU volume ---------------------------------
        with self._stage(job, JobStatus.PREPROCESSING, f"{len(files)} files"):
            try:
                processed = self.series_loader([str(p) for p in files])
            except ValueError as error:  # the series itself was rejected: an input problem, not a crash
                if case.task_graph.has_task(f"{case.case_id}-TECHNICAL"):
                    case.task_graph.mark_failed(f"{case.case_id}-TECHNICAL")
                self._end(job, JobStatus.BLOCKED, f"Series rejected by technical validation: {error}", CaseStatus.FAILED)
            volume = processed["volume"]
            spacing = [float(v) for v in processed["voxel_spacing"]]
            case.update_metadata("slice_count", int(volume.shape[0]))
            case.update_metadata("voxel_spacing", spacing)
            case.update_metadata("study_instance_uid", header["study_uid"])
            case.update_metadata("series_instance_uid", series_uid)
            if case.task_graph.has_task(f"{case.case_id}-TECHNICAL"):
                case.task_graph.mark_completed(f"{case.case_id}-TECHNICAL")

        # ---- running: the authorized tool ----------------------------------------------------
        with self._stage(job, JobStatus.RUNNING, f"{tool_name} on volume {list(volume.shape)}"):
            result = self.adapter.execute(tool_name, {"volume": volume})
            if not isinstance(result, dict):
                raise TypeError("The tool returned a non-dictionary result.")
            art.tool_result = result
            task_id = f"{case.case_id}-ANALYSIS"
            if case.task_graph.has_task(task_id):
                if result.get("status") == "completed":
                    case.task_graph.mark_completed(task_id)
                else:
                    case.task_graph.mark_failed(task_id)
        del volume, processed

        # ---- verifying: existing verifier, called through the orchestrator --------------------
        with self._stage(job, JobStatus.VERIFYING):
            outcome = orchestrator.verify_analysis(case, result)
            art.verification_outcome = outcome
        decision = outcome["verification_result"]["decision"]

        # ---- evidence_created: provenance + status from the verifier decision ------------------
        with self._stage(job, JobStatus.EVIDENCE_CREATED):
            evidence = self._create_evidence(job, case, tool_name, result, decision, outcome, spacing, series_uid)
            art.evidence_id = evidence.evidence_id
            report = create_structured_draft_report(case, f"{job.job_id}-REP-1")
            review = HumanReview(review_id=f"{job.job_id}-REV-1", case_id=case.case_id, report_id=report.report_id)
            case.add_human_review(review)
            art.report, art.review = report, review
            art.lifecycle = ReviewLifecycle(case=case, report=report, review=review)

        job.outcome = {
            "verification_decision": decision["status"],
            "verification_action": decision["action"],
            "case_status": case.status.value,
            "evidence_status": evidence.status.value,
            "report_status": report.status.value,
            "human_review": "pending",
            "clinical_diagnosis": False,
        }
        if decision["status"] == "blocked":
            job.note = "Verification blocked this result. It cannot support a report finding."
            job.transition(JobStatus.BLOCKED, job.note)
        else:
            job.note = "Human review is required. No clinical decision has been made."
            job.transition(JobStatus.REQUIRES_REVIEW, job.note)

    def _create_evidence(
        self,
        job: JobRecord,
        case: CaseState,
        tool_name: str,
        result: dict[str, Any],
        decision: dict[str, Any],
        outcome: dict[str, Any],
        spacing: list[float],
        series_uid: str,
    ) -> EvidenceItem:
        probability = (result.get("prediction") or {}).get("any_probability")
        produced = result.get("status") == "completed" and isinstance(probability, (int, float))
        claim = (
            f"Research-model any-hemorrhage probability {float(probability):.4f} (unvalidated, not a diagnosis)"
            if produced
            else "The tool did not return a prediction. No finding exists."
        )
        info = result.get("evidence") or {}
        metadata = self.adapter.registry().get_metadata(tool_name)
        evidence = EvidenceItem(
            evidence_id=f"{job.job_id}-EV-1",
            case_id=case.case_id,
            evidence_type="model_output",
            source=tool_name,
            claim=claim,
            output=result,
            confidence=float(probability) if produced else None,
            series_uid=series_uid,
            supporting_slices=_slice_indices(result),
            task_id=f"{case.case_id}-ANALYSIS",
            warnings=[str(w) for w in (result.get("warnings") or [])],
            provenance=EvidenceProvenance(
                tool_name=tool_name,
                tool_version=metadata.version,
                model_name=info.get("model"),
                model_version=info.get("model_version"),
                runtime=self.adapter.name,
                input_references=[series_uid],
                metadata={
                    "job_id": job.job_id,
                    "device": info.get("device"),
                    "voxel_spacing_mm": spacing,
                    "units": (result.get("input") or {}).get("units"),
                    "verifier": outcome["verification_result"].get("verifier"),
                    "runtime": self.adapter.provenance(),
                    "validation_status": "research model; clinical validation not established",
                },
            ),
            metadata={"job_id": job.job_id},
        )
        case.add_evidence(evidence)
        status = decision["status"]
        if status == "verified_for_workflow_review":
            evidence.mark_valid("verification_passed")
        elif status == "requires_review":
            evidence.mark_requires_review("verification_requires_review")
        else:
            evidence.invalidate(decision.get("reason") or "verifier blocked this result", "verification_blocked")
        return evidence

    # ----------------------------------------------------------------------------------------
    # result and human review
    # ----------------------------------------------------------------------------------------
    def _snapshot(self, job: JobRecord) -> dict[str, Any]:
        """Everything GET /jobs/{id}/result shows besides the notice and the job status view."""
        art = job.artifacts
        case = art.case
        if case is None:
            return {}  # failed or abstained before a case existed
        return to_jsonable(
            {
                "case": case.summary(),
                "safety_contract": case.safety_contract.to_dict() if case.safety_contract else None,
                "task_graph": case.task_graph.to_dict(),
                "verification": (art.verification_outcome or {}).get("verification_result"),
                "evidence": list(case.evidence),
                "report": art.report.to_dict() if art.report else None,
                "human_review": art.review.to_dict() if art.review else None,
            }
        )

    def result(self, job_id: str) -> dict[str, Any]:
        job = self.get(job_id)
        if job.status in WORKING:
            raise JobRejected("conflict", f"Job {job_id} is still '{job.status.value}'.")
        snapshot = (self.store.snapshot(job_id) or {}) if job.restored else self._snapshot(job)
        return to_jsonable({"notice": NOTICE, "job": job.to_dict(), **snapshot})

    def review(
        self,
        job_id: str,
        *,
        reviewer_id: str,
        decision: str,
        reason: Optional[str] = None,
        comments: Optional[list[str]] = None,
        modified_observations: Optional[list[dict[str, Any]]] = None,
    ) -> dict[str, Any]:
        job = self.get(job_id)
        art = job.artifacts
        if job.restored and job.status == JobStatus.REQUIRES_REVIEW:
            raise JobRejected(
                "conflict",
                f"Job {job_id} was awaiting human review when the backend restarted. Its live review context "
                "(case state, report and review lifecycle) was interrupted and is not stored, so this review "
                f"cannot be completed. The stored result stays readable. Rerun the analysis for case "
                f"{job.case_id} (POST /cases/{job.case_id}/analysis) and review the new job.",
            )
        if job.status == JobStatus.REQUIRES_REVIEW and not art.persisted.wait(timeout=15):
            raise JobRejected("conflict", f"Job {job_id} is still being finalized. Try again in a moment.")
        with art.lock:
            if job.status != JobStatus.REQUIRES_REVIEW or art.lifecycle is None:
                raise JobRejected(
                    "conflict",
                    f"Job {job_id} is '{job.status.value}'. Review is possible only while it is 'requires_review'.",
                )
            lifecycle: ReviewLifecycle = art.lifecycle
            case: CaseState = art.case
            if decision in ("modify", "reject") and not (reason or "").strip():
                raise JobRejected("invalid", f"A reason is required to {decision} a report.")
            if decision == "modify" and not modified_observations:
                raise JobRejected("invalid", "modified_observations are required to modify a report.")
            if decision not in ("accept", "modify", "reject"):
                raise JobRejected("invalid", "decision must be accept, modify or reject.")
            try:
                if lifecycle.review.started_at is None:
                    lifecycle.start_review()
                verification_refs = ["verification_passed"] if case.verification.status == VerificationStatus.PASSED else []
                lifecycle.record_review_context([e.evidence_id for e in case.evidence], verification_refs)
                if decision == "accept":
                    lifecycle.accept(reviewer_id, comments=comments)
                elif decision == "modify":
                    lifecycle.modify(reviewer_id, modified_observations or [], reason or "", comments=comments)
                else:
                    lifecycle.reject(reviewer_id, reason or "", comments=comments)
            except ValueError as error:
                raise JobRejected("invalid", str(error)) from error

            task_id = f"{case.case_id}-HUMAN-REVIEW"
            if case.task_graph.has_task(task_id):
                case.task_graph.mark_completed(task_id)
            case.set_status(CaseStatus.COMPLETED)
            job.outcome = {**(job.outcome or {}), "human_review": f"completed: {decision}"}
            job.note = f"Human review recorded: {decision} by {reviewer_id}."
            job.transition(JobStatus.COMPLETED, job.note)
            self.store.save(job, self._snapshot(job), write_snapshot=True)
            self.store.persist_case_state(case, reviews=True)  # the review is completed: safe to write
            return to_jsonable(art.review.to_dict())
