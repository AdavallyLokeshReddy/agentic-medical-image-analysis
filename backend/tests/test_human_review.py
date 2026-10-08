from agent.human_review import (
    HumanReview,
    ReviewDecision,
    ReviewStatus,
)


def make_review() -> HumanReview:
    return HumanReview(
        review_id="REV-001",
        case_id="CASE-001",
        report_id="REPORT-001",
    )


def test_review_starts_pending():
    review = make_review()

    assert review.status == ReviewStatus.PENDING
    assert review.decision is None
    assert review.reviewer_id is None
    assert review.started_at is None


def test_review_can_be_started():
    review = make_review()

    review.start()

    assert review.started_at is not None
    assert review.status == ReviewStatus.PENDING


def test_reviewer_can_accept_report():
    review = make_review()

    review.start()
    review.accept(
        reviewer_id="REVIEWER-001",
        comments=["Reviewed the available evidence."],
    )

    assert review.status == ReviewStatus.COMPLETED
    assert review.decision == ReviewDecision.ACCEPT
    assert review.reviewer_id == "REVIEWER-001"
    assert review.completed_at is not None
    assert "Reviewed the available evidence." in review.reviewer_comments


def test_reviewer_can_modify_report():
    review = make_review()

    review.start()

    modified = [
        {
            "evidence_id": "E001",
            "claim": "Human-corrected observation.",
        }
    ]

    review.modify(
        reviewer_id="REVIEWER-001",
        modified_observations=modified,
        reason="The original observation required correction.",
    )

    assert review.status == ReviewStatus.COMPLETED
    assert review.decision == ReviewDecision.MODIFY
    assert review.reviewer_id == "REVIEWER-001"

    assert review.modified_observations == modified
    assert (
        review.intervention_reason
        == "The original observation required correction."
    )


def test_reviewer_can_reject_report():
    review = make_review()

    review.start()

    review.reject(
        reviewer_id="REVIEWER-001",
        reason="The evidence was not sufficient for acceptance.",
    )

    assert review.status == ReviewStatus.COMPLETED
    assert review.decision == ReviewDecision.REJECT
    assert review.reviewer_id == "REVIEWER-001"
    assert (
        review.intervention_reason
        == "The evidence was not sufficient for acceptance."
    )


def test_modify_requires_reason():
    review = make_review()

    review.start()

    try:
        review.modify(
            reviewer_id="REVIEWER-001",
            modified_observations=[],
            reason="",
        )
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert "reason is required" in str(exc).lower()


def test_reject_requires_reason():
    review = make_review()

    review.start()

    try:
        review.reject(
            reviewer_id="REVIEWER-001",
            reason="",
        )
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert "reason is required" in str(exc).lower()


def test_reviewer_id_is_required():
    review = make_review()

    review.start()

    try:
        review.accept(reviewer_id="")
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert "reviewer id is required" in str(exc).lower()


def test_completed_review_cannot_be_changed():
    review = make_review()

    review.start()
    review.accept(reviewer_id="REVIEWER-001")

    try:
        review.reject(
            reviewer_id="REVIEWER-002",
            reason="Attempted second decision.",
        )
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert "already been completed" in str(exc).lower()


def test_review_records_evidence():
    review = make_review()

    review.record_reviewed_evidence(
        ["E001", "E002", "E002"]
    )

    assert review.reviewed_evidence_ids == [
        "E001",
        "E002",
    ]


def test_review_records_verifications():
    review = make_review()

    review.record_reviewed_verifications(
        ["V001", "V002", "V002"]
    )

    assert review.reviewed_verification_ids == [
        "V001",
        "V002",
    ]


def test_review_serialization():
    review = make_review()

    review.start()

    review.record_reviewed_evidence(["E001"])
    review.record_reviewed_verifications(["V001"])

    review.accept(
        reviewer_id="REVIEWER-001",
        comments=["Reviewed."],
    )

    data = review.to_dict()

    assert data["review_id"] == "REV-001"
    assert data["case_id"] == "CASE-001"
    assert data["report_id"] == "REPORT-001"

    assert data["status"] == "completed"
    assert data["decision"] == "accept"

    assert data["reviewer_id"] == "REVIEWER-001"
    assert data["reviewed_evidence_ids"] == ["E001"]
    assert data["reviewed_verification_ids"] == ["V001"]