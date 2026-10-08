import sys
from pathlib import Path

# ------------------------------------------------------------
# PROJECT ROOT / IMPORT PATH
# ------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


import json
import os

import nibabel as nib

from tools.brain_tumor_segmentation import BrainTumorSegmentationTool
from verification.mri1_verification import MRI1VerificationEngine
from agent.case_state import (
    EvidenceItem,
    EvidenceProvenance,
    EvidenceStatus,
)


print("=== MRI-1 STEP 13: EVIDENCE + PROVENANCE ===")


# ------------------------------------------------------------
# CASE / INPUT SETUP
# ------------------------------------------------------------

CASE_ID = "BraTS-GLI-00000-000"

CASE_DIR = (
    r"data\mri\brats2023-gli\BraTS-GLI-00000-000"
    r"\ASNR-MICCAI-BraTS2023-GLI-Challenge-TrainingData"
    r"\BraTS-GLI-00000-000"
)

PATHS = {
    "T1c": os.path.join(
        CASE_DIR,
        "BraTS-GLI-00000-000-t1c.nii.gz",
    ),
    "T1": os.path.join(
        CASE_DIR,
        "BraTS-GLI-00000-000-t1n.nii.gz",
    ),
    "T2": os.path.join(
        CASE_DIR,
        "BraTS-GLI-00000-000-t2w.nii.gz",
    ),
    "FLAIR": os.path.join(
        CASE_DIR,
        "BraTS-GLI-00000-000-t2f.nii.gz",
    ),
}


# ------------------------------------------------------------
# CHECK INPUT FILES
# ------------------------------------------------------------

print("\nChecking MRI input files:")

for sequence, path in PATHS.items():
    print(f"{sequence}: {path}")

    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Missing MRI sequence: {sequence}: {path}"
        )

print("\nAll four MRI sequence files found.")


# ------------------------------------------------------------
# STEP 1 — RUN ACTUAL MRI-1 TOOL
# ------------------------------------------------------------

tool = BrainTumorSegmentationTool()

result = tool.run(
    {
        "T1c": PATHS["T1c"],
        "T1": PATHS["T1"],
        "T2": PATHS["T2"],
        "FLAIR": PATHS["FLAIR"],
        "case_id": CASE_ID,
    }
)

print("\nTool execution complete.")

print("Tool:", result.get("tool"))
print("Tool version:", result.get("tool_version"))
print("Model:", result.get("model"))
print("Model version:", result.get("model_version"))
print("Input shape:", result.get("input_shape"))
print("Prediction shape:", result.get("prediction_shape"))
print("Runtime:", result.get("runtime"))


# ------------------------------------------------------------
# STEP 2 — BUILD ACTUAL MRI METADATA
# ------------------------------------------------------------

print("\nBuilding MRI metadata from actual sequence files...")

sequence_metadata = {}

for sequence, path in PATHS.items():

    image = nib.load(path)

    sequence_metadata[sequence] = {
        "shape": tuple(image.shape),
        "spacing": tuple(
            float(value)
            for value in image.header.get_zooms()[:3]
        ),
        "path": path,
    }

    print(
        f"{sequence}: "
        f"shape={sequence_metadata[sequence]['shape']}, "
        f"spacing={sequence_metadata[sequence]['spacing']}"
    )


mri_metadata = {
    "modality": "MRI",
    "body_region": "brain",
    "sequences": sequence_metadata,
}


# ------------------------------------------------------------
# STEP 3 — RUN ACTUAL MRI-1 VERIFIER
# ------------------------------------------------------------

print("\nRunning MRI-1 verifier...")

verifier = MRI1VerificationEngine()

verification = verifier.verify(
    {
        "mri_metadata": mri_metadata,
        "segmentation_result": result,
    }
)


print("\n=== MRI-1 VERIFICATION ===")

print(
    "Verified:",
    verification["verified"]
)

print(
    "Decision:",
    verification["decision"]
)

print(
    "Next action:",
    verification["next_action"]
)

print(
    "Human review required:",
    verification["human_review_required"]
)


if not verification["verified"]:

    print("\nFailures:")

    for failure in verification["failures"]:
        print(" -", failure)

    raise SystemExit(
        "\nMRI-1 Step 13 cannot continue because "
        "Step 12 verification failed."
    )


print("\nMRI-1 Step 12 verification: PASS")


# ------------------------------------------------------------
# STEP 4 — BUILD PROVENANCE
# ------------------------------------------------------------

print("\nBuilding EvidenceProvenance...")

runtime = result.get("runtime", {})

