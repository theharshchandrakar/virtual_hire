"""Job requisition CRUD routes (VHIRE-24 / E3). Org-scoped via
`app.api.deps.get_org_scoped_db` — `organization_id` always comes from the
requester's authenticated session context, never a path/body field (I2).
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_hr_user, get_org_scoped_db
from app.core.security import HRUserClaims
from app.schemas.requisition import (
    JobRequisitionCreate,
    JobRequisitionRead,
    JobRequisitionStatusUpdate,
)
from app.services import requisitions as requisitions_service

router = APIRouter(prefix="/requisitions", tags=["requisitions"])


@router.post("", response_model=JobRequisitionRead, status_code=status.HTTP_201_CREATED)
async def create_requisition(
    body: JobRequisitionCreate,
    hr_user: HRUserClaims = Depends(get_current_hr_user),
    session: AsyncSession = Depends(get_org_scoped_db),
) -> JobRequisitionRead:
    """Create a JobRequisition in `status=draft` for the requester's organization."""
    return await requisitions_service.create_requisition(
        session,
        organization_id=hr_user.organization_id,
        title=body.title,
        department=body.department,
        owner_hr_user_id=body.owner_hr_user_id,
        scorecard_template=body.scorecard_template,
    )


@router.get("/{requisition_id}", response_model=JobRequisitionRead)
async def read_requisition(
    requisition_id: uuid.UUID, session: AsyncSession = Depends(get_org_scoped_db)
) -> JobRequisitionRead:
    """Fetch a JobRequisition by id, scoped to the requester's organization (I2)."""
    result = await requisitions_service.get_requisition(session, requisition_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="requisition not found")
    return result


@router.patch("/{requisition_id}/status", response_model=JobRequisitionRead)
async def update_requisition_status(
    requisition_id: uuid.UUID,
    body: JobRequisitionStatusUpdate,
    session: AsyncSession = Depends(get_org_scoped_db),
) -> JobRequisitionRead:
    """Transition a requisition's status.

    Raises:
        HTTPException: 404 if the requisition doesn't exist; 409 if the
            requested transition isn't valid (I5).
    """
    try:
        result = await requisitions_service.transition_requisition_status(
            session, requisition_id, new_status=body.status
        )
    except requisitions_service.InvalidStatusTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="requisition not found")
    return result
