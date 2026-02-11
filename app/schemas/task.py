"""Task schemas."""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    """Task status enum."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskNode(BaseModel):
    """Task node in execution plan."""

    task_id: str = Field(..., description="Unique task ID")
    agent_name: str = Field(..., description="Agent to execute the task")
    description: str = Field(..., description="Task description")
    dependencies: list[str] = Field(default_factory=list, description="Task IDs this depends on")
    estimated_duration: int = Field(..., description="Estimated duration in seconds")
    estimated_cost: float = Field(..., description="Estimated cost in USD")


class TaskPlan(BaseModel):
    """Task execution plan schema."""

    plan_id: str = Field(..., description="Unique plan ID")
    tasks: list[TaskNode] = Field(..., description="List of tasks in the plan")
    estimated_cost: float = Field(..., description="Total estimated cost in USD")
    estimated_duration: int = Field(..., description="Total estimated duration in seconds")
    parallel_execution: bool = Field(
        default=True, description="Whether tasks can be executed in parallel"
    )

    model_config = {"json_schema_extra": {
        "example": {
            "plan_id": "plan_123",
            "tasks": [
                {
                    "task_id": "task_1",
                    "agent_name": "researcher",
                    "description": "Research the bug",
                    "dependencies": [],
                    "estimated_duration": 30,
                    "estimated_cost": 0.05
                },
                {
                    "task_id": "task_2",
                    "agent_name": "coder",
                    "description": "Fix the bug",
                    "dependencies": ["task_1"],
                    "estimated_duration": 60,
                    "estimated_cost": 0.10
                }
            ],
            "estimated_cost": 0.15,
            "estimated_duration": 90,
            "parallel_execution": False
        }
    }}


class TaskResponse(BaseModel):
    """Task response schema."""

    id: UUID = Field(..., description="Task UUID")
    session_id: UUID = Field(..., description="Session UUID")
    agent_id: UUID = Field(..., description="Agent UUID")
    status: TaskStatus = Field(..., description="Task status")
    result: dict[str, Any] | None = Field(default=None, description="Task result")
    created_at: datetime = Field(..., description="Creation timestamp")
    started_at: datetime | None = Field(default=None, description="Start timestamp")
    completed_at: datetime | None = Field(default=None, description="Completion timestamp")

    model_config = {"from_attributes": True}
