from verification.ct2_verification import CT2VerificationEngine


def test_ct2_verification_passes_for_valid_result():

    verifier = CT2VerificationEngine()

    result = verifier.verify(
        {
            "ct_metadata": {
                "modality": "CT",
                "body_region": "CHEST",
                "slice_count": 80,
                "voxel_spacing": (
                    1.25,
                    0.703125,
                    0.703125,
                ),
                "series_instance_uid": (
                    "TEST-SERIES-001"
                ),
            },
            "detection_result": {
                "tool_name": (
                    "lung_nodule_detection"
                ),
                "model_name": (
                    "MONAI lung_nodule_ct_detection"
                ),
                "model_version": (
                    "MONAI-lung_nodule_ct_detection"
                ),
                "input_shape": (
                    80,
                    512,
                    512,
                ),
                "verification_required": True,
                "clinical_use": (
                    "research_demo_only"
                ),
                "prediction": [
                    {
                        "box": [],
                        "label": [],
                        "label_scores": [],
                    }
                ],
            },
        }
    )

    assert (
        result["decision"]
        == "verified_for_workflow_review"
    )

    assert (
        result["next_step"]
        == "proceed_to_human_review"
    )

    assert (
        result["failed_checks"]
        == []
    )

    assert (
        result["human_review_required"]
        is True
    )

    assert (
        result["safety"][
            "clinical_diagnosis_authorized"
        ]
        is False
    )

    assert (
        result["safety"][
            "treatment_authorized"
        ]
        is False
    )

    assert (
        result["safety"][
            "irreversible_action_authorized"
        ]
        is False
    )


def test_ct2_verification_blocks_wrong_modality():

    verifier = CT2VerificationEngine()

    result = verifier.verify(
        {
            "ct_metadata": {
                "modality": "MRI",
                "body_region": "CHEST",
                "slice_count": 80,
                "voxel_spacing": (
                    1.25,
                    0.703125,
                    0.703125,
                ),
            },
            "detection_result": {
                "tool_name": (
                    "lung_nodule_detection"
                ),
                "input_shape": (
                    80,
                    512,
                    512,
                ),
                "verification_required": True,
                "clinical_use": (
                    "research_demo_only"
                ),
                "prediction": [
                    {
                        "box": [],
                        "label": [],
                        "label_scores": [],
                    }
                ],
            },
        }
    )

    assert (
        result["decision"]
        == "blocked"
    )

    assert (
        "ct_modality"
        in result["failed_checks"]
    )

    assert (
        result["human_review_required"]
        is True
    )


def test_ct2_verification_blocks_missing_verification_requirement():

    verifier = CT2VerificationEngine()

    result = verifier.verify(
        {
            "ct_metadata": {
                "modality": "CT",
                "body_region": "CHEST",
                "slice_count": 80,
                "voxel_spacing": (
                    1.25,
                    0.703125,
                    0.703125,
                ),
            },
            "detection_result": {
                "tool_name": (
                    "lung_nodule_detection"
                ),
                "input_shape": (
                    80,
                    512,
                    512,
                ),
                "verification_required": False,
                "clinical_use": (
                    "research_demo_only"
                ),
                "prediction": [
                    {
                        "box": [],
                        "label": [],
                        "label_scores": [],
                    }
                ],
            },
        }
    )

    assert (
        result["decision"]
        == "blocked"
    )

    assert (
        "verification_required"
        in result["failed_checks"]
    )