"""
Run a REAL CT series (a folder of DICOM files) through the governed pipeline, locally.

    preprocessing -> orchestrator plan -> model tool -> verifier -> evidence -> report

Honest behaviour:
  * If the research model cannot be loaded (torch, the external `skp` code, or the weights are
    missing) the script says so, stops before the model step, and still writes a report that is
    BLOCKED because there is no evidence. It never invents a prediction.
  * Evidence becomes VALID only when the verifier says so. Human review stays pending.
  * Results are written to JSON next to a preview PNG. Nothing is uploaded anywhere.

Usage (from the repository root):
    python scripts/run_real_pipeline.py PATH_TO_DICOM_FOLDER [--case-id CASE-REAL-1]
                                         [--body-region head] [--out out_real] [--skip-model]

Requires: numpy, pydicom, pillow.  The model step also needs torch, skp and the model weights
(see README: "Optional: head CT hemorrhage model"). Use only data you are permitted to use, and
keep patient data off shared machines.
"""
import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))


def say(text=""):
    print(text, flush=True)


def heading(text):
    say("\n" + "=" * 74)
    say(text)
    say("=" * 74)


def find_dicom_files(folder: Path):
    files = sorted(p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() == ".dcm")
    if not files:  # some datasets ship DICOM without an extension
        files = sorted(p for p in folder.rglob("*") if p.is_file() and not p.name.startswith("."))
    return files


