"""Tests for app.workers.tasks.embedding (VHIRE-2x / E7): resume and
transcript embedding, sharing the same chunk -> embed -> upsert path
(`_embed_and_upsert`). Tests the async task bodies directly, mirroring
tests/workers/test_parsing.py's approach - fakes/stubs rather than live
Postgres/Qdrant/Voyage.
"""

import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import pytest

from app.models.enums import EmbeddingStatus
from app.models.resume import Resume
from app.models.transcript import Transcript
from app.workers.tasks import embedding


class _FakeSession:
    """Keys its store by `str(id)` so lookups work whether the caller
    passes a UUID (following a model attribute, e.g. `interview.application_id`)
    or a string (a task's own `resume_id`/`transcript_id` kwarg, since
    Celery payloads are JSON)."""

    def __init__(self, objects: list | None = None):
        self.store = {str(obj.id): obj for obj in (objects or [])}
        self.commit_calls = 0
        self.flush_calls = 0

    async def get(self, model, obj_id):
        return self.store.get(str(obj_id))

    async def flush(self) -> None:
        self.flush_calls += 1

    async def commit(self) -> None:
        self.commit_calls += 1


def _fake_org_scoped_session(session: _FakeSession):
    @asynccontextmanager
    async def _factory(organization_id):
        yield session

    return _factory


def _resume(**overrides) -> Resume:
    defaults = dict(
        id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        candidate_id=uuid.uuid4(),
        file_object_key="org/resume/file.txt",
        embedding_status=EmbeddingStatus.not_embedded,
    )
    return Resume(**{**defaults, **overrides})


@pytest.fixture(autouse=True)
def _stub_vector_pipeline(monkeypatch):
    deleted = []
    upserted = []

    async def _delete(organization_id, *, source_type, source_id):
        deleted.append((organization_id, source_type, source_id))

    async def _upsert(organization_id, points):
        upserted.append((organization_id, points))

    monkeypatch.setattr(embedding.vector_store, "delete_points_by_source", _delete)
    monkeypatch.setattr(embedding.vector_store, "upsert_points", _upsert)
    monkeypatch.setattr(embedding.chunking, "chunk_text", lambda text: [text] if text else [])
    monkeypatch.setattr(embedding.embeddings, "embed_chunks", _fake_embed_chunks)
    return {"deleted": deleted, "upserted": upserted}


async def _fake_embed_chunks(chunks):
    return [[0.1, 0.2] for _ in chunks]


async def test_embed_resume_success_sets_embedded_status(monkeypatch, _stub_vector_pipeline):
    resume = _resume()
    session = _FakeSession([resume])
    monkeypatch.setattr(embedding, "org_scoped_session", _fake_org_scoped_session(session))
    monkeypatch.setattr(embedding.storage, "download_object", lambda key: b"raw text bytes")
    monkeypatch.setattr(
        embedding.text_extraction, "extract_text", lambda content, filename: "resume text content"
    )

    await embedding._embed_resume(str(resume.id), str(resume.organization_id))

    assert resume.embedding_status == EmbeddingStatus.embedded
    assert resume.embedding_error is None
    assert len(_stub_vector_pipeline["upserted"]) == 1
    assert len(_stub_vector_pipeline["deleted"]) == 1


async def test_embed_resume_failure_sets_embed_failed(monkeypatch, _stub_vector_pipeline):
    resume = _resume()
    session = _FakeSession([resume])
    monkeypatch.setattr(embedding, "org_scoped_session", _fake_org_scoped_session(session))

    def _raise(key):
        raise RuntimeError("s3 unavailable")

    monkeypatch.setattr(embedding.storage, "download_object", _raise)

    await embedding._embed_resume(str(resume.id), str(resume.organization_id))

    assert resume.embedding_status == EmbeddingStatus.embed_failed
    assert "s3 unavailable" in resume.embedding_error


async def test_embed_resume_returns_quietly_when_missing(monkeypatch, _stub_vector_pipeline):
    session = _FakeSession([])
    monkeypatch.setattr(embedding, "org_scoped_session", _fake_org_scoped_session(session))

    await embedding._embed_resume(str(uuid.uuid4()), str(uuid.uuid4()))

    assert _stub_vector_pipeline["upserted"] == []


async def test_embed_transcript_success_resolves_candidate_via_interview_application(
    monkeypatch, _stub_vector_pipeline
):
    from app.models.application import Application
    from app.models.interview import Interview

    org_id = uuid.uuid4()
    candidate_id = uuid.uuid4()
    application = Application(
        id=uuid.uuid4(),
        organization_id=org_id,
        candidate_id=candidate_id,
        job_requisition_id=uuid.uuid4(),
        resume_id=uuid.uuid4(),
    )
    interview = Interview(
        id=uuid.uuid4(),
        organization_id=org_id,
        application_id=application.id,
        interviewer_hr_user_id=uuid.uuid4(),
        scheduled_at=datetime.now(UTC),
    )
    transcript = Transcript(
        id=uuid.uuid4(), organization_id=org_id, interview_id=interview.id, text="transcript text"
    )
    session = _FakeSession([transcript, interview, application])
    monkeypatch.setattr(embedding, "org_scoped_session", _fake_org_scoped_session(session))

    await embedding._embed_transcript(str(transcript.id), str(org_id))

    assert len(_stub_vector_pipeline["upserted"]) == 1
    upserted_org, points = _stub_vector_pipeline["upserted"][0]
    assert upserted_org == org_id
    assert points[0].candidate_id == candidate_id
    assert points[0].source_type == "transcript"


async def test_embed_transcript_skips_when_no_text_yet(monkeypatch, _stub_vector_pipeline):
    transcript = Transcript(id=uuid.uuid4(), organization_id=uuid.uuid4(), interview_id=uuid.uuid4(), text=None)
    session = _FakeSession([transcript])
    monkeypatch.setattr(embedding, "org_scoped_session", _fake_org_scoped_session(session))

    await embedding._embed_transcript(str(transcript.id), str(transcript.organization_id))

    assert _stub_vector_pipeline["upserted"] == []


async def test_embed_transcript_returns_quietly_when_missing(monkeypatch, _stub_vector_pipeline):
    session = _FakeSession([])
    monkeypatch.setattr(embedding, "org_scoped_session", _fake_org_scoped_session(session))

    await embedding._embed_transcript(str(uuid.uuid4()), str(uuid.uuid4()))

    assert _stub_vector_pipeline["upserted"] == []
