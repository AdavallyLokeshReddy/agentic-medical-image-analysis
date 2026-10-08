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

from tools.brain_tumor_segmentation import (
    BrainTumorSegmentationTool,
)

from verification.mri1_verification import (
    MRI1VerificationEngine,
)

from agent.case_state import (
    CaseModality,
    CaseState,
    CaseStatus,
    EvidenceItem,
    EvidenceProvenance,
    EvidenceStatus,
)


print("=== MRI-1 STEP 14: CASESTATE INTEGRATION ===")


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
# CHECK INPUTS
# ------------------------------------------------------------

print("\nChecking MRI input files:")

for sequence, path in PATHS.items():

    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Missing MRI sequence: {sequence}: {path}"
        )

    print(f" - {sequence}: OK")


print("\nAll required MRI sequences found.")


# ------------------------------------------------------------
# STEP 1 — RUN MRI-1 TOOL
# ------------------------------------------------------------

print("\nRunning MRI-1 tool...")

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

print("Tool execution: PASS")


# ------------------------------------------------------------
# STEP 2 — BUILD MRI METADATA
# ------------------------------------------------------------

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


mri_metadata = {
    "modality": "MRI",
    "body_region": "brain",
    "sequences": sequence_metadata,
}


# ------------------------------------------------------------
# STEP 3 — VERIFY MRI-1 RESULT
# ------------------------------------------------------------

print("\nRunning MRI-1 verifier...")

verifier = MRI1VerificationEngine()

verification = verifier.verify(
    {
        "mri_metadata": mri_metadata,
        "segmentation_result": result,
    }
)


if not verification["verified"]:

    print("\nVerification failures:")

    for failure in verification["failures"]:
        print(" -", failure)

    raise SystemExit(
        "Step 14 cannot continue because "
        "MRI-1 verification failed."
    )


print("MRI-1 verification: PASS")


# ------------------------------------------------------------
# STEP 4 — BUILD PROVENANCE
# ------------------------------------------------------------

runtime = result.get(
    "runtime",
    {},
)


provenance = EvidenceProvenance(
    tool_name=result.get(
        "tool"
    ),

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

        "verification_decision": (
            verification["decision"]
        ),

        "verification_warnings": (
            verification["warnings"]
        ),
    },
)


# ------------------------------------------------------------
# STEP 5 — BUILD EVIDENCE
# ------------------------------------------------------------

label_summary = result.get(
    "label_summary",
    {},
)


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
        "tumor regions from T1c, T1, T2, "
        "and FLAIR MRI sequences."
    ),

    output={
        "label_summary": label_summary,

        "input_shape": tuple(
            result["input_shape"]
        ),

        "prediction_shape": tuple(
            result["prediction_shape"]
        ),
    },

    status=EvidenceStatus.VALID,

    applicable=True,

    image_ids=[
        f"{CASE_ID}:T1c",
        f"{CASE_ID}:T1",
        f"{CASE_ID}:T2",
        f"{CASE_ID}:FLAIR",
    ],

    supporting_regions=[
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
    ],

    provenance=provenance,

    verification_ids=[
        (
            f"{CASE_ID}:MRI1:"
            f"VERIFICATION:001"
        )
    ],

    task_id=(
        "MRI-1-BRAIN-TUMOR-SEGMENTATION"
    ),

    dependencies=[
        "MRI-1-SAFETY-CONTRACT",
        "MRI-1-STEP-12-VERIFICATION",
        "MRI-1-STEP-13-EVIDENCE",
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
    },
)


print("\nEvidence object created: PASS")


# ------------------------------------------------------------
# STEP 6 — CREATE CASESTATE
# ------------------------------------------------------------

print("\nCreating CaseState...")

case_state = CaseState(
    case_id=CASE_ID,
    modality=CaseModality.MRI,
    body_region="brain",
)


print("CaseState created.")

print(
    "Case ID:",
    case_state.case_id,
)

print(
    "Modality:",
    case_state.modality.value,
)

print(
    "Body region:",
    case_state.body_region,
)


# ------------------------------------------------------------
# STEP 7 — ADD EVIDENCE THROUGH REAL API
# ------------------------------------------------------------

print(
    "\nAdding evidence through "
    "CaseState.add_evidence()..."
)

case_state.add_evidence(
    evidence
)

print(
    "CaseState.add_evidence(): PASS"
)


# ------------------------------------------------------------
# STEP 8 — VERIFY EVIDENCE STORAGE
# ------------------------------------------------------------