def save_preview(volume, out_dir: Path):
    try:
        import numpy as np
        from PIL import Image
    except ImportError:
        return None
    middle = volume[volume.shape[0] // 2]
    lower, upper = 0.0, 80.0  # brain window: centre 40 HU, width 80 HU
    image = ((np.clip(middle, lower, upper) - lower) / (upper - lower) * 255).astype(np.uint8)
    path = out_dir / "preview_middle_slice.png"
    Image.fromarray(image).save(path)
    return path


def try_load_model_tool():
    """Returns (tool, None) or (None, reason). Never raises."""
    try:
        from tools.ich_detection import ICHDetectionTool
    except Exception as error:  # torch missing, etc.
        return None, f"could not import the ICH tool: {type(error).__name__}: {error}"
    try:
        return ICHDetectionTool(), None
    except Exception as error:  # skp or weights missing
        return None, f"could not load the research model: {type(error).__name__}: {error}"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("dicom_dir")
    parser.add_argument("--case-id", default="CASE-REAL-1")
    parser.add_argument("--body-region", default="head")
    parser.add_argument("--out", default="out_real")
    parser.add_argument("--skip-model", action="store_true", help="stop before the model step")
    args = parser.parse_args()

    folder = Path(args.dicom_dir)
    if not folder.is_dir():
        sys.exit(f"Not a folder: {folder}")
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        from agent.case_state import (
            CaseModality, CaseState, EvidenceItem, EvidenceProvenance, VerificationStatus,
        )
        from agent.orchestrator import AgentOrchestrator
        from preprocessing.ct_preprocessing import preprocess_ct_series
        from reporting.structured_report import create_structured_draft_report
        from tools.base import MedicalAITool
        from tools.registry import ToolMetadata, ToolRegistry
    except ImportError as error:
        sys.exit(f"Missing dependency: {error}\nInstall with: pip install numpy pydicom pillow")

    record = {"case_id": args.case_id, "synthetic": False, "steps": {}}

    # ---- 1. real preprocessing ------------------------------------------------------------
    heading("1. PREPROCESSING (real DICOM series)")
    files = find_dicom_files(folder)
    say(f"  files found      : {len(files)} in {folder}")
    started = time.perf_counter()
    try:
        processed = preprocess_ct_series([str(p) for p in files])
    except Exception as error:
        sys.exit(f"  Preprocessing failed (the series was rejected): {error}")
    volume = processed["volume"]
    spacing = [float(v) for v in processed["voxel_spacing"]]
    first = processed["datasets"][0]
    uids = {
        "study_instance_uid": str(getattr(first, "StudyInstanceUID", "")),
        "series_instance_uid": str(getattr(first, "SeriesInstanceUID", "")),
    }
    stats = {
        "volume_shape": list(volume.shape),
        "voxel_spacing_mm": spacing,
        "hu_min": float(volume.min()),
        "hu_max": float(volume.max()),
        "hu_mean": float(volume.mean()),
        "seconds": round(time.perf_counter() - started, 2),
    }
    say(f"  volume shape     : {stats['volume_shape']} (slices, rows, columns)")
    say(f"  voxel spacing    : {spacing} mm (slice, row, column)")
    say(f"  HU range         : {stats['hu_min']:.0f} to {stats['hu_max']:.0f} (mean {stats['hu_mean']:.1f})")
    say(f"  time             : {stats['seconds']} s")
    preview = save_preview(volume, out_dir)
    if preview:
        say(f"  preview image    : {preview}")
    record["steps"]["preprocessing"] = stats

    # ---- 2. governed plan ------------------------------------------------------------------
    heading("2. GOVERNED PLAN (orchestrator, safety contract, task graph)")
    tool, reason = (None, "skipped by --skip-model") if args.skip_model else try_load_model_tool()

    class PlanningStub(MedicalAITool):
        name = "ich_detection"
        description = "Registered ICH detection tool (planning only if the model is unavailable)."

        def run(self, input_data):
            raise RuntimeError("planning stub: no model executed")

    registry = ToolRegistry()
    registry.register(
        tool if tool is not None else PlanningStub(),
        ToolMetadata(
            supported_modalities=["CT"],
            supported_body_regions=["head", "brain"],
            intended_use="Research/demo detection of suspected intracranial hemorrhage.",
            validation_population="Research/demo use only. Clinical validation not established.",
            exclusions=["Not a clinical diagnosis.", "Not for autonomous decisions."],
            version="research-model",
        ),
    )
    case = CaseState(
        case_id=args.case_id,
        modality=CaseModality.CT,
        body_region=args.body_region,
        clinical_question="Research demonstration on a real series: workflow governance",
    )
    case.metadata.update(
        {"slice_count": int(volume.shape[0]), "voxel_spacing": spacing, **uids}
    )
    orchestrator = AgentOrchestrator(registry)
    plan = orchestrator.plan(case)
    orchestrator.select_tool(case, "ich_detection")
    contract = plan["safety_contract"]
    say(f"  tasks            : {[t['task_type'] for t in plan['task_graph']['tasks']]}")
    say(f"  allowed ops      : {contract['operation_policy']['allowed_operations']}")
    say(f"  max action tier  : {contract['operation_policy']['maximum_action_tier']}")
    say(f"  execution started: {plan['execution_started']} (planning never executes a tool)")
    record["steps"]["plan"] = {"tasks": [t["task_type"] for t in plan["task_graph"]["tasks"]]}

    # ---- 3. model ----------------------------------------------------------------------------
    heading("3. MODEL RUNTIME")
    if tool is None:
        say(f"  MODEL NOT RUN: {reason}")
        say("  No prediction exists, so no evidence will be created. This is reported, not hidden.")
        record["steps"]["model"] = {"ran": False, "reason": reason}
        result = None
    else:
        say("  running the registered research model on the real volume ...")
        started = time.perf_counter()
        try:
            result = tool.run({"volume": volume})
        except Exception as error:
            result = None
            say(f"  MODEL RUN FAILED: {type(error).__name__}: {error}")
            record["steps"]["model"] = {"ran": False, "reason": f"run failed: {error}"}
        else:
            seconds = round(time.perf_counter() - started, 2)
            probability = result.get("prediction", {}).get("any_probability")
            say(f"  status           : {result.get('status')}  ({seconds} s)")
            say(f"  any-hemorrhage probability (research model, unvalidated): {probability}")
            record["steps"]["model"] = {
                "ran": True,
                "seconds": seconds,
                "status": result.get("status"),
                "prediction": result.get("prediction"),
            }

    # ---- 4. verification and evidence --------------------------------------------------------
    heading("4. VERIFICATION AND EVIDENCE")
    if result is None:
        say("  nothing to verify: no model output")
    else:
        outcome = orchestrator.verify_analysis(case, result)
        decision = outcome["verification_result"]["decision"]
        for name, check in outcome["verification_result"]["verification"]["checks"].items():
            say(f"    {check['status']:<8} {name}")
        say(f"  decision         : {decision['status']} -> {decision['action']}")
        say(f"  case status      : {outcome['case_status']}")
        evidence = EvidenceItem(
            evidence_id=f"{args.case_id}-EV-1",
            case_id=args.case_id,
            evidence_type="model_output",
            source="ich_detection",
            claim=(
                "Research-model any-hemorrhage probability "
                f"{result.get('prediction', {}).get('any_probability')} (unvalidated, not a diagnosis)"
            ),
            confidence=result.get("prediction", {}).get("any_probability"),
            supporting_slices=list(result.get("series", {}).get("supporting_slices") or []),
            provenance=EvidenceProvenance(tool_name="ich_detection", runtime="local research runtime"),
        )
        case.add_evidence(evidence)
        if decision["status"] == "verified_for_workflow_review":
            evidence.mark_valid("verification_passed")
        elif decision["status"] == "requires_review":
            evidence.mark_requires_review("verification_requires_review")
        else:
            evidence.invalidate("verifier blocked this result")
        say(f"  evidence status  : {evidence.status.value}")
        record["steps"]["verification"] = {
            "decision": decision,
            "case_verification_status": outcome["case_verification_status"],
            "evidence_status": evidence.status.value,
        }
        if case.verification.status == VerificationStatus.FAILED:
            say("  verification FAILED: this result would not enter the report as an observation")

    # ---- 5. report ---------------------------------------------------------------------------
    heading("5. STRUCTURED REPORT (governed)")
    report = create_structured_draft_report(case, f"{args.case_id}-REP-1")
    say(f"  report status    : {report.status.value}")
    say(f"  observations     : {len(report.observations)}")
    say(f"  uncertainty      : {report.uncertainty}")
    say(f"  human review     : REQUIRED and still PENDING (no reviewer has acted)")
    record["steps"]["report"] = report.to_dict()

    out_json = out_dir / f"{args.case_id}_pipeline_result.json"
    out_json.write_text(json.dumps(record, indent=2, default=str))
    heading("DONE")
    say(f"  written: {out_json}")
    say("  Research & Engineering Prototype - Not for clinical diagnosis or treatment.")


if __name__ == "__main__":
    main()
