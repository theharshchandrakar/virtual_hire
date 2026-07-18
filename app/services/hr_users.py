"""HR user invite/activate/deactivate lifecycle. See docs/03-ontology.md's
HRUser lifecycle and A2/A3 in docs/02-assumptions.md.

VHIRE-24 (E3). All operations here are org-scoped (I2) — `organization_id`
always comes from the authenticated requester's session context (see
app.api.deps.get_org_scoped_db), never a client-supplied field, matching
every other org-scoped service in this codebase.

Known gap, out of scope for this story: inviting an organization's very
first HR user has no bootstrap path here, since every route in this
module requires an already-authenticated HR user to act as the inviter.
Seeding the first HR user for a newly created Organization is an
operational/tooling problem (e.g. a seed script or admin console), not
solved by this API surface.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import HRUserRole, HRUserStatus
from app.models.hr_user import HRUser


async def invite_hr_user(
    session: AsyncSession, *, organization_id: uuid.UUID, email: str, full_name: str, role: HRUserRole
) -> HRUser:
    """Create an HR user in `status=invited` for `organization_id`."""
    hr_user = HRUser(
        organization_id=organization_id,
        email=email,
        full_name=full_name,
        role=role,
        status=HRUserStatus.invited,
    )
    session.add(hr_user)
    await session.commit()
    await session.refresh(hr_user)
    return hr_user


async def get_hr_user(session: AsyncSession, hr_user_id: uuid.UUID) -> HRUser | None:
    """Fetch an HR user by id, scoped by the caller's RLS session context."""
    result = await session.execute(select(HRUser).where(HRUser.id == hr_user_id))
    return result.scalar_one_or_none()


async def activate_hr_user(session: AsyncSession, hr_user_id: uuid.UUID) -> HRUser | None:
    """Transition an HR user from `invited` to `active`.

    Returns `None` if no HR user with this id exists (in the caller's
    org, per RLS). No-op (returns the row unchanged) if already active.
    """
    hr_user = await get_hr_user(session, hr_user_id)
    if hr_user is None:
        return None
    if hr_user.status == HRUserStatus.invited:
        hr_user.status = HRUserStatus.active
        await session.commit()
        await session.refresh(hr_user)
    return hr_user


async def deactivate_hr_user(session: AsyncSession, hr_user_id: uuid.UUID) -> HRUser | None:
    """Transition an HR user to `deactivated`.

    Returns `None` if no HR user with this id exists (in the caller's
    org, per RLS).
    """
    hr_user = await get_hr_user(session, hr_user_id)
    if hr_user is None:
        return None
    hr_user.status = HRUserStatus.deactivated
    await session.commit()
    await session.refresh(hr_user)
    return hr_user
