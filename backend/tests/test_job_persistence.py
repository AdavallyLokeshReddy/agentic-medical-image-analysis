"""
Phase 3: PostgreSQL persistence of analysis jobs. Needs a reachable PostgreSQL (DATABASE_URL); skipped otherwise.

The tool is the TEST DOUBLE from test_jobs.py. These tests prove that job state, the /result snapshot and
completed reviews are durable and that a "restart" (a brand-new service and store on the same database)
behaves as documented. They say nothing about model quality.
"""
from __future__ import annotations

import importlib.util
import threading
import time
import uuid

import pytest
from sqlalchemy import select, text

from database.connection import SessionLocal, engine
from database.job_repository import JobRepository
from database.models import CaseModel, EvidenceModel, HumanReviewModel, JobModel, VerificationModel
from jobs.models import WORKING, JobStatus
from jobs.persistence import RESTART_REASON, PersistentJobStore, store_from_environment
from jobs.service import AnalysisJobService, JobRejected, JobStore
from tests.test_jobs import RESTING, FakeIchTool, make_service, wait_for


@pytest.fixture()
def store():
    PersistentJobStore(SessionLocal)  # creates the jobs table if needed
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM jobs"))
    return PersistentJobStore(SessionLocal)


@pytest.fixture()
def case_id():
    return f"CASE-P-{uuid.uuid4().hex[:8].upper()}"


@pytest.fixture()
def services():
    made = []
    yield made
    for service in made:
        service.shutdown()


def build(services, store, **kw):
    service, tool = make_service(store=store, **kw)
    services.append(service)
    return service, tool


def restart(services, **kw):
    """A new process: new store, new service, same database. Recovery runs once, as at startup."""
    fresh_store = PersistentJobStore(SessionLocal)
    fresh_store.recover_interrupted()
    service, _ = build(services, fresh_store, **kw)
    return service, fresh_store


def run_to_rest(service, case_id):
    """Wait for the job to rest AND for the worker's final database write (it lands a moment after the
    in-memory status changes; live reads are served from memory, restored reads from the database)."""
    job = service.submit(case_id, "head")
    wait_for(service, job, RESTING)
    assert job.artifacts.persisted.wait(10), "worker never finished its final write"
    return job


def row(job_id):
    return JobRepository(SessionLocal).get(job_id)


# ------------------------------------------------------------------ persist and retrieve

def test_job_is_persisted_and_can_be_retrieved(services, store, case_id):
    service, _ = build(services, store)
    job = run_to_rest(service, case_id)
    saved = row(job.job_id)
    assert saved is not None
    assert (saved["case_id"], saved["tool_name"], saved["body_region"]) == (case_id, "ich_detection", "head")
    assert saved["status"] == "requires_review"
    assert saved["outcome"]["human_review"] == "pending"
    assert saved["outcome"]["clinical_diagnosis"] is False


def test_steps_timings_and_timestamps_are_persisted_exactly(services, store, case_id):
    service, _ = build(services, store)
    job = run_to_rest(service, case_id)
    saved = row(job.job_id)
    assert [s["status"] for s in saved["steps"]] == [
        "queued", "validating", "preprocessing", "running", "verifying", "evidence_created", "requires_review",
    ]
    assert saved["steps"] == job.steps
    assert saved["timings_seconds"] == job.timings_seconds
    assert set(saved["timings_seconds"]) >= {"validating", "preprocessing", "running", "verifying", "evidence_created"}
    assert (saved["created_at"], saved["updated_at"], saved["started_at"], saved["finished_at"]) == (
        job.created_at, job.updated_at, job.started_at, job.finished_at,
    )


def test_every_transition_is_written_while_the_job_runs(services, store, case_id):
    gate = threading.Event()
    service, _ = build(services, store, tool=FakeIchTool(gate=gate))
    job = service.submit(case_id, "head")
    assert row(job.job_id)["status"] in {"queued", "validating", "preprocessing", "running"}
    wait_for(service, job, {JobStatus.RUNNING})
    deadline = time.time() + 5
    while time.time() < deadline and row(job.job_id)["status"] != "running":
        time.sleep(0.01)
    during = row(job.job_id)
    assert during["status"] == "running"  # visible in PostgreSQL before the model has finished
    assert [s["status"] for s in during["steps"]][-1] == "running"
    assert during["finished_at"] is None
    gate.set()
    wait_for(service, job, RESTING)
    assert job.artifacts.persisted.wait(10)
    assert row(job.job_id)["status"] == "requires_review"


