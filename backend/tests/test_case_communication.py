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


def test_case_can_store_triage():
    case = make_case()

    triage = TriageRecord(
        triage_id="TRIAGE-001",
        case_id="CASE-001",
        level=TriageLevel.URGENT,
        reason="Verification-supported workflow escalation.",
    )

    case.add_triage(triage)

    assert len(case.triage_records) == 1
    assert case.triage_records[0].triage_id == "TRIAGE-001"


def test_case_can_retrieve_triage():
    case = make_case()

    triage = TriageRecord(
        triage_id="TRIAGE-001",
        case_id="CASE-001",
        level=TriageLevel.PRIORITY,
        reason="Priority workflow handling.",
    )

    case.add_triage(triage)

    retrieved = case.get_triage("TRIAGE-001")

    assert retrieved is triage


def test_case_rejects_triage_for_different_case():
    case = make_case()

    triage = TriageRecord(
        triage_id="TRIAGE-001",
        case_id="CASE-999",
        level=TriageLevel.URGENT,
        reason="Invalid case association.",
    )

    try:
        case.add_triage(triage)
        assert False
    except ValueError:
        pass


def test_case_raises_when_triage_is_missing():
    case = make_case()

    try:
        case.get_triage("MISSING")
        assert False
    except KeyError:
        pass


def test_case_can_store_communication():
    case = make_case()

    communication = CommunicationRecord(
        communication_id="COMM-001",
        case_id="CASE-001",
        message="Governed workflow communication.",
    )

    case.add_communication(communication)

    assert len(case.communications) == 1
    assert case.communications[0].communication_id == "COMM-001"


def test_case_can_retrieve_communication():
    case = make_case()

    communication = CommunicationRecord(
        communication_id="COMM-001",
        case_id="CASE-001",
        message="Governed workflow communication.",
    )

    case.add_communication(communication)

    retrieved = case.get_communication("COMM-001")

    assert retrieved is communication


def test_case_rejects_communication_for_different_case():
    case = make_case()

    communication = CommunicationRecord(
        communication_id="COMM-001",
        case_id="CASE-999",
        message="Invalid case association.",
    )

    try:
        case.add_communication(communication)
        assert False
    except ValueError:
        pass


def test_case_raises_when_communication_is_missing():
    case = make_case()

    try:
        case.get_communication("MISSING")
        assert False
    except KeyError:
        pass


def test_case_serializes_triage_and_communication():
    case = make_case()

    triage = TriageRecord(
        triage_id="TRIAGE-001",
        case_id="CASE-001",
        level=TriageLevel.URGENT,
        reason="Verification-supported workflow escalation.",
    )

    communication = CommunicationRecord(
        communication_id="COMM-001",
        case_id="CASE-001",
        message="Governed workflow communication.",
    )

    case.add_triage(triage)
    case.add_communication(communication)

    data = case.to_dict()

    assert len(data["triage_records"]) == 1
    assert data["triage_records"][0]["triage_id"] == "TRIAGE-001"

    assert len(data["communications"]) == 1
    assert (
        data["communications"][0]["communication_id"]
        == "COMM-001"
    )


def test_case_rejects_invalid_triage_type():
    case = make_case()

    try:
        case.add_triage("not a triage record")
        assert False
    except TypeError:
        pass


def test_case_rejects_invalid_communication_type():
    case = make_case()

    try:
        case.add_communication("not a communication record")
        assert False
    except TypeError:
        pass