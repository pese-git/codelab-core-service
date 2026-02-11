"""Approval schemas."""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ApprovalType(str, Enum):
    """Approval type enum."""

    TOOL = "tool"
    PLAN = "plan"


class ApprovalStatus(str, Enum):
    """Approval status enum."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    TIMEOUT = "timeout"


class ApprovalRequest(BaseModel):
    """Approval request schema."""

    id: UUID = Field(..., description="Approval request UUID")
    type: ApprovalType = Field(..., description="Approval type")
    payload: dict[str, Any] = Field(..., description="Request payload")
    status: ApprovalStatus = Field(..., description="Approval status")
    timeout: int = Field(default=300, description="Timeout in seconds")
    created_at: datetime = Field(..., description="Creation timestamp")

    model_config = {"from_attributes": True, "json_schema_extra": {
        "example": {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "type": "tool",
            "payload": {
                "tool_name": "file_writer",
                "arguments": {"path": "/etc/passwd", "content": "..."}
            },
            "status": "pending",
            "timeout": 300,
            "created_at": "2026-02-11T07:00:00Z"
        }
    }}


class ApprovalResponse(BaseModel):
    """Approval response schema."""

    id: UUID = Field(..., description="Approval request UUID")
    type: ApprovalType = Field(..., description="Approval type")
    payload: dict[str, Any] = Field(..., description="Request payload")
    status: ApprovalStatus = Field(..., description="Approval status")
    created_at: datetime = Field(..., description="Creation timestamp")
    resolved_at: datetime | None = Field(default=None, description="Resolution timestamp")
    decision: str | None = Field(default=None, description="User decision/comment")

    model_config = {"from_attributes": True}


class ApprovalDecision(BaseModel):
    """Approval decision schema."""

    approved: bool = Field(..., description="Whether to approve or reject")
    decision: str | None = Field(default=None, description="Optional decision comment")

    model_config = {"json_schema_extra": {
        "example": {
            "approved": True,
            "decision": "Approved after review"
        }
    }}


class ApprovalListResponse(BaseModel):
    """Approval list response schema."""

    approvals: list[ApprovalResponse] = Field(..., description="List of approval requests")
    total: int = Field(..., description="Total number of approval requests")