# ------------------------------------------------------------------ result snapshot and governance rows

def test_result_snapshot_is_persisted(services, store, case_id):
    service, _ = build(services, store)
    job = run_to_rest(service, case_id)
    snapshot = row(job.job_id)["result_json"]
    live = service.result(job.job_id)
    for key in ("case", "safety_contract", "task_graph", "verification", "evidence", "report", "human_review"):
        assert snapshot[key] == live[key], key
    assert snapshot["evidence"][0]["provenance"]["tool_name"] == "ich_detection"
    assert snapshot["evidence"][0]["id" if "id" in snapshot["evidence"][0] else "evidence_id"].endswith("-EV-1")
    assert snapshot["report"]["status"] == "draft" and snapshot["report"]["human_review_required"] is True
    assert snapshot["human_review"]["status"] == "pending"


def test_case_evidence_and_verification_rows_are_written_but_no_pending_review_row(services, store, case_id):
    service, _ = build(services, store)
    job = run_to_rest(service, case_id)
    evidence_id = f"{job.job_id}-EV-1"
    with SessionLocal() as session:
        case = session.scalar(select(CaseModel).where(CaseModel.case_id == case_id))
        evidence = session.scalar(select(EvidenceModel).where(EvidenceModel.evidence_id == evidence_id))
        verification = session.scalar(select(VerificationModel).where(VerificationModel.case_id == case_id))
        reviews = session.scalars(select(HumanReviewModel).where(HumanReviewModel.case_id == case_id)).all()
    assert case is not None and case.status == "requires_review"
    assert evidence is not None and evidence.status == "valid"
    assert evidence.metadata_json["provenance"]["tool_name"] == "ich_detection"
    assert verification is not None and verification.status == "passed"
    assert reviews == []  # a pending review is never written to human_reviews


def test_blocked_and_failed_jobs_are_persisted_with_their_reason(services, store, case_id):
    service, _ = build(services, store, tool=FakeIchTool(raises=RuntimeError("model exploded")))
    failed = run_to_rest(service, case_id)
    saved = row(failed.job_id)
    assert saved["status"] == "failed"
    assert saved["error"]["type"] == "RuntimeError" and "model exploded" in saved["error"]["message"]
    service2, _ = build(services, store, tool=FakeIchTool(status="failed"))
    blocked = run_to_rest(service2, f"{case_id}-B")
    assert row(blocked.job_id)["status"] == "blocked"
    assert row(blocked.job_id)["result_json"]["evidence"][0]["status"] == "invalid"


# ------------------------------------------------------------------ completed review

def test_completed_review_is_persisted_in_human_reviews_and_in_the_job(services, store, case_id):
    service, _ = build(services, store)
    job = run_to_rest(service, case_id)
    service.review(job.job_id, reviewer_id="reviewer-1", decision="accept", comments=["looks consistent"])
    saved = row(job.job_id)
    assert saved["status"] == "completed"
    assert saved["steps"][-1]["status"] == "completed"
    assert saved["result_json"]["human_review"]["status"] == "completed"
    assert saved["result_json"]["human_review"]["decision"] == "accept"
    with SessionLocal() as session:
        review = session.scalar(select(HumanReviewModel).where(HumanReviewModel.review_id == f"{job.job_id}-REV-1"))
        case = session.scalar(select(CaseModel).where(CaseModel.case_id == case_id))
    assert (review.reviewer_id, review.decision, review.status) == ("reviewer-1", "accept", "completed")
    assert f"{job.job_id}-EV-1" in review.evidence_ids
    assert case.status == "completed"


def test_a_refused_review_writes_nothing(services, store, case_id):
    service, _ = build(services, store)
    job = run_to_rest(service, case_id)
    with pytest.raises(JobRejected):
        service.review(job.job_id, reviewer_id="r1", decision="reject")  # reason required
    assert row(job.job_id)["status"] == "requires_review"
    with SessionLocal() as session:
        assert session.scalars(select(HumanReviewModel).where(HumanReviewModel.case_id == case_id)).all() == []


# ------------------------------------------------------------------ restart

