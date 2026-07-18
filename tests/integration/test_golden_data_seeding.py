"""Golden-data seeding integration test (TESTING.md §8): proves the
golden resumes/requisitions/transcripts land correctly as real rows in a
real Postgres instance (via docker-compose/CI service containers) - the
relational half of "seed the golden dataset". The vector/LLM half (real
Voyage embeddings, real Qdrant retrieval, real OpenRouter Judge calls)
lives in tests/live/test_golden_rag_live.py instead, gated on real
vendor keys rather than just Postgres reachability.

Requires DATABASE_URL to be reachable - see tests/integration/conftest.py
for the skip-if-unreachable behavior.
"""

import json
import uuid

import asyncpg
import pytest

from tests.fixtures.golden.loader import load_golden_requisitions, load_golden_resumes


def _parsed_data_from_answer_key(expected_parsed_data: dict) -> dict:
    """Build a plausible `resumes.parsed_data` JSONB shape from an answer
    key's compact `expected_parsed_data` (which records counts, not full
    nested objects - this is a seeding/plumbing test, not a content-quality
    one, so placeholder items are fine as long as the counts are right).
    """
    return {
        "work_history": [{"title": "role"} for _ in range(expected_parsed_data["work_history_min_count"])],
        "education": [{"institution": "school"} for _ in range(expected_parsed_data["education_min_count"])],
        "skills": expected_parsed_data["skills"],
    }


@pytest.fixture
async def seeded_org(conn: asyncpg.Connection) -> dict:
    org_id = uuid.uuid4()
    hr_user_id = uuid.uuid4()

    await conn.execute("INSERT INTO organizations (id, name) VALUES ($1, 'Golden Seed Org')", org_id)
    await conn.execute(
        """
        INSERT INTO hr_users (id, organization_id, email, full_name, role, status)
        VALUES ($1, $2, 'seed-owner@golden.test', 'Seed Owner', 'recruiter', 'active')
        """,
        hr_user_id,
        org_id,
    )

    requisition_ids: dict[str, uuid.UUID] = {}
    for requisition in load_golden_requisitions():
        requisition_id = uuid.uuid4()
        await conn.execute(
            """
            INSERT INTO job_requisitions
                (id, organization_id, title, owner_hr_user_id, status, scorecard_template)
            VALUES ($1, $2, $3, $4, 'open', $5::jsonb)
            """,
            requisition_id,
            org_id,
            requisition.data["title"],
            hr_user_id,
            json.dumps(requisition.data["scorecard_template"]),
        )
        requisition_ids[requisition.slug] = requisition_id

    return {"org_id": org_id, "hr_user_id": hr_user_id, "requisition_ids": requisition_ids}


async def test_every_golden_requisition_lands_in_postgres(conn: asyncpg.Connection, seeded_org: dict):
    rows = await conn.fetch(
        "SELECT title FROM job_requisitions WHERE organization_id = $1", seeded_org["org_id"]
    )
    seeded_titles = {row["title"] for row in rows}
    expected_titles = {req.data["title"] for req in load_golden_requisitions()}
    assert seeded_titles == expected_titles


async def test_every_golden_resume_seeds_a_candidate_resume_and_application(
    conn: asyncpg.Connection, seeded_org: dict
):
    org_id = seeded_org["org_id"]
    requisition_ids = seeded_org["requisition_ids"]

    for resume in load_golden_resumes():
        requisition_matches = resume.answer_key.get("requisition_matches", {})
        if not requisition_matches:
            continue
        requisition_slug = next(iter(requisition_matches))
        requisition_id = requisition_ids[requisition_slug]

        candidate_id = uuid.uuid4()
        resume_id = uuid.uuid4()
        application_id = uuid.uuid4()
        parsed_data = _parsed_data_from_answer_key(resume.answer_key["expected_parsed_data"])

        await conn.execute(
            """
            INSERT INTO candidates (id, organization_id, email, full_name, status)
            VALUES ($1, $2, $3, $4, 'active')
            """,
            candidate_id,
            org_id,
            f"{resume.slug}@golden.test",
            resume.answer_key["candidate_name"],
        )
        await conn.execute(
            """
            INSERT INTO resumes (id, organization_id, candidate_id, file_object_key, status, parsed_data)
            VALUES ($1, $2, $3, $4, 'parsed', $5::jsonb)
            """,
            resume_id,
            org_id,
            candidate_id,
            f"golden/{resume.slug}.txt",
            json.dumps(parsed_data),
        )
        await conn.execute(
            """
            INSERT INTO applications
                (id, organization_id, candidate_id, job_requisition_id, resume_id, status)
            VALUES ($1, $2, $3, $4, $5, 'submitted')
            """,
            application_id,
            org_id,
            candidate_id,
            requisition_id,
            resume_id,
        )

        row = await conn.fetchrow(
            "SELECT parsed_data, status FROM resumes WHERE id = $1", resume_id
        )
        assert row["status"] == "parsed"
        stored_parsed_data = json.loads(row["parsed_data"])
        assert stored_parsed_data["skills"] == resume.answer_key["expected_parsed_data"]["skills"]

        application_row = await conn.fetchrow(
            "SELECT status FROM applications WHERE id = $1", application_id
        )
        assert application_row["status"] == "submitted"
