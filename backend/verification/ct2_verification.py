from __future__ import annotations

from typing import Any, Dict


class CT2VerificationEngine:
    """
    Governance verifier for the CT-2 lung-nodule detection capability.

    This verifier checks technical and governance conditions around
    the research/demo detection output.

    It does NOT determine whether a lung nodule is clinically present.
    It only determines whether the tool output is structurally eligible
    for human workflow review.
    """

    TOOL_NAME = "lung_nodule_detection"

    def verify(
        self,
        verifier_input: Dict[str, Any],
    ) -> Dict[str, Any]:

        if not isinstance(
            verifier_input,
            dict,
        ):
            raise TypeError(
                "Verifier input must be a dictionary."
            )

        if "ct_metadata" not in verifier_input:
            raise ValueError(
                "Verifier input must contain 'ct_metadata'."
            )

        if "detection_result" not in verifier_input:
            raise ValueError(
                "Verifier input must contain 'detection_result'."
            )

        ct_metadata = verifier_input[
            "ct_metadata"
        ]

        detection_result = verifier_input[
            "detection_result"
        ]

        checks = []
        failed_checks = []
        warnings = []

        # -------------------------------------------------
        # 1. CT modality
        # -------------------------------------------------

        modality = str(
            ct_metadata.get(
                "modality",
                "",
            )
        ).upper()

        check = {
            "check": "ct_modality",
            "passed": modality == "CT",
        }

        checks.append(check)

        if not check["passed"]:
            failed_checks.append(
                "ct_modality"
            )

        # -------------------------------------------------
        # 2. Chest body region
        # -------------------------------------------------

        body_region = str(
            ct_metadata.get(
                "body_region",
                "",
            )
        ).upper()

        allowed_regions = {
            "CHEST",
            "THORAX",
            "LUNG",
        }

        check = {
            "check": "chest_body_region",
            "passed": body_region in allowed_regions,
        }

        checks.append(check)

        if not check["passed"]:
            failed_checks.append(
                "chest_body_region"
            )

        # -------------------------------------------------
        # 3. Input volume
        # -------------------------------------------------

        input_shape = detection_result.get(
            "input_shape"
        )

        check = {
            "check": "input_shape",
            "passed": (
                isinstance(
                    input_shape,
                    (tuple, list),
                )
                and len(input_shape) == 3
                and all(
                    int(value) > 0
                    for value in input_shape
                )
            ),
        }

        checks.append(check)

        if not check["passed"]:
            failed_checks.append(
                "input_shape"
            )

        # -------------------------------------------------
        # 4. Tool identity
        # -------------------------------------------------

        check = {
            "check": "tool_identity",
            "passed": (
                detection_result.get(
                    "tool_name"
                )
                == self.TOOL_NAME
            ),
        }

        checks.append(check)

        if not check["passed"]:
            failed_checks.append(
                "tool_identity"
            )

        # -------------------------------------------------
        # 5. Prediction structure
        # -------------------------------------------------

        prediction = detection_result.get(
            "prediction"
        )

        prediction_valid = (
            isinstance(
                prediction,
                list,
            )
            and len(prediction) >= 1
            and isinstance(
                prediction[0],
                dict,
            )
            and "box" in prediction[0]
            and "label" in prediction[0]
            and "label_scores" in prediction[0]
        )

        check = {
            "check": "prediction_structure",
            "passed": prediction_valid,
        }

        checks.append(check)

        if not check["passed"]:
            failed_checks.append(
                "prediction_structure"
            )

        # -------------------------------------------------
        # 6. Verification requirement
        # -------------------------------------------------

        check = {
            "check": "verification_required",
            "passed": (
                detection_result.get(
                    "verification_required"
                )
                is True
            ),
        }

        checks.append(check)

        if not check["passed"]:
            failed_checks.append(
                "verification_required"
            )

        # -------------------------------------------------
        # 7. Research-only boundary
        # -------------------------------------------------

        check = {
            "check": "research_only_boundary",
            "passed": (
                detection_result.get(
                    "clinical_use"
                )
                == "research_demo_only"
            ),
        }

        checks.append(check)

        if not check["passed"]:
            failed_checks.append(
                "research_only_boundary"
            )

        # -------------------------------------------------
        # Safety boundary
        # -------------------------------------------------

        warnings.extend(
            [
                "Lung-nodule detection output is not a diagnosis.",
                "Human clinical verification is required.",
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
            "decision": decision,
            "next_step": next_step,
            "checks": checks,
            "failed_checks": failed_checks,
            "warnings": warnings,
            "human_review_required": human_review_required,
            "safety": {
                "clinical_diagnosis_authorized": False,
                "treatment_authorized": False,
                "irreversible_action_authorized": False,
            },
        }