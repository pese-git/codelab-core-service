"""SSE Event schemas."""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class SSEEventType(str, Enum):
    """SSE event type enum."""

    DIRECT_AGENT_CALL = "direct_agent_call"
    AGENT_STATUS_CHANGED = "agent_status_changed"
    TASK_PLAN_CREATED = "task_plan_created"
    TASK_STARTED = "task_started"
    TASK_PROGRESS = "task_progress"
    TASK_COMPLETED = "task_completed"
    TOOL_REQUEST = "tool_request"
    PLAN_REQUEST = "plan_request"
    CONTEXT_RETRIEVED = "context_retrieved"
    APPROVAL_REQUIRED = "approval_required"


class SSEEvent(BaseModel):
    """SSE event schema."""

    event_type: SSEEventType = Field(..., description="Event type")
    payload: dict[str, Any] = Field(..., description="Event payload")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Event timestamp")
    session_id: UUID | None = Field(default=None, description="Session UUID (if applicable)")

    model_config = {"json_schema_extra": {
        "example": {
            "event_type": "task_started",
            "payload": {
                "task_id": "task_1",
                "agent_name": "coder",
                "description": "Fix bug in auth.py"
            },
            "timestamp": "2026-02-11T07:00:00Z",
            "session_id": "550e8400-e29b-41d4-a716-446655440000"
        }
    }}

    def to_sse_format(self) -> str:
        """Convert to SSE format."""
        return f"event: {self.event_type.value}\ndata: {self.model_dump_json()}\n\n"
