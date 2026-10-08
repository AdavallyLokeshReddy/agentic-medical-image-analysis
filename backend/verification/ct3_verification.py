from __future__ import annotations

from typing import Any, Dict


class CT3VerificationEngine:
    """
    Verification engine for the governed CT-3
    multi-organ segmentation workflow.

    This verifier checks technical structure and governance
    boundaries. It does not determine clinical correctness
    of the segmentation.
    """

    TOOL_NAME = "multi_organ_segmentation"

    EXPECTED_LABELS = {
        0: "background",
        1: "spleen",
        2: "right_kidney",
        3: "left_kidney",
        4: "gallbladder",
        5: "esophagus",
        6: "liver",
        7: "stomach",
        8: "aorta",
        9: "ivc",
        10: "portal_splenic_veins",
        11: "pancreas",
        12: "right_adrenal",
        13: "left_adrenal",
    }

    def verify(
        self,
        verifier_input: Dict[str, Any],
    ) -> Dict[str, Any]:
        checks = []
        failed_checks = []
        warnings = []

        ct_metadata = verifier_input.get("ct_metadata")
        segmentation_result = verifier_input.get(
            "segmentation_result"
        )

        if not isinstance(ct_metadata, dict):
            failed_checks.append(
                "ct_metadata is missing or invalid."
            )
        else:
            modality = str(
                ct_metadata.get("modality", "")
            ).upper()

            if modality == "CT":
                checks.append(
                    "CT modality confirmed."
                )
            else:
                failed_checks.append(
                    "Input modality must be CT."
                )

            body_region = str(
                ct_metadata.get(
                    "body_region",
                    "",
                )
            ).upper()

            if body_region in {
                "ABDOMEN",
                "ABDOMINAL",
            }:
                checks.append(
                    "Abdominal body region confirmed."
                )
            else:
                failed_checks.append(
                    "Body region must be abdominal."
                )

            slice_count = ct_metadata.get(
                "slice_count"
            )

            if (
                isinstance(slice_count, int)
                and slice_count > 0
            ):
                checks.append(
                    "CT slice count is valid."
                )
            else:
                failed_checks.append(
                    "CT slice count must be a positive integer."
                )

            voxel_spacing = ct_metadata.get(
                "voxel_spacing"
            )

            if (
                isinstance(
                    voxel_spacing,
                    (tuple, list),
                )
                and len(voxel_spacing) == 3
                and all(
                    isinstance(value, (int, float))
                    and value > 0
                    for value in voxel_spacing
                )
            ):
                checks.append(
                    "Voxel spacing is valid."
                )
            else:
                failed_checks.append(
                    "Voxel spacing must contain three positive values."
                )

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

        if not isinstance(
            segmentation_result,
            dict,
        ):
            failed_checks.append(
                "Segmentation result is missing or invalid."
            )
        else:
            tool = segmentation_result.get("tool")

            if tool == self.TOOL_NAME:
                checks.append(
                    "Tool identity confirmed."
                )
            else:
                failed_checks.append(
                    "Segmentation result came from an unexpected tool."
                )

            prediction = segmentation_result.get(
                "prediction"
            )

            if prediction is not None:
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
                        "Segmentation prediction has a valid 3D shape."
                    )
                else:
                    failed_checks.append(
                        "Segmentation prediction must be a non-empty 3D volume."
                    )
            else:
                failed_checks.append(
                    "Segmentation prediction is missing."
                )

            label_summary = segmentation_result.get(
                "label_summary"
            )

            if isinstance(
                label_summary,
                dict,
            ):
                invalid_labels = []

                for key, value in label_summary.items():
                    try:
                        label_id = int(key)
                    except (TypeError, ValueError):
                        invalid_labels.append(key)
                        continue

                    if label_id not in self.EXPECTED_LABELS:
                        invalid_labels.append(label_id)
                        continue

                    if not isinstance(value, dict):
                        invalid_labels.append(label_id)
                        continue

                    if value.get("name") != self.EXPECTED_LABELS[
                        label_id
                    ]:
                        invalid_labels.append(label_id)

                if invalid_labels:
                    failed_checks.append(
                        "Segmentation label schema contains unexpected labels."
                    )
                else:
                    checks.append(
                        "Segmentation label schema is valid."
                    )
            else:
                failed_checks.append(
                    "label_summary is missing or invalid."
                )

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

            warnings.extend(
                [
                    "Segmentation output is not a diagnosis.",
                    "Human clinical verification is required before interpretation.",
                    "No autonomous treatment or irreversible clinical action is permitted.",
                ]
            )

        if failed_checks:
            decision = "blocked"
            next_step = "escalate_to_human"
            human_review_required = True
        else:
            decision = "verified_for_workflow_review"
            next_step = "proceed_to_human_review"
            human_review_required = True

        return {
            "verifier": self.__class__.__name__,
            "tool": self.TOOL_NAME,
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