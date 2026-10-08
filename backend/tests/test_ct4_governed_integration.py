from pathlib import Path
from uuid import uuid4

from pydicom import dcmread

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
    OperationPolicy,
    SafetyContract,
    UncertaintyPolicy,
    EscalationPolicy,
    ResourcePolicy,
)
from agent.task_graph import (
    TaskNode,
    TaskStatus,
)
from tools.pancreas_tumor_segmentation import (
    PancreasTumorSegmentationTool,
)
from verification.ct4_verification import (
    CT4VerificationEngine,
)


CASE_ID = "CASE-ABDOMEN-0001"

SERIES_DIR = Path(
    "uploads/CASE-ABDOMEN-0001/series"
)


def assert_true(
    condition,
    message,
):
    if not condition:
        raise AssertionError(message)


def load_ct_metadata(
    dicom_files,
    voxel_spacing,
):
    """
    Build the metadata required by CaseState
    and CT-4 verification.
    """

    first = dcmread(
        str(dicom_files[0]),
        stop_before_pixels=True,
    )

    return {
        "modality": str(
            getattr(
                first,
                "Modality",
                "",
            )
        ).upper(),

        "body_region": str(
            getattr(
                first,
                "BodyPartExamined",
                "",
            )
        ).upper(),

        "slice_count": len(
            dicom_files
        ),

        "voxel_spacing": list(
            voxel_spacing
        ),

        "study_instance_uid": str(
            getattr(
                first,
                "StudyInstanceUID",
                "",
            )
        ),

        "series_instance_uid": str(
            getattr(
                first,
                "SeriesInstanceUID",
                "",
            )
        ),
    }


def build_safety_contract():
    """
    Build the case-specific CT-4 safety contract.
    """

    return SafetyContract(
        contract_id=(
            "CT4-CONTRACT-"
            "CASE-ABDOMEN-0001"
        ),

        data_policy=DataPolicy(
            allowed_modalities=[
                "CT",
            ],

            allowed_body_regions=[
                "PANCREAS",
                "ABDOMEN",
                "ABDOMINAL",
            ],

            required_data=[
                "DICOM_series",
                "voxel_spacing",
                "study_instance_uid",
                "series_instance_uid",
            ],
        ),

        approved_tools=[
            "pancreas_tumor_segmentation",
        ],

        task_preconditions={
            "ct4_pancreas_tumor_segmentation": [
                "modality_is_CT",
                "body_region_is_compatible",
                "DICOM_series_available",
                "voxel_spacing_available",
                "series_identity_available",
            ],
        },

        operation_policy=OperationPolicy(
            allowed_operations=[
                "analyze_ct_pancreas",
                "generate_segmentation_evidence",
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
                "human_clinical_review",
            ],

            human_review_required=True,
        ),

        resource_policy=ResourcePolicy(
            maximum_retries=0,
            timeout_seconds=300,
            maximum_concurrent_tools=1,
        ),
    )


