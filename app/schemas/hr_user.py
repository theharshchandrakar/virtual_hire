"""Pydantic request/response schemas for the HR User API.

VHIRE-12 (E3).
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.models.enums import HRUserRole, HRUserStatus


class HRUserInvite(BaseModel):
    """Request body for `POST /organizations/{organization_id}/hr-users`."""

    email: EmailStr
    full_name: str = Field(min_length=1, max_length=255)
    role: HRUserRole


class HRUserRead(BaseModel):
    """Response body for HR user read/lifecycle endpoints."""

    id: uuid.UUID
    organization_id: uuid.UUID
    email: str
    full_name: str
    role: HRUserRole
    status: HRUserStatus
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
