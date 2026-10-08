from __future__ import annotations

from pathlib import Path

from preprocessing.ct_volume_preprocessing import (
    preprocess_ct_volume,
)

from tools.multi_organ_segmentation import (
    MultiOrganSegmentationTool,
)

from tools.registry import (
    tool_registry,
)

from tools.register_tools import (
    register_default_tools,
)

from agent.case_state import (
    CaseModality,
    CaseState,
    CaseStatus,
    EvidenceItem,
    EvidenceProvenance,
    EvidenceStatus,
    VerificationStatus,
)

from agent.safety_contract import (
    ActionTier,
    DataPolicy,
    EscalationPolicy,
    OperationPolicy,
    ResourcePolicy,
    SafetyContract,
    UncertaintyPolicy,
)

from agent.task_graph import (
    TaskNode,
    TaskStatus,
)

from verification.ct3_verification import (
    CT3VerificationEngine,
)


CASE_DIR = Path(
    "uploads/CASE-ABDOMEN-0001/series"
)


def test_ct3_governed_integration():
    """
    Full governed integration test for CT-3.

    Validates:

        CT preprocessing
        -> CaseState
        -> SafetyContract
        -> TaskGraph
        -> Tool Registry
        -> CT-3 tool discovery
        -> CT-3 tool selection
        -> CT-3 tool execution
        -> EvidenceItem
        -> CT-3 verification
        -> VerificationState
        -> human-review boundary

    This test does NOT establish clinical validity.
    """

    # =========================================================
    # 1. Validate test dataset
    # =========================================================

    assert CASE_DIR.exists()
    assert CASE_DIR.is_dir()

    # =========================================================
    # 2. Register approved tools
    # =========================================================

    register_default_tools()

    registered_tool_names = {
        tool["name"]
        for tool in tool_registry.list_tools()
    }

    print(
        "\nRegistered tools:",
        registered_tool_names,
    )

    assert (
        "multi_organ_segmentation"
        in registered_tool_names
    )

    # =========================================================
    # 3. Preprocess abdominal CT
    # =========================================================

    preprocessing_result = preprocess_ct_volume(
        CASE_DIR
    )

    datasets = preprocessing_result["datasets"]

    volume = preprocessing_result["volume"]

    voxel_spacing = tuple(
        preprocessing_result["voxel_spacing"]
    )

    assert len(datasets) > 0

    assert volume.ndim == 3

    assert volume.size > 0

    assert all(
        float(value) > 0
        for value in voxel_spacing
    )

    first_dataset = datasets[0]

    image_position_patient = tuple(
        float(value)
        for value in first_dataset.ImagePositionPatient
    )

    image_orientation_patient = tuple(
        float(value)
        for value in first_dataset.ImageOrientationPatient
    )

    study_instance_uid = str(
        first_dataset.StudyInstanceUID
    )

    series_instance_uid = str(
        first_dataset.SeriesInstanceUID
    )

    # =========================================================
    # 4. Create CaseState
    # =========================================================

    case = CaseState(
        case_id="CASE-ABDOMEN-0001",
        modality=CaseModality.CT,
        body_region="ABDOMEN",
        clinical_question=(
            "Research/demo multi-organ segmentation "
            "workflow evaluation."
        ),
    )

    case.update_metadata(
        "modality",
        "CT",
    )

    case.update_metadata(
        "body_region",
        "ABDOMEN",
    )

    case.update_metadata(
        "study_instance_uid",
        study_instance_uid,
    )

    case.update_metadata(
        "series_instance_uid",
        series_instance_uid,
    )

    case.update_metadata(
        "slice_count",
        len(datasets),
    )

    case.update_metadata(
        "voxel_spacing",
        voxel_spacing,
    )

    case.update_metadata(
        "volume_shape",
        tuple(
            int(value)
            for value in volume.shape
        ),
    )

    assert case.case_id == (
        "CASE-ABDOMEN-0001"
    )

    assert case.modality == CaseModality.CT

    assert case.body_region == "ABDOMEN"

    # =========================================================
    # 5. Build SafetyContract
    # =========================================================

    contract = SafetyContract(
        contract_id=(
            "CT3-CASE-ABDOMEN-0001"
        ),
        approved_tools=[
            "multi_organ_segmentation"
        ],
        task_preconditions=[
            "CT modality confirmed",
            "Abdominal body region confirmed",
            "Valid CT volume available",
            "Study identity available",
            "Series identity available",
        ],
        data_policy=DataPolicy(
            allowed_modalities=[
                "CT"
            ],
            allowed_body_regions=[
                "ABDOMEN"
            ],
            required_data=[
                "CT volume",
                "voxel spacing",
                "StudyInstanceUID",
                "SeriesInstanceUID",
            ],
        ),
        operation_policy=OperationPolicy(
            allowed_operations=[
                "observe",
                "segment",
                "recommend_review",
            ],
            maximum_action_tier=ActionTier.T1,
        ),
        uncertainty_policy=UncertaintyPolicy(
            minimum_confidence=0.5,
            require_verification=True,
            abstain_on_missing_evidence=True,
            abstain_on_verification_failure=True,
        ),
        escalation_policy=EscalationPolicy(
            escalation_paths=[
                "human_clinical_review"
            ],
            human_review_required=True,
        ),
        resource_policy=ResourcePolicy(
            maximum_retries=0,
            timeout_seconds=300,
            maximum_concurrent_tools=1,
        ),
    )

    case.safety_contract = contract

    # =========================================================
    # 6. Validate CT-3 permission
    # =========================================================

    assert contract.is_tool_permitted(
        "multi_organ_segmentation"
    )

    contract.validate_tool(
        "multi_organ_segmentation"
    )

    # =========================================================
    # 7. Build intake task
    # =========================================================

    intake_task = TaskNode(
        task_id="ct3-intake",
        task_type="intake",
        description=(
            "Validate abdominal CT input "
            "for CT-3 segmentation."
        ),
        status=TaskStatus.PROPOSED,
        permitted_tools=[],
        preconditions=[
            "CT modality",
            "abdominal body region",
            "valid CT volume",
        ],
        verification_required=True,
        stopping_conditions=[
            "Invalid CT input"
        ],
    )

    case.add_task(
        intake_task
    )

    # =========================================================
    # 8. Build CT-3 segmentation task
    # =========================================================

    segmentation_task = TaskNode(
        task_id="ct3-segmentation",
        task_type="multi_organ_segmentation",
        description=(
            "Run research/demo multi-organ "
            "segmentation on abdominal CT."
        ),
        status=TaskStatus.PROPOSED,
        dependencies=[
            "ct3-intake"
        ],
        permitted_tools=[
            "multi_organ_segmentation"
        ],
        preconditions=[
            "CT intake completed",
            "CT-3 tool permitted",
        ],
        verification_required=True,
        stopping_conditions=[
            "Missing CT evidence",
            "Verification failure",
        ],
    )

    case.add_task(
        segmentation_task
    )

    # =========================================================
    # 9. Confirm task dependency behavior
    # =========================================================

    ready_tasks = (
        case.task_graph.get_ready_tasks()
    )

    ready_task_ids = {
        task.task_id
        for task in ready_tasks
    }

    assert (
        "ct3-intake"
        in ready_task_ids
    )

    assert (
        "ct3-segmentation"
        not in ready_task_ids
    )

    # =========================================================
    # 10. Complete intake
    # =========================================================

    case.task_graph.mark_completed(
        "ct3-intake"
    )

    ready_tasks = (
        case.task_graph.get_ready_tasks()
    )

    ready_task_ids = {
        task.task_id
        for task in ready_tasks
    }

    assert (
        "ct3-segmentation"
        in ready_task_ids
    )

    # =========================================================
    # 11. Discover and select CT-3 tool
    # =========================================================

    case.discover_available_tools(
        tool_registry
    )

    print(
        "Case available tools:",
        case.available_tools,
    )

    assert (
        "multi_organ_segmentation"
        in case.available_tools
    )

    case.select_tool(
        "multi_organ_segmentation"
    )

    assert (
        "multi_organ_segmentation"
        in case.selected_tools
    )

    # =========================================================
    # 12. Run real CT-3 model
    #
    # Controlled 96x96x96 inference keeps CPU
    # integration bounded.
    # =========================================================

    tool = MultiOrganSegmentationTool(
        device="cpu"
    )

    segmentation_result = tool.run(
        {
            "volume": volume,
            "voxel_spacing": voxel_spacing,
            "image_position_patient": (
                image_position_patient
            ),
            "image_orientation_patient": (
                image_orientation_patient
            ),
            "roi_size": (
                96,
                96,
                96,
            ),
            "sw_batch_size": 1,
            "overlap": 0.0,
        }
    )

    # =========================================================
    # 13. Validate raw tool output
    # =========================================================

    assert (
        segmentation_result["tool"]
        == "multi_organ_segmentation"
    )

    assert (
        segmentation_result["tool_version"]
        == "research-demo-1.0"
    )

    assert (
        segmentation_result["model_name"]
        == "SwinUNETR-BTCV"
    )

    assert (
        segmentation_result[
            "verification_required"
        ]
        is True
    )

    assert (
        segmentation_result["clinical_use"]
        == "research_demo_only"
    )

    prediction = (
        segmentation_result["prediction"]
    )

    assert prediction.ndim == 3

    assert prediction.size > 0

    label_summary = (
        segmentation_result["label_summary"]
    )

    assert isinstance(
        label_summary,
        dict,
    )

    # =========================================================
    # 14. Mark segmentation task completed
    # =========================================================

    case.task_graph.mark_completed(
        "ct3-segmentation"
    )

    segmentation_task_state = (
        case.task_graph.get_task(
            "ct3-segmentation"
        )
    )

    assert (
        segmentation_task_state.status
        == TaskStatus.COMPLETED
    )

    # =========================================================
    # 15. Create governed evidence
    # =========================================================

    evidence = EvidenceItem(
        evidence_id="EVIDENCE-CT3-001",
        case_id="CASE-ABDOMEN-0001",
        evidence_type=(
            "multi_organ_segmentation"
        ),
        source="multi_organ_segmentation",
        claim=(
            "Research/demo segmentation output "
            "was produced for the abdominal CT."
        ),
        output={
            "prediction_shape": tuple(
                int(value)
                for value in prediction.shape
            ),
            "label_summary": label_summary,
        },
        status=EvidenceStatus.PROPOSED,
        confidence=None,
        applicable=True,
        image_ids=[],
        series_uid=series_instance_uid,
        supporting_slices=[],
        supporting_regions=[],
        provenance=EvidenceProvenance(
            tool_name=(
                segmentation_result["tool"]
            ),
            tool_version=(
                segmentation_result[
                    "tool_version"
                ]
            ),
            model_name=(
                segmentation_result[
                    "model_name"
                ]
            ),
            model_version=(
                segmentation_result[
                    "model_version"
                ]
            ),
            runtime=(
                segmentation_result[
                    "runtime"
                ]
            ),
            input_references=[
                "CASE-ABDOMEN-0001",
                series_instance_uid,
            ],
            metadata={
                "volume_shape": tuple(
                    int(value)
                    for value in volume.shape
                ),
                "voxel_spacing": voxel_spacing,
                "roi_size": (
                    96,
                    96,
                    96,
                ),
            },
        ),
        verification_ids=[],
        task_id="ct3-segmentation",
        dependencies=[
            "ct3-intake"
        ],
        warnings=list(
            segmentation_result[
                "warnings"
            ]
        ),
        metadata={
            "research_demo": True,
            "clinical_use": (
                "research_demo_only"
            ),
        },
    )

    case.add_evidence(
        evidence
    )

    # =========================================================
    # 16. Verify CT-3 result
    # =========================================================

    verifier = CT3VerificationEngine()

    verification_result = (
        verifier.verify(
            {
                "ct_metadata": {
                    "modality": "CT",
                    "body_region": "ABDOMEN",
                    "slice_count": len(
                        datasets
                    ),
                    "voxel_spacing": (
                        voxel_spacing
                    ),
                    "study_instance_uid": (
                        study_instance_uid
                    ),
                    "series_instance_uid": (
                        series_instance_uid
                    ),
                },
                "segmentation_result": (
                    segmentation_result
                ),
            }
        )
    )

    assert (
        verification_result["decision"]
        == "verified_for_workflow_review"
    )

    assert (
        verification_result["next_step"]
        == "proceed_to_human_review"
    )

    assert (
        verification_result[
            "human_review_required"
        ]
        is True
    )

    assert (
        verification_result[
            "failed_checks"
        ]
        == []
    )

    # =========================================================
    # 17. Attach verification to evidence
    # =========================================================

    verification_id = (
        "VERIFICATION-CT3-001"
    )

    evidence.verification_ids.append(
        verification_id
    )

    evidence.mark_requires_review()

    # =========================================================
    # 18. Update CaseState verification
    # =========================================================

    # IMPORTANT:
    # CaseState.set_verification() stores the supplied
    # status value. Therefore we pass the actual
    # VerificationStatus enum rather than a string.
    case.set_verification(
        status=VerificationStatus.REQUIRES_REVIEW,
        checks=(
            verification_result["checks"]
        ),
        warnings=(
            verification_result["warnings"]
        ),
        failed_checks=(
            verification_result[
                "failed_checks"
            ]
        ),
        human_review_required=(
            verification_result[
                "human_review_required"
            ]
        ),
    )

    # CaseState.set_status() also expects the actual
    # CaseStatus enum.
    case.set_status(
        CaseStatus.REQUIRES_REVIEW
    )

    # =========================================================
    # 19. Final governance assertions
    # =========================================================

    stored_evidence = (
        case.get_evidence(
            "EVIDENCE-CT3-001"
        )
    )

    assert (
        stored_evidence.status
        == EvidenceStatus.REQUIRES_REVIEW
    )

    assert (
        case.status
        == CaseStatus.REQUIRES_REVIEW
    )

    assert (
        case.verification.human_review_required
        is True
    )

    assert (
        case.verification.status
        == VerificationStatus.REQUIRES_REVIEW
    )

    safety = (
        verification_result["safety"]
    )

    assert (
        safety["autonomous_diagnosis"]
        is False
    )

    assert (
        safety["autonomous_treatment"]
        is False
    )

    assert (
        safety["irreversible_action"]
        is False
    )

    # =========================================================
    # 20. Final evidence boundary
    # =========================================================

    valid_evidence = (
        case.get_valid_evidence()
    )

    assert (
        "EVIDENCE-CT3-001"
        not in [
            item.evidence_id
            for item in valid_evidence
        ]
    )

    review_evidence = (
        case.get_review_required_evidence()
    )

    assert (
        "EVIDENCE-CT3-001"
        in [
            item.evidence_id
            for item in review_evidence
        ]
    )

    # =========================================================
    # 21. Final integration output
    # =========================================================

    print(
        "\nCT-3 GOVERNED INTEGRATION PASS"
    )

    print(
        f"Case: {case.case_id}"
    )

    print(
        f"Tool: {segmentation_result['tool']}"
    )

    print(
        f"Model: {segmentation_result['model_name']}"
    )

    print(
        f"Input volume: {volume.shape}"
    )

    print(
        f"Prediction: {prediction.shape}"
    )

    print(
        "Verification: "
        f"{verification_result['decision']}"
    )

    print(
        f"Case status: {case.status.value}"
    )

    print(
        "Verification status: "
        f"{case.verification.status.value}"
    )

    print(
        "Human review required: "
        f"{verification_result['human_review_required']}"
    )