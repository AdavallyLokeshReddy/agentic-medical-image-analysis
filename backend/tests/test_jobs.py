"""
Tests for the analysis job layer.

The tool used here is a TEST DOUBLE (FakeIchTool). It exists to exercise the governance chain
(authorization, verification, evidence, report, review) deterministically. It is not a model, its
numbers mean nothing, and passing these tests says nothing about model quality. The real model is
exercised by scripts/run_job_e2e.py on a machine that has the runtime and permitted data.
"""
from __future__ import annotations

import threading
import time
import unittest
from pathlib import Path

import numpy as np

from jobs.execution import LocalToolAdapter, ToolRuntimeUnavailable
from jobs.models import JobStatus
from jobs.service import AnalysisJobService, JobRejected
from tools.base import MedicalAITool
from tools.registry import ToolMetadata

SERIES_UID = "1.2.826.0.1.3680043.2.1125.1.1"


class FakeIchTool(MedicalAITool):
    name = "ich_detection"
    description = "TEST DOUBLE for the ICH tool. Not a model."

    def __init__(self, probability=0.82, status="completed", raises=None, gate=None):
        self.probability = probability
        self.status = status
        self.raises = raises
        self.gate = gate
        self.calls = 0

    def run(self, input_data):
        self.calls += 1
        if self.gate is not None:
            self.gate.wait(10)
        if self.raises is not None:
            raise self.raises
        assert isinstance(input_data["volume"], np.ndarray)
        return {
            "tool": self.name,
            "status": self.status,
            "prediction": {"any_probability": self.probability},
            "series": {
                "slice_count": int(input_data["volume"].shape[0]),
                "supporting_slices": {"subdural": [{"slice_index": 11, "probability": 0.7}, {"slice_index": 12, "probability": 0.6}]},
            },
            "input": {"units": "Hounsfield Units"},
            "evidence": {"model": "FAKE-TEST-TOOL", "model_version": "test", "device": "cpu"},
            "warnings": ["Test double output."],
        }


def metadata_provider(tool_name):
    return (
        "ich_detection",
        "TEST DOUBLE for the ICH tool. Not a model.",
        ToolMetadata(
            supported_modalities=["CT"],
            supported_body_regions=["head", "brain"],
            intended_use="Test only.",
            validation_population="None. Test double.",
            version="test",
        ),
    )


def make_service(tool=None, spacing=(1.0, 0.5, 0.5), modality="CT", loader_error=None, max_pending=3, required_modules=()):
    tool = tool or FakeIchTool()
    adapter = LocalToolAdapter(tool_factory=lambda: tool, metadata_provider=metadata_provider, required_modules=required_modules)

    def locator(case_id):
        return SERIES_UID, [Path(f"slice{i:03d}.dcm") for i in range(24)]

    def loader(paths):
        if loader_error is not None:
            raise loader_error
        return {"volume": np.zeros((len(paths), 8, 8), dtype=np.float32), "voxel_spacing": spacing}

    def header(path):
        return {"modality": modality, "study_uid": "1.2.3", "series_uid": SERIES_UID}

    service = AnalysisJobService(adapter, locator, series_loader=loader, header_reader=header, max_pending=max_pending)
    return service, tool


