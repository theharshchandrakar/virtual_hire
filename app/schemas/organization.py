"""Pydantic request/response schemas for the Organization API.

VHIRE-12 (E3).
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import OrganizationStatus


class OrganizationCreate(BaseModel):
    """Request body for `POST /organizations`."""

    name: str = Field(min_length=1, max_length=255)


class OrganizationRead(BaseModel):
    """Response body for organization read endpoints."""

    id: uuid.UUID
    name: str
    status: OrganizationStatus
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
