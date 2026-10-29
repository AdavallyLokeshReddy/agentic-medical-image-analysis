# Online runtime: audit and Stage 1 container

Research & Engineering Prototype - Not for clinical diagnosis or treatment.

## Phase 0 audit (what exists today, verified by reading the code)

| Area | Status | Evidence |
|---|---|---|
| HTTP API: create case, DICOM upload, series validation, preview | IMPLEMENTED | `backend/main.py` (v0.5.0) |
| Case storage | PARTIAL: folders under `backend/uploads/<case_id>` on local disk. Lost on restart/redeploy on every free host | `UPLOAD_DIR` in `main.py`; no database use in `main.py` |
| `/governance/status`, `/plan`, `/tools`, `/cases/{id}/audit` | IMPLEMENTED (planning and read-only). Plans never execute a tool | `backend/governance_api.py` |
| Orchestrator, Safety Contract, Task Graph, verifier, evidence, review lifecycle, structured report, triage, communication | IMPLEMENTED as a library, covered by tests. **No HTTP route calls them** | grep: `verify_analysis`, `ReviewLifecycle`, `create_structured_draft_report` are not referenced by `main.py` or `governance_api.py` |
| Model execution over HTTP (`tool.run`) | IMPLEMENTED in Phase 2 as an asynchronous job (see below); NOT yet run against the real model by the author | `backend/jobs/` |
| PostgreSQL persistence (`backend/database/*`) | IMPLEMENTED as a library; HTTP writes nothing to it | audit read is the only DB use in the API |
| ICH tool (`ich_detection`) | IMPLEMENTED; ran on a laptop CPU in ~27 s for 40x512x512 | `scripts/run_real_pipeline.py` real run |
| Other CT tools, MRI-1 | Registered and have tests; only ICH has a demonstrated end-to-end CT run | `backend/tools/*` |
| Container | Did not exist before this change | none |

### Findings that affect the deployment

1. **`skp` is an undocumented external dependency.** `backend/model_runtime/inference.py` imports `skp.configs`, `skp.models.*` and `skp.toolbox.dicom`. It is not in `requirements.txt`, not on PyPI, and the README only says it is external. The image cannot be built until its source is known. It is a required build argument (`SKP_SOURCE`); the build fails with a clear message without it.
2. **`timm` was missing from `requirements.txt`.** The model backbone is `maxvit_tiny_tf_512.in1k`. Added in `requirements-runtime.txt`.
3. **Weights licence.** The model card for `ianpan/ct-head-hemorrhage-detection` declares MIT, and states it is research software, not a medical device, not validated for clinical use, and must not be used to diagnose, exclude, triage or manage hemorrhage. Baking the weights into an image is permitted by that licence; the restrictions above must stay in the UI and reports. The licence of `skp` itself has **not** been checked yet.
4. **Weights are fetched from the `main` revision.** `HemorrhageSliceModel` does not pin a revision. `scripts/prefetch_weights.py` records the resolved commit and file hashes in `model_manifest.json` so a build can be traced; pinning the revision in the tool is a Phase 2 change.
5. **Local Python is 3.13; the image uses 3.12.** Versions were not pinned anywhere. The image uses ranges until a known-good build produces `requirements-lock.txt`.

## Phase 1: the container

Files: `Dockerfile`, `docker/entrypoint.sh`, `.dockerignore`, `requirements-runtime.txt`, `scripts/check_runtime.py`, `scripts/prefetch_weights.py`, `.github/workflows/docker.yml`.

What the image contains: FastAPI backend and all governance code, CPU PyTorch, MONAI, timm, `skp` (from `SKP_SOURCE`), DICOM/NIfTI libraries, and (optionally) the ICH weights with a provenance manifest. Runs as a non-root user, one worker, `/health` healthcheck, `PORT` aware.

### Build and run

```bash
docker build -t agentic-medical-runtime \
  --build-arg SKP_SOURCE="<public pip source of skp>" \
  --build-arg PREFETCH_WEIGHTS=1 .

docker run --rm -p 8080:8080 -e CORS_ORIGINS=http://localhost:3000 agentic-medical-runtime
# in another terminal
curl http://localhost:8080/health
curl http://localhost:8080/governance/status      # torch_installed / monai_installed / skp_installed should be true
docker exec <container> python /app/scripts/check_runtime.py --smoke --out /tmp/smoke.json
```

