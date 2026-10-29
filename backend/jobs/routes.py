"""
HTTP routes for analysis jobs.

  POST /cases/{case_id}/analysis     create a job; returns 202 immediately
  GET  /cases/{case_id}/jobs         jobs for a case
  GET  /jobs/{job_id}                status only. Never starts or advances anything.
  GET  /jobs/{job_id}/result         verification, evidence, report and review state (after the worker is done)
  POST /jobs/{job_id}/review         record the human decision (accept | modify | reject)

The reviewer id is a self-asserted label until authentication exists. It is recorded, not trusted.

Research & Engineering Prototype - Not for clinical diagnosis or treatment.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Literal, Optional

from fastapi import APIRouter, Body, HTTPException, Path as PathParam, Response
from pydantic import BaseModel, Field

from .service import NOTICE, AnalysisJobService, JobRejected

JOB_ID_PATTERN = r"^JOB-[A-F0-9]{12}$"

_STATUS_FOR_KIND = {
    "not_found": 404,
    "not_ready": 409,
    "conflict": 409,
    "busy": 429,
    "unavailable": 503,
    "invalid": 400,
}


class AnalysisRequest(BaseModel):
    body_region: str = Field("head", pattern=r"^[A-Za-z][A-Za-z _-]{0,31}$")
    clinical_question: Optional[str] = Field(None, max_length=300)


class ReviewRequest(BaseModel):
    reviewer_id: str = Field(..., pattern=r"^[A-Za-z0-9][A-Za-z0-9 _.@-]{0,63}$")
    decision: Literal["accept", "modify", "reject"]
    reason: Optional[str] = Field(None, max_length=500)
    comments: Optional[list[str]] = Field(None, max_length=10)
    modified_observations: Optional[list[dict[str, Any]]] = Field(None, max_length=50)


def series_locator_from_context(
    upload_dir: Path,
    validate_case_id: Callable[[str], None],
    select_series: Callable[..., tuple[str, Path]],
    get_dicom_files: Callable[[Path], list[Path]],
) -> Callable[[str], tuple[str, list[Path]]]:
    """Adapt main.py's series helpers. Refuses unknown cases without creating folders."""

    def locate(case_id: str) -> tuple[str, list[Path]]:
        try:
            validate_case_id(case_id)
        except HTTPException as error:
            raise JobRejected("invalid", str(error.detail)) from error
        if not (upload_dir / case_id).is_dir():
            raise JobRejected("not_found", f"Case not found: {case_id}")
        try:
            series_uid, series_dir = select_series(case_id)
        except HTTPException as error:
            if error.status_code == 404:
                raise JobRejected("not_ready", "Upload a CT series to this case before requesting an analysis.") from error
            raise JobRejected("invalid", str(error.detail)) from error
        files = sorted(get_dicom_files(series_dir))
        if not files:
            raise JobRejected("not_ready", "The selected series contains no DICOM files.")
        return series_uid, files

    return locate


def build_job_router(service: AnalysisJobService, validate_case_id: Callable[[str], None]) -> APIRouter:
    router = APIRouter(tags=["analysis jobs"])

    def reject(error: JobRejected) -> HTTPException:
        headers = {"Retry-After": "30"} if error.kind == "busy" else None
        return HTTPException(status_code=_STATUS_FOR_KIND.get(error.kind, 400), detail=error.reason, headers=headers)

    @router.post("/cases/{case_id}/analysis", status_code=202)
    def create_analysis(
        case_id: str,
        response: Response,
        payload: Optional[AnalysisRequest] = Body(default=None),
    ):
        validate_case_id(case_id)
        payload = payload or AnalysisRequest()
        try:
            job = service.submit(case_id, payload.body_region, payload.clinical_question)
        except JobRejected as error:
            raise reject(error) from error
        response.headers["Location"] = f"/jobs/{job.job_id}"
        return {
            "notice": NOTICE,
            "job_id": job.job_id,
            "case_id": job.case_id,
            # Status at acceptance. The worker runs on its own thread and may already have advanced.
            "status": job.accepted_status,
            "links": {"status": f"/jobs/{job.job_id}", "result": f"/jobs/{job.job_id}/result"},
        }

    @router.get("/cases/{case_id}/jobs")
    def list_case_jobs(case_id: str):
        validate_case_id(case_id)
        return {"case_id": case_id, "jobs": [job.to_dict() for job in service.list_for_case(case_id)]}

    @router.get("/jobs/{job_id}")
    def job_status(job_id: str = PathParam(..., pattern=JOB_ID_PATTERN)):
        try:
            return {"notice": NOTICE, **service.get(job_id).to_dict()}
        except JobRejected as error:
            raise reject(error) from error

    @router.get("/jobs/{job_id}/result")
    def job_result(job_id: str = PathParam(..., pattern=JOB_ID_PATTERN)):
        try:
            return service.result(job_id)
        except JobRejected as error:
            raise reject(error) from error

    @router.post("/jobs/{job_id}/review")
    def job_review(request: ReviewRequest, job_id: str = PathParam(..., pattern=JOB_ID_PATTERN)):
        try:
            review = service.review(
                job_id,
                reviewer_id=request.reviewer_id,
                decision=request.decision,
                reason=request.reason,
                comments=request.comments,
                modified_observations=request.modified_observations,
            )
        except JobRejected as error:
            raise reject(error) from error
        return {"notice": NOTICE, "job_id": job_id, "human_review": review}

    return router
