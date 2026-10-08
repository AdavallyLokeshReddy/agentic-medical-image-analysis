from agent.case_state import CaseState, CaseModality
from agent.communication import (
    TriageRecord,
    TriageLevel,
    CommunicationRecord,
    CommunicationStatus,
)


def make_case():
    return CaseState(
        case_id="CASE-001",
        modality=CaseModality.CT,
        body_region="head",
        clinical_question="Research demonstration",
    )


def test_governed_review_to_closure_lifecycle():
    case = make_case()

    # --------------------------------------------------------------
    # 1. Governed triage proposal
    # --------------------------------------------------------------

    triage = TriageRecord(
        triage_id="TRIAGE-001",
        case_id="CASE-001",
        level=TriageLevel.URGENT,
        reason="Verification-supported workflow escalation.",
        evidence_ids=["evidence-001"],
        verification_status="verified",
        requires_human_approval=True,
    )

    case.add_triage(triage)

    assert len(case.triage_records) == 1
    assert triage.requires_human_approval is True
    assert triage.approved_by is None

    # --------------------------------------------------------------
    # 2. Human approval of triage
    # --------------------------------------------------------------

    triage.approve("reviewer-001")

    assert triage.approved_by == "reviewer-001"
    assert triage.approved_at is not None

    # --------------------------------------------------------------
    # 3. Communication created from approved triage
    # --------------------------------------------------------------

    communication = CommunicationRecord(
        communication_id="COMM-001",
        case_id="CASE-001",
        message="Governed workflow notification.",
        triage_id="TRIAGE-001",
        recipient_role="clinical_reviewer",
    )

    case.add_communication(communication)

    assert communication.status == CommunicationStatus.PENDING
    assert communication.triage_id == "TRIAGE-001"

    # --------------------------------------------------------------
    # 4. Human acknowledgement
    # --------------------------------------------------------------

    communication.acknowledge("reviewer-001")

    assert communication.status == CommunicationStatus.ACKNOWLEDGED
    assert communication.acknowledged_by == "reviewer-001"
    assert communication.acknowledged_at is not None

    # --------------------------------------------------------------
    # 5. Governed closure
    # --------------------------------------------------------------

    communication.close()

    assert communication.status == CommunicationStatus.CLOSED
    assert communication.closed_at is not None

    # --------------------------------------------------------------
    # 6. Verify complete case state
    # --------------------------------------------------------------

    assert case.get_triage("TRIAGE-001") is triage
    assert case.get_communication("COMM-001") is communication

    serialized = case.to_dict()

    assert len(serialized["triage_records"]) == 1
    assert len(serialized["communications"]) == 1
    assert (
        serialized["communications"][0]["status"]
        == "closed"
    )