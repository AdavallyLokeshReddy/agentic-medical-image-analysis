from agent.case_state import (
    CaseModality,
    CaseState,
    VerificationStatus,
)
from agent.communication import (
    CommunicationRecord,
    TriageLevel,
    TriageRecord,
)
from agent.human_review import (
    HumanReview,
    ReviewDecision,
    ReviewStatus,
)
from database.case_persistence import CaseStatePersistence
from database.connection import SessionLocal, engine
from database.models import Base


def test_case_state_workflow_persistence():
    Base.metadata.create_all(bind=engine)

    case = CaseState(
        case_id="workflow-persistence-test-case",
        modality=CaseModality.CT,
        body_region="head",
        clinical_question="Workflow persistence integration test",
    )

    case.set_verification(
        status=VerificationStatus.PASSED,
        checks=[
            {
                "category": "technical",
                "status": "passed",
            }
        ],
        human_review_required=True,
    )

    review = HumanReview(
        review_id="workflow-test-review",
        case_id=case.case_id,
        report_id="workflow-test-report",
    )

    review.accept(
        reviewer_id="reviewer-001",
        comments=["Human review completed."],
    )

    case.add_human_review(review)

    triage = TriageRecord(
        triage_id="workflow-test-triage",
        case_id=case.case_id,
        level=TriageLevel.PRIORITY,
        reason="Requires priority communication.",
        evidence_ids=[],
        verification_status=VerificationStatus.PASSED,
    )

    triage.approve("reviewer-001")
    case.add_triage(triage)

    communication = CommunicationRecord(
        communication_id="workflow-test-communication",
        case_id=case.case_id,
        message="Priority workflow communication.",
        triage_id=triage.triage_id,
        recipient_role="radiologist",
        reason="Governed communication test.",
    )

    case.add_communication(communication)

    session = SessionLocal()

    try:
        persistence = CaseStatePersistence(session)
        persistence.save(case)
    finally:
        session.close()

    verification_session = SessionLocal()

    try:
        repository = CaseStatePersistence(
            verification_session
        ).repository

        stored_reviews = repository.list_human_reviews(
            case.case_id
        )

        assert len(stored_reviews) == 1
        assert (
            stored_reviews[0].review_id
            == "workflow-test-review"
        )
        assert (
            stored_reviews[0].case_id
            == case.case_id
        )
        assert (
            stored_reviews[0].reviewer_id
            == "reviewer-001"
        )
        assert (
            stored_reviews[0].decision
            == ReviewDecision.ACCEPT.value
        )
        assert (
            stored_reviews[0].status
            == ReviewStatus.COMPLETED.value
        )

        stored_triage = repository.list_triage(
            case.case_id
        )

        assert len(stored_triage) == 1
        assert (
            stored_triage[0].triage_id
            == "workflow-test-triage"
        )
        assert (
            stored_triage[0].case_id
            == case.case_id
        )
        assert stored_triage[0].level == "priority"
        assert (
            stored_triage[0].approved_by
            == "reviewer-001"
        )

        stored_communications = (
            repository.list_communications(
                case.case_id
            )
        )

        assert len(stored_communications) == 1
        assert (
            stored_communications[0].communication_id
            == "workflow-test-communication"
        )
        assert (
            stored_communications[0].case_id
            == case.case_id
        )
        assert (
            stored_communications[0].triage_id
            == triage.triage_id
        )
        assert (
            stored_communications[0].recipient_role
            == "radiologist"
        )

    finally:
        verification_session.close()


def test_case_state_workflow_persistence_does_not_duplicate_records():
    Base.metadata.create_all(bind=engine)

    case = CaseState(
        case_id="workflow-no-duplicate-case",
        modality=CaseModality.CT,
        body_region="head",
        clinical_question="Duplicate prevention test",
    )

    review = HumanReview(
        review_id="no-duplicate-review",
        case_id=case.case_id,
        report_id="no-duplicate-report",
    )

    review.accept(
        reviewer_id="reviewer-002",
        comments=["Approved."],
    )

    case.add_human_review(review)

    triage = TriageRecord(
        triage_id="no-duplicate-triage",
        case_id=case.case_id,
        level=TriageLevel.ROUTINE,
        reason="Routine workflow.",
        evidence_ids=[],
        verification_status=VerificationStatus.PASSED,
    )

    case.add_triage(triage)

    communication = CommunicationRecord(
        communication_id="no-duplicate-communication",
        case_id=case.case_id,
        message="Routine communication.",
        triage_id=triage.triage_id,
        recipient_role="radiologist",
    )

    case.add_communication(communication)

    session = SessionLocal()

    try:
        persistence = CaseStatePersistence(session)

        persistence.save(case)
        persistence.save(case)

    finally:
        session.close()

    verification_session = SessionLocal()

    try:
        repository = CaseStatePersistence(
            verification_session
        ).repository

        assert len(
            repository.list_human_reviews(
                case.case_id
            )
        ) == 1

        assert len(
            repository.list_triage(
                case.case_id
            )
        ) == 1

        assert len(
            repository.list_communications(
                case.case_id
            )
        ) == 1

    finally:
        verification_session.close()