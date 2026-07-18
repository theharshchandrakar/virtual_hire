"""Unit tests for the ORM model metadata (VHIRE-1 / E1). No DB required -
these assert the SQLAlchemy model shape matches docs/05-data-model.md;
see tests/integration/test_initial_schema.py for tests against a real
Postgres instance (triggers, RLS, actual constraint enforcement).
"""

import app.models
from app.db.base import Base

EXPECTED_TABLES = {
    "organizations",
    "hr_users",
    "job_requisitions",
    "candidates",
    "resumes",
    "applications",
    "interviews",
    "scorecards",
    "analysis_outputs",
    "audit_log",
    "transcripts",
    "verdicts",
}

ORG_SCOPED_TABLES = EXPECTED_TABLES - {"organizations"}


def test_every_data_model_table_is_registered():
    assert set(Base.metadata.tables.keys()) == EXPECTED_TABLES


def test_every_table_except_organizations_is_org_scoped():
    for table_name in ORG_SCOPED_TABLES:
        table = Base.metadata.tables[table_name]
        assert "organization_id" in table.columns, f"{table_name} missing organization_id (I2)"
        col = table.columns["organization_id"]
        assert not col.nullable
        assert any(fk.column.table.name == "organizations" for fk in col.foreign_keys)


def test_every_table_has_uuid_primary_key():
    for table_name in EXPECTED_TABLES:
        table = Base.metadata.tables[table_name]
        pk_cols = list(table.primary_key.columns)
        assert len(pk_cols) == 1
        assert pk_cols[0].name == "id"


def test_resume_candidate_id_not_nullable():
    """I1: a Resume always belongs to exactly one Candidate."""
    col = Base.metadata.tables["resumes"].columns["candidate_id"]
    assert not col.nullable
    assert any(fk.column.table.name == "candidates" for fk in col.foreign_keys)


def test_interview_application_id_not_nullable():
    """I7: an Interview always references exactly one Application."""
    col = Base.metadata.tables["interviews"].columns["application_id"]
    assert not col.nullable
    assert any(fk.column.table.name == "applications" for fk in col.foreign_keys)


def test_scorecard_interview_id_unique():
    """I8: a Scorecard exists for at most one Interview, and vice versa."""
    col = Base.metadata.tables["scorecards"].columns["interview_id"]
    assert not col.nullable
    assert col.unique

    assert app.models.Scorecard.__table__.name == "scorecards"


def test_applications_partial_unique_index_present():
    table = Base.metadata.tables["applications"]
    index = next(
        idx for idx in table.indexes if idx.name == "uq_applications_active_candidate_requisition"
    )
    assert index.unique
    assert {col.name for col in index.columns} == {"candidate_id", "job_requisition_id"}


def test_hr_users_email_unique_per_organization():
    table = Base.metadata.tables["hr_users"]
    constraint = next(
        c for c in table.constraints if getattr(c, "name", None) == "uq_hr_users_org_email"
    )
    assert {col.name for col in constraint.columns} == {"organization_id", "email"}


def test_candidates_email_unique_per_organization():
    table = Base.metadata.tables["candidates"]
    constraint = next(
        c for c in table.constraints if getattr(c, "name", None) == "uq_candidates_org_email"
    )
    assert {col.name for col in constraint.columns} == {"organization_id", "email"}


def test_analysis_outputs_application_id_unique():
    col = Base.metadata.tables["analysis_outputs"].columns["application_id"]
    assert col.unique


def test_audit_log_has_no_updated_at_column():
    assert "updated_at" not in Base.metadata.tables["audit_log"].columns


def test_transcripts_interview_id_unique():
    """One Transcript per Interview at most."""
    col = Base.metadata.tables["transcripts"].columns["interview_id"]
    assert not col.nullable
    assert col.unique


def test_verdicts_deterministic_score_not_nullable():
    """I12: a Verdict cannot exist without a Scoring Engine result."""
    col = Base.metadata.tables["verdicts"].columns["deterministic_score"]
    assert not col.nullable


def test_verdicts_unique_per_application_and_service_type():
    table = Base.metadata.tables["verdicts"]
    constraint = next(
        c for c in table.constraints if getattr(c, "name", None) == "uq_verdicts_application_service_type"
    )
    assert {col.name for col in constraint.columns} == {"application_id", "service_type"}


def test_verdicts_resume_id_and_interview_id_are_both_nullable():
    """Exclusivity (exactly one set, per service_type) is DB-trigger-enforced
    (see the transcripts_and_verdicts migration), not a NOT NULL constraint."""
    table = Base.metadata.tables["verdicts"]
    assert table.columns["resume_id"].nullable
    assert table.columns["interview_id"].nullable
