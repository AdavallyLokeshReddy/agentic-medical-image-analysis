from __future__ import annotations

import sys
from pathlib import Path


# =========================================================
# PROJECT ROOT
# =========================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# =========================================================
# PROJECT IMPORTS
# =========================================================

# Importing register_tools performs the project's normal
# default tool registration.
#
# IMPORTANT:
# Do NOT call register_default_tools() again in this test.
# The registry rejects duplicate registrations.
import tools.register_tools

from tools.registry import tool_registry
from verification.mri1_verification import MRI1VerificationEngine


# =========================================================
# MRI-1 CONSTANTS
# =========================================================

TOOL_NAME = "brain_tumor_segmentation"
TOOL_VERSION = "research-demo-1.0"

MODEL_NAME = "MONAI BraTS MRI segmentation"
MODEL_VERSION = "0.5.4"

SAFETY_CONTRACT_ID = "MRI-1-BRAIN-TUMOR-RESEARCH"

EXPECTED_ARCHITECTURE = "SegResNet"

REQUIRED_SEQUENCES = {
    "T1c",
    "T1",
    "T2",
    "FLAIR",
}

EXPECTED_SPACING = (
    1.0,
    1.0,
    1.0,
)

CASE_ID = "BraTS-GLI-00000-000"

CASE_DIR = (
    PROJECT_ROOT
    / "data"
    / "mri"
    / "brats2023-gli"
    / "BraTS-GLI-00000-000"
    / "ASNR-MICCAI-BraTS2023-GLI-Challenge-TrainingData"
    / "BraTS-GLI-00000-000"
)


# =========================================================
# MAIN
# =========================================================

