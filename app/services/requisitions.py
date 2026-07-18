"""Job requisition CRUD and status-transition guard (I5-style: reject any
(from, to) pair not explicitly allowed). See docs/05-data-model.md's
`job_requisitions.status` enum: draft -> open -> on_hold/filled/cancelled.

VHIRE-24 (E3). All operations are org-scoped (I2) via the caller's
`get_org_scoped_db` session — `organization_id` is never accepted as a
client-supplied field.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import JobRequisitionStatus
from app.models.job_requisition import JobRequisition

# Valid (from, to) transitions. Anything not listed here is rejected.
# filled/cancelled are terminal — no transition leaves them.
_VALID_TRANSITIONS: dict[JobRequisitionStatus, set[JobRequisitionStatus]] = {
    JobRequisitionStatus.draft: {JobRequisitionStatus.open, JobRequisitionStatus.cancelled},
    JobRequisitionStatus.open: {
        JobRequisitionStatus.on_hold,
        JobRequisitionStatus.filled,
        JobRequisitionStatus.cancelled,
    },
    JobRequisitionStatus.on_hold: {JobRequisitionStatus.open, JobRequisitionStatus.cancelled},
    JobRequisitionStatus.filled: set(),
    JobRequisitionStatus.cancelled: set(),
}


class InvalidStatusTransitionError(Exception):
    """Raised when a requisition status transition isn't in `_VALID_TRANSITIONS`."""


async def create_requisition(
    session: AsyncSession,
    *,
    organization_id: uuid.UUID,
    title: str,
    department: str | None,
    owner_hr_user_id: uuid.UUID,
    scorecard_template: dict,
) -> JobRequisition:
    """Create a JobRequisition in `status=draft`."""
    requisition = JobRequisition(
        organization_id=organization_id,
        title=title,
        department=department,
        owner_hr_user_id=owner_hr_user_id,
        scorecard_template=scorecard_template,
        status=JobRequisitionStatus.draft,
    )
    session.add(requisition)
    await session.commit()
    await session.refresh(requisition)
    return requisition


async def get_requisition(session: AsyncSession, requisition_id: uuid.UUID) -> JobRequisition | None:
    """Fetch a JobRequisition by id, scoped by the caller's RLS session context."""
    result = await session.execute(select(JobRequisition).where(JobRequisition.id == requisition_id))
    return result.scalar_one_or_none()


async def transition_requisition_status(
    session: AsyncSession, requisition_id: uuid.UUID, *, new_status: JobRequisitionStatus
) -> JobRequisition | None:
    """Transition a requisition's status, enforcing the valid-transitions table (I5).

    Returns `None` if no requisition with this id exists (in the caller's
    org, per RLS).

    Raises:
        InvalidStatusTransitionError: if `(current_status, new_status)`
            isn't an allowed transition.
    """
    requisition = await get_requisition(session, requisition_id)
    if requisition is None:
        return None

    if new_status not in _VALID_TRANSITIONS[requisition.status]:
        raise InvalidStatusTransitionError(
            f"cannot transition job requisition from {requisition.status} to {new_status}"
        )

    requisition.status = new_status
    await session.commit()
    await session.refresh(requisition)
    return requisition
