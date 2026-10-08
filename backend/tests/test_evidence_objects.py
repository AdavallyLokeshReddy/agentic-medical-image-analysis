from agent.case_state import (
    CaseState,
    CaseStatus,
    VerificationStatus,
    CaseModality,
)
from agent.orchestrator import AgentOrchestrator
from tools.register_tools import register_default_tools
from tools.registry import tool_registry


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
    # 3. Add the case information needed by the verifier
    #
    # These values correspond to the existing CASE-0004
    # integration setup.
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

    orchestrator = AgentOrchestrator(
        tool_registry
    )

    # --------------------------------------------------------------
    # 5. Plan the case
    # --------------------------------------------------------------

    print("\n[3] Planning case...")

    plan = orchestrator.plan(
        case
    )

    print(
        "Safety Contract:",
        plan["safety_contract"]["contract_id"]
    )

    print(
        "Available tools:",
        [
            tool["name"]
            for tool in plan["available_tools"]
        ]
    )

    print(
        "Ready tasks:",
        [
            task["task_id"]
            for task in plan["ready_tasks"]
        ]
    )

    # --------------------------------------------------------------
    # 6. Select ICH tool
    # --------------------------------------------------------------

    print("\n[4] Selecting ICH detection tool...")

    selected_tool = orchestrator.select_tool(
        case,
        "ich_detection",
    )

    print(
        "Selected tool:",
        selected_tool["name"]
    )

    # --------------------------------------------------------------
    # 7. Simulate the EXISTING ICH detection output
    #
    # IMPORTANT:
    # This test does not modify or replace your real model.
    # It only tests the orchestrator -> verifier integration.
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
        detection_result["prediction"]["any_probability"]
    )

    # --------------------------------------------------------------
    # 8. VERIFY ANALYSIS
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
        result["case_id"]
    )

    print(
        "Case verification status:",
        result["case_verification_status"]
    )

    print(
        "Case lifecycle status:",
        result["case_status"]
    )

    print(
        "Human review required:",
        result["human_review_required"]
    )

    # --------------------------------------------------------------
    # 10. Display individual checks
    # --------------------------------------------------------------

    verification = result[
        "verification_result"
    ]["verification"]

    print("\nVerification checks:")

    for check_name, check in verification[
        "checks"
    ].items():

        print(
            f"  {check_name}: "
            f"{check.get('status')}"
        )

    # --------------------------------------------------------------
    # 11. Display decision
    # --------------------------------------------------------------

    decision = result[
        "verification_result"
    ]["decision"]

    print("\nDecision:")
    print(
        "  Status:",
        decision.get("status")
    )

    print(
        "  Action:",
        decision.get("action")
    )

    print(
        "  Human review:",
        decision.get("human_review_required")
    )

    # --------------------------------------------------------------
    # 12. Verify CaseState was updated
    # --------------------------------------------------------------

    print("\nCaseState verification:")
    print(
        "  Status:",
        case.verification.status.value
    )

    print(
        "  Warnings:",
        case.verification.warnings
    )

    print(
        "  Failed checks:",
        case.verification.failed_checks
    )

    print(
        "  Human review:",
        case.verification.human_review_required
    )

    # --------------------------------------------------------------
    # 13. Verify TaskGraph was updated
    # --------------------------------------------------------------

    verification_task = case.task_graph.get_task(
        f"{case.case_id}-VERIFICATION"
    )

    print("\nVerification task:")
    print(
        "  Status:",
        verification_task.status.value
    )

    # --------------------------------------------------------------
    # 14. Assertions
    # --------------------------------------------------------------

    assert case.verification.status in (
        VerificationStatus.REQUIRES_REVIEW,
        VerificationStatus.PASSED,
    )

    assert case.status == CaseStatus.REQUIRES_REVIEW

    assert (
        case.verification.human_review_required
        is True
    )

    assert (
        verification_task.status.value
        == "completed"
    )

    print("\n" + "=" * 70)
    print("ALL VERIFICATION INTEGRATION TESTS PASSED")
    print("=" * 70)


if __name__ == "__main__":
    main()