assert len(
    case_state.evidence
) == 1


stored_evidence = case_state.evidence[0]


assert (
    stored_evidence.evidence_id
    == evidence.evidence_id
)

assert (
    stored_evidence.case_id
    == CASE_ID
)

assert (
    stored_evidence.status
    == EvidenceStatus.VALID
)

assert (
    stored_evidence.applicable
    is True
)


print(
    "Evidence storage: PASS"
)


# ------------------------------------------------------------
# STEP 9 — VERIFY PROVENANCE SURVIVAL
# ------------------------------------------------------------

assert (
    stored_evidence.provenance.tool_name
    == "brain_tumor_segmentation"
)

assert (
    stored_evidence.provenance.tool_version
    == "research-demo-1.0"
)

assert (
    stored_evidence.provenance.model_name
    == "MONAI BraTS MRI segmentation"
)

assert (
    stored_evidence.provenance.model_version
    == "0.5.4"
)

assert (
    len(
        stored_evidence.provenance
        .input_references
    )
    == 4
)


print(
    "Provenance survival: PASS"
)


# ------------------------------------------------------------
# STEP 10 — VERIFY MRI SEQUENCE REFERENCES
# ------------------------------------------------------------

expected_image_ids = {
    f"{CASE_ID}:T1c",
    f"{CASE_ID}:T1",
    f"{CASE_ID}:T2",
    f"{CASE_ID}:FLAIR",
}


assert (
    set(stored_evidence.image_ids)
    == expected_image_ids
)


print(
    "MRI sequence references: PASS"
)


# ------------------------------------------------------------
# STEP 11 — VERIFY SUPPORTING REGIONS
# ------------------------------------------------------------

expected_regions = {
    "tumor_core",
    "whole_tumor",
    "enhancing_tumor",
}


actual_regions = {
    item["region"]
    for item in (
        stored_evidence.supporting_regions
    )
}


assert (
    actual_regions
    == expected_regions
)


print(
    "Supporting regions: PASS"
)


# ------------------------------------------------------------
# STEP 12 — VERIFY VERIFICATION LINK
# ------------------------------------------------------------

assert (
    len(
        stored_evidence.verification_ids
    )
    == 1
)

assert (
    stored_evidence.verification_ids[0]
    == (
        f"{CASE_ID}:MRI1:"
        f"VERIFICATION:001"
    )
)


print(
    "Verification linkage: PASS"
)


# ------------------------------------------------------------
# STEP 13 — VERIFY GOVERNANCE SURVIVAL
# ------------------------------------------------------------

assert (
    stored_evidence.metadata[
        "clinical_use"
    ]
    == "research_demo_only"
)

assert (
    stored_evidence.metadata[
        "human_verification_required"
    ]
    is True
)

assert (
    stored_evidence.metadata[
        "autonomous_diagnosis_allowed"
    ]
    is False
)

assert (
    stored_evidence.metadata[
        "autonomous_treatment_allowed"
    ]
    is False
)

assert (
    stored_evidence.metadata[
        "irreversible_action_allowed"
    ]
    is False
)


print(
    "Governance metadata survival: PASS"
)


# ------------------------------------------------------------
# STEP 14 — VERIFY CASE SUMMARY
# ------------------------------------------------------------

print(
    "\nGenerating CaseState summary..."
)

summary = case_state.summary()

print(
    "\nCaseState summary:"
)

print(
    json.dumps(
        summary,
        indent=2,
        default=str,
    )
)


# ------------------------------------------------------------
# STEP 15 — FINAL
# ------------------------------------------------------------

print(
    "\n=== MRI-1 STEP 14 RESULT ==="
)

print(
    "CaseState:",
    case_state.case_id,
)

print(
    "Evidence count:",
    len(case_state.evidence),
)

print(
    "Evidence status:",
    stored_evidence.status.value,
)

print(
    "Verification linked:",
    len(
        stored_evidence.verification_ids
    ) > 0,
)

print(
    "Human review required:",
    stored_evidence.metadata[
        "human_verification_required"
    ],
)

print(
    "Autonomous diagnosis:",
    stored_evidence.metadata[
        "autonomous_diagnosis_allowed"
    ],
)

print(
    "Autonomous treatment:",
    stored_evidence.metadata[
        "autonomous_treatment_allowed"
    ],
)


print(
    "\nMRI-1 STEP 14: PASS"
)