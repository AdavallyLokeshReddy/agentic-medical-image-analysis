from typing import Any, Dict, List


class MRI1VerificationEngine:
    """
    Verification engine for MRI-1 Brain Tumor / Lesion Segmentation.

    This verifier checks whether the MRI-1 tool produced evidence that
    satisfies the technical, input-contract, output-contract, and
    research-governance requirements.

    It does NOT establish clinical validity or autonomous diagnostic authority.
    """

    TOOL_NAME = "brain_tumor_segmentation"
    TOOL_VERSION = "research-demo-1.0"

    MODEL_NAME = "MONAI BraTS MRI segmentation"
    MODEL_VERSION = "0.5.4"

    EXPECTED_REGIONS = {
        "tumor_core",
        "whole_tumor",
        "enhancing_tumor",
    }

    REQUIRED_SEQUENCES = {
        "T1C",
        "T1",
        "T2",
        "FLAIR",
    }

    EXPECTED_SPACING = (1.0, 1.0, 1.0)
    SPACING_TOLERANCE = 1e-4

    ALLOWED_BODY_REGIONS = {
        "brain",
        "head",
        "neuro",
        "neurological",
    }

    def _build_decision(
        self,
        failures: List[str],
        warnings: List[str],
    ) -> Dict[str, Any]:

        if failures:
            return {
                "verified": False,
                "decision": "blocked",
                "next_action": "escalate_to_human",
                "human_review_required": True,
                "safe_for_autonomous_diagnosis": False,
                "safe_for_autonomous_treatment": False,
                "safe_for_irreversible_action": False,
                "failures": failures,
                "warnings": warnings,
            }

        return {
            "verified": True,
            "decision": "verified_for_workflow_review",
            "next_action": "proceed_to_human_review",
            "human_review_required": True,
            "safe_for_autonomous_diagnosis": False,
            "safe_for_autonomous_treatment": False,
            "safe_for_irreversible_action": False,
            "failures": [],
            "warnings": warnings,
        }

    def _check_modality(
        self,
        metadata: Dict[str, Any],
        failures: List[str],
    ) -> None:

        modality = str(
            metadata.get("modality", "")
        ).strip().upper()

        if modality != "MRI":
            failures.append(
                f"Expected MRI modality, received "
                f"'{metadata.get('modality')}'."
            )

    def _check_body_region(
        self,
        metadata: Dict[str, Any],
        failures: List[str],
    ) -> None:

        body_region = str(
            metadata.get("body_region", "")
        ).strip().lower()

        if body_region not in self.ALLOWED_BODY_REGIONS:
            failures.append(
                f"Unsupported MRI body region '{body_region}'."
            )

    def _check_sequences(
        self,
        metadata: Dict[str, Any],
        failures: List[str],
    ) -> None:

        sequences = metadata.get("sequences")

        if not isinstance(sequences, dict):
            failures.append(
                "MRI sequence metadata must be a dictionary."
            )
            return

        normalized = {
            str(sequence).strip().upper()
            for sequence in sequences.keys()
        }

        missing = self.REQUIRED_SEQUENCES - normalized

        if missing:
            failures.append(
                "Missing required MRI sequences: "
                + ", ".join(sorted(missing))
            )

    def _check_sequence_geometry(
        self,
        metadata: Dict[str, Any],
        failures: List[str],
    ) -> None:

        sequences = metadata.get("sequences")

        if not isinstance(sequences, dict):
            return

        reference_shape = None
        reference_spacing = None

        for sequence_name, sequence_info in sequences.items():

            if not isinstance(sequence_info, dict):
                failures.append(
                    f"Sequence '{sequence_name}' metadata "
                    "must be a dictionary."
                )
                continue

            shape = sequence_info.get("shape")
            spacing = sequence_info.get("spacing")

            if shape is None:
                failures.append(
                    f"Sequence '{sequence_name}' is missing "
                    "shape metadata."
                )
                continue

            if spacing is None:
                failures.append(
                    f"Sequence '{sequence_name}' is missing "
                    "spacing metadata."
                )
                continue

            try:
                shape = tuple(shape)
            except Exception:
                failures.append(
                    f"Sequence '{sequence_name}' has invalid shape metadata."
                )
                continue

            try:
                spacing = tuple(
                    float(value)
                    for value in spacing
                )
            except Exception:
                failures.append(
                    f"Sequence '{sequence_name}' has invalid spacing metadata."
                )
                continue

            if reference_shape is None:
                reference_shape = shape
            elif shape != reference_shape:
                failures.append(
                    "MRI sequence geometry mismatch: "
                    f"'{sequence_name}' shape {shape} differs "
                    f"from {reference_shape}."
                )

            if reference_spacing is None:
                reference_spacing = spacing
            else:
                if len(spacing) != len(reference_spacing):
                    failures.append(
                        "MRI sequence spacing dimensionality mismatch."
                    )
                else:
                    for current, reference in zip(
                        spacing,
                        reference_spacing,
                    ):
                        if (
                            abs(current - reference)
                            > self.SPACING_TOLERANCE
                        ):
                            failures.append(
                                "MRI sequence voxel spacing mismatch."
                            )
                            break

        if reference_spacing is not None:

            if len(reference_spacing) != 3:
                failures.append(
                    "Expected 3D voxel spacing, "
                    f"received {reference_spacing}."
                )
            else:

                for current, expected in zip(
                    reference_spacing,
                    self.EXPECTED_SPACING,
                ):
                    if (
                        abs(current - expected)
                        > self.SPACING_TOLERANCE
                    ):
                        failures.append(
                            "MRI-1 requires 1mm isotropic voxel "
                            f"spacing; received {reference_spacing}."
                        )
                        break

    def _check_tool_identity(
        self,
        result: Dict[str, Any],
        failures: List[str],
    ) -> None:

        if result.get("tool") != self.TOOL_NAME:
            failures.append(
                f"Unexpected tool '{result.get('tool')}'. "
                f"Expected '{self.TOOL_NAME}'."
            )

        if result.get("tool_version") != self.TOOL_VERSION:
            failures.append(
                "Unexpected tool version: "
                f"{result.get('tool_version')}. "
                f"Expected {self.TOOL_VERSION}."
            )

        if result.get("model") != self.MODEL_NAME:
            failures.append(
                f"Unexpected model '{result.get('model')}'. "
                f"Expected '{self.MODEL_NAME}'."
            )

        if result.get("model_version") != self.MODEL_VERSION:
            failures.append(
                f"Unexpected model version "
                f"'{result.get('model_version')}'. "
                f"Expected '{self.MODEL_VERSION}'."
            )

    def _check_shapes(
        self,
        result: Dict[str, Any],
        failures: List[str],
    ) -> None:

        input_shape = result.get("input_shape")
        prediction_shape = result.get("prediction_shape")

        if input_shape is None:
            failures.append(
                "Missing input_shape."
            )

        if prediction_shape is None:
            failures.append(
                "Missing prediction_shape."
            )

        if (
            input_shape is not None
            and prediction_shape is not None
        ):
            if tuple(input_shape) != tuple(prediction_shape):
                failures.append(
                    "Input and prediction shapes do not match: "
                    f"{input_shape} vs {prediction_shape}."
                )

    def _check_probabilities(
        self,
        result: Dict[str, Any],
        failures: List[str],
    ) -> None:

        probabilities = result.get("probabilities")

        if not isinstance(probabilities, dict):
            failures.append(
                "Probabilities must be a dictionary."
            )
            return

        regions = set(probabilities.keys())

        missing = self.EXPECTED_REGIONS - regions

        if missing:
            failures.append(
                "Missing probability regions: "
                + ", ".join(sorted(missing))
            )

        unexpected = regions - self.EXPECTED_REGIONS

        if unexpected:
            failures.append(
                "Unexpected probability regions: "
                + ", ".join(sorted(unexpected))
            )

        expected_shape = result.get("prediction_shape")

        for region in self.EXPECTED_REGIONS:

            if region not in probabilities:
                continue

            probability = probabilities[region]

            try:
                shape = tuple(probability.shape)
            except AttributeError:
                failures.append(
                    f"Probability output for '{region}' "
                    "has no shape."
                )
                continue

            if len(shape) != 3:
                failures.append(
                    f"Probability output for '{region}' "
                    f"must be 3D, received {shape}."
                )

            if expected_shape is not None:
                if shape != tuple(expected_shape):
                    failures.append(
                        f"Probability shape mismatch for "
                        f"'{region}': {shape} vs {expected_shape}."
                    )

            try:
                if not bool(
                    (probability == probability).all()
                ):
                    failures.append(
                        f"Probability output for '{region}' "
                        "contains NaN values."
                    )

                if float(probability.min()) < 0.0:
                    failures.append(
                        f"Probability output for '{region}' "
                        "contains values below 0."
                    )

                if float(probability.max()) > 1.0:
                    failures.append(
                        f"Probability output for '{region}' "
                        "contains values above 1."
                    )

            except Exception as exc:
                failures.append(
                    f"Could not validate probabilities for "
                    f"'{region}': {exc}"
                )

    def _check_masks(
        self,
        result: Dict[str, Any],
        failures: List[str],
    ) -> None:

        masks = result.get("masks")

        if not isinstance(masks, dict):
            failures.append(
                "Masks must be a dictionary."
            )
            return

        regions = set(masks.keys())

        missing = self.EXPECTED_REGIONS - regions

        if missing:
            failures.append(
                "Missing mask regions: "
                + ", ".join(sorted(missing))
            )

        unexpected = regions - self.EXPECTED_REGIONS

        if unexpected:
            failures.append(
                "Unexpected mask regions: "
                + ", ".join(sorted(unexpected))
            )

        expected_shape = result.get("prediction_shape")

        for region in self.EXPECTED_REGIONS:

            if region not in masks:
                continue

            mask = masks[region]

            try:
                shape = tuple(mask.shape)
            except AttributeError:
                failures.append(
                    f"Mask output for '{region}' "
                    "has no shape."
                )
                continue

            if expected_shape is not None:
                if shape != tuple(expected_shape):
                    failures.append(
                        f"Mask shape mismatch for '{region}': "
                        f"{shape} vs {expected_shape}."
                    )

            try:
                unique_values = set(
                    mask.flatten().tolist()
                )

                if not unique_values.issubset(
                    {0, 1, False, True}
                ):
                    failures.append(
                        f"Mask '{region}' is not binary."
                    )

            except Exception as exc:
                failures.append(
                    f"Could not validate mask '{region}': {exc}"
                )

    def _check_label_summary(
        self,
        result: Dict[str, Any],
        failures: List[str],
    ) -> None:

        label_summary = result.get("label_summary")

        if not isinstance(label_summary, dict):
            failures.append(
                "label_summary must be a dictionary."
            )
            return

        regions = set(label_summary.keys())

        missing = self.EXPECTED_REGIONS - regions

        if missing:
            failures.append(
                "Missing label summary regions: "
                + ", ".join(sorted(missing))
            )

        unexpected = regions - self.EXPECTED_REGIONS

        if unexpected:
            failures.append(
                "Unexpected label summary regions: "
                + ", ".join(sorted(unexpected))
            )

        for region in self.EXPECTED_REGIONS:

            if region not in label_summary:
                continue

            summary = label_summary[region]

            if not isinstance(summary, dict):
                failures.append(
                    f"Label summary for '{region}' "
                    "must be a dictionary."
                )
                continue

            if "region" not in summary:
                failures.append(
                    f"Label summary for '{region}' "
                    "is missing 'region'."
                )

            # The actual BrainTumorSegmentationTool contract
            # uses 'voxel_count', not 'voxels'.
            if "voxel_count" not in summary:
                failures.append(
                    f"Label summary for '{region}' "
                    "is missing 'voxel_count'."
                )

            if "voxel_count" in summary:
                try:
                    voxel_count = int(
                        summary["voxel_count"]
                    )

                    if voxel_count < 0:
                        failures.append(
                            f"Voxel count for '{region}' "
                            "cannot be negative."
                        )

                except Exception:
                    failures.append(
                        f"Voxel count for '{region}' "
                        "must be numeric."
                    )

    def _check_governance(
        self,
        result: Dict[str, Any],
        failures: List[str],
        warnings: List[str],
    ) -> None:

        if result.get("verification_required") is not True:
            failures.append(
                "MRI-1 result must require verification."
            )

        if result.get("clinical_use") != "research_demo_only":
            failures.append(
                "MRI-1 must remain research_demo_only."
            )

        warnings.extend(
            [
                (
                    "MRI-1 is a research/demo capability "
                    "and is not clinically validated."
                ),
                (
                    "Human verification is required "
                    "before workflow use."
                ),
                (
                    "MRI-1 output must not be used for "
                    "autonomous diagnosis or treatment."
                ),
            ]
        )

    def _check_hierarchy(
        self,
        result: Dict[str, Any],
        warnings: List[str],
    ) -> None:
        """
        Diagnostic-only hierarchy check.

        TC and ET are normally expected to be subsets of WT,
        but MRI-1 exposes independently thresholded output
        channels. Therefore hierarchy inconsistency is reported
        as a warning and does not invalidate the evidence.
        """

        masks = result.get("masks")

        if not isinstance(masks, dict):
            return

        try:
            wt = masks.get("whole_tumor")
            tc = masks.get("tumor_core")
            et = masks.get("enhancing_tumor")

            if (
                wt is None
                or tc is None
                or et is None
            ):
                return

            if bool((tc & ~wt).any()):
                warnings.append(
                    "Diagnostic warning: tumor_core contains "
                    "voxels outside whole_tumor."
                )

            if bool((et & ~wt).any()):
                warnings.append(
                    "Diagnostic warning: enhancing_tumor "
                    "contains voxels outside whole_tumor."
                )

        except Exception as exc:
            warnings.append(
                "Hierarchy diagnostic check could not be "
                f"completed: {exc}"
            )

    def verify(
        self,
        evidence: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Verify MRI-1 evidence.

        Expected structure:

        {
            "mri_metadata": {
                "modality": "MRI",
                "body_region": "brain",
                "sequences": {
                    "T1c": {
                        "shape": (...),
                        "spacing": (...)
                    },
                    "T1": {
                        "shape": (...),
                        "spacing": (...)
                    },
                    "T2": {
                        "shape": (...),
                        "spacing": (...)
                    },
                    "FLAIR": {
                        "shape": (...),
                        "spacing": (...)
                    }
                }
            },
            "segmentation_result": {
                ...
            }
        }
        """

        failures: List[str] = []
        warnings: List[str] = []

        if not isinstance(evidence, dict):
            return self._build_decision(
                ["Evidence must be a dictionary."],
                warnings,
            )

        mri_metadata = evidence.get(
            "mri_metadata"
        )

        segmentation_result = evidence.get(
            "segmentation_result"
        )

        if not isinstance(mri_metadata, dict):
            failures.append(
                "Missing or invalid mri_metadata."
            )

        if not isinstance(segmentation_result, dict):
            failures.append(
                "Missing or invalid segmentation_result."
            )

        if failures:
            return self._build_decision(
                failures,
                warnings,
            )

        self._check_modality(
            mri_metadata,
            failures,
        )

        self._check_body_region(
            mri_metadata,
            failures,
        )

        self._check_sequences(
            mri_metadata,
            failures,
        )

        self._check_sequence_geometry(
            mri_metadata,
            failures,
        )

        self._check_tool_identity(
            segmentation_result,
            failures,
        )

        self._check_shapes(
            segmentation_result,
            failures,
        )

        self._check_probabilities(
            segmentation_result,
            failures,
        )

        self._check_masks(
            segmentation_result,
            failures,
        )

        self._check_label_summary(
            segmentation_result,
            failures,
        )

        self._check_governance(
            segmentation_result,
            failures,
            warnings,
        )

        self._check_hierarchy(
            segmentation_result,
            warnings,
        )

        return self._build_decision(
            failures,
            warnings,
        )