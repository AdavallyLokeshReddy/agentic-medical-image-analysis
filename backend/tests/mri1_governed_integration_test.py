from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import nibabel as nib

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

from tools.brain_tumor_segmentation import (
    BrainTumorSegmentationTool,
)

from verification.mri1_verification import (
    MRI1VerificationEngine,
)


CASE_ID = "BraTS-GLI-00000-000"

CASE_DIR = Path(
    "data/mri/brats2023-gli/BraTS-GLI-00000-000/"
    "ASNR-MICCAI-BraTS2023-GLI-Challenge-TrainingData/"
    "BraTS-GLI-00000-000"
)


def main() -> None:

    print()
    print("=== MRI-1 STEP 15: GOVERNED INTEGRATION TEST ===")
    print("=" * 60)

    # =========================================================
    # 1. Validate MRI input sequences
    # =========================================================

    sequence_paths = {
        "T1C": CASE_DIR / "BraTS-GLI-00000-000-t1c.nii.gz",
        "T1": CASE_DIR / "BraTS-GLI-00000-000-t1n.nii.gz",
        "T2": CASE_DIR / "BraTS-GLI-00000-000-t2w.nii.gz",
        "FLAIR": CASE_DIR / "BraTS-GLI-00000-000-t2f.nii.gz",
    }

    print()
    print("1. MRI INPUT VALIDATION")

    for sequence_name, path in sequence_paths.items():

        assert path.exists(), (
            f"Missing MRI sequence: {sequence_name}: {path}"
        )

        print(f" - {sequence_name}: OK")

    print("MRI input validation: PASS")

    # =========================================================
    # 2. Inspect sequence geometry
    # =========================================================

    sequences = {}

    for sequence_name, path in sequence_paths.items():

        image = nib.load(str(path))

        shape = tuple(
            int(value)
            for value in image.shape
        )

        spacing = tuple(
            float(value)
            for value in image.header.get_zooms()[:3]
        )

        sequences[sequence_name] = {
            "shape": shape,
            "spacing": spacing,
        }

    reference_shape = sequences["T1C"]["shape"]

    assert reference_shape == (240, 240, 155)

    for sequence_name, metadata in sequences.items():

        assert metadata["shape"] == reference_shape, (
            f"{sequence_name} shape mismatch."
        )

        assert all(
            abs(value - 1.0) < 1e-5
            for value in metadata["spacing"]
        ), (
            f"{sequence_name} spacing is not 1mm isotropic."
        )

    print("MRI geometry/preconditions: PASS")

    # =========================================================
    # 3. Create CaseState
    # =========================================================

    case = CaseState(
        case_id=CASE_ID,
        modality=CaseModality.MRI,
        body_region="brain",
        clinical_question=(
            "Research/demo brain tumor segmentation "
            "workflow evaluation."
        ),
    )

    assert case.modality == CaseModality.MRI
    assert case.body_region == "brain"

    print("CaseState creation: PASS")

    # =========================================================
    # 4. Attach MRI case metadata
    # =========================================================

    case.update_metadata(
        "modality",
        "MRI",
    )

    case.update_metadata(
        "body_region",
        "brain",
    )

    case.update_metadata(
        "required_sequences",
        [
            "T1C",
            "T1",
            "T2",
            "FLAIR",
        ],
    )

    case.update_metadata(
        "sequence_geometry",
        sequences,
    )

    print("CaseState MRI metadata: PASS")

    # =========================================================
    # 5. Build MRI-1 Safety Contract
    # =========================================================

    contract = SafetyContract(
        contract_id="MRI-1-BRAIN-TUMOR-RESEARCH",
        approved_tools=[
            "brain_tumor_segmentation",
        ],
        task_preconditions=[
            "MRI modality required",
            "Brain/head body region required",
            "T1C sequence required",
            "T1 sequence required",
            "T2 sequence required",
            "FLAIR sequence required",
            "1mm isotropic geometry required",
        ],
        data_policy=DataPolicy(
            allowed_modalities=[
                "MRI",
            ],
            allowed_body_regions=[
                "brain",
                "head",
                "neuro",
                "neurological",
            ],
            required_data=[
                "T1C",
                "T1",
                "T2",
                "FLAIR",
                "1mm isotropic geometry",
            ],
        ),
        operation_policy=OperationPolicy(
            allowed_operations=[
                "observe",
                "analyze",
                "segment",
                "generate_evidence",
                "request_human_review",
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
                "human_clinical_review",
                "specialist_review",
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

    assert case.safety_contract is not None

    assert contract.is_tool_permitted(
        "brain_tumor_segmentation"
    )

    assert contract.is_operation_permitted(
        "segment"
    )

    assert contract.is_operation_permitted(
        "generate_evidence"
    )

    assert contract.is_operation_permitted(
        "request_human_review"
    )

    print("Safety Contract authorization: PASS")

    # =========================================================
    # 6. Verify prohibited authority boundaries
    # =========================================================

    assert not contract.is_action_tier_permitted(
        ActionTier.T2
    )

    assert not contract.is_action_tier_permitted(
        ActionTier.T3
    )

    assert not contract.is_operation_permitted(
        "diagnose"
    )

    assert not contract.is_operation_permitted(
        "treat"
    )

    assert not contract.is_operation_permitted(
        "prescribe"
    )

    assert not contract.is_operation_permitted(
        "irreversible_action"
    )

    print("Clinical authority boundary: PASS")

    # =========================================================
    # 7. Create governed TaskGraph
    # =========================================================

    intake_task = TaskNode(
        task_id="mri1-intake",
        task_type="intake",
        description=(
            "Validate MRI sequences and geometry."
        ),
        status=TaskStatus.READY,
        permitted_tools=[],
        preconditions=[
            "MRI modality",
            "Brain body region",
            "T1C present",
            "T1 present",
            "T2 present",
            "FLAIR present",
            "1mm isotropic geometry",
        ],
        verification_required=False,
    )

    case.add_task(
        intake_task
    )

    case.task_graph.mark_completed(
        "mri1-intake"
    )

    segmentation_task = TaskNode(
        task_id="mri1-brain-tumor-segmentation",
        task_type="brain_tumor_segmentation",
        description=(
            "Run research/demo MRI-1 brain tumor "
            "segmentation."
        ),
        dependencies=[
            "mri1-intake",
        ],
        permitted_tools=[
            "brain_tumor_segmentation",
        ],
        preconditions=[
            "Valid MRI sequences",
            "Consistent sequence geometry",
            "1mm isotropic geometry",
        ],
        verification_required=True,
    )

    case.add_task(
        segmentation_task
    )

    ready_tasks = case.task_graph.get_ready_tasks()

    assert any(
        task.task_id
        == "mri1-brain-tumor-segmentation"
        for task in ready_tasks
    )

    print("TaskGraph authorization/readiness: PASS")

    # =========================================================
    # 8. Tool selection
    # =========================================================

    case.set_available_tools(
        [
            "brain_tumor_segmentation",
        ]
    )

    case.select_tool(
        "brain_tumor_segmentation"
    )

    assert (
        "brain_tumor_segmentation"
        in case.selected_tools
    )

    print("Tool selection: PASS")

    # =========================================================
    # 9. Execute MRI-1 through approved tool
    # =========================================================

    tool = BrainTumorSegmentationTool()

    task = case.task_graph.get_task(
        "mri1-brain-tumor-segmentation"
    )

    task.status = TaskStatus.RUNNING

    output = tool.run(
        {
            "T1c": str(sequence_paths["T1C"]),
            "T1": str(sequence_paths["T1"]),
            "T2": str(sequence_paths["T2"]),
            "FLAIR": str(sequence_paths["FLAIR"]),
        }
    )

    assert output["tool"] == "brain_tumor_segmentation"

    assert (
        output["verification_required"]
        is True
    )

    assert (
        output["clinical_use"]
        == "research_demo_only"
    )

    assert output["runtime"]["device"] == "cpu"

    print("MRI-1 execution: PASS")

    # =========================================================
    # 10. Complete segmentation task
    # =========================================================

    case.task_graph.mark_completed(
        "mri1-brain-tumor-segmentation"
    )

    assert (
        case.task_graph.get_task(
            "mri1-brain-tumor-segmentation"
        ).status
        == TaskStatus.COMPLETED
    )

    print("Task completion: PASS")

    # =========================================================
    # 11. Verify MRI-1 output
    # =========================================================

    verifier = MRI1VerificationEngine()

    verification = verifier.verify(
        {
            "mri_metadata": {
                "modality": "MRI",
                "body_region": "brain",
                "sequences": sequences,
            },
            "segmentation_result": output,
        }
    )

    assert verification["verified"] is True

    assert (
        verification["decision"]
        == "verified_for_workflow_review"
    )

    assert verification["failures"] == []

    assert (
        verification["human_review_required"]
        is True
    )

    assert (
        verification["safe_for_autonomous_diagnosis"]
        is False
    )

    assert (
        verification["safe_for_autonomous_treatment"]
        is False
    )

    assert (
        verification["safe_for_irreversible_action"]
        is False
    )

    print("MRI-1 verification: PASS")

    # =========================================================
    # 12. Create governed EvidenceItem
    # =========================================================

    evidence = EvidenceItem(
        evidence_id=(
            f"{CASE_ID}:MRI1:GOVERNED:001"
        ),
        case_id=CASE_ID,
        evidence_type=(
            "MRI_BRAIN_TUMOR_SEGMENTATION"
        ),
        source="brain_tumor_segmentation",
        claim=(
            "Research/demo MRI-1 segmentation "
            "evidence generated under the MRI-1 "
            "Safety Contract."
        ),
        output=output,
        status=EvidenceStatus.PROPOSED,
        applicable=True,
        image_ids=[],
        series_uid=None,
        supporting_slices=[],
        supporting_regions=[
            {
                "region": region,
                "voxel_count": int(
                    output["label_summary"][region][
                        "voxel_count"
                    ]
                ),
            }
            for region in (
                "tumor_core",
                "whole_tumor",
                "enhancing_tumor",
            )
        ],
        provenance=EvidenceProvenance(
            tool_name=output["tool"],
            tool_version=output["tool_version"],
            model_name=output["model"],
            model_version=output["model_version"],
            runtime=output["runtime"]["device"],
            input_references=[
                str(sequence_paths["T1C"]),
                str(sequence_paths["T1"]),
                str(sequence_paths["T2"]),
                str(sequence_paths["FLAIR"]),
            ],
            metadata={
                "safety_contract_id": (
                    contract.contract_id
                ),
                "verification_decision": (
                    verification["decision"]
                ),
                "runtime": output["runtime"],
                "model_input_spacing": (
                    output["model_input_spacing"]
                ),
                "voxel_spacing": (
                    output["voxel_spacing"]
                ),
            },
        ),
        verification_ids=[
            "VER-MRI1-0001",
        ],
        task_id=(
            "mri1-brain-tumor-segmentation"
        ),
        dependencies=[],
        warnings=output["warnings"],
        metadata={
            "clinical_use": output["clinical_use"],
            "verification_required": (
                output["verification_required"]
            ),
            "human_review_required": (
                verification["human_review_required"]
            ),
            "autonomous_diagnosis": (
                verification[
                    "safe_for_autonomous_diagnosis"
                ]
            ),
            "autonomous_treatment": (
                verification[
                    "safe_for_autonomous_treatment"
                ]
            ),
            "irreversible_action": (
                verification[
                    "safe_for_irreversible_action"
                ]
            ),
            "safety_contract_id": (
                contract.contract_id
            ),
        },
    )

    case.add_evidence(
        evidence
    )

    stored_evidence = case.get_evidence(
        evidence.evidence_id
    )

    assert stored_evidence is not None

    print("Evidence attachment: PASS")

    # =========================================================
    # 13. Evidence governance state
    # =========================================================

    stored_evidence.mark_requires_review(
        verification_id="VER-MRI1-0001"
    )

    assert (
        stored_evidence.status
        == EvidenceStatus.REQUIRES_REVIEW
    )

    assert (
        "VER-MRI1-0001"
        in stored_evidence.verification_ids
    )

    print("Evidence human-review state: PASS")

    # =========================================================
    # 14. Record CaseState verification
    # =========================================================

    case.set_verification(
        VerificationStatus.REQUIRES_REVIEW,
        checks={
            "verified": verification["verified"],
            "decision": verification["decision"],
            "next_action": verification["next_action"],
        },
        warnings=verification["warnings"],
        failed_checks=verification["failures"],
        human_review_required=(
            verification["human_review_required"]
        ),
    )

    case.set_status(
        CaseStatus.REQUIRES_REVIEW
    )

    assert (
        case.verification.status
        == VerificationStatus.REQUIRES_REVIEW
    )

    assert (
        case.verification.human_review_required
        is True
    )

    print("CaseState verification state: PASS")

    # =========================================================
    # 15. Final governance assertions
    # =========================================================

    assert contract.is_tool_permitted(
        "brain_tumor_segmentation"
    )

    assert contract.is_operation_permitted(
        "request_human_review"
    )

    assert not contract.is_action_tier_permitted(
        ActionTier.T2
    )

    assert not contract.is_action_tier_permitted(
        ActionTier.T3
    )

    assert not contract.is_operation_permitted(
        "diagnose"
    )

    assert not contract.is_operation_permitted(
        "treat"
    )

    assert not contract.is_operation_permitted(
        "prescribe"
    )

    assert (
        verification["safe_for_autonomous_diagnosis"]
        is False
    )

    assert (
        verification["safe_for_autonomous_treatment"]
        is False
    )

    assert (
        verification["safe_for_irreversible_action"]
        is False
    )

    print("Governance boundary assertions: PASS")

    # =========================================================
    # 16. Final result
    # =========================================================

    print()
    print("=" * 60)
    print("MRI-1 STEP 15: GOVERNED INTEGRATION PASS")
    print("=" * 60)

    print()
    print("Governed chain:")
    print("   MRI sequences")
    print("        ↓")
    print("   CaseState")
    print("        ↓")
    print("   Safety Contract")
    print("        ↓")
    print("   TaskGraph")
    print("        ↓")
    print("   Tool authorization")
    print("        ↓")
    print("   MRI-1 execution")
    print("        ↓")
    print("   Verification")
    print("        ↓")
    print("   Evidence")
    print("        ↓")
    print("   Human review required")
    print("        ↓")
    print("   No autonomous diagnosis/treatment")
    print()
    print("MRI-1 STEP 15: PASS")


if __name__ == "__main__":
    main()