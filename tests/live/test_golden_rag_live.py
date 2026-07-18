"""Live LLM & Vector DB tests (TESTING.md §7.9): real Voyage embeddings,
real Qdrant upsert/search, and a real OpenRouter Judge call against the
golden dataset (tests/fixtures/golden/). Every other test in this repo
fakes these calls - this file is the one place that doesn't, because it
exists specifically to answer a question mocks can't: does the real
model produce a usable verdict from real embeddings?

Requires OPENROUTER_API_KEY and VOYAGE_API_KEY to be genuinely configured
(skips, not fails, otherwise - same convention tests/integration/conftest.py
uses for an unreachable Postgres) and a reachable Qdrant (via docker-compose
locally, or CI's dedicated live-RAG job). Never part of the default `pytest`
invocation - see pyproject.toml's `live_llm` marker and addopts.
"""

import uuid

import pytest

from app.core.config import get_settings
from app.crew.agents import judge as judge_agent
from app.models.enums import VerdictLabel
from app.services import chunking, embeddings, vector_store
from app.services.scoring import resume_fit, transcript_review
from app.services.vector_store import ChunkPoint
from tests.fixtures.golden.loader import (
    load_golden_requisitions,
    load_golden_resumes,
    load_golden_transcripts,
)

pytestmark = pytest.mark.live_llm


@pytest.fixture(scope="module", autouse=True)
def _require_live_vendor_keys():
    settings = get_settings()
    if not settings.openrouter_api_key or not settings.voyage_api_key:
        pytest.skip("OPENROUTER_API_KEY/VOYAGE_API_KEY not configured; skipping live RAG tests")


@pytest.fixture
async def live_org_collection():
    """Provision a throwaway Qdrant collection for one test, real Qdrant
    calls only (no Postgres involved - this tier tests RAG/LLM quality,
    not the DB plumbing tests/integration/ already covers).
    """
    org_id = uuid.uuid4()
    await vector_store.provision_collection(org_id)
    try:
        yield org_id
    finally:
        await vector_store.delete_collection(org_id)


def _requisition_by_slug(slug: str) -> dict:
    for requisition in load_golden_requisitions():
        if requisition.slug == slug:
            return requisition.data
    raise KeyError(slug)


def _resume_by_slug(slug: str):
    for resume in load_golden_resumes():
        if resume.slug == slug:
            return resume
    raise KeyError(slug)


def _transcript_by_slug(slug: str):
    for transcript in load_golden_transcripts():
        if transcript.slug == slug:
            return transcript
    raise KeyError(slug)


async def _embed_and_upsert_resume(org_id: uuid.UUID, resume, candidate_id: uuid.UUID) -> None:
    chunks = chunking.chunk_text(resume.text)
    vectors = await embeddings.embed_chunks(chunks)
    points = [
        ChunkPoint(
            organization_id=org_id,
            source_type="resume",
            source_id=candidate_id,
            candidate_id=candidate_id,
            chunk_index=index,
            chunk_text=chunk,
            vector=vector,
        )
        for index, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True))
    ]
    await vector_store.upsert_points(org_id, points)


async def _judge_resume_against_requisition(org_id, resume, requisition_slug, resume_id):
    requisition_data = _requisition_by_slug(requisition_slug)
    required_skills = requisition_data["scorecard_template"]["required_skills"]

    deterministic_score = resume_fit.score_resume_fit(
        resume.answer_key["expected_parsed_data"], {"required_skills": required_skills}
    )

    query_text = f"{requisition_data['title']}. Required skills: {', '.join(required_skills)}"
    query_vector = (await embeddings.embed_chunks([query_text]))[0]
    retrieved = await vector_store.search(org_id, query_vector, source_type="resume", source_id=resume_id, limit=5)
    context_chunks = [point.payload["chunk_text"] for point in retrieved if point.payload]

    return deterministic_score, judge_agent.run_judge(
        deterministic_score=deterministic_score,
        context_chunks=context_chunks,
        task_description=f"Assess this candidate's resume fit for the '{requisition_data['title']}' requisition.",
    )


@pytest.mark.parametrize(
    ("resume_slug", "requisition_slug"),
    [
        ("resume_01_strong_backend_match", "req_backend_engineer"),
        ("resume_02_weak_backend_match", "req_backend_engineer"),
    ],
)
async def test_live_resume_verdict_matches_expected_band(live_org_collection, resume_slug, requisition_slug):
    """Real Voyage embeddings + real Qdrant retrieval + a real OpenRouter
    Judge call, graded against the golden answer key's expected verdict band.
    """
    org_id = live_org_collection
    resume = _resume_by_slug(resume_slug)
    candidate_id = uuid.uuid4()

    await _embed_and_upsert_resume(org_id, resume, candidate_id)
    deterministic_score, judge_result = await _judge_resume_against_requisition(
        org_id, resume, requisition_slug, candidate_id
    )

    expectation = resume.answer_key["requisition_matches"][requisition_slug]
    assert len(deterministic_score["matched_skills"]) >= expectation["expected_min_matched_skills"]

    verdict_label = VerdictLabel(judge_result["verdict_label"])
    expected_band = {VerdictLabel(label) for label in expectation["expected_verdict_label_band"]}
    assert judge_result["narrative"].strip()
    assert verdict_label in expected_band, (
        f"{resume_slug} vs {requisition_slug}: expected verdict in {expected_band}, "
        f"got {verdict_label} - narrative: {judge_result['narrative']}"
    )


@pytest.mark.parametrize(
    "transcript_slug",
    ["transcript_01_strong", "transcript_02_short"],
)
async def test_live_transcript_verdict_produces_a_valid_verdict(live_org_collection, transcript_slug):
    """Real Voyage embeddings + real Qdrant retrieval + a real OpenRouter
    Judge call for the transcript path, using the same pipeline as the
    resume case (vector.md's "same RAG pipeline" design).
    """
    org_id = live_org_collection
    transcript = _transcript_by_slug(transcript_slug)
    candidate_id = uuid.uuid4()

    chunks = chunking.chunk_text(transcript.text)
    vectors = await embeddings.embed_chunks(chunks)
    points = [
        ChunkPoint(
            organization_id=org_id,
            source_type="transcript",
            source_id=candidate_id,
            candidate_id=candidate_id,
            chunk_index=index,
            chunk_text=chunk,
            vector=vector,
        )
        for index, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True))
    ]
    await vector_store.upsert_points(org_id, points)

    expected_scoring = transcript.answer_key["expected_scoring"]
    deterministic_score = transcript_review.score_transcript(
        transcript.text, rubric={"min_word_count": expected_scoring["min_word_count"]}
    )
    assert deterministic_score["flags"] == expected_scoring["expected_flags"]

    query_vector = (await embeddings.embed_chunks([transcript.text[:500]]))[0]
    retrieved = await vector_store.search(
        org_id, query_vector, source_type="transcript", source_id=candidate_id, limit=5
    )
    context_chunks = [point.payload["chunk_text"] for point in retrieved if point.payload]

    judge_result = judge_agent.run_judge(
        deterministic_score=deterministic_score,
        context_chunks=context_chunks,
        task_description="Review this interview transcript and produce a hiring verdict.",
    )

    assert judge_result["narrative"].strip()
    assert VerdictLabel(judge_result["verdict_label"]) in set(VerdictLabel)
