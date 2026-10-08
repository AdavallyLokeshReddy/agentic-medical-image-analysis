from pathlib import Path

from agent.case_state import CaseModality, CaseState
from agent.safety_contract import (
    SafetyContract,
    DataPolicy,
    OperationPolicy,
    UncertaintyPolicy,
    EscalationPolicy,
    ResourcePolicy,
)
from tools.pancreas_tumor_segmentation import PancreasTumorSegmentationTool
from verification.ct4_verification import CT4VerificationEngine


CASE_ID = "CASE-ABDOMEN-0001"

BASE_DIR = Path(__file__).resolve().parents[1]
SERIES_DIR = BASE_DIR / "uploads" / CASE_ID / "series"


def main():
    print("CT-4 REGRESSION TEST")
    print("=" * 60)

    # ---------------------------------------------------------
    # 1. Dataset availability
    # ---------------------------------------------------------
    dicom_files = sorted(SERIES_DIR.glob("*.dcm"))

    assert SERIES_DIR.exists(), (
        f"Missing CT series directory: {SERIES_DIR}"
    )

    assert len(dicom_files) > 0, (
        "No DICOM files found"
    )

    print(f"DICOM FILES: {len(dicom_files)}")

    # ---------------------------------------------------------
    # 2. Tool construction
    # ---------------------------------------------------------
    tool = PancreasTumorSegmentationTool()

    assert tool.name == (
        "pancreas_tumor_segmentation"
    )

    assert tool.TOOL_VERSION == (
        "research-demo-1.0"
    )

    print("TOOL IDENTITY: PASS")

    # ---------------------------------------------------------
    # 3. Case State
    # ---------------------------------------------------------
    case = CaseState(
        case_id=CASE_ID,
        modality=CaseModality.CT,
        body_region="PANCREAS",
        clinical_question=(
            "Research/demo pancreas and "
            "pancreatic tumor segmentation"
        ),
    )

    assert case.case_id == CASE_ID
    assert case.modality == CaseModality.CT
    assert case.body_region == "PANCREAS"

    print("CASE STATE: PASS")

    # ---------------------------------------------------------
    # 4. Safety Contract
    # ---------------------------------------------------------
    contract = SafetyContract(
        contract_id=f"{CASE_ID}-CT4-REGRESSION",

        data_policy=DataPolicy(
            allowed_modalities=["CT"],
            allowed_body_regions=[
                "PANCREAS",
                "ABDOMEN",
            ],
            required_data=[
                "CT image series",
            ],
        ),

        approved_tools=[
            "pancreas_tumor_segmentation"
        ],

        task_preconditions=[
            "CT modality confirmed",
            "Pancreas/abdomen body region confirmed",
            "Valid CT series available",
        ],

        operation_policy=OperationPolicy(
            allowed_operations=[
                "analyze",
                "segment",
                "generate_evidence",
            ],
            maximum_action_tier="T1",
        ),

        uncertainty_policy=UncertaintyPolicy(
            minimum_confidence=0.5,
            require_verification=True,
            abstain_on_missing_evidence=True,
            abstain_on_verification_failure=True,
        ),

        escalation_policy=EscalationPolicy(
            escalation_paths=[
                "human_clinical_review"
            ],
            human_review_required=True,
        ),

        resource_policy=ResourcePolicy(
            maximum_retries=0,
            timeout_seconds=300,
            maximum_concurrent_tools=1,
        ),
    )

    case.safety_contract = contract

    assert contract.is_tool_permitted(
        "pancreas_tumor_segmentation"
    )

    print("TOOL PERMISSION: PASS")

    # ---------------------------------------------------------
    # 5. CT-4 execution
    # ---------------------------------------------------------
    result = tool.run(
        {
            "modality": "CT",
            "body_region": "PANCREAS",
            "series_dir": str(SERIES_DIR),
        }
    )

    assert isinstance(result, dict)

    assert result["tool_name"] == (
        "pancreas_tumor_segmentation"
    )

    assert result["model_name"] == (
        "MONAI Pancreas and Tumor DiNTS Segmentation"
    )

    print("CT-4 EXECUTION: PASS")

    # ---------------------------------------------------------
    # 6. Output structure regression
    # ---------------------------------------------------------
    assert "prediction" in result
    assert "input_shape" in result
    assert "resampled_shape" in result
    assert "label_summary" in result
    assert "voxel_spacing" in result
    assert "provenance" in result

    label_summary = result["label_summary"]

    # Background and pancreas are valid expected labels.
    assert "background" in label_summary
    assert "pancreas" in label_summary

    # Pancreatic tumor is an allowed label, but it does not
    # have to appear if the model predicts zero tumor voxels
    # in the controlled crop.
    valid_labels = {
        "background",
        "pancreas",
        "pancreatic_tumor",
    }

    assert set(
        label_summary.keys()
    ).issubset(valid_labels)

    assert all(
        isinstance(value, int) and value >= 0
        for value in label_summary.values()
    )

    assert result["verification_required"] is True

    assert result["clinical_use"] == (
        "research_demo_only"
    )

    print("OUTPUT STRUCTURE: PASS")

    # ---------------------------------------------------------
    # 7. Safety boundary regression
    # ---------------------------------------------------------
    warnings = result.get(
        "warnings",
        [],
    )

    warning_text = " ".join(
        warnings
    ).lower()

    assert (
        "not clinically validated"
        in warning_text
    )

    assert (
        "not a diagnosis"
        in warning_text
    )

    assert (
        "human clinical verification is required"
        in warning_text
    )

    print("CLINICAL SAFETY BOUNDARY: PASS")

    # ---------------------------------------------------------
    # 8. Prepare verifier input
    #
    # CT4VerificationEngine.verify() expects:
    #
    # {
    #     "ct_metadata": {...},
    #     "segmentation_result": {...}
    # }
    #
    # The verifier itself owns the verification logic.
    # ---------------------------------------------------------

    ct_metadata = {
        "modality": "CT",
        "body_region": "PANCREAS",
        "slice_count": len(dicom_files),
        "voxel_spacing": result.get(
            "voxel_spacing"
        ),
        "series_identity": {
            "case_id": CASE_ID,
        },
    }

    segmentation_result = {
        "tool_name": result.get(
        "tool_name"
        ),
        "model_name": result.get(
        "model_name"
        ),
        "model_version": result.get(
            "model_version"
        ),
        "input_shape": result.get(
        "input_shape"
    ),
    "resampled_shape": result.get(
        "resampled_shape"
    ),
    "label_summary": result.get(
        "label_summary"
    ),
    "prediction": result.get(
        "prediction"
    ),
    "verification_required": result.get(
        "verification_required"
    ),
    "clinical_use": result.get(
        "clinical_use"
    ),
    "warnings": result.get(
        "warnings",
        [],
    ),
    "provenance": result.get(
        "provenance"
    ),
}

    verifier_input = {
    "ct_metadata": ct_metadata,
    "segmentation_result": segmentation_result,
}

    # 9. CT-4 verification
    # ---------------------------------------------------------
    verifier = CT4VerificationEngine()

    verification = verifier.verify(
        verifier_input
    )

    assert isinstance(
        verification,
        dict,
    )

    assert verification.get(
        "status"
    ) == "completed"

    print("VERIFICATION: PASS")

    # ---------------------------------------------------------
    # 10. Verification structure
    # ---------------------------------------------------------
    assert "verification" in verification
    assert "decision" in verification
    assert "safety" in verification

    verification_block = verification[
        "verification"
    ]

    decision = verification[
        "decision"
    ]

    safety = verification[
        "safety"
    ]

    assert isinstance(
        verification_block,
        dict,
    )

    assert isinstance(
        decision,
        dict,
    )

    assert isinstance(
        safety,
        dict,
    )

    print("VERIFICATION STRUCTURE: PASS")

    # ---------------------------------------------------------
    # 11. Human review boundary
    # ---------------------------------------------------------
    assert (
        safety["human_review_required"]
        is True
    )

    assert (
        safety["clinical_diagnosis"]
        is False
    )

    assert (
        safety["treatment_authorized"]
        is False
    )

    assert (
        safety["irreversible_action_authorized"]
        is False
    )

    print("HUMAN REVIEW BOUNDARY: PASS")

    # ---------------------------------------------------------
    # 12. No autonomous clinical conclusion
    # ---------------------------------------------------------
    assert decision["status"] in {
        "verified_for_workflow_review",
        "requires_review",
        "blocked",
    }

    assert decision["action"] in {
        "proceed_to_human_review",
        "escalate_to_human",
    }

    print(
        "NO AUTONOMOUS CLINICAL CONCLUSION: PASS"
    )

    # ---------------------------------------------------------
    # Final
    # ---------------------------------------------------------
    print()
    print("=" * 60)
    print("CT-4 REGRESSION TEST: PASS")
    print("=" * 60)


if __name__ == "__main__":
    main()