provenance = EvidenceProvenance(
    tool_name=result.get("tool"),

    tool_version=result.get(
        "tool_version"
    ),

    model_name=result.get(
        "model"
    ),

    model_version=result.get(
        "model_version"
    ),

    runtime=json.dumps(
        runtime,
        sort_keys=True,
    ),

    input_references=[
        PATHS["T1c"],
        PATHS["T1"],
        PATHS["T2"],
        PATHS["FLAIR"],
    ],

    metadata={
        "case_id": CASE_ID,

        "modality": "MRI",

        "body_region": "brain",

        "sequences": [
            "T1c",
            "T1",
            "T2",
            "FLAIR",
        ],

        "verification_decision": verification[
            "decision"
        ],

        "verification_failures": verification[
            "failures"
        ],

        "verification_warnings": verification[
            "warnings"
        ],
    },
)


# ------------------------------------------------------------
# STEP 5 — BUILD GOVERNED EVIDENCE ITEM
# ------------------------------------------------------------

print("Building EvidenceItem...")

label_summary = result.get(
    "label_summary",
    {}
)


supporting_regions = [
    {
        "region": "tumor_core",
        "voxel_count": int(
            label_summary[
                "tumor_core"
            ]["voxel_count"]
        ),
    },
    {
        "region": "whole_tumor",
        "voxel_count": int(
            label_summary[
                "whole_tumor"
            ]["voxel_count"]
        ),
    },
    {
        "region": "enhancing_tumor",
        "voxel_count": int(
            label_summary[
                "enhancing_tumor"
            ]["voxel_count"]
        ),
    },
]


probabilities = result.get(
    "probabilities",
    {}
)

masks = result.get(
    "masks",
    {}
)


evidence_output = {
    "label_summary": label_summary,

    "prediction_shape": tuple(
        result.get(
            "prediction_shape"
        )
    ),

    "input_shape": tuple(
        result.get(
            "input_shape"
        )
    ),

    "probability_shapes": {
        region: tuple(
            values.shape
        )
        for region, values in probabilities.items()
    },

    "mask_shapes": {
        region: tuple(
            values.shape
        )
        for region, values in masks.items()
    },
}


evidence = EvidenceItem(
    evidence_id=(
        f"{CASE_ID}:MRI1:"
        f"SEGMENTATION:001"
    ),

    case_id=CASE_ID,

    evidence_type=(
        "MRI_BRAIN_TUMOR_SEGMENTATION"
    ),

    source=(
        "brain_tumor_segmentation"
    ),

    claim=(
        "MRI-1 produced research/demo "
        "segmentation evidence for tumor "
        "core, whole tumor, and enhancing "
        "tumor regions from the required "
        "T1c, T1, T2, and FLAIR sequences."
    ),

    output=evidence_output,

    status=EvidenceStatus.VALID,

    confidence=None,

    applicable=True,

    image_ids=[
        f"{CASE_ID}:T1c",
        f"{CASE_ID}:T1",
        f"{CASE_ID}:T2",
        f"{CASE_ID}:FLAIR",
    ],

    supporting_regions=supporting_regions,

    provenance=provenance,

    verification_ids=[
        f"{CASE_ID}:MRI1:"
        f"VERIFICATION:001"
    ],

    task_id=(
        "MRI-1-BRAIN-TUMOR-SEGMENTATION"
    ),

    dependencies=[
        "MRI-1-SAFETY-CONTRACT",
        "MRI-1-STEP-12-VERIFICATION",
    ],

    warnings=verification[
        "warnings"
    ],

    metadata={
        "clinical_use": (
            "research_demo_only"
        ),

        "human_verification_required": True,

        "autonomous_diagnosis_allowed": False,

        "autonomous_treatment_allowed": False,

        "irreversible_action_allowed": False,

        "verification_status": (
            verification["decision"]
        ),
    },
)


# ------------------------------------------------------------
# STEP 6 — VALIDATE EVIDENCE IDENTITY
# ------------------------------------------------------------

assert (
    evidence.evidence_id
    == f"{CASE_ID}:MRI1:SEGMENTATION:001"
)

assert evidence.case_id == CASE_ID

assert (
    evidence.evidence_type
    == "MRI_BRAIN_TUMOR_SEGMENTATION"
)

assert (
    evidence.source
    == "brain_tumor_segmentation"
)

print("\nEvidence identity: PASS")


# ------------------------------------------------------------
# STEP 7 — VALIDATE EVIDENCE STATUS
# ------------------------------------------------------------

assert (
    evidence.status
    == EvidenceStatus.VALID
)

assert evidence.applicable is True

print(
    "Evidence status/applicability: PASS"
)


# ------------------------------------------------------------
# STEP 8 — VALIDATE INPUT REFERENCES
# ------------------------------------------------------------

assert (
    len(
        evidence.provenance.input_references
    )
    == 4
)

for sequence, path in PATHS.items():

    assert (
        path
        in evidence.provenance.input_references
    )

print(
    "Input provenance references: PASS"
)


# ------------------------------------------------------------
# STEP 9 — VALIDATE TOOL/MODEL PROVENANCE
# ------------------------------------------------------------

