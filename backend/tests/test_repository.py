from database.connection import SessionLocal, engine
from database.models import Base
from database.repository import MedicalCaseRepository


def test_repository_case_crud():
    Base.metadata.create_all(bind=engine)

    session = SessionLocal()

    try:
        repository = MedicalCaseRepository(session)

        case = repository.create_case(
            case_id="repo-test-case",
            modality="CT",
            body_region="head",
            clinical_question="Repository integration test",
            status="created",
        )

        session.commit()

        assert case.case_id == "repo-test-case"

        retrieved = repository.get_case("repo-test-case")

        assert retrieved is not None
        assert retrieved.case_id == "repo-test-case"
        assert retrieved.modality == "CT"
        assert retrieved.body_region == "head"
        assert retrieved.status == "created"

    finally:
        session.close()


def test_repository_evidence_crud():
    session = SessionLocal()

    try:
        repository = MedicalCaseRepository(session)

        evidence = repository.add_evidence(
            evidence_id="repo-test-evidence",
            case_id="repo-test-case",
            source_type="test",
            source_reference="test-reference",
            status="available",
            metadata={"source": "repository-test"},
        )

        session.commit()

        assert evidence.evidence_id == "repo-test-evidence"

        retrieved = repository.get_evidence(
            "repo-test-evidence"
        )

        assert retrieved is not None
        assert retrieved.case_id == "repo-test-case"
        assert retrieved.metadata_json["source"] == "repository-test"

        evidence_list = repository.list_evidence(
            "repo-test-case"
        )

        assert len(evidence_list) >= 1

    finally:
        session.close()


def test_repository_human_review_crud():
    session = SessionLocal()

    try:
        repository = MedicalCaseRepository(session)

        review = repository.add_human_review(
            review_id="repo-test-review",
            case_id="repo-test-case",
            reviewer_id="reviewer-1",
            decision="accepted",
            status="completed",
            reason="Repository test",
            evidence_ids=["repo-test-evidence"],
            verification_ids=[],
        )

        session.commit()

        retrieved = repository.get_human_review(
            "repo-test-review"
        )

        assert retrieved is not None
        assert retrieved.reviewer_id == "reviewer-1"
        assert retrieved.decision == "accepted"

        reviews = repository.list_human_reviews(
            "repo-test-case"
        )

        assert len(reviews) >= 1

    finally:
        session.close()


def test_repository_verification_crud():
    session = SessionLocal()

    try:
        repository = MedicalCaseRepository(session)

        verification = repository.add_verification(
            verification_id="repo-test-verification",
            case_id="repo-test-case",
            status="verified",
            categories=["technical", "clinical"],
            findings={"result": "consistent"},
            reason="Repository test",
        )

        session.commit()

        retrieved = repository.get_verification(
            "repo-test-verification"
        )

        assert retrieved is not None
        assert retrieved.status == "verified"
        assert "technical" in retrieved.categories

        verifications = repository.list_verifications(
            "repo-test-case"
        )

        assert len(verifications) >= 1

    finally:
        session.close()


def test_repository_triage_crud():
    session = SessionLocal()

    try:
        repository = MedicalCaseRepository(session)

        triage = repository.add_triage(
            triage_id="repo-test-triage",
            case_id="repo-test-case",
            level="priority",
            reason="Repository test",
            verification_status="verified",
            evidence_ids=["repo-test-evidence"],
            requires_human_approval=True,
        )

        session.commit()

        retrieved = repository.get_triage(
            "repo-test-triage"
        )

        assert retrieved is not None
        assert retrieved.level == "priority"
        assert retrieved.requires_human_approval is True

        triage_records = repository.list_triage(
            "repo-test-case"
        )

        assert len(triage_records) >= 1

    finally:
        session.close()


def test_repository_communication_crud():
    session = SessionLocal()

    try:
        repository = MedicalCaseRepository(session)

        communication = repository.add_communication(
            communication_id="repo-test-communication",
            case_id="repo-test-case",
            message="Repository test message",
            status="pending",
            triage_id="repo-test-triage",
            recipient_role="reviewer",
            reason="Repository test",
        )

        session.commit()

        retrieved = repository.get_communication(
            "repo-test-communication"
        )

        assert retrieved is not None
        assert retrieved.message == "Repository test message"
        assert retrieved.triage_id == "repo-test-triage"

        communications = repository.list_communications(
            "repo-test-case"
        )

        assert len(communications) >= 1

    finally:
        session.close()


def test_repository_audit_event_crud():
    session = SessionLocal()

    try:
        repository = MedicalCaseRepository(session)

        event = repository.add_audit_event(
            event_id="repo-test-audit",
            case_id="repo-test-case",
            actor_type="system",
            actor_id="repository-test",
            action="test_action",
            entity_type="case",
            entity_id="repo-test-case",
            metadata={"test": True},
        )

        session.commit()

        retrieved = repository.get_audit_event(
            "repo-test-audit"
        )

        assert retrieved is not None
        assert retrieved.action == "test_action"
        assert retrieved.actor_type == "system"
        assert retrieved.metadata_json["test"] is True

        events = repository.list_audit_events(
            "repo-test-case"
        )

        assert len(events) >= 1

    finally:
        session.close()