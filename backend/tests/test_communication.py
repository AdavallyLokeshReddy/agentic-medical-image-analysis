from agent.communication import (
    CommunicationRecord,
    CommunicationStatus,
    TriageLevel,
    TriageRecord,
)


# ======================================================================
# TRIAGE TESTS
# ======================================================================


def test_triage_record_defaults_to_human_approval():
    triage = TriageRecord(
        triage_id="triage-001",
        case_id="case-001",
        level=TriageLevel.PRIORITY,
        reason="Verified evidence requires priority workflow review.",
    )

    assert triage.level == TriageLevel.PRIORITY
    assert triage.requires_human_approval is True
    assert triage.approved_by is None
    assert triage.approved_at is None


def test_triage_record_preserves_evidence_references():
    triage = TriageRecord(
        triage_id="triage-002",
        case_id="case-001",
        level=TriageLevel.URGENT,
        reason="Verified evidence meets urgent workflow criteria.",
        evidence_ids=["evidence-001", "evidence-002"],
        verification_status="passed",
    )

    assert triage.evidence_ids == [
        "evidence-001",
        "evidence-002",
    ]
    assert triage.verification_status == "passed"


def test_triage_requires_reviewer_for_approval():
    triage = TriageRecord(
        triage_id="triage-003",
        case_id="case-001",
        level=TriageLevel.PRIORITY,
        reason="Priority workflow proposed.",
    )

    try:
        triage.approve("")
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert "Reviewer ID is required" in str(exc)


def test_triage_can_be_approved_by_human():
    triage = TriageRecord(
        triage_id="triage-004",
        case_id="case-001",
        level=TriageLevel.URGENT,
        reason="Urgent workflow proposed.",
    )

    triage.approve("reviewer-001")

    assert triage.approved_by == "reviewer-001"
    assert triage.approved_at is not None


def test_triage_cannot_be_approved_twice():
    triage = TriageRecord(
        triage_id="triage-005",
        case_id="case-001",
        level=TriageLevel.ROUTINE,
        reason="Routine workflow proposed.",
    )

    triage.approve("reviewer-001")

    try:
        triage.approve("reviewer-002")
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert "already been approved" in str(exc)


# ======================================================================
# COMMUNICATION TESTS
# ======================================================================


def test_communication_starts_pending():
    communication = CommunicationRecord(
        communication_id="communication-001",
        case_id="case-001",
        message="Case requires workflow acknowledgement.",
    )

    assert communication.status == CommunicationStatus.PENDING
    assert communication.acknowledged_by is None
    assert communication.closed_at is None


def test_communication_can_be_acknowledged():
    communication = CommunicationRecord(
        communication_id="communication-002",
        case_id="case-001",
        message="Priority workflow review requested.",
    )

    communication.acknowledge("reviewer-001")

    assert (
        communication.status
        == CommunicationStatus.ACKNOWLEDGED
    )
    assert communication.acknowledged_by == "reviewer-001"
    assert communication.acknowledged_at is not None


def test_communication_requires_reviewer_for_acknowledgement():
    communication = CommunicationRecord(
        communication_id="communication-003",
        case_id="case-001",
        message="Workflow notification.",
    )

    try:
        communication.acknowledge("")
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert "Reviewer ID is required" in str(exc)


def test_acknowledged_communication_can_be_closed():
    communication = CommunicationRecord(
        communication_id="communication-004",
        case_id="case-001",
        message="Workflow notification.",
    )

    communication.acknowledge("reviewer-001")
    communication.close()

    assert communication.status == CommunicationStatus.CLOSED
    assert communication.closed_at is not None


def test_pending_communication_cannot_be_closed():
    communication = CommunicationRecord(
        communication_id="communication-005",
        case_id="case-001",
        message="Workflow notification.",
    )

    try:
        communication.close()
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert "must be acknowledged" in str(exc)


def test_communication_can_be_escalated():
    communication = CommunicationRecord(
        communication_id="communication-006",
        case_id="case-001",
        message="Workflow notification.",
    )

    communication.escalate(
        "Acknowledgement was not received within the configured workflow."
    )

    assert (
        communication.status
        == CommunicationStatus.ESCALATED
    )
    assert (
        communication.reason
        == "Acknowledgement was not received within the configured workflow."
    )


def test_escalation_requires_reason():
    communication = CommunicationRecord(
        communication_id="communication-007",
        case_id="case-001",
        message="Workflow notification.",
    )

    try:
        communication.escalate("")
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert "Escalation reason is required" in str(exc)


def test_communication_can_enter_fallback():
    communication = CommunicationRecord(
        communication_id="communication-008",
        case_id="case-001",
        message="Workflow notification.",
    )

    communication.fallback(
        "Primary communication pathway unavailable."
    )

    assert (
        communication.status
        == CommunicationStatus.FALLBACK
    )
    assert (
        communication.reason
        == "Primary communication pathway unavailable."
    )


def test_fallback_requires_reason():
    communication = CommunicationRecord(
        communication_id="communication-009",
        case_id="case-001",
        message="Workflow notification.",
    )

    try:
        communication.fallback("")
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert "Fallback reason is required" in str(exc)


def test_closed_communication_cannot_enter_fallback():
    communication = CommunicationRecord(
        communication_id="communication-010",
        case_id="case-001",
        message="Workflow notification.",
    )

    communication.acknowledge("reviewer-001")
    communication.close()

    try:
        communication.fallback(
            "Attempted fallback after closure."
        )
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert "Closed communication" in str(exc)


def test_communication_serialization():
    communication = CommunicationRecord(
        communication_id="communication-011",
        case_id="case-001",
        message="Priority workflow notification.",
        triage_id="triage-001",
        recipient_role="clinical_reviewer",
    )

    data = communication.to_dict()

    assert data["communication_id"] == "communication-011"
    assert data["case_id"] == "case-001"
    assert data["message"] == "Priority workflow notification."
    assert data["status"] == "pending"
    assert data["triage_id"] == "triage-001"
    assert data["recipient_role"] == "clinical_reviewer"


def test_triage_serialization():
    triage = TriageRecord(
        triage_id="triage-012",
        case_id="case-001",
        level=TriageLevel.ESCALATE,
        reason="Workflow escalation required.",
        evidence_ids=["evidence-001"],
        verification_status="passed",
    )

    data = triage.to_dict()

    assert data["triage_id"] == "triage-012"
    assert data["case_id"] == "case-001"
    assert data["level"] == "escalate"
    assert data["reason"] == "Workflow escalation required."
    assert data["evidence_ids"] == ["evidence-001"]
    assert data["verification_status"] == "passed"
    assert data["requires_human_approval"] is True