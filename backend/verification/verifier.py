from typing import Any, Dict, List, Tuple


class ICHVerificationEngine:
    """
    Verification layer for the ICH detection workflow.

    This layer does NOT perform diagnosis.

    Its responsibility is to check whether:
    1. The CT input is applicable.
    2. Required metadata is available.
    3. The detection tool completed successfully.
    4. The model produced usable evidence.
    5. The result should proceed or require human review.

    Important:
        This is a research/demo verification layer.
        It does not provide clinical validation.
    """

    name = "ich_verification"

    # Prototype threshold.
    #
    # This is NOT a clinically validated threshold.
    MIN_CONFIDENCE = 0.50

    # Extremely coarse slices can affect interpretation.
    # This is therefore treated as a warning rather than
    # an automatic rejection in the prototype.
    COARSE_SLICE_THRESHOLD_MM = 3.0

    def __init__(
        self,
        min_confidence: float = MIN_CONFIDENCE,
    ):
        """
        Initialize the verification engine.

        Parameters
        ----------
        min_confidence:
            Prototype probability threshold used to decide
            whether model evidence is sufficiently strong
            for further workflow review.

            This is not a clinical threshold.
        """

        if not 0.0 <= min_confidence <= 1.0:
            raise ValueError(
                "min_confidence must be between 0 and 1."
            )

        self.min_confidence = min_confidence

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
        Validate the overall verifier input.
        """

        if not isinstance(input_data, dict):
            raise ValueError(
                "Verifier input must be a dictionary."
            )

        if "ct_metadata" not in input_data:
            raise ValueError(
                "Verifier input must contain "
                "'ct_metadata'."
            )

        if "detection_result" not in input_data:
            raise ValueError(
                "Verifier input must contain "
                "'detection_result'."
            )

        ct_metadata = input_data["ct_metadata"]

        detection_result = input_data[
            "detection_result"
        ]

        if not isinstance(
            ct_metadata,
            dict,
        ):
            raise ValueError(
                "'ct_metadata' must be a dictionary."
            )

        if not isinstance(
            detection_result,
            dict,
        ):
            raise ValueError(
                "'detection_result' must be a dictionary."
            )

        return (
            ct_metadata,
            detection_result,
        )

    # ==================================================================
    # CT INPUT CHECKS
    # ==================================================================

    def _check_modality(
        self,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Check whether the supplied study is CT.
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
                "modality": modality,
                "message": "CT modality confirmed.",
            }

        return {
            "status": "failed",
            "modality": modality or None,
            "message": (
                "Input modality is not confirmed "
                "as CT."
            ),
        }

    def _check_slice_count(
        self,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Check whether the series contains valid slices.
        """

        slice_count = metadata.get(
            "slice_count"
        )

        if slice_count is None:
            return {
                "status": "failed",
                "slice_count": None,
                "message": (
                    "CT slice count is unavailable."
                ),
            }

        try:
            slice_count = int(
                slice_count
            )
        except (
            TypeError,
            ValueError,
        ):
            return {
                "status": "failed",
                "slice_count": slice_count,
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
        Check voxel spacing.

        The spacing is recorded for verification
        and provenance.

        A coarse slice spacing produces a warning,
        not an automatic rejection, in this prototype.
        """

        spacing = metadata.get(
            "voxel_spacing"
        )

        if spacing is None:
            return {
                "status": "failed",
                "voxel_spacing": None,
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
                "voxel_spacing": spacing,
                "message": (
                    "Voxel spacing must contain "
                    "three values."
                ),
            }

        if len(spacing) != 3:
            return {
                "status": "failed",
                "voxel_spacing": list(spacing),
                "message": (
                    "Voxel spacing must contain "
                    "slice, row, and column spacing."
                ),
            }

        try:
            slice_spacing = float(
                spacing[0]
            )

            row_spacing = float(
                spacing[1]
            )

            column_spacing = float(
                spacing[2]
            )

        except (
            TypeError,
            ValueError,
        ):
            return {
                "status": "failed",
                "voxel_spacing": list(spacing),
                "message": (
                    "Voxel spacing contains "
                    "invalid values."
                ),
            }

        values = [
            slice_spacing,
            row_spacing,
            column_spacing,
        ]

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

        warnings: List[str] = []

        if (
            slice_spacing
            > self.COARSE_SLICE_THRESHOLD_MM
        ):
            warnings.append(
                (
                    "Slice spacing is coarse "
                    f"({slice_spacing} mm)."
                )
            )

        if warnings:
            return {
                "status": "warning",
                "voxel_spacing": values,
                "message": (
                    "Voxel spacing is valid "
                    "but requires attention."
                ),
                "warnings": warnings,
            }

        return {
            "status": "passed",
            "voxel_spacing": values,
            "message": (
                "Voxel spacing is valid."
            ),
            "warnings": [],
        }

    def _check_series_identity(
        self,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Check that study and series identifiers
        are available for provenance.
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
                "study_instance_uid": study_uid,
                "series_instance_uid": series_uid,
                "message": (
                    "Required DICOM identity "
                    "information is missing."
                ),
                "missing": missing,
            }

        return {
            "status": "passed",
            "study_instance_uid": study_uid,
            "series_instance_uid": series_uid,
            "message": (
                "Study and series identity "
                "information is available."
            ),
        }

    # ==================================================================
    # DETECTION RESULT CHECKS
    # ==================================================================

    def _check_detection_result(
        self,
        detection_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Check whether the ICH detection tool
        produced a usable result.
        """

        status = detection_result.get(
            "status"
        )

        if status != "completed":
            return {
                "status": "failed",
                "message": (
                    "ICH detection tool did not "
                    "complete successfully."
                ),
            }

        prediction = detection_result.get(
            "prediction"
        )

        if not isinstance(
            prediction,
            dict,
        ):
            return {
                "status": "failed",
                "message": (
                    "ICH detection prediction "
                    "data is unavailable."
                ),
            }

        if (
            "any_probability"
            not in prediction
        ):
            return {
                "status": "failed",
                "message": (
                    "ICH detection result does not "
                    "contain an any-hemorrhage probability."
                ),
            }

        try:
            probability = float(
                prediction[
                    "any_probability"
                ]
            )

        except (
            TypeError,
            ValueError,
        ):
            return {
                "status": "failed",
                "message": (
                    "ICH probability is invalid."
                ),
            }

        if not 0.0 <= probability <= 1.0:
            return {
                "status": "failed",
                "probability": probability,
                "message": (
                    "ICH probability is outside "
                    "the valid range."
                ),
            }

        return {
            "status": "passed",
            "probability": probability,
            "message": (
                "ICH detection result is "
                "available and valid."
            ),
        }

    def _check_evidence(
        self,
        detection_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Check whether model evidence is available.

        Evidence includes:
        - Model identity
        - Model classes
        - Supporting slices
        """

        evidence = detection_result.get(
            "evidence"
        )

        series = detection_result.get(
            "series"
        )

        problems: List[str] = []

        if not isinstance(
            evidence,
            dict,
        ):
            problems.append(
                "model evidence metadata is missing"
            )

        if not isinstance(
            series,
            dict,
        ):
            problems.append(
                "series evidence is missing"
            )

        supporting_slices = None

        if isinstance(
            series,
            dict,
        ):
            supporting_slices = series.get(
                "supporting_slices"
            )

        if not supporting_slices:
            problems.append(
                "supporting slice evidence is unavailable"
            )

        if problems:
            return {
                "status": "warning",
                "message": (
                    "Detection completed, but "
                    "evidence is incomplete."
                ),
                "problems": problems,
            }

        return {
            "status": "passed",
            "message": (
                "Model and slice-level evidence "
                "are available."
            ),
        }

    def _check_confidence(
        self,
        detection_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Apply the prototype confidence check.

        This does NOT represent clinical validation.
        """

        prediction = detection_result.get(
            "prediction",
            {},
        )

        if not isinstance(
            prediction,
            dict,
        ):
            return {
                "status": "failed",
                "probability": None,
                "message": (
                    "Confidence cannot be evaluated "
                    "because prediction data is invalid."
                ),
            }

        probability = prediction.get(
            "any_probability"
        )

        if probability is None:
            return {
                "status": "failed",
                "probability": None,
                "message": (
                    "Confidence cannot be evaluated."
                ),
            }

        try:
            probability = float(
                probability
            )

        except (
            TypeError,
            ValueError,
        ):
            return {
                "status": "failed",
                "probability": None,
                "message": (
                    "Confidence probability is invalid."
                ),
            }

        if not 0.0 <= probability <= 1.0:
            return {
                "status": "failed",
                "probability": probability,
                "message": (
                    "Confidence probability is "
                    "outside the valid range."
                ),
            }

        if (
            probability
            >= self.min_confidence
        ):
            return {
                "status": "passed",
                "probability": probability,
                "threshold": self.min_confidence,
                "message": (
                    "Model probability exceeds "
                    "the prototype verification threshold."
                ),
            }

        return {
            "status": "warning",
            "probability": probability,
            "threshold": self.min_confidence,
            "message": (
                "Model probability does not "
                "exceed the prototype threshold."
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
        Convert verification checks into
        a bounded workflow decision.

        The verifier never authorizes treatment
        or irreversible clinical actions.
        """

        failed_checks: List[str] = []
        warning_checks: List[str] = []

        for name, result in checks.items():

            status = result.get(
                "status"
            )

            if status == "failed":
                failed_checks.append(
                    name
                )

            elif status == "warning":
                warning_checks.append(
                    name
                )

        # --------------------------------------------------------------
        # Failed checks
        # --------------------------------------------------------------

        if failed_checks:
            return {
                "status": "blocked",
                "action": "escalate_to_human",
                "human_review_required": True,
                "reason": (
                    "One or more required verification "
                    "checks failed."
                ),
                "failed_checks": failed_checks,
                "warning_checks": warning_checks,
            }

        # --------------------------------------------------------------
        # Warnings
        # --------------------------------------------------------------

        if warning_checks:
            return {
                "status": "requires_review",
                "action": "escalate_to_human",
                "human_review_required": True,
                "reason": (
                    "Verification completed with "
                    "warnings requiring human review."
                ),
                "failed_checks": [],
                "warning_checks": warning_checks,
            }

        # --------------------------------------------------------------
        # All checks passed
        # --------------------------------------------------------------

        return {
            "status": "verified_for_workflow_review",
            "action": "proceed_to_human_review",
            "human_review_required": True,
            "reason": (
                "Verification checks passed. "
                "Human review remains required."
            ),
            "failed_checks": [],
            "warning_checks": [],
        }

    # ==================================================================
    # COMPLETE VERIFICATION
    # ==================================================================

    def verify(
        self,
        input_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Run the complete verification process.

        Input:

            {
                "ct_metadata": {...},
                "detection_result": {...}
            }

        Output:

            {
                "verifier": "...",
                "status": "completed",
                "verification": {...},
                "decision": {...},
                "safety": {...}
            }
        """

        (
            ct_metadata,
            detection_result,
        ) = self._validate_input(
            input_data
        )

        # --------------------------------------------------------------
        # Run individual checks
        # --------------------------------------------------------------

        modality_check = (
            self._check_modality(
                ct_metadata
            )
        )

        slice_count_check = (
            self._check_slice_count(
                ct_metadata
            )
        )

        spacing_check = (
            self._check_voxel_spacing(
                ct_metadata
            )
        )

        identity_check = (
            self._check_series_identity(
                ct_metadata
            )
        )

        detection_check = (
            self._check_detection_result(
                detection_result
            )
        )

        evidence_check = (
            self._check_evidence(
                detection_result
            )
        )

        confidence_check = (
            self._check_confidence(
                detection_result
            )
        )

        # --------------------------------------------------------------
        # Collect checks
        # --------------------------------------------------------------

        checks = {
            "modality": modality_check,
            "slice_count": slice_count_check,
            "voxel_spacing": spacing_check,
            "series_identity": identity_check,
            "detection_result": detection_check,
            "evidence": evidence_check,
            "confidence": confidence_check,
        }

        # --------------------------------------------------------------
        # Build bounded workflow decision
        # --------------------------------------------------------------

        decision = self._build_decision(
            checks
        )

        # --------------------------------------------------------------
        # Return complete verification result
        # --------------------------------------------------------------

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

                "warnings_present": (
                    any(
                        result.get("status")
                        == "warning"
                        for result in checks.values()
                    )
                ),
            },

            "decision": decision,

            # ----------------------------------------------------------
            # Explicit authority boundary
            # ----------------------------------------------------------

            "safety": {
                "clinical_diagnosis": False,
                "treatment_authorized": False,
                "irreversible_action_authorized": False,
                "human_review_required": True,
            },
        }