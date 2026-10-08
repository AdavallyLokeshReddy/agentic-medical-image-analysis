from agent.case_state import (
    CaseState,
    EvidenceItem,
    EvidenceProvenance,
    EvidenceStatus,
)


def test_create_evidence_with_provenance():
    provenance = EvidenceProvenance(
        tool_name="ich_detection",
        tool_version="research-model",
        model_name="ct-head-hemorrhage-detection",
        model_version="914c57d",
        runtime="pytorch_cpu",
        input_references=["SERIES-001"],
    )

    evidence = EvidenceItem(
        evidence_id="EVID-001",
        case_id="CASE-0005",
        evidence_type="model_output",
        source="ich_detection",
        claim="Possible intracranial hemorrhage detected",
        output={"any": 0.82},
        confidence=0.82,
        image_ids=["IMG-001", "IMG-002"],
        series_uid="SERIES-001",
        supporting_slices=[12, 13],
        provenance=provenance,
        task_id="TASK-ICH",
    )

    assert evidence.evidence_id == "EVID-001"
    assert evidence.case_id == "CASE-0005"
    assert evidence.provenance.tool_name == "ich_detection"
    assert evidence.provenance.model_name == "ct-head-hemorrhage-detection"
    assert evidence.series_uid == "SERIES-001"
    assert evidence.supporting_slices == [12, 13]


def test_evidence_status_transitions():
    evidence = EvidenceItem(
        evidence_id="EVID-002",
        case_id="CASE-0005",
        evidence_type="model_output",
        source="ich_detection",
        claim="Possible hemorrhage",
        output={"any": 0.75},
    )

    assert evidence.status == EvidenceStatus.PROPOSED

    evidence.mark_valid()

    assert evidence.status == EvidenceStatus.VALID
    assert evidence.applicable is True

    evidence.mark_requires_review()

    assert evidence.status == EvidenceStatus.REQUIRES_REVIEW

    evidence.invalidate("Verification failed")

    assert evidence.status == EvidenceStatus.INVALID
    assert "Verification failed" in evidence.warnings


def test_case_state_valid_and_review_evidence():
    case = CaseState(
        case_id="CASE-0005",
        modality="CT",
        body_region="head",
        clinical_question="Evaluate for intracranial hemorrhage",
    )

    valid_evidence = EvidenceItem(
        evidence_id="EVID-VALID",
        case_id="CASE-0005",
        evidence_type="model_output",
        source="ich_detection",
        claim="No strong hemorrhage signal",
        output={"any": 0.20},
    )

    review_evidence = EvidenceItem(
        evidence_id="EVID-REVIEW",
        case_id="CASE-0005",
        evidence_type="model_output",
        source="ich_detection",
        claim="Possible hemorrhage",
        output={"any": 0.75},
    )

    valid_evidence.mark_valid()
    review_evidence.mark_requires_review()

    case.add_evidence(valid_evidence)
    case.add_evidence(review_evidence)

    valid = case.get_valid_evidence()
    review = case.get_review_required_evidence()

    assert len(valid) == 1
    assert valid[0].evidence_id == "EVID-VALID"

    assert len(review) == 1
    assert review[0].evidence_id == "EVID-REVIEW"


def test_case_state_invalidates_evidence():
    case = CaseState(
        case_id="CASE-0005",
        modality="CT",
        body_region="head",
        clinical_question="Evaluate for intracranial hemorrhage",
    )

    evidence = EvidenceItem(
        evidence_id="EVID-003",
        case_id="CASE-0005",
        evidence_type="model_output",
        source="ich_detection",
        claim="Possible hemorrhage",
        output={"any": 0.80},
    )

    evidence.mark_valid()
    case.add_evidence(evidence)

    case.invalidate_evidence(
        "EVID-003",
        reason="Technical verification failed",
    )

    assert evidence.status == EvidenceStatus.INVALID
    assert evidence.applicable is False
    assert "Technical verification failed" in evidence.warnings