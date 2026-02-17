"""Project schemas."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    """Create project schema."""

    name: str = Field(..., min_length=1, max_length=255, description="Project name")
    workspace_path: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Local path to user's workspace directory"
    )


class ProjectUpdate(BaseModel):
    """Update project schema."""

    name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Project name"
    )
    workspace_path: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Local path to user's workspace directory"
    )


class ProjectResponse(BaseModel):
    """Project response schema."""

    id: UUID = Field(..., description="Project UUID")
    user_id: UUID = Field(..., description="User UUID")
    name: str = Field(..., description="Project name")
    workspace_path: Optional[str] = Field(
        default=None,
        description="Local path to user's workspace directory"
    )
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    model_config = {"from_attributes": True}


class ProjectListResponse(BaseModel):
    """Project list response schema."""

    projects: list[ProjectResponse] = Field(..., description="List of projects")
    total: int = Field(..., description="Total number of projects")
