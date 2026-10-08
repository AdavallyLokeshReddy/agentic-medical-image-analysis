from __future__ import annotations

from typing import Any, Dict


class CT5VerificationEngine:
    """
    Verification engine for the governed CT-5
    whole-body CT segmentation workflow.

    This verifier checks:

    1. CT modality applicability.
    2. Whole-body CT applicability.
    3. Required CT metadata.
    4. CT series identity.
    5. CT-5 tool identity.
    6. CT-5 model identity and version.
    7. Segmentation prediction structure.
    8. Segmentation label range.
    9. Segmentation label-summary structure.
    10. Verification requirement.
    11. Research/demo clinical-use boundary.

    This verifier does NOT determine clinical correctness.

    A successful verification only means that the result is
    structurally suitable to proceed to human workflow review.

    It does NOT authorize:
        - autonomous diagnosis
        - autonomous treatment
        - irreversible clinical action
    """

    # =========================================================
    # CT-5 IDENTITY
    # =========================================================

    TOOL_NAME = "whole_body_segmentation"

    MODEL_NAME = "MONAI wholeBody_ct_segmentation"

    MODEL_VERSION = "0.2.7"

    EXPECTED_LABEL_COUNT = 105

    EXPECTED_LABEL_IDS = set(range(105))

    # =========================================================
    # MAIN VERIFICATION
    # =========================================================

    def verify(
        self,
        verifier_input: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Run the complete CT-5 verification process.

        Parameters
        ----------
        verifier_input:
            Dictionary containing:

                {
                    "ct_metadata": {...},
                    "segmentation_result": {...}
                }

        Returns
        -------
        Dict[str, Any]
            Structured verification result.
        """

        checks = []
        failed_checks = []
        warnings = []

        # =====================================================
        # INPUT EXTRACTION
        # =====================================================

        if not isinstance(
            verifier_input,
            dict,
        ):
            return {
                "verifier": self.__class__.__name__,
                "tool": self.TOOL_NAME,
                "model": self.MODEL_NAME,
                "model_version": self.MODEL_VERSION,
                "decision": "blocked",
                "next_step": "escalate_to_human",
                "checks": [],
                "failed_checks": [
                    "Verifier input must be a dictionary."
                ],
                "warnings": [
                    "CT-5 verification could not be completed."
                ],
                "human_review_required": True,
                "safety": {
                    "autonomous_diagnosis": False,
                    "autonomous_treatment": False,
                    "irreversible_action": False,
                },
            }

        ct_metadata = verifier_input.get(
            "ct_metadata"
        )

        segmentation_result = verifier_input.get(
            "segmentation_result"
        )

        # =====================================================
        # CT INPUT VALIDATION
        # =====================================================

        if not isinstance(
            ct_metadata,
            dict,
        ):
            failed_checks.append(
                "ct_metadata is missing or invalid."
            )

        else:

            # -------------------------------------------------
            # Modality
            # -------------------------------------------------

            modality = str(
                ct_metadata.get(
                    "modality",
                    "",
                )
            ).upper()

            if modality == "CT":
                checks.append(
                    "CT modality confirmed."
                )
            else:
                failed_checks.append(
                    "Input modality must be CT."
                )

            # -------------------------------------------------
            # Body region
            # -------------------------------------------------

            body_region = str(
                ct_metadata.get(
                    "body_region",
                    "",
                )
            ).lower()

            allowed_body_regions = {
                "whole_body",
                "whole-body",
                "body",
            }

            if body_region in allowed_body_regions:
                checks.append(
                    "Whole-body CT region confirmed."
                )
            else:
                failed_checks.append(
                    "Body region must be compatible with CT-5."
                )

            # -------------------------------------------------
            # Slice count
            # -------------------------------------------------

            slice_count = ct_metadata.get(
                "slice_count"
            )

            if (
                isinstance(
                    slice_count,
                    int,
                )
                and slice_count > 0
            ):
                checks.append(
                    "CT slice count is valid."
                )
            else:
                failed_checks.append(
                    "CT slice count must be a positive integer."
                )

            # -------------------------------------------------
            # Voxel spacing
            # -------------------------------------------------

            voxel_spacing = ct_metadata.get(
                "voxel_spacing"
            )

            if (
                isinstance(
                    voxel_spacing,
                    (tuple, list),
                )
                and len(voxel_spacing) == 3
            ):
                try:
                    spacing_values = [
                        float(value)
                        for value in voxel_spacing
                    ]

                    if all(
                        value > 0
                        for value in spacing_values
                    ):
                        checks.append(
                            "Voxel spacing is valid."
                        )
                    else:
                        failed_checks.append(
                            "Voxel spacing must contain "
                            "three positive values."
                        )

                except (
                    TypeError,
                    ValueError,
                ):
                    failed_checks.append(
                        "Voxel spacing contains invalid values."
                    )

            else:
                failed_checks.append(
                    "Voxel spacing must contain three values."
                )

            # -------------------------------------------------
            # Study identity
            # -------------------------------------------------

            if ct_metadata.get(
                "study_instance_uid"
            ):
                checks.append(
                    "Study identity is present."
                )
            else:
                failed_checks.append(
                    "StudyInstanceUID is missing."
                )

            # -------------------------------------------------
            # Series identity
            # -------------------------------------------------

            if ct_metadata.get(
                "series_instance_uid"
            ):
                checks.append(
                    "Series identity is present."
                )
            else:
                failed_checks.append(
                    "SeriesInstanceUID is missing."
                )

        # =====================================================
        # SEGMENTATION RESULT VALIDATION
        # =====================================================

        if not isinstance(
            segmentation_result,
            dict,
        ):
            failed_checks.append(
                "Segmentation result is missing or invalid."
            )

        else:

            # -------------------------------------------------
            # Tool identity
            # -------------------------------------------------

            tool = segmentation_result.get(
                "tool"
            )

            tool_name = segmentation_result.get(
                "tool_name"
            )

            if (
                tool == self.TOOL_NAME
                or tool_name == self.TOOL_NAME
            ):
                checks.append(
                    "CT-5 tool identity confirmed."
                )
            else:
                failed_checks.append(
                    "Segmentation result came from "
                    "an unexpected tool."
                )

            # -------------------------------------------------
            # Model identity
            # -------------------------------------------------

            model_name = segmentation_result.get(
                "model_name"
            )

            if model_name == self.MODEL_NAME:
                checks.append(
                    "CT-5 model identity confirmed."
                )
            else:
                failed_checks.append(
                    "Segmentation result has unexpected "
                    "model identity."
                )

            # -------------------------------------------------
            # Model version
            # -------------------------------------------------

            model_version = segmentation_result.get(
                "model_version"
            )

            if model_version == self.MODEL_VERSION:
                checks.append(
                    "CT-5 model version confirmed."
                )
            else:
                failed_checks.append(
                    "Segmentation result has unexpected "
                    "model version."
                )

            # -------------------------------------------------
            # Prediction
            # -------------------------------------------------

            prediction = segmentation_result.get(
                "prediction"
            )

            if prediction is None:

                failed_checks.append(
                    "Segmentation prediction is missing."
                )

            else:

                shape = getattr(
                    prediction,
                    "shape",
                    None,
                )

                ndim = getattr(
                    prediction,
                    "ndim",
                    None,
                )

                if (
                    ndim == 3
                    and shape is not None
                    and all(
                        int(value) > 0
                        for value in shape
                    )
                ):
                    checks.append(
                        "Segmentation prediction has "
                        "a valid non-empty 3D shape."
                    )
                else:
                    failed_checks.append(
                        "Segmentation prediction must be "
                        "a non-empty 3D volume."
                    )

                # -------------------------------------------------
                # Prediction label range
                # -------------------------------------------------

                try:
                    import numpy as np

                    if not isinstance(
                        prediction,
                        np.ndarray,
                    ):
                        failed_checks.append(
                            "Segmentation prediction must "
                            "be a NumPy array."
                        )

                    elif prediction.ndim != 3:
                        failed_checks.append(
                            "Segmentation prediction must "
                            "be a 3D NumPy array."
                        )

                    elif prediction.size == 0:
                        failed_checks.append(
                            "Segmentation prediction is empty."
                        )

                    else:

                        unique_labels = set(
                            int(value)
                            for value in np.unique(
                                prediction
                            )
                        )

                        invalid_labels = sorted(
                            label
                            for label in unique_labels
                            if label
                            not in self.EXPECTED_LABEL_IDS
                        )

                        if invalid_labels:
                            failed_checks.append(
                                "Segmentation prediction contains "
                                "labels outside the valid 0-104 range."
                            )
                        else:
                            checks.append(
                                "Segmentation prediction labels "
                                "are within the valid 0-104 range."
                            )

                except Exception as exc:
                    failed_checks.append(
                        "Segmentation label validation failed: "
                        f"{type(exc).__name__}."
                    )

            # -------------------------------------------------
            # Label summary
            # -------------------------------------------------

            label_summary = segmentation_result.get(
                "label_summary"
            )

            if not isinstance(
                label_summary,
                dict,
            ):

                failed_checks.append(
                    "label_summary is missing or invalid."
                )

            else:

                invalid_summary_labels = []

                for key, value in label_summary.items():

                    # -----------------------------------------
                    # Label ID
                    # -----------------------------------------

                    try:
                        label_id = int(key)

                    except (
                        TypeError,
                        ValueError,
                    ):
                        invalid_summary_labels.append(
                            key
                        )
                        continue

                    if label_id not in self.EXPECTED_LABEL_IDS:
                        invalid_summary_labels.append(
                            label_id
                        )
                        continue

                    # -----------------------------------------
                    # Label object
                    # -----------------------------------------

                    if not isinstance(
                        value,
                        dict,
                    ):
                        invalid_summary_labels.append(
                            label_id
                        )
                        continue

                    # -----------------------------------------
                    # Required fields
                    # -----------------------------------------

                    required_fields = {
                        "label_id",
                        "name",
                        "voxel_count",
                    }

                    if not required_fields.issubset(
                        value.keys()
                    ):
                        invalid_summary_labels.append(
                            label_id
                        )
                        continue

                    # -----------------------------------------
                    # ID consistency
                    # -----------------------------------------

                    try:
                        if int(
                            value["label_id"]
                        ) != label_id:
                            invalid_summary_labels.append(
                                label_id
                            )
                            continue

                    except (
                        TypeError,
                        ValueError,
                    ):
                        invalid_summary_labels.append(
                            label_id
                        )
                        continue

                    # -----------------------------------------
                    # Voxel count
                    # -----------------------------------------

                    try:
                        voxel_count = int(
                            value["voxel_count"]
                        )

                        if voxel_count < 0:
                            invalid_summary_labels.append(
                                label_id
                            )

                    except (
                        TypeError,
                        ValueError,
                    ):
                        invalid_summary_labels.append(
                            label_id
                        )

                if invalid_summary_labels:

                    failed_checks.append(
                        "Segmentation label summary contains "
                        "invalid labels or structure."
                    )

                else:

                    checks.append(
                        "Segmentation label summary structure is valid."
                    )

            # -------------------------------------------------
            # Verification requirement
            # -------------------------------------------------

            if (
                segmentation_result.get(
                    "verification_required"
                )
                is True
            ):
                checks.append(
                    "Verification requirement is enforced."
                )
            else:
                failed_checks.append(
                    "verification_required must be True."
                )

            # -------------------------------------------------
            # Research-only boundary
            # -------------------------------------------------

            if (
                segmentation_result.get(
                    "clinical_use"
                )
                == "research_demo_only"
            ):
                checks.append(
                    "Research-only clinical boundary confirmed."
                )
            else:
                failed_checks.append(
                    "clinical_use must be research_demo_only."
                )

            # -------------------------------------------------
            # Safety warnings
            # -------------------------------------------------

            warnings.extend(
                [
                    "Whole-body segmentation output is not a diagnosis.",
                    "Human clinical verification is required before interpretation.",
                    "No autonomous treatment or irreversible clinical action is permitted.",
                    "The MONAI wholeBody_ct_segmentation model is a research/demo model.",
                ]
            )

        # =====================================================
        # FINAL DECISION
        # =====================================================

        if failed_checks:

            decision = "blocked"
            next_step = "escalate_to_human"
            human_review_required = True

        else:

            decision = "verified_for_workflow_review"
            next_step = "proceed_to_human_review"
            human_review_required = True

        # =====================================================
        # FINAL RESULT
        # =====================================================

        return {
            "verifier": self.__class__.__name__,
            "tool": self.TOOL_NAME,
            "model": self.MODEL_NAME,
            "model_version": self.MODEL_VERSION,
            "decision": decision,
            "next_step": next_step,
            "checks": checks,
            "failed_checks": failed_checks,
            "warnings": warnings,
            "human_review_required": human_review_required,
            "safety": {
                "autonomous_diagnosis": False,
                "autonomous_treatment": False,
                "irreversible_action": False,
            },
        }