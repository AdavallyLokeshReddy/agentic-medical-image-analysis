
from agent.case_state import (
    CaseModality,
    CaseState,
    EvidenceItem,
    EvidenceStatus,
    VerificationStatus,
)
from agent.communication import (
    CommunicationRecord,
    TriageLevel,
    TriageRecord,
)
from agent.human_review import HumanReview
from database.case_audit import CaseAudit
from database.connection import SessionLocal, engine
from database.models import Base


def test_case_audit_records_governed_workflow():
    Base.metadata.create_all(bind=engine)

    case = CaseState(
        case_id="audit-workflow-test-case-002",
        modality=CaseModality.CT,
        body_region="head",
        clinical_question="Audit workflow integration test",
    )

    evidence = EvidenceItem(
        evidence_id="audit-test-evidence-002",
        case_id=case.case_id,
        evidence_type="observation",
        source="test-tool",
        claim="Test evidence",
        status=EvidenceStatus.VALID,
        confidence=0.95,
    )

    case.add_evidence(evidence)

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
        review_id="audit-test-review-002",
        case_id=case.case_id,
        report_id="audit-test-report-002",
    )

    review.accept(
        reviewer_id="reviewer-audit-001",
        comments=["Review completed."],
    )

    case.add_human_review(review)

    triage = TriageRecord(
        triage_id="audit-test-triage-002",
        case_id=case.case_id,
        level=TriageLevel.PRIORITY,
        reason="Priority workflow test.",
        evidence_ids=[evidence.evidence_id],
        verification_status=VerificationStatus.PASSED,
    )

    triage.approve("reviewer-audit-001")
    case.add_triage(triage)

    communication = CommunicationRecord(
        communication_id="audit-test-communication-002",
        case_id=case.case_id,
        message="Priority communication test.",
        triage_id=triage.triage_id,
        recipient_role="radiologist",
        reason="Audit integration test.",
    )

    case.add_communication(communication)

    session = SessionLocal()

    try:
        audit = CaseAudit(session)

        audit.record_case_created(
            case,
            actor_type="system",
            actor_id="test-system",
        )

        audit.record_evidence_added(
            case,
            evidence.evidence_id,
            actor_type="tool",
            actor_id="test-tool",
        )

        audit.record_verification(
            case,
            actor_type="system",
            actor_id="verification-engine",
        )

        audit.record_human_review(
            case,
            review.review_id,
            actor_type="human",
            actor_id="reviewer-audit-001",
        )

        audit.record_triage(
            case,
            triage.triage_id,
            actor_type="human",
            actor_id="reviewer-audit-001",
        )

        audit.record_communication(
            case,
            communication.communication_id,
            actor_type="system",
            actor_id="communication-engine",
        )

        session.commit()

        events = audit.list_case_events(case)

        assert len(events) == 6

        actions = [event.action for event in events]

        assert actions == [
            "case_created",
            "evidence_added",
            "verification_completed",
            "human_review_completed",
            "triage_approved",
            "communication_created",
        ]

        for event in events:
            assert event.case_id == case.case_id

    finally:
        session.close()


def test_case_audit_rejects_missing_case_entities():
    Base.metadata.create_all(bind=engine)

    case = CaseState(
        case_id="audit-validation-test-case-002",
        modality=CaseModality.CT,
        body_region="head",
        clinical_question="Audit validation test",
    )

    session = SessionLocal()

    try:
        audit = CaseAudit(session)

        try:
            audit.record_evidence_added(
                case,
                "missing-evidence",
            )
        except KeyError as exc:
            assert "Evidence not found" in exc.args[0]
        else:
            raise AssertionError(
                "Expected KeyError for missing evidence."
            )

        try:
            audit.record_human_review(
                case,
                "missing-review",
            )
        except KeyError as exc:
            assert "Human review" in exc.args[0]
            assert "not found" in exc.args[0]
        else:
            raise AssertionError(
                "Expected KeyError for missing human review."
            )

        try:
            audit.record_triage(
                case,
                "missing-triage",
            )
        except KeyError as exc:
            assert "Triage" in exc.args[0]
            assert "not found" in exc.args[0]
        else:
            raise AssertionError(
                "Expected KeyError for missing triage."
            )

        try:
            audit.record_communication(
                case,
                "missing-communication",
            )
        except KeyError as exc:
            assert "Communication" in exc.args[0]
            assert "not found" in exc.args[0]
        else:
            raise AssertionError(
                "Expected KeyError for missing communication."
            )

    finally:
        session.rollback()
        session.close()