def test_restart_completed_job_is_still_readable(services, store, case_id):
    service, _ = build(services, store)
    job = run_to_rest(service, case_id)
    service.review(job.job_id, reviewer_id="reviewer-1", decision="reject", reason="image quality")
    before = service.result(job.job_id)
    service.shutdown()

    service2, _ = restart(services)
    restored = service2.get(job.job_id)
    assert restored.restored is True and restored.status == JobStatus.COMPLETED
    after = service2.result(job.job_id)
    assert after["job"]["restored_after_restart"] is True
    assert {k: v for k, v in after["job"].items() if k != "restored_after_restart"} == {
        k: v for k, v in before["job"].items() if k != "restored_after_restart"
    }
    for key in ("case", "safety_contract", "task_graph", "verification", "evidence", "report", "human_review"):
        assert after[key] == before[key], key
    assert after["human_review"]["decision"] == "reject"
    assert [j.job_id for j in service2.list_for_case(case_id)] == [job.job_id]


def test_restart_requires_review_job_is_readable_but_its_review_cannot_be_completed(services, store, case_id):
    service, _ = build(services, store)
    job = run_to_rest(service, case_id)
    service.shutdown()

    service2, _ = restart(services)
    restored = service2.get(job.job_id)
    assert restored.status == JobStatus.REQUIRES_REVIEW and restored.restored is True
    result = service2.result(job.job_id)
    assert result["human_review"]["status"] == "pending"
    assert result["evidence"][0]["provenance"]["tool_name"] == "ich_detection"

    with pytest.raises(JobRejected) as refused:
        service2.review(job.job_id, reviewer_id="reviewer-1", decision="accept")
    assert refused.value.kind == "conflict"
    message = refused.value.reason.lower()
    assert "restart" in message and "interrupted" in message and "rerun" in message
    # Nothing changed anywhere.
    assert service2.get(job.job_id).status == JobStatus.REQUIRES_REVIEW
    assert row(job.job_id)["status"] == "requires_review"
    with SessionLocal() as session:
        assert session.scalars(select(HumanReviewModel).where(HumanReviewModel.case_id == case_id)).all() == []


def test_restart_analysis_can_be_rerun_and_the_new_job_can_be_reviewed(services, store, case_id):
    service, _ = build(services, store)
    old = run_to_rest(service, case_id)
    service.shutdown()

    service2, _ = restart(services)
    new = run_to_rest(service2, case_id)  # the orphaned requires_review job must not block a rerun
    assert new.job_id != old.job_id and new.status == JobStatus.REQUIRES_REVIEW
    service2.review(new.job_id, reviewer_id="reviewer-2", decision="accept")
    assert row(new.job_id)["status"] == "completed"
    assert row(old.job_id)["status"] == "requires_review"  # the old one stays as it was
    assert {j.job_id for j in service2.list_for_case(case_id)} == {old.job_id, new.job_id}


def test_restart_marks_interrupted_jobs_failed_and_leaves_the_rest_alone(services, store, case_id):
    service, _ = build(services, store)
    resting = run_to_rest(service, case_id)
    service.shutdown()
    repository = JobRepository(SessionLocal)
    # A worker that died mid-run leaves exactly this behind: a job stuck in a working status.
    dead = {}
    for status in ("queued", "validating", "preprocessing", "running", "verifying", "evidence_created"):
        job_id = f"JOB-DEAD{status.upper()[:6]}"
        dead[status] = job_id
        repository.save({
            "job_id": job_id, "case_id": f"{case_id}-D", "body_region": "head", "clinical_question": None,
            "status": status, "tool_name": "ich_detection", "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:01+00:00", "started_at": "2026-01-01T00:00:00+00:00",
            "finished_at": None, "steps": [{"status": status, "at": "2026-01-01T00:00:01+00:00", "detail": None}],
            "timings_seconds": {}, "error": None, "note": None, "outcome": None,
        })

    service2, store2 = restart(services)
    for status, job_id in dead.items():
        job = service2.get(job_id)
        assert job.status == JobStatus.FAILED, status
        assert job.error == {"stage": status, "type": "RestartInterrupted", "message": RESTART_REASON}
        assert job.steps[0]["status"] == status and job.steps[-1]["status"] == "failed"  # history kept
        assert job.finished_at is not None
    assert service2.get(resting.job_id).status == JobStatus.REQUIRES_REVIEW  # untouched
    assert store2.recover_interrupted() == []  # idempotent


def test_failed_interrupted_job_does_not_block_a_new_analysis(services, store, case_id):
    JobRepository(SessionLocal).save({
        "job_id": "JOB-DEADRUNNING", "case_id": case_id, "body_region": "head", "clinical_question": None,
        "status": "running", "tool_name": "ich_detection", "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:01+00:00", "started_at": "2026-01-01T00:00:00+00:00",
        "finished_at": None, "steps": [], "timings_seconds": {}, "error": None, "note": None, "outcome": None,
    })
    service, _ = restart(services)
    assert run_to_rest(service, case_id).status == JobStatus.REQUIRES_REVIEW


