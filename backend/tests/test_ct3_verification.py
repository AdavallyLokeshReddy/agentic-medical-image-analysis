import numpy as np

from verification.ct3_verification import (
    CT3VerificationEngine,
)


def make_valid_input():
    prediction = np.ones(
        (96, 96, 96),
        dtype=np.uint8,
    )

    return {
        "ct_metadata": {
            "modality": "CT",
            "body_region": "ABDOMEN",
            "slice_count": 218,
            "voxel_spacing": (
                1.0,
                0.858,
                0.858,
            ),
            "study_instance_uid": "STUDY-001",
            "series_instance_uid": "SERIES-001",
        },
        "segmentation_result": {
            "prediction": prediction,
            "label_summary": {
                "0": {
                    "label_id": 0,
                    "name": "background",
                    "voxel_count": 100,
                },
                "1": {
                    "label_id": 1,
                    "name": "spleen",
                    "voxel_count": 20,
                },
                "6": {
                    "label_id": 6,
                    "name": "liver",
                    "voxel_count": 30,
                },
            },
            "tool": "multi_organ_segmentation",
            "tool_version": "research-demo-1.0",
            "model_name": "SwinUNETR-BTCV",
            "model_version": "MONAI-BTCV-bundle",
            "verification_required": True,
            "clinical_use": "research_demo_only",
        },
    }


def test_ct3_valid_result_passes():
    verifier = CT3VerificationEngine()

    result = verifier.verify(
        make_valid_input()
    )

    assert result["decision"] == (
        "verified_for_workflow_review"
    )

    assert result["next_step"] == (
        "proceed_to_human_review"
    )

    assert result["human_review_required"] is True
    assert result["failed_checks"] == []

    assert result["safety"][
        "autonomous_diagnosis"
    ] is False

    assert result["safety"][
        "autonomous_treatment"
    ] is False

    assert result["safety"][
        "irreversible_action"
    ] is False


def test_ct3_wrong_modality_blocks():
    verifier = CT3VerificationEngine()

    data = make_valid_input()
    data["ct_metadata"]["modality"] = "MRI"

    result = verifier.verify(data)

    assert result["decision"] == "blocked"
    assert result["next_step"] == (
        "escalate_to_human"
    )
    assert result["human_review_required"] is True
    assert result["failed_checks"]


def test_ct3_wrong_body_region_blocks():
    verifier = CT3VerificationEngine()

    data = make_valid_input()
    data["ct_metadata"]["body_region"] = "CHEST"

    result = verifier.verify(data)

    assert result["decision"] == "blocked"
    assert result["next_step"] == (
        "escalate_to_human"
    )


def test_ct3_missing_verification_requirement_blocks():
    verifier = CT3VerificationEngine()

    data = make_valid_input()

    data["segmentation_result"][
        "verification_required"
    ] = False

    result = verifier.verify(data)

    assert result["decision"] == "blocked"
    assert result["human_review_required"] is True


def test_ct3_wrong_label_schema_blocks():
    verifier = CT3VerificationEngine()

    data = make_valid_input()

    data["segmentation_result"][
        "label_summary"
    ]["99"] = {
        "label_id": 99,
        "name": "unknown",
        "voxel_count": 10,
    }

    result = verifier.verify(data)

    assert result["decision"] == "blocked"
    assert result["failed_checks"]