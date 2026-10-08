from __future__ import annotations

from pathlib import Path

from preprocessing.chest_ct_preprocessing import (
    preprocess_chest_ct_series,
)

from tools.lung_nodule_detection import (
    LungNoduleDetectionTool,
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

from verification.ct2_verification import (
    CT2VerificationEngine,
)


CASE_DIR = Path(
    "uploads/CASE-LUNG-0001/series"
)


def test_ct2_governed_integration():
    print()
    print("CT-2 GOVERNED INTEGRATION TEST")
    print("=" * 60)

    # ---------------------------------------------------------
    # 1. Load engineering-test chest CT
    # ---------------------------------------------------------

    assert CASE_DIR.exists(), (
        f"Test CT series not found: {CASE_DIR}"
    )

    preprocessing_result = (
        preprocess_chest_ct_series(
            CASE_DIR
        )
    )

    datasets = preprocessing_result[
        "datasets"
    ]

    volume = preprocessing_result[
        "volume"
    ]

    voxel_spacing = tuple(
        float(value)
        for value in preprocessing_result[
            "voxel_spacing"
        ]
    )

    assert len(datasets) > 0
    assert volume.ndim == 3
    assert volume.size > 0

    assert all(
        float(value) > 0
        for value in voxel_spacing
    )

    print(
        "DICOM FILES:",
        len(datasets),
    )

    print(
        "CT VOLUME:",
        volume.shape,
    )

    print(
        "VOXEL SPACING:",
        voxel_spacing,
    )

    # ---------------------------------------------------------
    # 2. Create CaseState
    # ---------------------------------------------------------

    case = CaseState(
        case_id="CASE-LUNG-0001",
        modality=CaseModality.CT,
        body_region="CHEST",
        clinical_question=(
            "Research/demo lung-nodule detection "
            "workflow evaluation."
        ),
    )

    print(
        "CASE STATE:",
        case.status.value,
    )

    assert case.modality == CaseModality.CT
    assert case.body_region == "CHEST"

    # ---------------------------------------------------------
    # 3. Attach CT metadata
    #
    # CaseState.update_metadata() expects:
    #     update_metadata(key, value)
    #
    # Therefore each metadata field is attached
    # individually.
    # ---------------------------------------------------------

    first_dataset = datasets[0]

    study_instance_uid = str(
        first_dataset.StudyInstanceUID
    )

    series_instance_uid = str(
        first_dataset.SeriesInstanceUID
    )

    case.update_metadata(
        "modality",
        "CT",
    )

    case.update_metadata(
        "body_region",
        "CHEST",
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

    print(
        "CASE METADATA: ATTACHED"
    )

    # ---------------------------------------------------------
    # 4. Safety Contract
    # ---------------------------------------------------------

    safety_contract = SafetyContract(
        contract_id="CT2-LUNG-NODULE-DEMO",
        approved_tools=[
            "lung_nodule_detection"
        ],
        task_preconditions=[
            "CT modality required",
            "Chest body region required",
            "Valid 3D CT volume required",
        ],
        data_policy=DataPolicy(
            allowed_modalities=[
                "CT"
            ],
            allowed_body_regions=[
                "CHEST"
            ],
            required_data=[
                "image",
                "acquisition_metadata",
            ],
        ),
        operation_policy=OperationPolicy(
            allowed_operations=[
                "observe",
                "detect",
                "recommend_review",
            ],
            maximum_action_tier="T1",
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

    case.safety_contract = safety_contract

    assert case.safety_contract is not None

    assert safety_contract.is_tool_permitted(
        "lung_nodule_detection"
    )

    print(
        "SAFETY CONTRACT CT-2 PERMISSION: PASS"
    )

    # ---------------------------------------------------------
    # 5. Task Graph
    # ---------------------------------------------------------

    intake_task = TaskNode(
        task_id="ct2-intake",
        task_type="intake",
        description=(
            "Validate chest CT input and metadata."
        ),
        status=TaskStatus.PROPOSED,
        permitted_tools=[],
        preconditions=[
            "CT modality",
            "Chest body region",
        ],
        verification_required=False,
    )

    case.add_task(
        intake_task
    )

    # Complete intake after the task has been added.
    case.task_graph.mark_completed(
        "ct2-intake"
    )

    detection_task = TaskNode(
        task_id="ct2-lung-nodule-detection",
        task_type="lung_nodule_detection",
        description=(
            "Run research/demo lung-nodule "
            "detection."
        ),
        status=TaskStatus.PROPOSED,
        dependencies=[
            "ct2-intake"
        ],
        permitted_tools=[
            "lung_nodule_detection"
        ],
        preconditions=[
            "Valid CT volume",
            "Valid chest metadata",
        ],
        verification_required=True,
    )

    case.add_task(
        detection_task
    )

    ready_tasks = (
        case.task_graph.get_ready_tasks()
    )

    assert any(
        task.task_id
        == "ct2-lung-nodule-detection"
        for task in ready_tasks
    )

    print(
        "TASK GRAPH: CT-2 READY"
    )

    # ---------------------------------------------------------
    # 6. Tool selection
    # ---------------------------------------------------------

    case.set_available_tools(
        [
            "lung_nodule_detection"
        ]
    )

    case.select_tool(
        "lung_nodule_detection"
    )

    assert (
        "lung_nodule_detection"
        in case.selected_tools
    )

    print(
        "TOOL SELECTION: PASS"
    )

    # ---------------------------------------------------------
    # 7. Run CT-2
    #
    # Use a controlled crop so CPU inference remains
    # practical, matching the existing CT-2 regression.
    # ---------------------------------------------------------

    start = 80
    end = 160

    cropped_volume = volume[
        start:end
    ]

    image_position_patient = tuple(
        float(value)
        for value in datasets[
            start
        ].ImagePositionPatient
    )

    image_orientation_patient = tuple(
        float(value)
        for value in datasets[
            start
        ].ImageOrientationPatient
    )

    tool = LungNoduleDetectionTool()

    case.task_graph.get_task(
        "ct2-lung-nodule-detection"
    ).status = TaskStatus.RUNNING

    result = tool.run(
        {
            "volume": cropped_volume,
            "voxel_spacing": voxel_spacing,
            "image_position_patient": (
                image_position_patient
            ),
            "image_orientation_patient": (
                image_orientation_patient
            ),
        }
    )

    assert result[
        "tool_name"
    ] == "lung_nodule_detection"

    print(
        "CT-2 EXECUTION: PASS"
    )

    # ---------------------------------------------------------
    # 8. Complete task
    # ---------------------------------------------------------

    case.task_graph.mark_completed(
        "ct2-lung-nodule-detection"
    )

    task = case.task_graph.get_task(
        "ct2-lung-nodule-detection"
    )

    assert (
        task.status
        == TaskStatus.COMPLETED
    )

    print(
        "TASK COMPLETION: PASS"
    )

    # ---------------------------------------------------------
    # 9. Create EvidenceItem
    # ---------------------------------------------------------

    evidence = EvidenceItem(
        evidence_id="EV-CT2-0001",
        case_id=case.case_id,
        evidence_type="lung_nodule_detection",
        source="lung_nodule_detection",
        claim=(
            "Research/demo lung-nodule detection "
            "output generated from chest CT."
        ),
        output=result,
        status=EvidenceStatus.PROPOSED,
        confidence=None,
        applicable=True,
        image_ids=[],
        series_uid=series_instance_uid,
        supporting_slices=[],
        supporting_regions=[],
        provenance=EvidenceProvenance(
            tool_name=result[
                "tool_name"
            ],
            tool_version=result[
                "tool_version"
            ],
            model_name=result[
                "model_name"
            ],
            model_version=result[
                "model_version"
            ],
            runtime=result[
                "device"
            ],
            input_references=[
                "CASE-LUNG-0001",
                series_instance_uid,
            ],
            metadata={
                "input_shape": result[
                    "input_shape"
                ],
                "input_spacing": result[
                    "input_spacing"
                ],
                "target_spacing": result[
                    "target_spacing"
                ],
            },
        ),
        verification_ids=[],
        task_id=(
            "ct2-lung-nodule-detection"
        ),
        dependencies=[],
        warnings=result[
            "warnings"
        ],
        metadata={
            "clinical_use": result[
                "clinical_use"
            ],
            "verification_required": result[
                "verification_required"
            ],
        },
    )

    case.add_evidence(
        evidence
    )

    stored_evidence = case.get_evidence(
        "EV-CT2-0001"
    )

    assert stored_evidence is not None

    print(
        "EVIDENCE ITEM: CREATED"
    )

    # ---------------------------------------------------------
    # 10. CT-2 verification
    # ---------------------------------------------------------

    verifier = CT2VerificationEngine()

    verification = verifier.verify(
        {
            "ct_metadata": {
                "modality": "CT",
                "body_region": "CHEST",
                "slice_count": len(
                    datasets
                ),
                "voxel_spacing": voxel_spacing,
                "study_instance_uid": (
                    study_instance_uid
                ),
                "series_instance_uid": (
                    series_instance_uid
                ),
            },
            "detection_result": result,
        }
    )

    print(
        "CT-2 VERIFICATION: COMPLETED"
    )

    assert (
        verification["decision"]
        == "verified_for_workflow_review"
    )

    assert (
        verification["human_review_required"]
        is True
    )

    assert (
        verification["failed_checks"]
        == []
    )

    # ---------------------------------------------------------
    # 11. Attach verification to evidence
    # ---------------------------------------------------------

    evidence.verification_ids.append(
        "VER-CT2-0001"
    )

    evidence.mark_requires_review()

    # CaseState.set_verification() stores the supplied
    # status directly, so use the actual enum rather
    # than a raw string.
    case.set_verification(
        status=VerificationStatus.REQUIRES_REVIEW,
        checks=verification[
            "checks"
        ],
        warnings=verification[
            "warnings"
        ],
        failed_checks=verification[
            "failed_checks"
        ],
        human_review_required=True,
    )

    # CaseState.set_status() also expects the
    # CaseStatus enum.
    case.set_status(
        CaseStatus.REQUIRES_REVIEW
    )

    # ---------------------------------------------------------
    # 12. Governance assertions
    # ---------------------------------------------------------

    assert (
        evidence.status
        == EvidenceStatus.REQUIRES_REVIEW
    )

    assert (
        case.verification.human_review_required
        is True
    )

    assert (
        case.status
        == CaseStatus.REQUIRES_REVIEW
    )

    assert (
        case.verification.status
        == VerificationStatus.REQUIRES_REVIEW
    )

    print(
        "HUMAN REVIEW BOUNDARY: PASS"
    )

    # ---------------------------------------------------------
    # 13. No autonomous clinical conclusion
    # ---------------------------------------------------------

    assert (
        verification[
            "safety"
        ][
            "clinical_diagnosis_authorized"
        ]
        is False
    )

    assert (
        verification[
            "safety"
        ][
            "treatment_authorized"
        ]
        is False
    )

    assert (
        verification[
            "safety"
        ][
            "irreversible_action_authorized"
        ]
        is False
    )

    print(
        "NO AUTONOMOUS CLINICAL CONCLUSION: PASS"
    )

    # ---------------------------------------------------------
    # 14. Evidence boundary
    #
    # Verified-for-workflow-review does NOT make the
    # evidence valid clinical evidence. The evidence
    # remains explicitly in review because human review
    # is required.
    # ---------------------------------------------------------

    valid_evidence = (
        case.get_valid_evidence()
    )

    assert (
        "EV-CT2-0001"
        not in [
            item.evidence_id
            for item in valid_evidence
        ]
    )

    review_evidence = (
        case.get_review_required_evidence()
    )

    assert (
        "EV-CT2-0001"
        in [
            item.evidence_id
            for item in review_evidence
        ]
    )

    print(
        "EVIDENCE REVIEW BOUNDARY: PASS"
    )

    # ---------------------------------------------------------
    # 15. Final integration output
    # ---------------------------------------------------------

    print()
    print("=" * 60)
    print(
        "CT-2 GOVERNED INTEGRATION: PASS"
    )
    print("=" * 60)

    print(
        f"Case: {case.case_id}"
    )

    print(
        f"Tool: {result['tool_name']}"
    )

    print(
        f"Model: {result['model_name']}"
    )

    print(
        f"Input volume: {cropped_volume.shape}"
    )

    print(
        "Verification: "
        f"{verification['decision']}"
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
        f"{case.verification.human_review_required}"
    )


if __name__ == "__main__":
    test_ct2_governed_integration()