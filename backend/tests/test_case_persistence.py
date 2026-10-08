from agent.case_state import (
    CaseModality,
    CaseState,
    EvidenceItem,
    EvidenceStatus,
    VerificationStatus,
)
from database.case_persistence import CaseStatePersistence
from database.connection import SessionLocal, engine
from database.models import Base


def test_case_state_persistence():
    Base.metadata.create_all(bind=engine)

    case = CaseState(
        case_id="persistence-test-case",
        modality=CaseModality.CT,
        body_region="head",
        clinical_question="Persistence integration test",
    )

    case.add_evidence(
        EvidenceItem(
            evidence_id="persistence-test-evidence",
            case_id=case.case_id,
            evidence_type="observation",
            source="test-tool",
            claim="Test evidence",
            status=EvidenceStatus.VALID,
            confidence=0.95,
        )
    )

    case.set_verification(
        status=VerificationStatus.PASSED,
        checks=[
            {
                "category": "technical",
                "status": "passed",
            }
        ],
        human_review_required=False,
    )

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

        stored_case = repository.get_case(
            "persistence-test-case"
        )

        assert stored_case is not None
        assert stored_case.modality == "CT"
        assert stored_case.body_region == "head"
        assert (
            stored_case.clinical_question
            == "Persistence integration test"
        )

        stored_evidence = repository.list_evidence(
            "persistence-test-case"
        )

        assert len(stored_evidence) == 1
        assert (
            stored_evidence[0].evidence_id
            == "persistence-test-evidence"
        )
        assert stored_evidence[0].status == "valid"

        stored_verifications = (
            repository.list_verifications(
                "persistence-test-case"
            )
        )

        assert len(stored_verifications) == 1
        assert (
            stored_verifications[0].status
            == "passed"
        )

    finally:
        verification_session.close()


def test_case_state_persistence_rejects_invalid_input():
    session = SessionLocal()

    try:
        persistence = CaseStatePersistence(session)

        try:
            persistence.save("not-a-case-state")
        except TypeError as exc:
            assert "CaseState" in str(exc)
        else:
            raise AssertionError(
                "Expected TypeError was not raised."
            )

    finally:
        session.close()


def test_case_state_updates_existing_case():
    Base.metadata.create_all(bind=engine)

    case = CaseState(
        case_id="persistence-update-case",
        modality=CaseModality.CT,
        body_region="head",
        clinical_question="Initial question",
    )

    session = SessionLocal()

    try:
        persistence = CaseStatePersistence(session)

        persistence.save(case)

    finally:
        session.close()

    case.clinical_question = "Updated question"
    case.set_verification(
        status=VerificationStatus.PASSED
    )

    update_session = SessionLocal()

    try:
        persistence = CaseStatePersistence(
            update_session
        )

        persistence.save(case)

    finally:
        update_session.close()

    verification_session = SessionLocal()

    try:
        repository = CaseStatePersistence(
            verification_session
        ).repository

        stored_case = repository.get_case(
            "persistence-update-case"
        )

        assert stored_case is not None
        assert (
            stored_case.clinical_question
            == "Updated question"
        )

        stored_verifications = (
            repository.list_verifications(
                "persistence-update-case"
            )
        )

        assert len(stored_verifications) == 1
        assert (
            stored_verifications[0].status
            == "passed"
        )

    finally:
        verification_session.close()