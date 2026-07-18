"""SQLAlchemy models — one per Postgres table in docs/05-data-model.md.

Importing this package registers every model on app.db.base.Base.metadata,
which alembic/env.py and Base.metadata.create_all(...) (used by tests)
both depend on.
"""

from app.models.analysis_output import AnalysisOutput
from app.models.application import Application
from app.models.audit_log import AuditLog
from app.models.candidate import Candidate
from app.models.hr_user import HRUser
from app.models.interview import Interview
from app.models.job_requisition import JobRequisition
from app.models.organization import Organization
from app.models.resume import Resume
from app.models.scorecard import Scorecard
from app.models.transcript import Transcript
from app.models.verdict import Verdict

__all__ = [
    "AnalysisOutput",
    "Application",
    "AuditLog",
    "Candidate",
    "HRUser",
    "Interview",
    "JobRequisition",
    "Organization",
    "Resume",
    "Scorecard",
    "Transcript",
    "Verdict",
]