`--smoke` runs the model once on a **synthetic phantom** and records load time, inference time and peak memory. The phantom output is not a finding.

### Build without Docker on your machine

Set the repository variable `SKP_SOURCE`, then run the **Runtime image** workflow (Actions tab, "Run workflow"; tick the weights box for the model smoke test). It builds the image, starts it, checks `/health` and `/governance/status`, and uploads `runtime_smoke.json` and `model_manifest.json`.

### Not yet true (do not claim)

- The HTTP API still does not run the model, verify, create evidence, review or report. Those are Phases 2 and 5-10.
- Uploads are still on ephemeral disk. Persistence is Phases 3 and 4.
- The image has not been built or started by the author of this change (no Docker daemon or package registry in the authoring sandbox). The CI workflow is the first real build.


## Phase 2: governed analysis jobs (`backend/jobs/`)

Status: IMPLEMENTED and unit-tested with a **test double** for the tool. The real ICH model has **not** been executed through this layer by the author (no `skp`, torch or data in the authoring sandbox). That first real run is `scripts/run_job_e2e.py` on a machine that has the runtime.

### Routes

| Route | Purpose |
|---|---|
| `POST /cases/{case_id}/analysis` | Create a job. Returns `202` with a job id. Body optional: `body_region` (default `head`), `clinical_question`. |
| `GET /jobs/{job_id}` | Status only. Never starts or advances anything. Contains no model output. |
| `GET /jobs/{job_id}/result` | Verification, evidence with provenance, safety contract, task graph, draft report, human-review state. `409` while the worker is still busy. |
| `POST /jobs/{job_id}/review` | Record `accept`, `modify` or `reject` (`reason` required for the last two). |
| `GET /cases/{case_id}/jobs` | Jobs for a case. |

Refusals: `503` model runtime not installed (reason given), `409` case has no series, or a job is already open for the case, `429` queue full, `404` unknown case or job, `400`/`422` malformed input.

### Execution path (what actually runs, in order)

1. Route validates the case id and request body, and refuses if the runtime is missing (`LocalToolAdapter.runtime_status`, no model is loaded for this check).
2. `validating`: `CaseState` is built from the DICOM header; `AgentOrchestrator.plan` creates the Safety Contract and task graph; the tool must be discovered by the orchestrator, executable by the adapter, **and** approved by the contract (`select_tool`). Otherwise the job **abstains** and nothing runs.
3. `preprocessing`: `preprocess_ct_series` (the existing DICOM validation, sorting, HU conversion, spacing). A rejected series makes the job **blocked**, and the tool never runs.
4. `running`: `adapter.execute("ich_detection", {"volume": ...})`. The adapter loads the real `ICHDetectionTool` on first use. If torch, `skp` or the weights are unavailable the job **fails** with that exact reason.
5. `verifying`: `AgentOrchestrator.verify_analysis` (the existing `ICHVerificationEngine`).
6. `evidence_created`: an `EvidenceItem` with provenance is added to the case and marked valid / requires_review / invalid from the verifier decision; `create_structured_draft_report` builds the report; a pending `HumanReview` is attached.
7. The job rests in `requires_review` (or `blocked` when verification blocked the result). It becomes `completed` only when a human review decision is recorded.

Job statuses: `queued, validating, preprocessing, running, verifying, evidence_created, requires_review, completed, failed, blocked, abstained`.

### What this layer deliberately does not do yet

- **Job and case state live in process memory.** A restart loses them. PostgreSQL and object storage are Phases 3 and 4.
- **The reviewer id is a self-asserted label.** There is no authentication.
- **No per-job time limit is enforced** (the contract's resource policy is not yet applied to execution).
- **One worker thread, one tool.** The model runs one case at a time. Only `ich_detection` is executable.
- **The model loads on the first job.** Cold-start time is unmeasured.
- A `completed` job means a human decision was recorded, not that anything was clinically confirmed.

### Moving the model later

`ExecutionAdapter` is the only place that knows where a tool runs. A remote-worker adapter implementing `execute()` replaces `LocalToolAdapter`; the service, routes, governance code and frontend do not change.

### First real run (on a machine with the runtime and permitted data)

```
cd backend && uvicorn main:app --port 8000
# second terminal, repo root:
python scripts/run_job_e2e.py "C:\path\to\one_series_folder" --review accept --reviewer reviewer-1
```
