from agent.case_state import (
    CaseState,
    CaseStatus,
    VerificationStatus,
    CaseModality,
)
from agent.orchestrator import AgentOrchestrator
from tools.register_tools import register_default_tools
from tools.registry import tool_registry
from agent.task_graph import TaskStatus

def main():
    print("=" * 70)
    print("VERIFICATION INTEGRATION TEST")
    print("=" * 70)

    # --------------------------------------------------------------
    # 1. Register tools
    # --------------------------------------------------------------

    register_default_tools()

    print("\n[1] Tool Registry")
    print("Registered tools:", tool_registry.list_tools())

    # --------------------------------------------------------------
    # 2. Create CaseState
    # --------------------------------------------------------------

    case = CaseState(
        case_id="CASE-0004",
        modality=CaseModality.CT,
        body_region="head",
        clinical_question=(
            "Evaluate the non-contrast head CT for "
            "possible intracranial hemorrhage."
        ),
    )

    # --------------------------------------------------------------
    # 3. Add case metadata
    # --------------------------------------------------------------
    #
    # These values correspond to the existing CASE-0004
    # integration setup.
    #
    # The actual CT series used in the earlier integration test
    # contains:
    #   - 40 slices
    #   - 512 x 512 image dimensions
    #   - 5.0 mm slice spacing
    #   - 0.488281 mm in-plane spacing
    #
    # The 5.0 mm slice spacing is expected to generate a
    # verification warning because the prototype verifier uses
    # 3.0 mm as its coarse-slice warning threshold.
    # --------------------------------------------------------------

    case.metadata.update(
        {
            "modality": "CT",
            "body_region": "head",
            "slice_count": 40,
            "voxel_spacing": [
                5.0,
                0.488281,
                0.488281,
            ],
            "study_instance_uid": "TEST-STUDY-CASE-0004",
            "series_instance_uid": "TEST-SERIES-CASE-0004",
        }
    )

    print("\n[2] CaseState")
    print("Case ID:", case.case_id)
    print("Modality:", case.modality.value)
    print("Body region:", case.body_region)

    # --------------------------------------------------------------
    # 4. Create orchestrator
    # --------------------------------------------------------------

    orchestrator = AgentOrchestrator(tool_registry)

    # --------------------------------------------------------------
    # 5. Plan the case
    # --------------------------------------------------------------

    print("\n[3] Planning case...")

    plan = orchestrator.plan(case)

    print(
        "Safety Contract:",
        plan["safety_contract"]["contract_id"],
    )

    print(
        "Available tools:",
        [
            tool["name"]
            for tool in plan["available_tools"]
        ],
    )

    print(
        "Ready tasks:",
        [
            task["task_id"]
            for task in plan["ready_tasks"]
        ],
    )

    # --------------------------------------------------------------
    # 6. Select ICH detection tool
    # --------------------------------------------------------------

    print("\n[4] Selecting ICH detection tool...")

    selected_tool = orchestrator.select_tool(
        case,
        "ich_detection",
    )

    print(
        "Selected tool:",
        selected_tool["name"],
    )

    # --------------------------------------------------------------
    # 7. Prepare simulated detection result
    # --------------------------------------------------------------
    #
    # We are NOT running the medical model here.
    #
    # This test is specifically for verifying that the result
    # produced by an analysis tool can successfully pass through
    # the orchestrator's verification layer.
    #
    # The probability values correspond to the earlier
    # CASE-0004 integration setup.
    # --------------------------------------------------------------

    detection_result = {
        "tool": "ich_detection",
        "status": "completed",

        "prediction": {
            "any_probability": 0.9977140426635742,

            "subtype_probabilities": {
                "epidural": 0.001,
                "intraparenchymal": 0.002,
                "intraventricular": 0.001,
                "subarachnoid": 0.003,
                "subdural": 0.9967080354690552,
            },
        },

        "evidence": {
            "metadata": {
                "modality": "CT",
                "body_region": "head",
            },

            "series": {
                "slice_count": 40,
            },

            "supporting_slices": [
                {
                    "slice_index": 10,
                    "probability": 0.95,
                },
                {
                    "slice_index": 11,
                    "probability": 0.97,
                },
            ],
        },
    }

    print("\n[5] Detection result prepared")

    print(
        "Any probability:",
        detection_result["prediction"]["any_probability"],
    )

    # --------------------------------------------------------------
    # 8. Run verification through orchestrator
    # --------------------------------------------------------------

    print("\n[6] Running verification...")

    result = orchestrator.verify_analysis(
        case,
        detection_result,
    )

    # --------------------------------------------------------------
    # 9. Display verification result
    # --------------------------------------------------------------

    print("\n" + "=" * 70)
    print("VERIFICATION RESULT")
    print("=" * 70)

    print(
        "Case ID:",
        result["case_id"],
    )

    print(
        "Case verification status:",
        result["case_verification_status"],
    )

    print(
        "Case lifecycle status:",
        result["case_status"],
    )

    print(
        "Human review required:",
        result["human_review_required"],
    )

    # --------------------------------------------------------------
    # 10. Display verification checks
    # --------------------------------------------------------------

    verification = result["verification_result"]["verification"]

    print("\nVerification checks:")

    for check_name, check in verification["checks"].items():
        print(
            f"  {check_name}: {check.get('status')}"
        )

        if check.get("message"):
            print(
                f"    Message: {check.get('message')}"
            )

    # --------------------------------------------------------------
    # 11. Display verification decision
    # --------------------------------------------------------------

    decision = result["verification_result"]["decision"]

    print("\nDecision:")

    print(
        "  Status:",
        decision.get("status"),
    )

    print(
        "  Action:",
        decision.get("action"),
    )

    print(
        "  Human review:",
        decision.get("human_review_required"),
    )

    # --------------------------------------------------------------
    # 12. Display CaseState verification state
    # --------------------------------------------------------------

    print("\nCaseState verification:")

    print(
        "  Status:",
        case.verification.status.value,
    )

    print(
        "  Warnings:",
        case.verification.warnings,
    )

    print(
        "  Failed checks:",
        case.verification.failed_checks,
    )

    print(
        "  Human review:",
        case.verification.human_review_required,
    )

    # --------------------------------------------------------------
    # 13. Inspect verification task
    # --------------------------------------------------------------

    verification_task = case.task_graph.get_task(
        f"{case.case_id}-VERIFICATION"
    )

    print("\nVerification task:")

    print(
        "  Status:",
        verification_task.status.value,
    )

    # --------------------------------------------------------------
    # 14. Assertions
    # --------------------------------------------------------------
    #
    # The current verifier is intentionally conservative.
    #
    # Because the test CT has 5.0 mm slice spacing, the verifier
    # is expected to produce a warning rather than a clean pass.
    #
    # Therefore the expected workflow state is:
    #
    #   Verification -> REQUIRES_REVIEW
    #   Case         -> REQUIRES_REVIEW
    #   Human review -> REQUIRED
    #
    # This is correct behavior for the safety architecture.
    # --------------------------------------------------------------

    assert case.verification.status in (
        VerificationStatus.REQUIRES_REVIEW,
        VerificationStatus.PASSED,
    ), (
        "Unexpected verification status: "
        f"{case.verification.status}"
    )

    assert case.status == CaseStatus.REQUIRES_REVIEW, (
        "Expected case lifecycle status to be "
        "REQUIRES_REVIEW, got: "
        f"{case.status}"
    )

    assert case.verification.human_review_required is True, (
        "Human review must remain required."
    )

    assert verification_task.status == TaskStatus.COMPLETED, (
    "Verification task should be COMPLETED after "
    "verification has been performed."
    )

    # --------------------------------------------------------------
    # 15. Final result
    # --------------------------------------------------------------

    print("\n" + "=" * 70)
    print("ALL VERIFICATION INTEGRATION TESTS PASSED")
    print("=" * 70)


if __name__ == "__main__":
    main()