"""Verdict. See docs/05-data-model.md#verdicts (Verdict-service tables
section). One row per (Application, service_type) - up to two in this
session's scope (`resume_analysis`, `transcript_assignment_review`);
`interview_proctoring` is not in `VerdictServiceType` yet, since E21
(biometric proctoring) is out of scope here - see vector.md.

VHIRE-2x (RAG-driven Scoring Engine + Judge). `deterministic_score` is
NOT NULL - a Verdict row cannot exist without a Scoring Engine result
(I12); the generation pipeline enforces the *ordering* (Scoring Engine
before Judge), this column is the DB-layer half of that guarantee.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.base import OrgScopedMixin, TimestampMixin, UUIDPkMixin
from app.models.enums import VerdictLabel, VerdictServiceType


class Verdict(UUIDPkMixin, OrgScopedMixin, TimestampMixin, Base):
    __tablename__ = "verdicts"
    __table_args__ = (
        UniqueConstraint("application_id", "service_type", name="uq_verdicts_application_service_type"),
        Index("ix_verdicts_application_id", "application_id"),
    )

    application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("applications.id"), nullable=False
    )
    service_type: Mapped[VerdictServiceType] = mapped_column(
        Enum(VerdictServiceType, name="verdict_service_type", create_type=False), nullable=False
    )
    resume_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("resumes.id"), nullable=True
    )
    interview_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("interviews.id"), nullable=True
    )
    deterministic_score: Mapped[dict] = mapped_column(JSONB, nullable=False)
    verdict_label: Mapped[VerdictLabel] = mapped_column(
        Enum(VerdictLabel, name="verdict_label", create_type=False), nullable=False
    )
    narrative: Mapped[str] = mapped_column(nullable=False)
    crew_run: Mapped[dict] = mapped_column(JSONB, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    stale: Mapped[bool] = mapped_column(nullable=False, default=False, server_default="false")
