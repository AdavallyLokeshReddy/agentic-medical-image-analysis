from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """
    Base class for all PostgreSQL ORM models.
    """
    pass


class CaseModel(Base):
    """
    Persistent representation of a medical AI case.
    """

    __tablename__ = "cases"

    case_id: Mapped[str] = mapped_column(
        String(100),
        primary_key=True,
    )

    modality: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    body_region: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    clinical_question: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class EvidenceModel(Base):
    """
    Persistent evidence reference associated with a case.

    Raw medical image volumes are not stored here.
    This table stores evidence metadata and references.
    """

    __tablename__ = "evidence"

    evidence_id: Mapped[str] = mapped_column(
        String(100),
        primary_key=True,
    )

    case_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    source_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    source_reference: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )


class HumanReviewModel(Base):
    """
    Persistent human-review record.
    """

    __tablename__ = "human_reviews"

    review_id: Mapped[str] = mapped_column(
        String(100),
        primary_key=True,
    )

    case_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    reviewer_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    decision: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    evidence_ids: Mapped[list[str] | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    verification_ids: Mapped[list[str] | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class VerificationModel(Base):
    """
    Persistent verification state for a case.
    """

    __tablename__ = "verifications"

    verification_id: Mapped[str] = mapped_column(
        String(100),
        primary_key=True,
    )

    case_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    categories: Mapped[list[str] | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    findings: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )


class TriageModel(Base):
    """
    Persistent governed triage record.
    """

    __tablename__ = "triage"

    triage_id: Mapped[str] = mapped_column(
        String(100),
        primary_key=True,
    )

    case_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    level: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    evidence_ids: Mapped[list[str] | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    verification_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    requires_human_approval: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    approved_by: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )


class CommunicationModel(Base):
    """
    Persistent communication and closure record.
    """

    __tablename__ = "communications"

    communication_id: Mapped[str] = mapped_column(
        String(100),
        primary_key=True,
    )

    case_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    triage_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )

    message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    recipient_role: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    acknowledged_by: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    acknowledged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class AuditEventModel(Base):
    """
    Append-only audit event.

    This records governed actions and state transitions
    for traceability and accountability.
    """

    __tablename__ = "audit_events"

    event_id: Mapped[str] = mapped_column(
        String(100),
        primary_key=True,
    )

    case_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    actor_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    actor_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    action: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    entity_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    entity_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
    )