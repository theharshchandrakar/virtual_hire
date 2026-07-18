"""transcripts and verdicts

Adds the `transcripts` and `verdicts` tables from docs/05-data-model.md's
"Verdict-service tables" section - purely additive to the initial schema,
no existing table changed. Scoped to these two tables for this revision
(the RAG-driven Resume Analyzer + Transcript Reviewer verdict services);
`proctoring_sessions`/`proctoring_events`/`assignments`/`assignment_submissions`
are out of scope here (E21 biometric proctoring is legally gated and not
built in this pass - see vector.md), so `verdict_service_type` only has
`resume_analysis` and `transcript_assignment_review` members for now.

RLS policies follow the exact pattern the initial migration already
established for I2. The `verdicts` exclusivity trigger is the I3-pattern
CHECK described in docs/05-data-model.md: exactly one of resume_id/
interview_id is set per service_type, and whichever is set belongs to
the same application_id (transitively, the same organization_id).

Revision ID: 5fb963736085
Revises: 607fb6e98882
Create Date: 2026-07-18 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "5fb963736085"
down_revision: str | None = "607fb6e98882"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ENUMS: list[tuple[str, list[str]]] = [
    ("transcript_status", ["pending", "available", "unavailable"]),
    ("transcript_source", ["platform_provided", "generated_stt"]),
    ("verdict_service_type", ["resume_analysis", "transcript_assignment_review"]),
    ("verdict_label", ["pass", "review", "fail"]),
]

ORG_SCOPED_TABLES = ["transcripts", "verdicts"]

TIMESTAMP_COLS = (
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
)


def _uuid_pk() -> sa.Column:
    return sa.Column(
        "id",
        postgresql.UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )


def _org_fk() -> sa.Column:
    return sa.Column(
        "organization_id",
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey("organizations.id"),
        nullable=False,
    )


def upgrade() -> None:
    bind = op.get_bind()
    for name, values in ENUMS:
        postgresql.ENUM(*values, name=name).create(bind, checkfirst=True)

    op.create_table(
        "transcripts",
        _uuid_pk(),
        _org_fk(),
        sa.Column(
            "interview_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("interviews.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "status",
            postgresql.ENUM(name="transcript_status", create_type=False),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("source", postgresql.ENUM(name="transcript_source", create_type=False), nullable=True),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("language", sa.Text(), nullable=True),
        *TIMESTAMP_COLS,
    )

    op.create_table(
        "verdicts",
        _uuid_pk(),
        _org_fk(),
        sa.Column(
            "application_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("applications.id"), nullable=False
        ),
        sa.Column(
            "service_type", postgresql.ENUM(name="verdict_service_type", create_type=False), nullable=False
        ),
        sa.Column("resume_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("resumes.id"), nullable=True),
        sa.Column(
            "interview_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("interviews.id"), nullable=True
        ),
        sa.Column("deterministic_score", postgresql.JSONB(), nullable=False),
        sa.Column("verdict_label", postgresql.ENUM(name="verdict_label", create_type=False), nullable=False),
        sa.Column("narrative", sa.Text(), nullable=False),
        sa.Column("crew_run", postgresql.JSONB(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("stale", sa.Boolean(), nullable=False, server_default=sa.false()),
        *TIMESTAMP_COLS,
        sa.UniqueConstraint("application_id", "service_type", name="uq_verdicts_application_service_type"),
    )

    for table in ORG_SCOPED_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY {table}_org_isolation ON {table}
            USING (organization_id = current_setting('app.current_org_id', true)::uuid)
            WITH CHECK (organization_id = current_setting('app.current_org_id', true)::uuid)
            """
        )

    # I12/I3-pattern: exactly one of resume_id/interview_id set per
    # service_type, and whichever is set must belong to the same
    # application (transitively, the same organization_id) as this Verdict.
    op.execute(
        """
        CREATE FUNCTION enforce_verdict_consistency() RETURNS TRIGGER AS $$
        DECLARE
            v_match_count INT;
        BEGIN
            IF NEW.service_type = 'resume_analysis' THEN
                IF NEW.resume_id IS NULL OR NEW.interview_id IS NOT NULL THEN
                    RAISE EXCEPTION
                        'verdicts.resume_id must be set (and interview_id NULL) when service_type=resume_analysis';
                END IF;
                SELECT count(*) INTO v_match_count FROM applications
                    WHERE id = NEW.application_id AND resume_id = NEW.resume_id;
                IF v_match_count = 0 THEN
                    RAISE EXCEPTION 'verdicts.resume_id must belong to verdicts.application_id';
                END IF;
            ELSIF NEW.service_type = 'transcript_assignment_review' THEN
                IF NEW.interview_id IS NULL OR NEW.resume_id IS NOT NULL THEN
                    RAISE EXCEPTION
                        'verdicts.interview_id must be set (and resume_id NULL) when service_type=transcript_assignment_review';
                END IF;
                SELECT count(*) INTO v_match_count FROM interviews
                    WHERE id = NEW.interview_id AND application_id = NEW.application_id;
                IF v_match_count = 0 THEN
                    RAISE EXCEPTION 'verdicts.interview_id must belong to verdicts.application_id';
                END IF;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_verdict_consistency
        BEFORE INSERT OR UPDATE ON verdicts
        FOR EACH ROW EXECUTE FUNCTION enforce_verdict_consistency()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_verdict_consistency ON verdicts")
    op.execute("DROP FUNCTION IF EXISTS enforce_verdict_consistency()")

    for table in ORG_SCOPED_TABLES:
        op.execute(f"DROP POLICY IF EXISTS {table}_org_isolation ON {table}")

    op.drop_table("verdicts")
    op.drop_table("transcripts")

    bind = op.get_bind()
    for name, values in reversed(ENUMS):
        postgresql.ENUM(*values, name=name).drop(bind, checkfirst=True)
