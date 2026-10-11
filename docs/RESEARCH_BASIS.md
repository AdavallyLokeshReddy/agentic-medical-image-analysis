# Research basis

This project is the working prototype behind the paper **"Agentic AI for Autonomous Medical Image Analysis and Clinical Workflow Management"** (G. Hariharan, B. Sai Jitesh, A. Anirudh, A. Lokesh Reddy), accepted for presentation at the *2026 IEEE 4th International Conference on Communication, Security, and Artificial Intelligence* (ICCSAI 2026, Galgotias University, 28-30 November 2026). The camera-ready version is still being prepared, so the paper is not yet published.

The paper is a **design proposal**. It states that it has not been implemented in a live hospital and is not a report of a clinical trial. This repository implements parts of that design as a research prototype. It is not a clinically validated medical device.

## Paper idea to code

Status uses only what was checked in the code and tests (`python -m pytest`). "Implemented" means code exists and its tests pass. It does not mean clinically validated.

| Paper idea | Where in this repo | Status |
| --- | --- | --- |
| Autonomy levels L0-L3 (observe, recommend, reversible action, controlled execution) | `ActionTier` T0-T3 and `SafetyContract` in `backend/agent/safety_contract.py` | Implemented as tiers and policy checks. The paper's measurable promotion gates (per-action thresholds, demotion on drift) are not implemented. |
| Planner builds a bounded task graph | `backend/agent/task_graph.py`, `orchestrator.py` | Implemented |
| Case state and temporary per-case memory | `backend/agent/case_state.py` | Implemented. Durable memory with reviewed corrections: not implemented. |
| Registry of tools with intended use and version | `backend/tools/registry.py`, `register_tools.py` (`ToolMetadata`) | Implemented. Validated population and calibration record are not tracked. |
| Evidence objects with provenance | `EvidenceItem`, `EvidenceProvenance` in `case_state.py` | Implemented |
| Separate verifier with deterministic checks | `backend/verification/` (CT-2 to CT-5, MRI-1) | Implemented for the CT checks; weights and imaging data are not in the repo, so the model-backed paths were not run in CI |
| Abstention when evidence is missing or verification fails | `UncertaintyPolicy` in `safety_contract.py` | Implemented. The thresholds are prototype configuration values, not clinically validated. |
| Human review and escalation | `agent/human_review.py`, `review_lifecycle.py` | Implemented |
| Structured report draft | `backend/reporting/structured_report.py` | Implemented |
| Audit trail and persistence | `backend/database/` (PostgreSQL), `audit.py`, `case_audit.py` | Implemented. Tests pass against a real PostgreSQL server. |
| Head-CT hemorrhage detector as the example pathway | `backend/tools/ich_detection.py`, `model_runtime/inference.py` | Partial. Needs the external `skp` code and weights, which are not in the repo. |
| Utility-risk action scoring (paper Eq. 2) | none | Not implemented |
| Calibrated outputs, ECE, risk-coverage reporting | none | Not implemented |
| Prior-study retrieval and interval change | none | Not implemented |
| Midline shift and volume tools | none | Not implemented |
| DICOMweb, FHIR/HL7 adapters | none | Not implemented (DICOM files are read locally) |
| Retrieval-grounded verification, language-model verifier | none | Not implemented |
| Prompt-injection and memory-poisoning defences | none | Not implemented |
| Staged validation (retrospective, external, silent prospective, clinician comparison) | none | Proposed in the paper only. No evaluation has been run. |

## Using the paper as the roadmap

The "Not implemented" rows are the next work, in this order:

1. Run the head-CT pathway end to end on public data and report component metrics with confidence intervals (paper Stage 1).
2. Add calibration and a risk-coverage report for the verifier.
3. Turn the T0-T3 tiers into the paper's measurable per-action gates, with demotion on failure.
4. Add midline-shift and volume tools, then prior-study comparison.

Nothing above should be described as done until it has a test and a result.
