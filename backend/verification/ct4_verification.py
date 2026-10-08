from typing import Any, Dict, List, Tuple


class CT4VerificationEngine:
    """
    Verification layer for the CT-4 pancreas and pancreatic
    tumor segmentation workflow.

    This verifier does NOT perform diagnosis.

    Its responsibility is to check whether:
    1. The CT input is applicable.
    2. Required metadata is available.
    3. The CT-4 tool completed successfully.
    4. The segmentation output is structurally usable.
    5. The output remains explicitly research/demo evidence.
    6. The result should proceed to human review or be blocked.

    Important:
        This is a research/demo verification layer.
        It does not provide clinical validation.
    """

    name = "ct4_verification"

    def __init__(self):
        """
        Initialize the CT-4 verification engine.
        """
        pass

    # ==================================================================
    # INPUT VALIDATION
    # ==================================================================

    def _validate_input(
        self,
        input_data: Dict[str, Any],
    ) -> Tuple[
        Dict[str, Any],
        Dict[str, Any],
    ]:
        """
        Validate verifier input.
        """

        if not isinstance(input_data, dict):
            raise ValueError(
                "Verifier input must be a dictionary."
            )

        if "ct_metadata" not in input_data:
            raise ValueError(
                "Verifier input must contain 'ct_metadata'."
            )

        if "segmentation_result" not in input_data:
            raise ValueError(
                "Verifier input must contain "
                "'segmentation_result'."
            )

        ct_metadata = input_data["ct_metadata"]
        segmentation_result = input_data[
            "segmentation_result"
        ]

        if not isinstance(ct_metadata, dict):
            raise ValueError(
                "'ct_metadata' must be a dictionary."
            )

        if not isinstance(
            segmentation_result,
            dict,
        ):
            raise ValueError(
                "'segmentation_result' must be a dictionary."
            )

        return (
            ct_metadata,
            segmentation_result,
        )

    # ==================================================================
    # CT INPUT CHECKS
    # ==================================================================

    def _check_modality(
        self,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Confirm that the input modality is CT.
        """

        modality = str(
            metadata.get(
                "modality",
                "",
            )
        ).upper()

        if modality == "CT":
            return {
                "status": "passed",
                "message": "CT modality confirmed.",
            }

        return {
            "status": "failed",
            "message": (
                "Input modality is not confirmed as CT."
            ),
        }

    def _check_body_region(
        self,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Check that the CT body region is compatible
        with the pancreas/tumor segmentation task.
        """

        body_region = str(
            metadata.get(
                "body_region",
                "",
            )
        ).upper()

        allowed_regions = {
            "PANCREAS",
            "ABDOMEN",
            "ABDOMINAL",
        }

        if body_region in allowed_regions:
            return {
                "status": "passed",
                "body_region": body_region,
                "message": (
                    "CT body region is compatible "
                    "with CT-4."
                ),
            }

        return {
            "status": "failed",
            "body_region": body_region or None,
            "message": (
                "CT body region is not confirmed "
                "as compatible with CT-4."
            ),
        }

    def _check_slice_count(
        self,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Confirm that the input series contains slices.
        """

        slice_count = metadata.get(
            "slice_count"
        )

        if slice_count is None:
            return {
                "status": "failed",
                "message": (
                    "CT slice count is unavailable."
                ),
            }

        try:
            slice_count = int(slice_count)
        except (
            TypeError,
            ValueError,
        ):
            return {
                "status": "failed",
                "message": (
                    "CT slice count is invalid."
                ),
            }

        if slice_count < 1:
            return {
                "status": "failed",
                "slice_count": slice_count,
                "message": (
                    "CT series contains no valid slices."
                ),
            }

        return {
            "status": "passed",
            "slice_count": slice_count,
            "message": (
                "CT series contains valid slice data."
            ),
        }

    def _check_voxel_spacing(
        self,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Validate Z/Y/X voxel spacing.

        Spacing is expected to follow the project convention:

            (Z, Y, X)
        """

        spacing = metadata.get(
            "voxel_spacing"
        )

        if spacing is None:
            return {
                "status": "failed",
                "message": (
                    "Voxel spacing is unavailable."
                ),
            }

        if not isinstance(
            spacing,
            (list, tuple),
        ):
            return {
                "status": "failed",
                "message": (
                    "Voxel spacing must contain "
                    "three values."
                ),
            }

        if len(spacing) != 3:
            return {
                "status": "failed",
                "message": (
                    "Voxel spacing must contain "
                    "Z, Y, and X values."
                ),
            }

        try:
            values = [
                float(value)
                for value in spacing
            ]
        except (
            TypeError,
            ValueError,
        ):
            return {
                "status": "failed",
                "message": (
                    "Voxel spacing contains invalid values."
                ),
            }

        if any(
            value <= 0
            for value in values
        ):
            return {
                "status": "failed",
                "voxel_spacing": values,
                "message": (
                    "Voxel spacing must contain "
                    "positive values."
                ),
            }

        return {
            "status": "passed",
            "voxel_spacing": values,
            "message": (
                "Voxel spacing is valid."
            ),
        }

    def _check_series_identity(
        self,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Confirm study and series identifiers exist
        for provenance.
        """

        study_uid = metadata.get(
            "study_instance_uid"
        )

        series_uid = metadata.get(
            "series_instance_uid"
        )

        missing: List[str] = []

        if not study_uid:
            missing.append(
                "study_instance_uid"
            )

        if not series_uid:
            missing.append(
                "series_instance_uid"
            )

        if missing:
            return {
                "status": "failed",
                "missing": missing,
                "message": (
                    "Required DICOM identity information "
                    "is missing."
                ),
            }

        return {
            "status": "passed",
            "study_instance_uid": study_uid,
            "series_instance_uid": series_uid,
            "message": (
                "Study and series identity information "
                "is available."
            ),
        }

    # ==================================================================
    # SEGMENTATION RESULT CHECKS
    # ==================================================================

    def _check_tool_completion(
        self,
        result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Confirm that CT-4 completed successfully.
        """

        if result.get("tool_name") != (
            "pancreas_tumor_segmentation"
        ):
            return {
                "status": "failed",
                "message": (
                    "Segmentation result does not "
                    "identify the CT-4 tool."
                ),
            }

        return {
            "status": "passed",
            "message": (
                "CT-4 tool identity is confirmed."
            ),
        }

    def _check_output_shape(
        self,
        result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Confirm that the controlled model input
        has the expected 96x96x96 shape.
        """

        input_shape = result.get(
            "input_shape"
        )

        expected_shape = [
            1,
            1,
            96,
            96,
            96,
        ]

        if input_shape != expected_shape:
            return {
                "status": "failed",
                "input_shape": input_shape,
                "expected_shape": expected_shape,
                "message": (
                    "CT-4 input shape does not "
                    "match the expected controlled "
                    "96x96x96 model input."
                ),
            }

        return {
            "status": "passed",
            "input_shape": input_shape,
            "message": (
                "CT-4 controlled model input shape "
                "is valid."
            ),
        }

    def _check_label_summary(
        self,
        result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Check whether the segmentation output contains
        the expected label summary.

        Labels:
            0 = background
            1 = pancreas
            2 = pancreatic tumor
        """

        label_summary = result.get(
            "label_summary"
        )

        if not isinstance(
            label_summary,
            dict,
        ):
            return {
                "status": "failed",
                "message": (
                    "CT-4 label summary is unavailable."
                ),
            }

        allowed_labels = {
            "background",
            "pancreas",
            "pancreatic_tumor",
        }

        unexpected = [
            key
            for key in label_summary.keys()
            if key not in allowed_labels
        ]

        if unexpected:
            return {
                "status": "failed",
                "unexpected_labels": unexpected,
                "message": (
                    "CT-4 produced unexpected "
                    "segmentation labels."
                ),
            }

        return {
            "status": "passed",
            "label_summary": label_summary,
            "message": (
                "CT-4 segmentation label structure "
                "is valid."
            ),
        }

    def _check_research_boundary(
        self,
        result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Confirm that the tool explicitly preserves
        the research/demo safety boundary.
        """

        clinical_use = result.get(
            "clinical_use"
        )

        verification_required = result.get(
            "verification_required"
        )

        if clinical_use != "research_demo_only":
            return {
                "status": "failed",
                "clinical_use": clinical_use,
                "message": (
                    "CT-4 clinical-use boundary "
                    "is not explicitly research-only."
                ),
            }

        if verification_required is not True:
            return {
                "status": "failed",
                "message": (
                    "CT-4 does not explicitly require "
                    "human verification."
                ),
            }

        return {
            "status": "passed",
            "clinical_use": clinical_use,
            "verification_required": (
                verification_required
            ),
            "message": (
                "CT-4 research-only and verification "
                "boundaries are preserved."
            ),
        }

    # ==================================================================
    # DECISION
    # ==================================================================

    def _build_decision(
        self,
        checks: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Convert verification checks into a bounded
        workflow decision.

        Verification never authorizes diagnosis,
        treatment, or irreversible action.
        """

        failed_checks: List[str] = []

        for name, result in checks.items():

            if result.get("status") == "failed":
                failed_checks.append(name)

        if failed_checks:
            return {
                "status": "blocked",
                "action": "escalate_to_human",
                "human_review_required": True,
                "reason": (
                    "One or more required CT-4 "
                    "verification checks failed."
                ),
                "failed_checks": failed_checks,
            }

        return {
            "status": "verified_for_workflow_review",
            "action": "proceed_to_human_review",
            "human_review_required": True,
            "reason": (
                "CT-4 verification checks passed. "
                "Human review remains required."
            ),
            "failed_checks": [],
        }

    # ==================================================================
    # COMPLETE VERIFICATION
    # ==================================================================

    def verify(
        self,
        input_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Run the complete CT-4 verification process.
        """

        (
            ct_metadata,
            segmentation_result,
        ) = self._validate_input(
            input_data
        )

        checks = {
            "modality": self._check_modality(
                ct_metadata
            ),

            "body_region": self._check_body_region(
                ct_metadata
            ),

            "slice_count": self._check_slice_count(
                ct_metadata
            ),

            "voxel_spacing": self._check_voxel_spacing(
                ct_metadata
            ),

            "series_identity": self._check_series_identity(
                ct_metadata
            ),

            "tool_completion": self._check_tool_completion(
                segmentation_result
            ),

            "output_shape": self._check_output_shape(
                segmentation_result
            ),

            "label_summary": self._check_label_summary(
                segmentation_result
            ),

            "research_boundary": self._check_research_boundary(
                segmentation_result
            ),
        }

        decision = self._build_decision(
            checks
        )

        return {
            "verifier": self.name,
            "status": "completed",

            "verification": {
                "checks": checks,

                "all_required_checks_passed": (
                    not any(
                        result.get("status")
                        == "failed"
                        for result in checks.values()
                    )
                ),
            },

            "decision": decision,

            "safety": {
                "clinical_diagnosis": False,
                "treatment_authorized": False,
                "irreversible_action_authorized": False,
                "human_review_required": True,
            },
        }