import sys
from pathlib import Path


# ============================================================
# PROJECT PATH
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================
# IMPORTS
# ============================================================

from tools.register_tools import register_default_tools
from tools.registry import tool_registry
from verification.mri1_verification import MRI1VerificationEngine


# ============================================================
# REAL MRI-1 TEST CASE
# ============================================================

CASE_DIR = (
    PROJECT_ROOT
    / "data"
    / "mri"
    / "brats2023-gli"
    / "BraTS-GLI-00000-000"
    / "ASNR-MICCAI-BraTS2023-GLI-Challenge-TrainingData"
    / "BraTS-GLI-00000-000"
)


# ============================================================
# MAIN REGRESSION TEST
# ============================================================

def main():

    print()
    print("=== MRI-1 STEP 16: REGRESSION TEST ===")
    print("=" * 60)

    # --------------------------------------------------------
    # 1. TOOL REGISTRY
    # --------------------------------------------------------

    print()
    print("1. TOOL REGISTRY")

    # register_tools.py registers the default tools during
    # import. Do NOT call register_default_tools() again here.
    tool_names = {
        tool["name"]
        for tool in tool_registry.list_tools()
    }

    assert "brain_tumor_segmentation" in tool_names, (
        "brain_tumor_segmentation is not registered."
    )

    print(" - brain_tumor_segmentation: REGISTERED")
    print("Tool Registry regression: PASS")

    # --------------------------------------------------------
    # 2. REAL MRI INPUTS
    # --------------------------------------------------------

    print()
    print("2. REAL MRI INPUTS")

    sequence_files = {
        "T1c": (
            CASE_DIR
            / "BraTS-GLI-00000-000-t1c.nii.gz"
        ),
        "T1": (
            CASE_DIR
            / "BraTS-GLI-00000-000-t1n.nii.gz"
        ),
        "T2": (
            CASE_DIR
            / "BraTS-GLI-00000-000-t2w.nii.gz"
        ),
        "FLAIR": (
            CASE_DIR
            / "BraTS-GLI-00000-000-t2f.nii.gz"
        ),
    }

    for sequence, path in sequence_files.items():

        assert path.exists(), (
            f"Missing MRI sequence: "
            f"{sequence} -> {path}"
        )

        print(f" - {sequence}: OK")

    print("MRI input regression: PASS")

    # --------------------------------------------------------
    # 3. MRI-1 EXECUTION
    # --------------------------------------------------------

    print()
    print("3. MRI-1 EXECUTION")

    tool = tool_registry.get(
        "brain_tumor_segmentation"
    )

    assert tool is not None, (
        "brain_tumor_segmentation tool "
        "could not be retrieved."
    )

    input_data = {
        sequence: str(path)
        for sequence, path in sequence_files.items()
    }

    input_data["case_id"] = (
        "BraTS-GLI-00000-000"
    )

    output = tool.run(input_data)

    # Tool identity
    assert (
        output["tool"]
        == "brain_tumor_segmentation"
    )

    assert (
        output["tool_version"]
        == "research-demo-1.0"
    )

    # Model identity
    assert (
        output["model"]
        == "MONAI BraTS MRI segmentation"
    )

    assert (
        output["model_version"]
        == "0.5.4"
    )

    print(" - tool identity: OK")
    print(" - model identity: OK")
    print(" - execution: OK")
    print("MRI-1 execution regression: PASS")

    # --------------------------------------------------------
    # 4. OUTPUT CONTRACT
    # --------------------------------------------------------

    print()
    print("4. OUTPUT CONTRACT")

    required_keys = {
        "case_id",
        "modality",
        "body_region",
        "input_sequences",
        "input_shape",
        "prediction_shape",
        "probabilities",
        "masks",
        "label_summary",
        "voxel_spacing",
        "model_input_spacing",
        "runtime",
        "tool",
        "tool_version",
        "model",
        "model_version",
        "verification_required",
        "clinical_use",
        "warnings",
        "provenance",
    }

    missing = (
        required_keys
        - set(output.keys())
    )

    assert not missing, (
        f"Missing output keys: "
        f"{sorted(missing)}"
    )

    # Modality
    assert output["modality"] == "MRI"

    # Body region
    assert output["body_region"] == "brain"

    # Shapes
    assert (
        output["input_shape"]
        == (240, 240, 155)
    )

    assert (
        output["prediction_shape"]
        == (240, 240, 155)
    )

    # Segmentation regions
    expected_regions = (
        "tumor_core",
        "whole_tumor",
        "enhancing_tumor",
    )

    for region in expected_regions:

        assert region in output["masks"], (
            f"Missing mask output: {region}"
        )

        assert region in output["probabilities"], (
            f"Missing probability output: {region}"
        )

        assert region in output["label_summary"], (
            f"Missing label summary: {region}"
        )

    # Runtime metadata
    assert isinstance(
        output["runtime"],
        dict
    )

    assert (
        output["runtime"]["device"]
        == "cpu"
    )

    assert (
        output["runtime"]["framework"]
        == "PyTorch"
    )

    assert (
        output["runtime"]["architecture"]
        == "SegResNet"
    )

    assert (
        output["runtime"]["inferer"]
        == "SlidingWindowInferer"
    )

    print(" - required output schema: OK")
    print(" - prediction shape: OK")
    print(" - segmentation regions: OK")
    print(" - runtime metadata: OK")
    print("Output contract regression: PASS")

    # --------------------------------------------------------
    # 5. MRI-1 VERIFICATION
    # --------------------------------------------------------

    print()
    print("5. MRI-1 VERIFICATION")

    verifier = MRI1VerificationEngine()

    # --------------------------------------------------------
    # IMPORTANT:
    #
    # output["voxel_spacing"] is a dictionary:
    #
    # {
    #     "T1c": (1.0, 1.0, 1.0),
    #     "T1": (1.0, 1.0, 1.0),
    #     "T2": (1.0, 1.0, 1.0),
    #     "FLAIR": (1.0, 1.0, 1.0),
    # }
    #
    # The verifier expects each sequence's "spacing"
    # to be the individual tuple, NOT the whole dictionary.
    # --------------------------------------------------------

    mri_metadata = {
        "modality": "MRI",

        "body_region": "brain",

        "sequences": {

            "T1c": {
                "shape": output["input_shape"],
                "spacing": (
                    output["voxel_spacing"]["T1c"]
                ),
            },

            "T1": {
                "shape": output["input_shape"],
                "spacing": (
                    output["voxel_spacing"]["T1"]
                ),
            },

            "T2": {
                "shape": output["input_shape"],
                "spacing": (
                    output["voxel_spacing"]["T2"]
                ),
            },

            "FLAIR": {
                "shape": output["input_shape"],
                "spacing": (
                    output["voxel_spacing"]["FLAIR"]
                ),
            },
        },
    }

    print(
        " - MRI metadata sequence structure: OK"
    )

    print(
        " - T1c spacing:",
        output["voxel_spacing"]["T1c"]
    )

    print(
        " - T1 spacing:",
        output["voxel_spacing"]["T1"]
    )

    print(
        " - T2 spacing:",
        output["voxel_spacing"]["T2"]
    )

    print(
        " - FLAIR spacing:",
        output["voxel_spacing"]["FLAIR"]
    )

    verification = verifier.verify(
        {
            "mri_metadata": mri_metadata,
            "segmentation_result": output,
        }
    )

    print()
    print("VERIFIER OUTPUT:")

    print(
        f" - verified: "
        f"{verification.get('verified')}"
    )

    print(
        f" - decision: "
        f"{verification.get('decision')}"
    )

    print(
        f" - next_action: "
        f"{verification.get('next_action')}"
    )

    print(
        f" - human_review_required: "
        f"{verification.get('human_review_required')}"
    )

    print(
        f" - failures: "
        f"{verification.get('failures')}"
    )

    print(
        f" - warnings: "
        f"{verification.get('warnings')}"
    )

    # Verification must succeed.
    assert verification["verified"] is True, (
        "MRI-1 verification failed. "
        f"Failures: {verification.get('failures')}"
    )

    # Workflow decision must be the expected
    # governed research decision.
    assert (
        verification["decision"]
        == "verified_for_workflow_review"
    )

    assert (
        verification["next_action"]
        == "proceed_to_human_review"
    )

    print(" - verification: PASS")
    print(" - workflow decision: PASS")
    print(" - human-review routing: PASS")

    # --------------------------------------------------------
    # 6. GOVERNANCE BOUNDARY
    # --------------------------------------------------------

    print()
    print("6. GOVERNANCE BOUNDARY")

    # Human review must remain mandatory.
    assert (
        verification["human_review_required"]
        is True
    )

    # Autonomous diagnosis is prohibited.
    assert (
        verification[
            "safe_for_autonomous_diagnosis"
        ]
        is False
    )

    # Autonomous treatment is prohibited.
    assert (
        verification[
            "safe_for_autonomous_treatment"
        ]
        is False
    )

    # Irreversible actions are prohibited.
    assert (
        verification[
            "safe_for_irreversible_action"
        ]
        is False
    )

    print(" - human review required: YES")
    print(" - autonomous diagnosis: BLOCKED")
    print(" - autonomous treatment: BLOCKED")
    print(" - irreversible action: BLOCKED")
    print("Governance regression: PASS")

    # --------------------------------------------------------
    # FINAL REGRESSION RESULT
    # --------------------------------------------------------

    print()
    print("=" * 60)
    print("MRI-1 STEP 16: REGRESSION PASS")
    print("=" * 60)
    print()

    print("Regression coverage:")
    print("   Tool Registry")
    print("        ↓")
    print("   Real MRI input")
    print("        ↓")
    print("   MRI-1 execution")
    print("        ↓")
    print("   Output contract")
    print("        ↓")
    print("   Verification")
    print("        ↓")
    print("   Governance boundary")
    print()

    print("MRI-1 STEP 16: PASS")


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()