from database.models import (
    AuditEventModel,
    Base,
    CaseModel,
    CommunicationModel,
    EvidenceModel,
    HumanReviewModel,
    TriageModel,
    VerificationModel,
)


def test_all_database_models_are_registered():
    expected_tables = {
        "cases",
        "evidence",
        "human_reviews",
        "verifications",
        "triage",
        "communications",
        "audit_events",
    }

    actual_tables = set(Base.metadata.tables.keys())

    assert actual_tables == expected_tables


def test_case_model_columns():
    columns = set(CaseModel.__table__.columns.keys())

    assert {
        "case_id",
        "modality",
        "body_region",
        "clinical_question",
        "status",
        "created_at",
        "updated_at",
    }.issubset(columns)


def test_evidence_model_columns():
    columns = set(EvidenceModel.__table__.columns.keys())

    assert {
        "evidence_id",
        "case_id",
        "source_type",
        "source_reference",
        "status",
        "metadata_json",
        "created_at",
    }.issubset(columns)


def test_human_review_model_columns():
    columns = set(HumanReviewModel.__table__.columns.keys())

    assert {
        "review_id",
        "case_id",
        "reviewer_id",
        "decision",
        "status",
        "reason",
        "evidence_ids",
        "verification_ids",
        "created_at",
        "completed_at",
    }.issubset(columns)


def test_verification_model_columns():
    columns = set(VerificationModel.__table__.columns.keys())

    assert {
        "verification_id",
        "case_id",
        "status",
        "categories",
        "findings",
        "reason",
        "created_at",
    }.issubset(columns)


def test_triage_model_columns():
    columns = set(TriageModel.__table__.columns.keys())

    assert {
        "triage_id",
        "case_id",
        "level",
        "reason",
        "evidence_ids",
        "verification_status",
        "requires_human_approval",
        "approved_by",
        "approved_at",
        "created_at",
    }.issubset(columns)


def test_communication_model_columns():
    columns = set(CommunicationModel.__table__.columns.keys())

    assert {
        "communication_id",
        "case_id",
        "triage_id",
        "message",
        "status",
        "recipient_role",
        "acknowledged_by",
        "acknowledged_at",
        "reason",
        "created_at",
        "closed_at",
    }.issubset(columns)


def test_audit_event_model_columns():
    columns = set(AuditEventModel.__table__.columns.keys())

    assert {
        "event_id",
        "case_id",
        "actor_type",
        "actor_id",
        "action",
        "timestamp",
        "entity_type",
        "entity_id",
        "metadata_json",
    }.issubset(columns)


def test_primary_keys_are_defined():
    assert CaseModel.__table__.primary_key.columns.keys() == ["case_id"]
    assert EvidenceModel.__table__.primary_key.columns.keys() == ["evidence_id"]
    assert HumanReviewModel.__table__.primary_key.columns.keys() == ["review_id"]
    assert VerificationModel.__table__.primary_key.columns.keys() == ["verification_id"]
    assert TriageModel.__table__.primary_key.columns.keys() == ["triage_id"]
    assert CommunicationModel.__table__.primary_key.columns.keys() == ["communication_id"]
    assert AuditEventModel.__table__.primary_key.columns.keys() == ["event_id"]