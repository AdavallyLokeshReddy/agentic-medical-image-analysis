import pytest

from agent.case_state import (
    CaseModality,
    CaseState,
    EvidenceItem,
    EvidenceStatus,
    VerificationState,
    VerificationStatus,
)
from agent.human_review import HumanReview, ReviewDecision, ReviewStatus
from agent.review_lifecycle import ReviewLifecycle
from reporting.structured_report import (
    ReportStatus,
    StructuredDraftReport,
)


def create_test_case() -> CaseState:
    case = CaseState(
        case_id="CASE-001",
        modality=CaseModality.CT,
        body_region="head",
        clinical_question="Evaluate the head CT.",
    )

    evidence = EvidenceItem(
        evidence_id="EVID-001",
        case_id="CASE-001",
        evidence_type="model_output",
        source="ich_detection",
        claim="Intracranial abnormality requires review.",
        output={"probability": 0.91},
        status=EvidenceStatus.VALID,
        confidence=0.91,
    )

    case.add_evidence(evidence)

    verification = VerificationState(
        status=VerificationStatus.PASSED,
        human_review_required=True,
    )

    case.verification = verification

    return case


def create_test_report() -> StructuredDraftReport:
    return StructuredDraftReport(
        report_id="REPORT-001",
        case_id="CASE-001",
        generated_at="2026-01-01T00:00:00+00:00",
        status=ReportStatus.REQUIRES_REVIEW,
        clinical_question="Evaluate the head CT.",
        modality="CT",
        body_region="head",
    )


def create_lifecycle() -> ReviewLifecycle:
    case = create_test_case()
    report = create_test_report()

    review = HumanReview(
        review_id="REVIEW-001",
        case_id="CASE-001",
        report_id="REPORT-001",
    )

    case.add_human_review(review)

    return ReviewLifecycle(
        case=case,
        report=report,
        review=review,
    )


def test_lifecycle_validates_case_and_report_relationships():
    case = create_test_case()
    report = create_test_report()

    review = HumanReview(
        review_id="REVIEW-001",
        case_id="CASE-001",
        report_id="WRONG-REPORT",
    )

    with pytest.raises(ValueError, match="Review report ID"):
        ReviewLifecycle(
            case=case,
            report=report,
            review=review,
        )


def test_review_can_start():
    lifecycle = create_lifecycle()

    review = lifecycle.start_review()

    assert review.status == ReviewStatus.PENDING
    assert review.started_at is not None


def test_review_context_records_evidence_and_verification():
    lifecycle = create_lifecycle()

    lifecycle.record_review_context(
        evidence_ids=["EVID-001"],
        verification_ids=["verification_passed"],
    )

    assert lifecycle.review.reviewed_evidence_ids == ["EVID-001"]
    assert lifecycle.review.reviewed_verification_ids == [
        "verification_passed"
    ]


def test_unknown_evidence_is_rejected():
    lifecycle = create_lifecycle()

    with pytest.raises(ValueError, match="Unknown evidence IDs"):
        lifecycle.record_review_context(
            evidence_ids=["UNKNOWN"],
            verification_ids=[],
        )


def test_unknown_verification_is_rejected():
    lifecycle = create_lifecycle()

    with pytest.raises(ValueError, match="Unknown verification IDs"):
        lifecycle.record_review_context(
            evidence_ids=[],
            verification_ids=["UNKNOWN"],
        )


def test_reviewer_can_accept_report():
    lifecycle = create_lifecycle()

    lifecycle.start_review()

    lifecycle.record_review_context(
        evidence_ids=["EVID-001"],
        verification_ids=["verification_passed"],
    )

    review = lifecycle.accept(
        reviewer_id="REVIEWER-001",
        comments=["Evidence reviewed."],
    )

    assert review.status == ReviewStatus.COMPLETED
    assert review.decision == ReviewDecision.ACCEPT
    assert review.reviewer_id == "REVIEWER-001"
    assert review.completed_at is not None


def test_reviewer_can_modify_without_overwriting_original_report():
    lifecycle = create_lifecycle()

    original_observations = list(lifecycle.report.observations)

    lifecycle.start_review()

    review = lifecycle.modify(
        reviewer_id="REVIEWER-001",
        modified_observations=[
            {
                "claim": "Human reviewer modified observation."
            }
        ],
        reason="Reviewer identified an interpretation requiring correction.",
    )

    assert review.status == ReviewStatus.COMPLETED
    assert review.decision == ReviewDecision.MODIFY

    assert review.modified_observations == [
        {
            "claim": "Human reviewer modified observation."
        }
    ]

    assert review.intervention_reason is not None

    # Original AI-generated report remains unchanged.
    assert lifecycle.report.observations == original_observations


def test_reviewer_can_reject_report():
    lifecycle = create_lifecycle()

    lifecycle.start_review()

    review = lifecycle.reject(
        reviewer_id="REVIEWER-001",
        reason="Generated report is not acceptable.",
    )

    assert review.status == ReviewStatus.COMPLETED
    assert review.decision == ReviewDecision.REJECT
    assert review.intervention_reason == (
        "Generated report is not acceptable."
    )


def test_completed_review_cannot_be_changed():
    lifecycle = create_lifecycle()

    lifecycle.start_review()

    lifecycle.accept(
        reviewer_id="REVIEWER-001"
    )

    with pytest.raises(
        ValueError,
        match="already been completed and cannot be changed",
    ):
        lifecycle.reject(
            reviewer_id="REVIEWER-002",
            reason="Attempted second decision.",
        )


def test_lifecycle_reports_completion():
    lifecycle = create_lifecycle()

    assert lifecycle.is_completed() is False

    lifecycle.start_review()

    lifecycle.accept(
        reviewer_id="REVIEWER-001"
    )

    assert lifecycle.is_completed() is True
    assert lifecycle.decision() == ReviewDecision.ACCEPT