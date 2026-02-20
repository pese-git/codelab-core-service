"""Task plan schemas for API."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class PlanCreateRequest(BaseModel):
    """Request to create new plan."""

    description: str = Field(..., min_length=1, description="Task description")
    session_id: UUID | None = Field(None, description="Optional chat session ID")


class TaskResponse(BaseModel):
    """Task response schema."""

    id: UUID = Field(..., description="Task UUID")
    task_id: str = Field(..., description="Logical task ID (task_0, task_1, ...)")
    title: str | None = Field(None, description="Task title (from description if available)")
    description: str = Field(..., description="Task description")
    agent_id: UUID = Field(..., description="Agent UUID executing this task")
    agent_name: str = Field(..., description="Agent name")
    dependencies: list[str] = Field(default_factory=list, description="List of dependency task IDs")
    estimated_cost: float = Field(..., description="Estimated cost in USD")
    estimated_duration: float = Field(..., description="Estimated duration in seconds")
    risk_level: str = Field(..., description="Risk level: LOW, MEDIUM, HIGH")
    status: str = Field(..., description="Task status: pending, executing, completed, failed, aborted")
    result: dict | None = Field(None, description="Task execution result")
    error: str | None = Field(None, description="Error message if failed")
    created_at: datetime = Field(..., description="Creation timestamp")

    model_config = {"from_attributes": True}


class PlanResponse(BaseModel):
    """Plan response schema."""

    id: UUID = Field(..., description="Plan UUID")
    title: str | None = Field(None, description="Plan title")
    description: str = Field(..., description="Plan description")
    status: str = Field(..., description="Plan status")
    total_estimated_cost: float = Field(..., description="Total estimated cost")
    total_estimated_duration: float = Field(..., description="Total estimated duration in seconds")
    requires_approval: bool = Field(..., description="Whether plan requires approval")
    task_count: int = Field(..., description="Number of tasks in plan")
    created_at: datetime = Field(..., description="Creation timestamp")

    model_config = {"from_attributes": True}


class PlanDetailResponse(PlanResponse):
    """Detailed plan with tasks."""

    tasks: list[TaskResponse] = Field(default_factory=list, description="List of tasks")


class PlanExecutionResponse(BaseModel):
    """Plan execution response."""

    plan_id: UUID = Field(..., description="Plan UUID")
    status: str = Field(..., description="Execution status")
    message: str = Field(..., description="Execution status message")
    execution_time_ms: int | None = Field(None, description="Execution time in milliseconds")
    approval_id: UUID | None = Field(None, description="Approval request UUID if approval required")


class PlanListResponse(BaseModel):
    """List of plans with pagination."""

    plans: list[PlanResponse] = Field(default_factory=list, description="List of plans")
    total: int = Field(..., description="Total number of plans")
    offset: int = Field(..., description="Offset for pagination")
    limit: int = Field(..., description="Limit for pagination")
