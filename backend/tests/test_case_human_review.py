import pytest

from agent.case_state import CaseModality, CaseState
from agent.human_review import (
    HumanReview,
    ReviewDecision,
    ReviewStatus,
)


def make_case() -> CaseState:
    return CaseState(
        case_id="CASE-001",
        modality=CaseModality.CT,
        body_region="head",
        clinical_question="Evaluate the available imaging evidence.",
    )


def make_review() -> HumanReview:
    return HumanReview(
        review_id="REV-001",
        case_id="CASE-001",
        report_id="REPORT-001",
    )


def test_case_can_store_human_review():
    case = make_case()
    review = make_review()

    case.add_human_review(review)

    assert len(case.human_reviews) == 1
    assert case.human_reviews[0].review_id == "REV-001"


def test_case_can_retrieve_human_review():
    case = make_case()
    review = make_review()

    case.add_human_review(review)

    retrieved = case.get_human_review("REV-001")

    assert retrieved is review


def test_case_rejects_review_for_different_case():
    case = make_case()

    review = HumanReview(
        review_id="REV-002",
        case_id="CASE-999",
        report_id="REPORT-001",
    )

    with pytest.raises(ValueError, match="case ID"):
        case.add_human_review(review)


def test_case_raises_when_review_is_missing():
    case = make_case()

    with pytest.raises(KeyError, match="REV-999"):
        case.get_human_review("REV-999")


def test_case_can_list_completed_reviews():
    case = make_case()

    pending_review = make_review()

    completed_review = HumanReview(
        review_id="REV-002",
        case_id="CASE-001",
        report_id="REPORT-002",
    )

    completed_review.start()
    completed_review.accept(
        reviewer_id="REVIEWER-001"
    )

    case.add_human_review(pending_review)
    case.add_human_review(completed_review)

    completed = case.get_completed_human_reviews()

    assert len(completed) == 1
    assert completed[0].review_id == "REV-002"
    assert completed[0].status == ReviewStatus.COMPLETED
    assert completed[0].decision == ReviewDecision.ACCEPT


def test_case_serializes_human_reviews():
    case = make_case()
    review = make_review()

    review.start()
    review.accept(
        reviewer_id="REVIEWER-001",
        comments=["Reviewed evidence."],
    )

    case.add_human_review(review)

    data = case.to_dict()

    assert "human_reviews" in data
    assert len(data["human_reviews"]) == 1

    serialized_review = data["human_reviews"][0]

    assert serialized_review["review_id"] == "REV-001"
    assert serialized_review["case_id"] == "CASE-001"
    assert serialized_review["status"] == "completed"
    assert serialized_review["decision"] == "accept"