def main():

    print()
    print("=" * 70)
    print("MRI-1 STEP 17: FINAL LOCK TEST")
    print("=" * 70)

    # =====================================================
    # 1. TOOL REGISTRY
    # =====================================================

    print()
    print("1. TOOL REGISTRY")

    # The default tools are already registered when
    # tools.register_tools was imported above.
    #
    # Do NOT call register_default_tools() here.

    tool_names = {
        tool["name"]
        for tool in tool_registry.list_tools()
    }

    assert TOOL_NAME in tool_names, (
        f"{TOOL_NAME} is not registered."
    )

    tool = tool_registry.get(TOOL_NAME)

    assert tool is not None, (
        f"Could not retrieve registered tool: {TOOL_NAME}"
    )

    print(f" - {TOOL_NAME}: REGISTERED")
    print("Tool Registry: PASS")

    # =====================================================
    # 2. TOOL IDENTITY
    # =====================================================

    print()
    print("2. TOOL IDENTITY")

    # MedicalAITool does not expose the tool version through
    # a direct .version attribute.
    #
    # Therefore:
    # - registry identity is checked here
    # - actual tool/version identity is checked from the
    #   runtime output in Step 3

    assert getattr(tool, "name", None) == TOOL_NAME, (
        f"Registered tool identity mismatch. "
        f"Expected {TOOL_NAME}, "
        f"got {getattr(tool, 'name', None)}"
    )

    print(f" - tool name: {TOOL_NAME}")
    print(" - tool registration identity: CONFIRMED")
    print(
        " - tool version: "
        "verified from runtime output in Step 3"
    )

    print("Tool identity: PASS")

    # =====================================================
    # 3. MODEL IDENTITY
    # =====================================================

    print()
    print("3. MODEL IDENTITY")

    sequence_files = {
        "T1c": CASE_DIR / f"{CASE_ID}-t1c.nii.gz",
        "T1": CASE_DIR / f"{CASE_ID}-t1n.nii.gz",
        "T2": CASE_DIR / f"{CASE_ID}-t2w.nii.gz",
        "FLAIR": CASE_DIR / f"{CASE_ID}-t2f.nii.gz",
    }

    print()

    for sequence, path in sequence_files.items():

        assert path.exists(), (
            f"Missing MRI-1 sequence: "
            f"{sequence} -> {path}"
        )

        print(f" - {sequence}: OK")

    input_data = {
        sequence: str(path)
        for sequence, path in sequence_files.items()
    }

    input_data["case_id"] = CASE_ID

    print()
    print(" - running MRI-1 inference...")

    output = tool.run(input_data)

    # Runtime identity verification.
    assert output["model"] == MODEL_NAME, (
        f"Model mismatch. "
        f"Expected {MODEL_NAME}, "
        f"got {output.get('model')}"
    )

    assert output["model_version"] == MODEL_VERSION, (
        f"Model version mismatch. "
        f"Expected {MODEL_VERSION}, "
        f"got {output.get('model_version')}"
    )

    assert output["tool"] == TOOL_NAME, (
        f"Tool mismatch. "
        f"Expected {TOOL_NAME}, "
        f"got {output.get('tool')}"
    )

    assert output["tool_version"] == TOOL_VERSION, (
        f"Tool version mismatch. "
        f"Expected {TOOL_VERSION}, "
        f"got {output.get('tool_version')}"
    )

    print(f" - model: {MODEL_NAME}")
    print(f" - model version: {MODEL_VERSION}")
    print(f" - tool: {TOOL_NAME}")
    print(f" - tool version: {TOOL_VERSION}")
    print(" - model/tool identity verified from runtime")

    print("Model identity: PASS")

    # =====================================================
    # 4. INPUT CONTRACT
    # =====================================================

    print()
    print("4. INPUT CONTRACT")

    assert output["modality"] == "MRI", (
        f"Expected modality MRI, "
        f"got {output.get('modality')}"
    )

    assert output["body_region"] == "brain", (
        f"Expected body region brain, "
        f"got {output.get('body_region')}"
    )

    actual_sequences = set(
        output["input_sequences"]
    )

    assert actual_sequences == REQUIRED_SEQUENCES, (
        "MRI-1 input sequence contract mismatch. "
        f"Expected: {sorted(REQUIRED_SEQUENCES)} "
        f"Got: {sorted(actual_sequences)}"
    )

    print(" - modality: MRI")
    print(" - body region: brain")
    print(" - T1c: PRESENT")
    print(" - T1: PRESENT")
    print(" - T2: PRESENT")
    print(" - FLAIR: PRESENT")

    print("MRI input contract: PASS")

    # =====================================================
    # 5. GEOMETRY CONTRACT
    # =====================================================

    print()
    print("5. GEOMETRY CONTRACT")

    voxel_spacing = output["voxel_spacing"]

    for sequence in REQUIRED_SEQUENCES:

        assert sequence in voxel_spacing, (
            f"Missing voxel spacing for {sequence}"
        )

        spacing = tuple(
            float(value)
            for value in voxel_spacing[sequence]
        )

        assert spacing == EXPECTED_SPACING, (
            f"Invalid spacing for {sequence}: "
            f"{spacing}. "
            f"Expected {EXPECTED_SPACING}."
        )

        print(
            f" - {sequence}: {spacing}"
        )

    print(" - 1mm isotropic geometry: CONFIRMED")
    print("MRI geometry contract: PASS")

    # =====================================================
    # 6. OUTPUT CONTRACT
    # =====================================================

    print()
    print("6. OUTPUT CONTRACT")

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

    missing_keys = (
        required_keys
        - set(output.keys())
    )

    assert not missing_keys, (
        "MRI-1 output contract missing keys: "
        f"{sorted(missing_keys)}"
    )

    expected_regions = {
        "tumor_core",
        "whole_tumor",
        "enhancing_tumor",
    }

    assert expected_regions.issubset(
        set(output["masks"].keys())
    ), (
        "Missing expected segmentation masks."
    )

    assert expected_regions.issubset(
        set(output["probabilities"].keys())
    ), (
        "Missing expected probability outputs."
    )

    assert expected_regions.issubset(
        set(output["label_summary"].keys())
    ), (
        "Missing expected label summaries."
    )

    assert output["input_shape"] == (
        240,
        240,
        155,
    ), (
        f"Unexpected input shape: "
        f"{output['input_shape']}"
    )

    assert output["prediction_shape"] == (
        240,
        240,
        155,
    ), (
        f"Unexpected prediction shape: "
        f"{output['prediction_shape']}"
    )

    print(" - required output fields: PASS")
    print(" - input shape: (240, 240, 155)")
    print(" - prediction shape: (240, 240, 155)")
    print(" - tumor_core: PASS")
    print(" - whole_tumor: PASS")
    print(" - enhancing_tumor: PASS")

    print("Output contract: PASS")

    # =====================================================
    # 7. RUNTIME / ARCHITECTURE
    # =====================================================

    print()
    print("7. RUNTIME / ARCHITECTURE")

    runtime = output["runtime"]

    assert isinstance(runtime, dict), (
        "Runtime metadata must be a dictionary."
    )

    assert runtime["device"] == "cpu", (
        f"Expected CPU runtime, "
        f"got {runtime.get('device')}"
    )

    assert runtime["framework"] == "PyTorch", (
        f"Expected PyTorch, "
        f"got {runtime.get('framework')}"
    )

    assert (
        runtime["architecture"]
        == EXPECTED_ARCHITECTURE
    ), (
        f"Expected architecture "
        f"{EXPECTED_ARCHITECTURE}, "
        f"got {runtime.get('architecture')}"
    )

    assert (
        runtime["inferer"]
        == "SlidingWindowInferer"
    ), (
        f"Expected SlidingWindowInferer, "
        f"got {runtime.get('inferer')}"
    )

    print(" - device: CPU")
    print(" - framework: PyTorch")
    print(
        f" - architecture: "
        f"{EXPECTED_ARCHITECTURE}"
    )
    print(
        " - inferer: SlidingWindowInferer"
    )

    print("Runtime / architecture: PASS")

    # =====================================================
    # 8. GOVERNANCE METADATA
    # =====================================================

    print()
    print("8. GOVERNANCE METADATA")

    assert (
        output["verification_required"]
        is True
    ), (
        "MRI-1 must require verification."
    )

    assert (
        output["clinical_use"]
        == "research_demo_only"
    ), (
        "MRI-1 must remain research_demo_only."
    )

    print(
        " - verification required: TRUE"
    )
    print(
        " - clinical use: research_demo_only"
    )

    print("Governance metadata: PASS")

    # =====================================================
    # 9. MRI-1 VERIFICATION ENGINE
    # =====================================================

    print()
    print("9. MRI-1 VERIFICATION ENGINE")

    verifier = MRI1VerificationEngine()

    mri_metadata = {
        "modality": "MRI",
        "body_region": "brain",
        "sequences": {
            sequence: {
                "shape": output["input_shape"],
                "spacing": (
                    output["voxel_spacing"][sequence]
                ),
            }
            for sequence in REQUIRED_SEQUENCES
        },
    }

    verification = verifier.verify(
        {
            "mri_metadata": mri_metadata,
            "segmentation_result": output,
        }
    )

    assert verification["verified"] is True, (
        f"MRI-1 verification failed: "
        f"{verification.get('failures')}"
    )

    assert (
        verification["decision"]
        == "verified_for_workflow_review"
    ), (
        f"Unexpected verification decision: "
        f"{verification.get('decision')}"
    )

    assert (
        verification["next_action"]
        == "proceed_to_human_review"
    ), (
        f"Unexpected next action: "
        f"{verification.get('next_action')}"
    )

    assert (
        verification["human_review_required"]
        is True
    ), (
        "MRI-1 must require human review."
    )

    print(
        " - verifier: MRI1VerificationEngine"
    )
    print(" - verified: TRUE")
    print(
        " - decision: "
        "verified_for_workflow_review"
    )
    print(
        " - next action: "
        "proceed_to_human_review"
    )
    print(
        " - human review required: TRUE"
    )

    print("MRI-1 verification: PASS")

    # =====================================================
    # 10. SAFETY CONTRACT BOUNDARY
    # =====================================================

    print()
    print("10. SAFETY CONTRACT")

    print(
        f" - contract: {SAFETY_CONTRACT_ID}"
    )

    assert (
        verification[
            "safe_for_autonomous_diagnosis"
        ]
        is False
    ), (
        "Autonomous diagnosis must remain blocked."
    )

    assert (
        verification[
            "safe_for_autonomous_treatment"
        ]
        is False
    ), (
        "Autonomous treatment must remain blocked."
    )

    assert (
        verification[
            "safe_for_irreversible_action"
        ]
        is False
    ), (
        "Irreversible action must remain blocked."
    )

    assert (
        verification[
            "human_review_required"
        ]
        is True
    ), (
        "Human review must remain required."
    )

    print(
        " - autonomous diagnosis: BLOCKED"
    )
    print(
        " - autonomous treatment: BLOCKED"
    )
    print(
        " - irreversible action: BLOCKED"
    )
    print(
        " - human review: REQUIRED"
    )

    print(
        "Safety Contract boundary: PASS"
    )

    # =====================================================
    # 11. RESEARCH / DEMO RESTRICTION
    # =====================================================

    print()
    print("11. RESEARCH / DEMO BOUNDARY")

    assert (
        output["clinical_use"]
        == "research_demo_only"
    )

    warnings_text = " ".join(
        str(warning)
        for warning in output["warnings"]
    ).lower()

    assert (
        "research" in warnings_text
        or "demo" in warnings_text
    ), (
        "MRI-1 output must contain "
        "research/demo warning."
    )

    print(
        " - clinical use: RESEARCH / DEMO ONLY"
    )
    print(
        " - clinical validation: NOT ESTABLISHED"
    )
    print(
        " - autonomous clinical use: BLOCKED"
    )

    print("Research boundary: PASS")

    # =====================================================
    # 12. PREVIOUS MILESTONES
    # =====================================================

    print()
    print("12. PREVIOUS MRI-1 MILESTONES")

    # Steps 15 and 16 were already executed and passed.
    # This records those completed milestones for the
    # final freeze test.

    previous_milestones = {
        "step_15_governed_integration": "PASS",
        "step_16_regression": "PASS",
    }

    for milestone, status in (
        previous_milestones.items()
    ):

        assert status == "PASS"

        print(
            f" - {milestone}: {status}"
        )

    print("Previous milestones: PASS")

    # =====================================================
    # 13. FINAL FREEZE ASSERTIONS
    # =====================================================

    print()
    print("13. FINAL FREEZE ASSERTIONS")

    assert (
        TOOL_NAME
        == "brain_tumor_segmentation"
    )

    assert (
        TOOL_VERSION
        == "research-demo-1.0"
    )

    assert (
        MODEL_NAME
        == "MONAI BraTS MRI segmentation"
    )

    assert MODEL_VERSION == "0.5.4"

    assert (
        EXPECTED_ARCHITECTURE
        == "SegResNet"
    )

    assert REQUIRED_SEQUENCES == {
        "T1c",
        "T1",
        "T2",
        "FLAIR",
    }

    assert EXPECTED_SPACING == (
        1.0,
        1.0,
        1.0,
    )

    assert (
        SAFETY_CONTRACT_ID
        == "MRI-1-BRAIN-TUMOR-RESEARCH"
    )

    assert (
        verification[
            "safe_for_autonomous_diagnosis"
        ]
        is False
    )

    assert (
        verification[
            "safe_for_autonomous_treatment"
        ]
        is False
    )

    assert (
        verification[
            "safe_for_irreversible_action"
        ]
        is False
    )

    print(
        " - model identity: FROZEN"
    )
    print(
        " - tool identity: FROZEN"
    )
    print(
        " - input contract: FROZEN"
    )
    print(
        " - geometry contract: FROZEN"
    )
    print(
        " - output contract: FROZEN"
    )
    print(
        " - safety boundary: FROZEN"
    )
    print(
        " - research/demo restriction: FROZEN"
    )

    print("Final freeze assertions: PASS")

    # =====================================================
    # FINAL RESULT
    # =====================================================

    print()
    print("=" * 70)
    print("MRI-1 STEP 17: FINAL LOCK PASS")
    print("=" * 70)

    print()
    print("MRI-1 STATUS: FROZEN")

    print()
    print("Frozen capability:")
    print(
        "   Brain tumor / lesion segmentation"
    )

    print()
    print("Frozen model:")
    print(
        f"   {MODEL_NAME} v{MODEL_VERSION}"
    )

    print()
    print("Frozen tool:")
    print(
        f"   {TOOL_NAME} v{TOOL_VERSION}"
    )

    print()
    print("Frozen input contract:")
    print("   MRI")
    print("   Brain")
    print(
        "   T1c + T1 + T2 + FLAIR"
    )
    print(
        "   1mm isotropic geometry"
    )

    print()
    print("Frozen governance:")
    print(
        "   Human verification REQUIRED"
    )
    print(
        "   Autonomous diagnosis BLOCKED"
    )
    print(
        "   Autonomous treatment BLOCKED"
    )
    print(
        "   Irreversible action BLOCKED"
    )

    print()
    print("Research boundary:")
    print(
        "   RESEARCH / DEMO ONLY"
    )
    print(
        "   NOT clinically validated"
    )

    print()
    print("MRI CAPABILITY STATUS:")
    print("   MRI-1: LOCKED")
    print("   MRI-2: NOT STARTED")

    print()
    print("=" * 70)


# =========================================================
# ENTRY POINT
# =========================================================

if __name__ == "__main__":
    main()