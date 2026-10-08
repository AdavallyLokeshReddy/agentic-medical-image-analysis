from agent.case_state import (
    CaseModality,
    CaseState,
    EvidenceItem,
    EvidenceProvenance,
    EvidenceStatus,
)

from reporting.structured_report import (
    ReportStatus,
    create_structured_draft_report,
)


def make_case() -> CaseState:
    return CaseState(
        case_id="CASE-001",
        modality=CaseModality.CT,
        body_region="head",
        clinical_question="Assess the CT study for intracranial abnormality.",
    )


def make_evidence(
    evidence_id: str,
    claim: str,
    status: EvidenceStatus,
) -> EvidenceItem:

    evidence = EvidenceItem(
        evidence_id=evidence_id,
        case_id="CASE-001",
        evidence_type="imaging_finding",
        source="ICHDetectionTool",
        claim=claim,
        output={"finding": claim},
        status=status,
        confidence=0.92,
        image_ids=["IMG-001"],
        series_uid="SERIES-001",
        supporting_slices=[10, 11],
        provenance=EvidenceProvenance(
            tool_name="ICHDetectionTool",
            tool_version="research-model",
            model_name="ianpan/ct-head-hemorrhage-detection",
            model_version="research",
            runtime="cpu",
            input_references=["IMG-001"],
        ),
        verification_ids=["VER-001"],
    )

    return evidence


def test_create_draft_report_from_valid_evidence():
    case = make_case()

    evidence = make_evidence(
        "E001",
        "Intracranial hemorrhage signal detected.",
        EvidenceStatus.VALID,
    )

    case.add_evidence(evidence)

    report = create_structured_draft_report(
        case,
        report_id="REPORT-001",
    )

    assert report.report_id == "REPORT-001"
    assert report.case_id == "CASE-001"
    assert report.status == ReportStatus.DRAFT

    assert len(report.observations) == 1
    assert report.observations[0].evidence_id == "E001"

    assert "E001" in report.evidence_references
    assert report.human_review_required is True


def test_invalid_evidence_is_not_used_as_observation():
    case = make_case()

    evidence = make_evidence(
        "E002",
        "Invalid finding that must not enter the report.",
        EvidenceStatus.INVALID,
    )

    case.add_evidence(evidence)

    report = create_structured_draft_report(
        case,
        report_id="REPORT-002",
    )

    assert len(report.observations) == 0
    assert "E002" not in report.evidence_references


def test_review_required_evidence_requires_review():
    case = make_case()

    evidence = make_evidence(
        "E003",
        "Finding requiring verification.",
        EvidenceStatus.REQUIRES_REVIEW,
    )

    case.add_evidence(evidence)

    report = create_structured_draft_report(
        case,
        report_id="REPORT-003",
    )

    assert report.status == ReportStatus.REQUIRES_REVIEW
    assert len(report.observations) == 0

    assert "E003" in report.evidence_references
    assert len(report.uncertainty) == 1
    assert report.human_review_required is True


def test_mixed_evidence_only_valid_evidence_becomes_observation():
    case = make_case()

    valid = make_evidence(
        "E004",
        "Valid imaging finding.",
        EvidenceStatus.VALID,
    )

    review = make_evidence(
        "E005",
        "Finding requiring review.",
        EvidenceStatus.REQUIRES_REVIEW,
    )

    invalid = make_evidence(
        "E006",
        "Invalid finding.",
        EvidenceStatus.INVALID,
    )

    case.add_evidence(valid)
    case.add_evidence(review)
    case.add_evidence(invalid)

    report = create_structured_draft_report(
        case,
        report_id="REPORT-004",
    )

    assert report.status == ReportStatus.REQUIRES_REVIEW

    assert len(report.observations) == 1
    assert report.observations[0].evidence_id == "E004"

    assert "E005" in report.evidence_references
    assert "E006" not in report.evidence_references


def test_no_eligible_evidence_blocks_report():
    case = make_case()

    report = create_structured_draft_report(
        case,
        report_id="REPORT-005",
    )

    assert report.status == ReportStatus.BLOCKED
    assert len(report.observations) == 0
    assert report.verification_status == "no_eligible_evidence"
    assert report.human_review_required is True


def test_report_preserves_provenance_references():
    case = make_case()

    evidence = make_evidence(
        "E007",
        "Verified imaging observation.",
        EvidenceStatus.VALID,
    )

    case.add_evidence(evidence)

    report = create_structured_draft_report(
        case,
        report_id="REPORT-006",
    )

    assert report.provenance["generator"] == (
        "governed_medical_imaging_agent"
    )

    assert report.provenance["case_id"] == "CASE-001"
    assert "E007" in report.provenance["evidence_ids"]


def test_report_serialization():
    case = make_case()

    evidence = make_evidence(
        "E008",
        "Verified observation.",
        EvidenceStatus.VALID,
    )

    case.add_evidence(evidence)

    report = create_structured_draft_report(
        case,
        report_id="REPORT-007",
    )

    data = report.to_dict()

    assert data["report_id"] == "REPORT-007"
    assert data["case_id"] == "CASE-001"
    assert data["status"] == "draft"

    assert len(data["observations"]) == 1
    assert data["observations"][0]["evidence_id"] == "E008"

def test_report_with_valid_evidence_still_requires_human_review():
    case = make_case()

    evidence = make_evidence(
        "E009",
        "Verified imaging observation.",
        EvidenceStatus.VALID,
    )

    case.add_evidence(evidence)

    report = create_structured_draft_report(
        case,
        report_id="REPORT-008",
    )

    # Even when all evidence is valid, the agent does not
    # obtain autonomous clinical authority.
    assert report.human_review_required is True


def test_report_with_review_evidence_cannot_be_draft_only():
    case = make_case()

    evidence = make_evidence(
        "E010",
        "Observation requiring additional verification.",
        EvidenceStatus.REQUIRES_REVIEW,
    )

    case.add_evidence(evidence)

    report = create_structured_draft_report(
        case,
        report_id="REPORT-009",
    )

    assert report.status == ReportStatus.REQUIRES_REVIEW
    assert report.verification_status == "review_required"
    assert report.human_review_required is True


def test_report_does_not_promote_invalid_evidence():
    case = make_case()

    evidence = make_evidence(
        "E011",
        "Invalid evidence must remain excluded.",
        EvidenceStatus.INVALID,
    )

    case.add_evidence(evidence)

    report = create_structured_draft_report(
        case,
        report_id="REPORT-010",
    )

    assert report.status == ReportStatus.BLOCKED
    assert report.observations == []
    assert report.evidence_references == []


def test_report_provenance_matches_report_evidence():
    case = make_case()

    valid = make_evidence(
        "E012",
        "Verified observation A.",
        EvidenceStatus.VALID,
    )

    review = make_evidence(
        "E013",
        "Observation requiring review.",
        EvidenceStatus.REQUIRES_REVIEW,
    )

    case.add_evidence(valid)
    case.add_evidence(review)

    report = create_structured_draft_report(
        case,
        report_id="REPORT-011",
    )

    assert report.provenance["case_id"] == case.case_id

    assert set(report.provenance["evidence_ids"]) == {
        "E012",
        "E013",
    }

    assert set(report.evidence_references) == {
        "E012",
        "E013",
    }