# ------------------------------------------------------------------ configuration and resilience

def test_without_database_url_the_store_is_in_memory(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    memory = store_from_environment()
    assert type(memory) is JobStore
    assert memory.describe()["state_storage"] == "in-process memory (lost on restart)"


def test_runtime_status_reports_the_storage(services, store):
    service, _ = build(services, store)
    status = service.runtime_status()
    assert status["state_storage"].startswith("postgresql") and status["persistence_errors"] == 0


def test_a_database_failure_is_counted_and_does_not_kill_the_job(services, case_id):
    def broken():
        raise RuntimeError("database is down")

    flaky = PersistentJobStore(broken, create_schema=False)
    service, _ = build(services, flaky)
    job = run_to_rest(service, case_id)
    assert job.status == JobStatus.REQUIRES_REVIEW  # governance and the worker are unaffected
    assert flaky.persistence_errors > 0
    assert service.runtime_status()["persistence_errors"] == flaky.persistence_errors


def test_jobs_table_holds_no_image_data():
    assert {c.name for c in JobModel.__table__.columns} == {
        "job_id", "case_id", "body_region", "clinical_question", "status", "tool_name", "created_at",
        "updated_at", "started_at", "finished_at", "steps", "timings_seconds", "error", "note", "outcome",
        "result_json",
    }


# ------------------------------------------------------------------ HTTP

def test_http_flow_survives_a_restart(services, store, case_id):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from jobs.routes import build_job_router
    from tests.test_jobs import _validate_case_id

    def client_for(service):
        app = FastAPI()
        app.include_router(build_job_router(service, _validate_case_id))
        return TestClient(app)

    service, _ = build(services, store)
    client = client_for(service)
    created = client.post(f"/cases/{case_id}/analysis", json={"body_region": "head"})
    assert created.status_code == 202 and created.json()["status"] == "queued"
    job_id = created.json()["job_id"]
    wait_for(service, service.get(job_id), RESTING)
    service.shutdown()

    service2, _ = restart(services)
    client2 = client_for(service2)
    status = client2.get(f"/jobs/{job_id}")
    assert status.status_code == 200
    assert status.json()["status"] == "requires_review" and status.json()["restored_after_restart"] is True
    assert client2.get(f"/jobs/{job_id}/result").json()["human_review"]["status"] == "pending"
    refused = client2.post(f"/jobs/{job_id}/review", json={"reviewer_id": "reviewer-1", "decision": "accept"})
    assert refused.status_code == 409 and "Rerun" in refused.json()["detail"]
    assert [j["job_id"] for j in client2.get(f"/cases/{case_id}/jobs").json()["jobs"]] == [job_id]


# ------------------------------------------------------------------ the real model (only where the runtime exists)

def _real_runtime_available() -> bool:
    try:
        from jobs.execution import LocalToolAdapter

        return bool(LocalToolAdapter().runtime_status().get("available"))
    except Exception:
        return False


@pytest.mark.skipif(not _real_runtime_available(), reason="real ICH runtime (torch, skp, weights) not available here")
def test_real_ich_job_is_persisted_through_the_same_store(services, store, tmp_path):
    """Runs the REAL ICH tool on a synthetic phantom through PersistentJobStore. Slow (CPU model load + inference)."""
    import subprocess
    import sys
    from pathlib import Path

    from jobs.execution import LocalToolAdapter

    root = Path(__file__).resolve().parents[2]
    subprocess.run([sys.executable, str(root / "scripts/make_synthetic_ct.py"), str(tmp_path), "--slices", "24", "--size", "128"],
                   check=True, capture_output=True)
    files = sorted(tmp_path.glob("*.dcm"))
    service = AnalysisJobService(LocalToolAdapter(), lambda case_id: ("synthetic", files), store=store)
    services.append(service)
    job = service.submit(f"CASE-P-{uuid.uuid4().hex[:6].upper()}", "head")
    wait_for(service, job, RESTING, timeout=900)
    saved = row(job.job_id)
    assert saved["status"] in {"requires_review", "blocked"}
    assert saved["result_json"]["evidence"][0]["provenance"]["runtime"] == "local_in_process"
