"""Integration tests against a real Postgres instance for the
transcripts_and_verdicts migration: table existence, RLS, and the
enforce_verdict_consistency trigger (the I3/I12-pattern exclusivity
check on `verdicts.resume_id`/`interview_id`).

Requires DATABASE_URL to be reachable - see tests/integration/conftest.py
for the skip-if-unreachable behavior.
"""

import json
import uuid

import asyncpg
import pytest

NEW_TABLES = {"transcripts", "verdicts"}


async def test_new_tables_exist(conn: asyncpg.Connection):
    rows = await conn.fetch("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
    assert NEW_TABLES <= {row["tablename"] for row in rows}


async def test_rls_enabled_on_new_tables(conn: asyncpg.Connection):
    rows = await conn.fetch(
        "SELECT relname, relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname = ANY($1::text[])",
        list(NEW_TABLES),
    )
    assert len(rows) == len(NEW_TABLES)
    for row in rows:
        assert row["relrowsecurity"] is True, f"{row['relname']} missing ENABLE ROW LEVEL SECURITY"
        assert row["relforcerowsecurity"] is True, f"{row['relname']} missing FORCE ROW LEVEL SECURITY"


@pytest.fixture
async def seed(conn: asyncpg.Connection) -> dict[str, uuid.UUID]:
    org_id = uuid.uuid4()
    hr_user_id = uuid.uuid4()
    requisition_id = uuid.uuid4()
    other_requisition_id = uuid.uuid4()
    candidate_id = uuid.uuid4()
    resume_id = uuid.uuid4()
    other_resume_id = uuid.uuid4()
    application_id = uuid.uuid4()
    other_application_id = uuid.uuid4()
    interview_id = uuid.uuid4()
    other_interview_id = uuid.uuid4()

    await conn.execute("INSERT INTO organizations (id, name) VALUES ($1, 'Org A')", org_id)
    await conn.execute(
        """
        INSERT INTO hr_users (id, organization_id, email, full_name, role, status)
        VALUES ($1, $2, 'owner@org-a.test', 'Owner', 'recruiter', 'active')
        """,
        hr_user_id,
        org_id,
    )
    await conn.execute(
        """
        INSERT INTO job_requisitions (id, organization_id, title, owner_hr_user_id, status, scorecard_template)
        VALUES ($1, $2, 'Engineer', $3, 'open', $4::jsonb), ($5, $2, 'Other Role', $3, 'open', $4::jsonb)
        """,
        requisition_id,
        org_id,
        hr_user_id,
        json.dumps({"fields": []}),
        other_requisition_id,
    )
    await conn.execute(
        """
        INSERT INTO candidates (id, organization_id, email, full_name, status)
        VALUES ($1, $2, 'c@example.test', 'C', 'active')
        """,
        candidate_id,
        org_id,
    )
    await conn.execute(
        """
        INSERT INTO resumes (id, organization_id, candidate_id, file_object_key, status)
        VALUES ($1, $2, $3, 'orgA/resume.pdf', 'uploaded'), ($4, $2, $3, 'orgA/other.pdf', 'uploaded')
        """,
        resume_id,
        org_id,
        candidate_id,
        other_resume_id,
    )
    await conn.execute(
        """
        INSERT INTO applications (id, organization_id, candidate_id, job_requisition_id, resume_id, status)
        VALUES ($1, $2, $3, $4, $5, 'submitted'), ($6, $2, $3, $7, $8, 'submitted')
        """,
        application_id,
        org_id,
        candidate_id,
        requisition_id,
        resume_id,
        other_application_id,
        other_requisition_id,
        other_resume_id,
    )
    await conn.execute(
        """
        INSERT INTO interviews (id, organization_id, application_id, interviewer_hr_user_id, scheduled_at, status)
        VALUES ($1, $2, $3, $4, now(), 'completed'), ($5, $2, $6, $4, now(), 'completed')
        """,
        interview_id,
        org_id,
        application_id,
        hr_user_id,
        other_interview_id,
        other_application_id,
    )
    return {
        "org_id": org_id,
        "application_id": application_id,
        "other_application_id": other_application_id,
        "resume_id": resume_id,
        "other_resume_id": other_resume_id,
        "interview_id": interview_id,
        "other_interview_id": other_interview_id,
    }


def _verdict_insert_sql() -> str:
    return """
        INSERT INTO verdicts
            (id, organization_id, application_id, service_type, resume_id, interview_id,
             deterministic_score, verdict_label, narrative, crew_run, generated_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8, 'narrative', '{}'::jsonb, now())
    """


async def test_transcripts_unique_per_interview(conn: asyncpg.Connection, seed: dict):
    await conn.execute(
        "INSERT INTO transcripts (id, organization_id, interview_id, status) VALUES ($1, $2, $3, 'available')",
        uuid.uuid4(),
        seed["org_id"],
        seed["interview_id"],
    )
    with pytest.raises(asyncpg.UniqueViolationError):
        await conn.execute(
            "INSERT INTO transcripts (id, organization_id, interview_id, status) VALUES ($1, $2, $3, 'available')",
            uuid.uuid4(),
            seed["org_id"],
            seed["interview_id"],
        )


async def test_resume_analysis_verdict_allowed_when_resume_belongs_to_application(
    conn: asyncpg.Connection, seed: dict
):
    await conn.execute(
        _verdict_insert_sql(),
        uuid.uuid4(),
        seed["org_id"],
        seed["application_id"],
        "resume_analysis",
        seed["resume_id"],
        None,
        json.dumps({}),
        "pass",
    )


async def test_resume_analysis_verdict_rejects_missing_resume_id(conn: asyncpg.Connection, seed: dict):
    with pytest.raises(asyncpg.RaiseError):
        await conn.execute(
            _verdict_insert_sql(),
            uuid.uuid4(),
            seed["org_id"],
            seed["application_id"],
            "resume_analysis",
            None,
            None,
            json.dumps({}),
            "pass",
        )


async def test_resume_analysis_verdict_rejects_resume_from_a_different_application(
    conn: asyncpg.Connection, seed: dict
):
    with pytest.raises(asyncpg.RaiseError):
        await conn.execute(
            _verdict_insert_sql(),
            uuid.uuid4(),
            seed["org_id"],
            seed["application_id"],
            "resume_analysis",
            seed["other_resume_id"],
            None,
            json.dumps({}),
            "pass",
        )


async def test_transcript_review_verdict_allowed_when_interview_belongs_to_application(
    conn: asyncpg.Connection, seed: dict
):
    await conn.execute(
        _verdict_insert_sql(),
        uuid.uuid4(),
        seed["org_id"],
        seed["application_id"],
        "transcript_assignment_review",
        None,
        seed["interview_id"],
        json.dumps({}),
        "review",
    )


async def test_transcript_review_verdict_rejects_interview_from_a_different_application(
    conn: asyncpg.Connection, seed: dict
):
    with pytest.raises(asyncpg.RaiseError):
        await conn.execute(
            _verdict_insert_sql(),
            uuid.uuid4(),
            seed["org_id"],
            seed["application_id"],
            "transcript_assignment_review",
            None,
            seed["other_interview_id"],
            json.dumps({}),
            "review",
        )


async def test_verdicts_unique_per_application_and_service_type(conn: asyncpg.Connection, seed: dict):
    await conn.execute(
        _verdict_insert_sql(),
        uuid.uuid4(),
        seed["org_id"],
        seed["application_id"],
        "resume_analysis",
        seed["resume_id"],
        None,
        json.dumps({}),
        "pass",
    )
    with pytest.raises(asyncpg.UniqueViolationError):
        await conn.execute(
            _verdict_insert_sql(),
            uuid.uuid4(),
            seed["org_id"],
            seed["application_id"],
            "resume_analysis",
            seed["resume_id"],
            None,
            json.dumps({}),
            "fail",
        )
