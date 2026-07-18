"""Pydantic request/response schemas for the Job Requisition API.

VHIRE-24 (E3).
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import JobRequisitionStatus


class JobRequisitionCreate(BaseModel):
    """Request body for `POST /requisitions`."""

    title: str = Field(min_length=1, max_length=255)
    department: str | None = None
    owner_hr_user_id: uuid.UUID
    scorecard_template: dict = Field(
        description="Competency fields interviewers rate against, per A11."
    )


class JobRequisitionStatusUpdate(BaseModel):
    """Request body for `PATCH /requisitions/{id}/status`."""

    status: JobRequisitionStatus


class JobRequisitionRead(BaseModel):
    """Response body for job requisition read/lifecycle endpoints."""

    id: uuid.UUID
    organization_id: uuid.UUID
    title: str
    department: str | None
    owner_hr_user_id: uuid.UUID
    status: JobRequisitionStatus
    scorecard_template: dict
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
