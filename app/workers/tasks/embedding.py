"""Embedding Worker: chunk source text, embed each chunk via Voyage AI,
and upsert into the organization's Qdrant collection. `embed_resume` and
`embed_transcript` share every step after fetching their source text -
the concrete implementation of vector.md's "same RAG pipeline for
resumes and transcripts/audio" design (I11).

VHIRE-2x (E7).
"""

import logging
import uuid

from app.models.enums import EmbeddingStatus
from app.models.resume import Resume
from app.models.transcript import Transcript
from app.services import chunking, embeddings, storage, text_extraction, vector_store
from app.services.vector_store import ChunkPoint
from app.workers.base import OrgScopedTask, org_scoped_session, run_async
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


async def _embed_and_upsert(
    *, organization_id: uuid.UUID, source_type: str, source_id: uuid.UUID, candidate_id: uuid.UUID, text: str
) -> None:
    """Chunk `text`, embed every chunk, and replace that source's points
    in the org's collection - the one code path both `_embed_resume` and
    `_embed_transcript` call, parameterized only by `source_type`/`source_id`.
    """
    chunks = chunking.chunk_text(text)
    vectors = await embeddings.embed_chunks(chunks)
    points = [
        ChunkPoint(
            organization_id=organization_id,
            source_type=source_type,
            source_id=source_id,
            candidate_id=candidate_id,
            chunk_index=index,
            chunk_text=chunk,
            vector=vector,
        )
        for index, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True))
    ]
    await vector_store.delete_points_by_source(organization_id, source_type=source_type, source_id=source_id)
    await vector_store.upsert_points(organization_id, points)


async def _embed_resume(resume_id: str, organization_id: str) -> None:
    async with org_scoped_session(organization_id) as session:
        resume = await session.get(Resume, resume_id)
        if resume is None:
            logger.warning("embed_resume: resume %s not found for org %s", resume_id, organization_id)
            return

        resume.embedding_status = EmbeddingStatus.embedding
        await session.flush()

        try:
            file_content = storage.download_object(resume.file_object_key)
            resume_text = text_extraction.extract_text(file_content, resume.file_object_key)
            await _embed_and_upsert(
                organization_id=uuid.UUID(organization_id),
                source_type="resume",
                source_id=resume.id,
                candidate_id=resume.candidate_id,
                text=resume_text,
            )
        except Exception as exc:
            resume.embedding_status = EmbeddingStatus.embed_failed
            resume.embedding_error = str(exc)
            await session.commit()
            return

        resume.embedding_status = EmbeddingStatus.embedded
        resume.embedding_error = None
        await session.commit()


@celery_app.task(name="app.workers.tasks.embedding.embed_resume", base=OrgScopedTask, bind=True)
def embed_resume(self, resume_id: str, organization_id: str) -> None:
    run_async(_embed_resume(resume_id, organization_id))


async def _embed_transcript(transcript_id: str, organization_id: str) -> None:
    async with org_scoped_session(organization_id) as session:
        transcript = await session.get(Transcript, transcript_id)
        if transcript is None:
            logger.warning(
                "embed_transcript: transcript %s not found for org %s", transcript_id, organization_id
            )
            return
        if not transcript.text:
            logger.warning("embed_transcript: transcript %s has no text yet", transcript_id)
            return

        candidate_id = await _candidate_id_for_transcript(session, transcript)
        await _embed_and_upsert(
            organization_id=uuid.UUID(organization_id),
            source_type="transcript",
            source_id=transcript.id,
            candidate_id=candidate_id,
            text=transcript.text,
        )


async def _candidate_id_for_transcript(session, transcript: Transcript) -> uuid.UUID:
    """Resolve the Candidate a Transcript belongs to, via its Interview -> Application."""
    from app.models.application import Application
    from app.models.interview import Interview

    interview = await session.get(Interview, transcript.interview_id)
    application = await session.get(Application, interview.application_id)
    return application.candidate_id


@celery_app.task(name="app.workers.tasks.embedding.embed_transcript", base=OrgScopedTask, bind=True)
def embed_transcript(self, transcript_id: str, organization_id: str) -> None:
    run_async(_embed_transcript(transcript_id, organization_id))
