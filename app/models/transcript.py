"""Transcript. See docs/05-data-model.md#transcripts (Verdict-service
tables section). Holds interview transcript text regardless of source -
a platform-provided transcript or one generated via STT from an interview
audio recording (`source=generated_stt`) both land in the same `text`
column and feed the same embedding pipeline (see vector.md).

VHIRE-2x (E7, extended for the transcript/audio RAG pipeline).
"""

import uuid

from sqlalchemy import Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.base import OrgScopedMixin, TimestampMixin, UUIDPkMixin
from app.models.enums import TranscriptSource, TranscriptStatus


class Transcript(UUIDPkMixin, OrgScopedMixin, TimestampMixin, Base):
    __tablename__ = "transcripts"

    interview_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("interviews.id"), nullable=False, unique=True
    )
    status: Mapped[TranscriptStatus] = mapped_column(
        Enum(TranscriptStatus, name="transcript_status", create_type=False),
        nullable=False,
        default=TranscriptStatus.pending,
        server_default=TranscriptStatus.pending.value,
    )
    source: Mapped[TranscriptSource | None] = mapped_column(
        Enum(TranscriptSource, name="transcript_source", create_type=False), nullable=True
    )
    text: Mapped[str | None] = mapped_column(nullable=True)
    language: Mapped[str | None] = mapped_column(nullable=True)