def wait_for(service, job, targets, timeout=10.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if job.status in targets:
            return job
        time.sleep(0.01)
    raise AssertionError(f"job stuck in {job.status.value}; wanted {[t.value for t in targets]}")


RESTING = {JobStatus.REQUIRES_REVIEW, JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.BLOCKED, JobStatus.ABSTAINED}


class JobPipelineTests(unittest.TestCase):
    def tearDown(self):
        getattr(self, "service", None) and self.service.shutdown()

    def run_job(self, **kwargs):
        self.service, self.tool = make_service(**kwargs)
        job = self.service.submit("CASE-0001", "head")
        return wait_for(self.service, job, RESTING)

    def test_clean_run_ends_in_human_review_not_in_a_diagnosis(self):
        job = self.run_job()
        self.assertEqual(job.status, JobStatus.REQUIRES_REVIEW)
        self.assertEqual(job.tool_name, "ich_detection")
        self.assertEqual(
            [s["status"] for s in job.steps],
            ["queued", "validating", "preprocessing", "running", "verifying", "evidence_created", "requires_review"],
        )
        self.assertEqual(job.outcome["verification_decision"], "verified_for_workflow_review")
        self.assertEqual(job.outcome["evidence_status"], "valid")
        self.assertEqual(job.outcome["human_review"], "pending")
        self.assertFalse(job.outcome["clinical_diagnosis"])
        result = self.service.result(job.job_id)
        self.assertIn("Not for clinical", result["notice"])
        self.assertEqual(result["human_review"]["status"], "pending")
        self.assertEqual(len(result["report"]["observations"]), 1)
        self.assertEqual(result["report"]["status"], "draft")
        self.assertTrue(result["report"]["human_review_required"])
        evidence = result["evidence"][0]
        self.assertEqual(evidence["provenance"]["tool_name"], "ich_detection")
        self.assertEqual(evidence["provenance"]["runtime"], "local_in_process")
        self.assertEqual(evidence["supporting_slices"], [11, 12])
        self.assertEqual(evidence["series_uid"], SERIES_UID)
        self.assertIn("unvalidated", evidence["claim"])
        self.assertEqual(result["safety_contract"]["operation_policy"]["maximum_action_tier"], "T1")
        statuses = {t["task_type"]: t["status"] for t in result["task_graph"]["tasks"]}
        self.assertEqual(statuses["ich_analysis"], "completed")
        self.assertEqual(statuses["verification"], "completed")
        self.assertNotEqual(statuses["human_review"], "completed")

    def test_coarse_slices_escalate_to_review_and_produce_no_observation(self):
        job = self.run_job(spacing=(5.0, 0.49, 0.49))
        self.assertEqual(job.status, JobStatus.REQUIRES_REVIEW)
        self.assertEqual(job.outcome["verification_decision"], "requires_review")
        self.assertEqual(job.outcome["evidence_status"], "requires_review")
        result = self.service.result(job.job_id)
        self.assertEqual(result["report"]["observations"], [])
        self.assertTrue(result["report"]["uncertainty"])

    def test_low_confidence_escalates(self):
        job = self.run_job(tool=FakeIchTool(probability=0.3))
        self.assertEqual(job.outcome["verification_decision"], "requires_review")

    def test_tool_that_did_not_complete_is_blocked_and_evidence_invalidated(self):
        job = self.run_job(tool=FakeIchTool(status="failed"))
        self.assertEqual(job.status, JobStatus.BLOCKED)
        self.assertEqual(job.outcome["evidence_status"], "invalid")
        self.assertEqual(job.outcome["report_status"], "blocked")
        result = self.service.result(job.job_id)
        self.assertEqual(result["report"]["observations"], [])
        with self.assertRaises(JobRejected) as ctx:
            self.service.review(job.job_id, reviewer_id="r1", decision="accept")
        self.assertEqual(ctx.exception.kind, "conflict")

    def test_runtime_failure_is_reported_as_failed_with_the_real_reason(self):
        job = self.run_job(tool=FakeIchTool(raises=ToolRuntimeUnavailable("weights could not be loaded")))
        self.assertEqual(job.status, JobStatus.FAILED)
        self.assertEqual(job.error["stage"], "running")
        self.assertEqual(job.error["type"], "ToolRuntimeUnavailable")
        self.assertIn("weights could not be loaded", job.error["message"])
        result = self.service.result(job.job_id)
        self.assertEqual(result["evidence"], [])
        self.assertEqual(result["case"]["status"], "failed")

    def test_series_rejected_by_technical_validation_is_blocked_and_the_tool_never_runs(self):
        job = self.run_job(loader_error=ValueError("series contains mixed UIDs"))
        self.assertEqual(job.status, JobStatus.BLOCKED)
        self.assertIn("technical validation", job.note)
        self.assertEqual(self.tool.calls, 0)

    def test_non_ct_series_abstains_without_running_any_tool(self):
        job = self.run_job(modality="MR")
        self.assertEqual(job.status, JobStatus.ABSTAINED)
        self.assertEqual(self.tool.calls, 0)

    def test_unsupported_body_region_abstains(self):
        self.service, self.tool = make_service()
        job = self.service.submit("CASE-0001", "chest")
        wait_for(self.service, job, RESTING)
        self.assertEqual(job.status, JobStatus.ABSTAINED)
        self.assertEqual(self.tool.calls, 0)


class SubmissionRuleTests(unittest.TestCase):
    def tearDown(self):
        getattr(self, "service", None) and self.service.shutdown()

    def test_unavailable_runtime_is_refused_up_front_and_creates_no_job(self):
        self.service, _ = make_service(required_modules=("a_module_that_does_not_exist_xyz",))
        with self.assertRaises(JobRejected) as ctx:
            self.service.submit("CASE-0001")
        self.assertEqual(ctx.exception.kind, "unavailable")
        self.assertEqual(self.service.list_for_case("CASE-0001"), [])

    def test_only_one_open_job_per_case_until_a_human_has_reviewed(self):
        self.service, _ = make_service()
        first = self.service.submit("CASE-0001")
        wait_for(self.service, first, RESTING)
        with self.assertRaises(JobRejected) as ctx:
            self.service.submit("CASE-0001")
        self.assertEqual(ctx.exception.kind, "conflict")
        self.service.review(first.job_id, reviewer_id="reviewer-1", decision="accept")
        second = self.service.submit("CASE-0001")
        wait_for(self.service, second, RESTING)
        self.assertEqual(len(self.service.list_for_case("CASE-0001")), 2)

    def test_full_queue_is_refused(self):
        gate = threading.Event()
        self.service, _ = make_service(tool=FakeIchTool(gate=gate), max_pending=1)
        first = self.service.submit("CASE-0001")
        with self.assertRaises(JobRejected) as ctx:
            self.service.submit("CASE-0002")
        self.assertEqual(ctx.exception.kind, "busy")
        gate.set()
        wait_for(self.service, first, RESTING)

    def test_a_tool_the_adapter_does_not_own_cannot_be_executed(self):
        self.service, _ = make_service()
        with self.assertRaises(PermissionError):
            self.service.adapter.execute("lung_nodule_detection", {"volume": np.zeros((2, 2, 2))})

    def test_status_reads_never_change_or_run_anything(self):
        self.service, tool = make_service()
        job = self.service.submit("CASE-0001")
        wait_for(self.service, job, RESTING)
        calls = tool.calls
        before = self.service.get(job.job_id).to_dict()
        for _ in range(5):
            self.service.get(job.job_id).to_dict()
            self.service.result(job.job_id)
        self.assertEqual(self.service.get(job.job_id).to_dict(), before)
        self.assertEqual(tool.calls, calls)

    def test_status_view_contains_no_model_output(self):
        self.service, _ = make_service()
        job = self.service.submit("CASE-0001")
        wait_for(self.service, job, RESTING)
        text = str(self.service.get(job.job_id).to_dict())
        self.assertNotIn("any_probability", text)
        self.assertNotIn("0.82", text)

    def test_result_is_refused_while_the_job_is_still_working(self):
        gate = threading.Event()
        self.service, _ = make_service(tool=FakeIchTool(gate=gate))
        job = self.service.submit("CASE-0001")
        with self.assertRaises(JobRejected) as ctx:
            self.service.result(job.job_id)
        self.assertEqual(ctx.exception.kind, "conflict")
        gate.set()
        wait_for(self.service, job, RESTING)


class HumanReviewTests(unittest.TestCase):
    def setUp(self):
        self.service, _ = make_service()
        self.job = self.service.submit("CASE-0001")
        wait_for(self.service, self.job, RESTING)

    def tearDown(self):
        self.service.shutdown()

    def test_accept_completes_the_job_and_the_case_and_records_the_reviewer(self):
        review = self.service.review(self.job.job_id, reviewer_id="reviewer-1", decision="accept", comments=["ok"])
        self.assertEqual(review["status"], "completed")
        self.assertEqual(review["decision"], "accept")
        self.assertEqual(review["reviewer_id"], "reviewer-1")
        self.assertEqual(review["reviewed_verification_ids"], ["verification_passed"])
        self.assertEqual(self.job.status, JobStatus.COMPLETED)
        result = self.service.result(self.job.job_id)
        self.assertEqual(result["case"]["status"], "completed")
        # The AI-generated report is preserved, not overwritten.
        self.assertEqual(len(result["report"]["observations"]), 1)

    def test_reject_and_modify_need_a_reason(self):
        for decision in ("reject", "modify"):
            with self.assertRaises(JobRejected) as ctx:
                self.service.review(self.job.job_id, reviewer_id="r1", decision=decision, modified_observations=[{"claim": "x"}])
            self.assertEqual(ctx.exception.kind, "invalid")
        self.assertEqual(self.job.status, JobStatus.REQUIRES_REVIEW)

    def test_reject_with_reason_is_recorded(self):
        review = self.service.review(self.job.job_id, reviewer_id="r1", decision="reject", reason="Series quality inadequate")
        self.assertEqual(review["decision"], "reject")
        self.assertEqual(review["intervention_reason"], "Series quality inadequate")

    def test_a_completed_review_cannot_be_changed(self):
        self.service.review(self.job.job_id, reviewer_id="r1", decision="accept")
        with self.assertRaises(JobRejected) as ctx:
            self.service.review(self.job.job_id, reviewer_id="r2", decision="reject", reason="changed my mind")
        self.assertEqual(ctx.exception.kind, "conflict")

    def test_blank_reviewer_is_refused_and_leaves_the_review_pending(self):
        with self.assertRaises(JobRejected) as ctx:
            self.service.review(self.job.job_id, reviewer_id="  ", decision="accept")
        self.assertEqual(ctx.exception.kind, "invalid")
        self.assertEqual(self.job.status, JobStatus.REQUIRES_REVIEW)
        self.assertEqual(self.job.artifacts.review.status.value, "pending")

    def test_unknown_decision_is_refused(self):
        with self.assertRaises(JobRejected):
            self.service.review(self.job.job_id, reviewer_id="r1", decision="approve-everything")


try:  # HTTP-level tests need fastapi + httpx (present in CI and in the project's venv)
    from fastapi import FastAPI, HTTPException
    from fastapi.testclient import TestClient

    from jobs.routes import build_job_router

    HAVE_HTTP = True
except Exception:  # pragma: no cover
    HAVE_HTTP = False


def _validate_case_id(case_id):
    import re

    if not re.fullmatch(r"[A-Za-z0-9_-]+", case_id):
        raise HTTPException(status_code=400, detail="Invalid case_id.")


@unittest.skipUnless(HAVE_HTTP, "fastapi/httpx not installed")
class JobRouteTests(unittest.TestCase):
    def setUp(self):
        self.service, self.tool = make_service()
        app = FastAPI()
        app.include_router(build_job_router(self.service, _validate_case_id))
        self.client = TestClient(app)

    def tearDown(self):
        self.service.shutdown()

    def wait(self, job_id):
        deadline = time.time() + 10
        while time.time() < deadline:
            status = self.client.get(f"/jobs/{job_id}").json()["status"]
            if status in {s.value for s in RESTING}:
                return status
            time.sleep(0.02)
        raise AssertionError("job did not settle")

    def test_full_http_flow_to_a_recorded_human_review(self):
        created = self.client.post("/cases/CASE-0001/analysis", json={"body_region": "head"})
        self.assertEqual(created.status_code, 202)
        body = created.json()
        self.assertEqual(body["status"], "queued")
        self.assertEqual(created.headers["location"], f"/jobs/{body['job_id']}")
        self.assertEqual(self.wait(body["job_id"]), "requires_review")
        result = self.client.get(f"/jobs/{body['job_id']}/result")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["human_review"]["status"], "pending")
        review = self.client.post(f"/jobs/{body['job_id']}/review", json={"reviewer_id": "reviewer-1", "decision": "accept"})
        self.assertEqual(review.status_code, 200)
        self.assertEqual(self.client.get(f"/jobs/{body['job_id']}").json()["status"], "completed")

    def test_empty_body_uses_defaults(self):
        self.assertEqual(self.client.post("/cases/CASE-0002/analysis").status_code, 202)

    def test_hostile_case_ids_are_refused(self):
        for bad in ("..%2F..%2Fetc", "CASE;DROP", "CASE 1"):
            self.assertIn(self.client.post(f"/cases/{bad}/analysis").status_code, (400, 404, 422))
        self.assertEqual(self.tool.calls, 0)

    def test_malformed_job_ids_do_not_reach_the_service(self):
        for bad in ("JOB-ZZZ", "../x", "job-aaaaaaaaaaaa"):
            self.assertIn(self.client.get(f"/jobs/{bad}").status_code, (404, 422))
        self.assertEqual(self.client.get("/jobs/JOB-AAAAAAAAAAAA").status_code, 404)

    def test_bad_request_bodies_are_refused(self):
        self.assertEqual(self.client.post("/cases/CASE-0003/analysis", json={"body_region": "head; rm -rf"}).status_code, 422)
        self.assertEqual(self.client.post("/cases/CASE-0003/analysis", json={"clinical_question": "x" * 301}).status_code, 422)
        job = self.client.post("/cases/CASE-0004/analysis").json()["job_id"]
        self.wait(job)
        self.assertEqual(self.client.post(f"/jobs/{job}/review", json={"reviewer_id": "r", "decision": "delete"}).status_code, 422)
        self.assertEqual(self.client.post(f"/jobs/{job}/review", json={"reviewer_id": "bad/../id", "decision": "accept"}).status_code, 422)

    def test_unavailable_runtime_is_503(self):
        service, _ = make_service(required_modules=("a_module_that_does_not_exist_xyz",))
        app = FastAPI()
        app.include_router(build_job_router(service, _validate_case_id))
        self.assertEqual(TestClient(app).post("/cases/CASE-0001/analysis").status_code, 503)
        service.shutdown()

    def test_busy_queue_is_429_with_retry_after(self):
        gate = threading.Event()
        service, _ = make_service(tool=FakeIchTool(gate=gate), max_pending=1)
        app = FastAPI()
        app.include_router(build_job_router(service, _validate_case_id))
        client = TestClient(app)
        self.assertEqual(client.post("/cases/CASE-0001/analysis").status_code, 202)
        busy = client.post("/cases/CASE-0002/analysis")
        self.assertEqual(busy.status_code, 429)
        self.assertEqual(busy.headers["retry-after"], "30")
        gate.set()
        service.shutdown()


if __name__ == "__main__":
    unittest.main()