assert (
    evidence.provenance.tool_name
    == "brain_tumor_segmentation"
)

assert (
    evidence.provenance.tool_version
    == "research-demo-1.0"
)

assert (
    evidence.provenance.model_name
    == "MONAI BraTS MRI segmentation"
)

assert (
    evidence.provenance.model_version
    == "0.5.4"
)

assert evidence.provenance.runtime

print(
    "Tool/model/runtime provenance: PASS"
)


# ------------------------------------------------------------
# STEP 10 — VALIDATE MRI SEQUENCE REFERENCES
# ------------------------------------------------------------

expected_image_ids = {
    f"{CASE_ID}:T1c",
    f"{CASE_ID}:T1",
    f"{CASE_ID}:T2",
    f"{CASE_ID}:FLAIR",
}

assert (
    set(evidence.image_ids)
    == expected_image_ids
)

print(
    "MRI sequence references: PASS"
)


# ------------------------------------------------------------
# STEP 11 — VALIDATE SUPPORTING REGIONS
# ------------------------------------------------------------

expected_regions = {
    "tumor_core",
    "whole_tumor",
    "enhancing_tumor",
}

actual_regions = {
    item["region"]
    for item in evidence.supporting_regions
}

assert (
    actual_regions
    == expected_regions
)


for item in evidence.supporting_regions:

    assert (
        "voxel_count"
        in item
    )

    assert isinstance(
        item["voxel_count"],
        int,
    )

    assert (
        item["voxel_count"]
        >= 0
    )


print(
    "Supporting regions: PASS"
)


# ------------------------------------------------------------
# STEP 12 — VALIDATE VERIFICATION LINK
# ------------------------------------------------------------

assert (
    len(
        evidence.verification_ids
    )
    == 1
)

assert (
    evidence.verification_ids[0]
    == (
        f"{CASE_ID}:MRI1:"
        f"VERIFICATION:001"
    )
)

assert (
    evidence.provenance.metadata[
        "verification_decision"
    ]
    == "verified_for_workflow_review"
)

print(
    "Verification linkage: PASS"
)


# ------------------------------------------------------------
# STEP 13 — VALIDATE GOVERNANCE
# ------------------------------------------------------------

assert (
    evidence.metadata[
        "clinical_use"
    ]
    == "research_demo_only"
)

assert (
    evidence.metadata[
        "human_verification_required"
    ]
    is True
)

assert (
    evidence.metadata[
        "autonomous_diagnosis_allowed"
    ]
    is False
)

assert (
    evidence.metadata[
        "autonomous_treatment_allowed"
    ]
    is False
)

assert (
    evidence.metadata[
        "irreversible_action_allowed"
    ]
    is False
)

print(
    "Governance restrictions: PASS"
)


# ------------------------------------------------------------
# STEP 14 — VALIDATE DEPENDENCIES
# ------------------------------------------------------------

assert (
    "MRI-1-SAFETY-CONTRACT"
    in evidence.dependencies
)

assert (
    "MRI-1-STEP-12-VERIFICATION"
    in evidence.dependencies
)

print(
    "Evidence dependencies: PASS"
)


# ------------------------------------------------------------
# STEP 15 — FINAL EVIDENCE SUMMARY
# ------------------------------------------------------------

print(
    "\n=== MRI-1 EVIDENCE SUMMARY ==="
)

print(
    "Evidence ID:",
    evidence.evidence_id
)

print(
    "Case ID:",
    evidence.case_id
)

print(
    "Evidence type:",
    evidence.evidence_type
)

print(
    "Source:",
    evidence.source
)

print(
    "Status:",
    evidence.status.value
)

print(
    "Applicable:",
    evidence.applicable
)


print("\nProvenance:")

print(
    " Tool:",
    evidence.provenance.tool_name
)

print(
    " Tool version:",
    evidence.provenance.tool_version
)

print(
    " Model:",
    evidence.provenance.model_name
)

print(
    " Model version:",
    evidence.provenance.model_version
)

print(
    " Input references:",
    len(
        evidence.provenance.input_references
    )
)


print("\nSupporting regions:")

for region in evidence.supporting_regions:

    print(
        f" - {region['region']}: "
        f"{region['voxel_count']} voxels"
    )


print("\nGovernance:")

print(
    " Human verification required:",
    evidence.metadata[
        "human_verification_required"
    ],
)

print(
    " Autonomous diagnosis:",
    evidence.metadata[
        "autonomous_diagnosis_allowed"
    ],
)

print(
    " Autonomous treatment:",
    evidence.metadata[
        "autonomous_treatment_allowed"
    ],
)

print(
    " Irreversible action:",
    evidence.metadata[
        "irreversible_action_allowed"
    ],
)


print(
    "\nMRI-1 STEP 13: PASS"
)