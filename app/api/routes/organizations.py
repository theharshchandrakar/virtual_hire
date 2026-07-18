"""Organization management routes (VHIRE-12 / E3).

Bootstrap-only in v1, per EPIC.md ("likely admin-tooling not self-serve
signup") — deliberately **unauthenticated** for now, since Organization
creation is the one operation that can't depend on an already-existing
org-scoped HR user (there's no org yet to scope a JWT to). Not safe to
expose on a public-facing deployment as-is; flagged here for the
stub-approval discussion rather than silently assumed.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from qdrant_client.http.exceptions import ResponseHandlingException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import get_db
from app.schemas.organization import OrganizationCreate, OrganizationRead
from app.services import organizations as organizations_service

router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.post("", response_model=OrganizationRead, status_code=status.HTTP_201_CREATED)
async def create_organization(
    body: OrganizationCreate, session: AsyncSession = Depends(get_db)
) -> OrganizationRead:
    """Create an Organization and provision its Qdrant collection.

    Raises:
        HTTPException: 503 if Qdrant collection provisioning fails — no
            Organization row is created in that case (I11; see
            `app.services.organizations.create_organization`).
    """
    try:
        return await organizations_service.create_organization(session, name=body.name)
    except ResponseHandlingException as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="vector store unavailable; organization was not created",
        ) from exc


@router.get("/{organization_id}", response_model=OrganizationRead)
async def read_organization(
    organization_id: uuid.UUID, session: AsyncSession = Depends(get_db)
) -> OrganizationRead:
    """Fetch an Organization by id.

    Raises:
        HTTPException: 404 if no Organization with this id exists.
    """
    organization = await organizations_service.get_organization(session, organization_id)
    if organization is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="organization not found")
    return organization


@router.patch("/{organization_id}/deactivate", response_model=OrganizationRead)
async def deactivate_organization(
    organization_id: uuid.UUID, session: AsyncSession = Depends(get_db)
) -> OrganizationRead:
    """Deactivate an Organization and tear down its Qdrant collection.

    Raises:
        HTTPException: 404 if no Organization with this id exists.
    """
    organization = await organizations_service.deactivate_organization(session, organization_id)
    if organization is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="organization not found")
    return organization