def main():

    print()
    print("=" * 70)
    print("CT-4 GOVERNED INTEGRATION TEST")
    print("=" * 70)

    # --------------------------------------------------------------
    # 1. Locate DICOM series
    # --------------------------------------------------------------

    dicom_files = sorted(
        SERIES_DIR.glob("*.dcm")
    )

    assert_true(
        len(dicom_files) > 0,
        "No DICOM files found.",
    )

    print(
        f"DICOM FILES: {len(dicom_files)}"
    )

    # --------------------------------------------------------------
    # 2. Preprocess through the existing CT pipeline
    # --------------------------------------------------------------

    from preprocessing.ct_preprocessing import (
        preprocess_ct_series,
    )

    preprocessing_result = (
        preprocess_ct_series(
            dicom_files
        )
    )

    volume = preprocessing_result[
        "volume"
    ]

    voxel_spacing = preprocessing_result[
        "voxel_spacing"
    ]

    print(
        f"CT VOLUME: {volume.shape}"
    )

    print(
        f"VOXEL SPACING (Z,Y,X): "
        f"{voxel_spacing}"
    )

    # --------------------------------------------------------------
    # 3. Create CaseState
    # --------------------------------------------------------------

    case = CaseState(
        case_id=CASE_ID,
        modality=CaseModality.CT,
        body_region="PANCREAS",
        clinical_question=(
            "Research evaluation of pancreas "
            "and pancreatic tumor segmentation."
        ),
    )

    assert_true(
        case.case_id == CASE_ID,
        "CaseState case ID mismatch.",
    )

    print(
        "CASE STATE: CREATED"
    )

    # --------------------------------------------------------------
    # 4. Add CT metadata to CaseState
    # --------------------------------------------------------------

    ct_metadata = load_ct_metadata(
        dicom_files,
        voxel_spacing,
    )

    for key, value in ct_metadata.items():
        case.update_metadata(
            key,
            value,
        )

    print(
        "CASE METADATA: ATTACHED"
    )

    # --------------------------------------------------------------
    # 5. Build Safety Contract
    # --------------------------------------------------------------

    contract = (
        build_safety_contract()
    )

    case.safety_contract = contract

    print(
        "SAFETY CONTRACT: ATTACHED"
    )

    # --------------------------------------------------------------
    # 6. Check CT-4 permission
    # --------------------------------------------------------------

    tool_permission = (
        contract.validate_tool(
            "pancreas_tumor_segmentation"
        )
    )

    assert_true(
        tool_permission["allowed"],
        "CT-4 was not permitted by the Safety Contract.",
    )

    print(
        "SAFETY CONTRACT CT-4 PERMISSION: PASS"
    )

    # --------------------------------------------------------------
    # 7. Check operation permission
    # --------------------------------------------------------------

    operation_permission = (
        contract.is_operation_permitted(
            "analyze_ct_pancreas"
        )
    )

    assert_true(
        operation_permission,
        "CT pancreas analysis operation is not permitted.",
    )

    print(
        "OPERATION PERMISSION: PASS"
    )

    # --------------------------------------------------------------
    # 8. Add bounded task graph
    # --------------------------------------------------------------

    intake_task = TaskNode(
        task_id="intake",
        task_type="intake",
        description=(
            "Validate CT case input."
        ),
        permitted_tools=[],
        verification_required=True,
    )

    case.add_task(
        intake_task
    )

    case.task_graph.mark_completed(
        "intake"
    )

    ct4_task = TaskNode(
        task_id="ct4_segmentation",
        task_type=(
            "ct4_pancreas_tumor_segmentation"
        ),
        description=(
            "Run governed CT-4 pancreas and "
            "pancreatic tumor segmentation."
        ),
        dependencies=[
            "intake"
        ],
        permitted_tools=[
            "pancreas_tumor_segmentation"
        ],
        preconditions=[
            "modality_is_CT",
            "body_region_is_compatible",
            "DICOM_series_available",
            "voxel_spacing_available",
            "series_identity_available",
        ],
        verification_required=True,
        stopping_conditions=[
            "invalid_input",
            "tool_failure",
            "verification_failure",
        ],
    )

    case.add_task(
        ct4_task
    )

    ready_tasks = (
        case.task_graph.get_ready_tasks()
    )

    assert_true(
        any(
            task.task_id
            == "ct4_segmentation"
            for task in ready_tasks
        ),
        "CT-4 task is not ready.",
    )

    print(
        "TASK GRAPH: CT-4 READY"
    )

    # --------------------------------------------------------------
    # 9. Select CT-4
    # --------------------------------------------------------------

    case.set_available_tools(
        [
            "pancreas_tumor_segmentation"
        ]
    )

    case.select_tool(
        "pancreas_tumor_segmentation"
    )

    assert_true(
        "pancreas_tumor_segmentation"
        in case.selected_tools,
        "CT-4 was not selected.",
    )

    print(
        "TOOL SELECTION: PASS"
    )

    # --------------------------------------------------------------
    # 10. Execute CT-4
    # --------------------------------------------------------------

    case.set_status(
        CaseStatus.ANALYZING
    )

    tool = (
        PancreasTumorSegmentationTool()
    )

    segmentation_result = tool.run(
        {
            "modality": "CT",
            "series_dir": str(
                SERIES_DIR
            ),
        }
    )

    assert_true(
        segmentation_result.get(
            "tool_name"
        )
        == "pancreas_tumor_segmentation",
        "CT-4 execution returned unexpected tool name.",
    )

    print(
        "CT-4 EXECUTION: PASS"
    )

    # --------------------------------------------------------------
    # 11. Mark task completed
    # --------------------------------------------------------------

    case.task_graph.mark_completed(
        "ct4_segmentation"
    )

    assert_true(
        case.task_graph.get_task(
            "ct4_segmentation"
        ).status
        == TaskStatus.COMPLETED,
        "CT-4 task was not marked completed.",
    )

    print(
        "TASK COMPLETION: PASS"
    )

    # --------------------------------------------------------------
    # 12. Create governed EvidenceItem
    # --------------------------------------------------------------

    evidence_id = (
        f"EVIDENCE-CT4-{uuid4().hex[:8]}"
    )

    provenance = EvidenceProvenance(
        tool_name=segmentation_result.get(
            "tool_name"
        ),

        tool_version=segmentation_result.get(
            "tool_version"
        ),

        model_name=segmentation_result.get(
            "model_name"
        ),

        model_version=segmentation_result.get(
            "model_version"
        ),

        runtime=(
            "python/"
            "torch/"
            "monai/"
            "cpu"
        ),

        input_references=[
            (
                "study:"
                + ct_metadata[
                    "study_instance_uid"
                ]
            ),

            (
                "series:"
                + ct_metadata[
                    "series_instance_uid"
                ]
            ),
        ],

        metadata={
            "input_shape": segmentation_result.get(
                "input_shape"
            ),

            "resampled_shape": segmentation_result.get(
                "resampled_shape"
            ),

            "voxel_spacing": list(
                voxel_spacing
            ),

            "clinical_use": segmentation_result.get(
                "clinical_use"
            ),

            "verification_required": (
                segmentation_result.get(
                    "verification_required"
                )
            ),
        },
    )

    evidence = EvidenceItem(
        evidence_id=evidence_id,

        case_id=CASE_ID,

        evidence_type=(
            "ct4_segmentation"
        ),

        source=(
            "pancreas_tumor_segmentation"
        ),

        claim=(
            "CT-4 generated research/demo "
            "segmentation evidence for pancreas "
            "and pancreatic tumor labels."
        ),

        output=segmentation_result,

        status=EvidenceStatus.PROPOSED,

        applicable=None,

        series_uid=ct_metadata[
            "series_instance_uid"
        ],

        task_id="ct4_segmentation",

        dependencies=[
            "intake"
        ],

        warnings=list(
            segmentation_result.get(
                "warnings",
                []
            )
        ),

        provenance=provenance,
    )

    case.add_evidence(
        evidence
    )

    assert_true(
        case.get_evidence(
            evidence_id
        ).status
        == EvidenceStatus.PROPOSED,
        "Evidence was not created as PROPOSED.",
    )

    print(
        "EVIDENCE ITEM: CREATED"
    )

    # --------------------------------------------------------------
    # 13. Verify CT-4 evidence
    # --------------------------------------------------------------

    case.set_status(
        CaseStatus.VERIFICATION
    )

    verifier = (
        CT4VerificationEngine()
    )

    verification_result = verifier.verify(
        {
            "ct_metadata": ct_metadata,
            "segmentation_result": (
                segmentation_result
            ),
        }
    )

    print(
        "CT-4 VERIFICATION: COMPLETED"
    )

    # --------------------------------------------------------------
    # 14. Attach verification to evidence
    # --------------------------------------------------------------

    verification_id = (
        f"VERIFICATION-CT4-"
        f"{uuid4().hex[:8]}"
    )

    verification_checks = (
        verification_result[
            "verification"
        ][
            "checks"
        ]
    )

    failed_checks = [
        name
        for name, result
        in verification_checks.items()
        if result.get("status")
        == "failed"
    ]

    all_passed = (
        verification_result[
            "verification"
        ][
            "all_required_checks_passed"
        ]
    )

    decision = (
        verification_result[
            "decision"
        ]
    )

    # --------------------------------------------------------------
    # 15. Govern evidence status
    # --------------------------------------------------------------

    if all_passed:
        evidence.mark_requires_review(
            verification_id=verification_id
        )

        case.set_verification(
            status=(
                VerificationStatus.REQUIRES_REVIEW
            ),

            checks=[
                {
                    "name": name,
                    **result,
                }
                for name, result
                in verification_checks.items()
            ],

            warnings=list(
                segmentation_result.get(
                    "warnings",
                    []
                )
            ),

            failed_checks=[],

            human_review_required=True,
        )

        case.set_status(
            CaseStatus.REQUIRES_REVIEW
        )

    else:
        evidence.invalidate(
            reason=(
                "CT-4 verification failed: "
                + ", ".join(
                    failed_checks
                )
            ),

            verification_id=verification_id,
        )

        case.set_verification(
            status=(
                VerificationStatus.FAILED
            ),

            checks=[
                {
                    "name": name,
                    **result,
                }
                for name, result
                in verification_checks.items()
            ],

            warnings=[
                (
                    "CT-4 verification failed."
                )
            ],

            failed_checks=failed_checks,

            human_review_required=True,
        )

        case.set_status(
            CaseStatus.ABSTAINED
        )

    # --------------------------------------------------------------
    # 16. Final assertions
    # --------------------------------------------------------------

    assert_true(
        verification_id
        in evidence.verification_ids,
        "Verification ID was not attached to evidence.",
    )

    assert_true(
        evidence.case_id == CASE_ID,
        "Evidence case ID does not match CaseState.",
    )

    assert_true(
        evidence.provenance.tool_name
        == "pancreas_tumor_segmentation",
        "Evidence provenance tool name is incorrect.",
    )

    assert_true(
        evidence.provenance.model_name
        == segmentation_result.get(
            "model_name"
        ),
        "Evidence provenance model name is incorrect.",
    )

    assert_true(
        evidence.provenance.model_version
        == segmentation_result.get(
            "model_version"
        ),
        "Evidence provenance model version is incorrect.",
    )

    assert_true(
        evidence.status
        == EvidenceStatus.REQUIRES_REVIEW,
        "CT-4 evidence should require human review.",
    )

    assert_true(
        case.verification.status
        == VerificationStatus.REQUIRES_REVIEW,
        "Case verification should require human review.",
    )

    assert_true(
        case.status
        == CaseStatus.REQUIRES_REVIEW,
        "Case should enter requires_review state.",
    )

    assert_true(
        case.verification.human_review_required
        is True,
        "Human review requirement was not preserved.",
    )

    assert_true(
        decision[
            "human_review_required"
        ]
        is True,
        "Verifier did not require human review.",
    )

    # --------------------------------------------------------------
    # 17. Print governed result
    # --------------------------------------------------------------

    print()
    print("=" * 70)
    print("GOVERNED CT-4 RESULT")
    print("=" * 70)

    print(
        f"CASE ID: {case.case_id}"
    )

    print(
        f"CASE STATUS: {case.status.value}"
    )

    print(
        f"EVIDENCE ID: {evidence.evidence_id}"
    )

    print(
        f"EVIDENCE STATUS: "
        f"{evidence.status.value}"
    )

    print(
        f"VERIFICATION STATUS: "
        f"{case.verification.status.value}"
    )

    print(
        "HUMAN REVIEW REQUIRED: "
        f"{case.verification.human_review_required}"
    )

    print(
        "FAILED CHECKS: "
        f"{failed_checks}"
    )

    print(
        "TOOL: "
        f"{evidence.provenance.tool_name}"
    )

    print(
        "MODEL: "
        f"{evidence.provenance.model_name}"
    )

    print(
        "MODEL VERSION: "
        f"{evidence.provenance.model_version}"
    )

    print(
        "CLINICAL DIAGNOSIS AUTHORIZED: "
        "False"
    )

    print(
        "TREATMENT AUTHORIZED: "
        "False"
    )

    print(
        "IRREVERSIBLE ACTION AUTHORIZED: "
        "False"
    )

    print()
    print(
        "CT-4 GOVERNED INTEGRATION: PASS"
    )
    print("=" * 70)


if __name__ == "__main__":
    main()