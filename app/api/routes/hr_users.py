"""HR user invite/activate/deactivate routes (VHIRE-24 / E3). Org-scoped
via `app.api.deps.get_org_scoped_db` — `organization_id` always comes from
the authenticated inviter's own session context, never a path/body field,
per I2. See `app.services.hr_users` for the known first-user-bootstrap gap.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_hr_user, get_org_scoped_db
from app.core.security import HRUserClaims
from app.schemas.hr_user import HRUserInvite, HRUserRead
from app.services import hr_users as hr_users_service

router = APIRouter(prefix="/hr-users", tags=["hr-users"])


@router.post("", response_model=HRUserRead, status_code=status.HTTP_201_CREATED)
async def invite_hr_user(
    body: HRUserInvite,
    hr_user: HRUserClaims = Depends(get_current_hr_user),
    session: AsyncSession = Depends(get_org_scoped_db),
) -> HRUserRead:
    """Invite a new HR user into the requesting HR user's organization."""
    return await hr_users_service.invite_hr_user(
        session,
        organization_id=hr_user.organization_id,
        email=body.email,
        full_name=body.full_name,
        role=body.role,
    )


@router.get("/{hr_user_id}", response_model=HRUserRead)
async def read_hr_user(
    hr_user_id: uuid.UUID, session: AsyncSession = Depends(get_org_scoped_db)
) -> HRUserRead:
    """Fetch an HR user by id, scoped to the requester's organization (I2)."""
    result = await hr_users_service.get_hr_user(session, hr_user_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="hr user not found")
    return result


@router.patch("/{hr_user_id}/activate", response_model=HRUserRead)
async def activate_hr_user(
    hr_user_id: uuid.UUID, session: AsyncSession = Depends(get_org_scoped_db)
) -> HRUserRead:
    """Transition an HR user from `invited` to `active`."""
    result = await hr_users_service.activate_hr_user(session, hr_user_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="hr user not found")
    return result


@router.patch("/{hr_user_id}/deactivate", response_model=HRUserRead)
async def deactivate_hr_user(
    hr_user_id: uuid.UUID, session: AsyncSession = Depends(get_org_scoped_db)
) -> HRUserRead:
    """Transition an HR user to `deactivated`."""
    result = await hr_users_service.deactivate_hr_user(session, hr_user_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="hr user not found")
    return result
