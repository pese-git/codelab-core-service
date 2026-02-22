"""Streaming Event schemas."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class StreamEventType(str, Enum):
    """Stream event type enum."""

    MESSAGE_CREATED = "message_created"
    AGENT_SWITCHED = "agent_switched"
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
    APPROVAL_RESOLVED = "approval_resolved"
    APPROVAL_TIMEOUT = "approval_timeout"
    APPROVAL_TIMEOUT_WARNING = "approval_timeout_warning"
    HEARTBEAT = "heartbeat"
    ERROR = "error"


class StreamEvent(BaseModel):
    """Stream event schema for JSON Lines (NDJSON) format."""

    event_type: StreamEventType = Field(..., description="Event type")
    payload: dict[str, Any] = Field(..., description="Event payload")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Event timestamp"
    )
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

    def to_ndjson(self) -> str:
        """
        Convert to NDJSON (Newline Delimited JSON) format.
        
        Returns:
            JSON string with newline terminator
        """
        return self.model_dump_json() + "\n"

    def to_sse_format(self) -> str:
        """
        Convert to SSE (Server-Sent Events) format.
        
        Returns SSE format with event type and JSON data.
        Format: event: <event_type>\ndata: <json>\n\n
        
        Returns:
            String in SSE format
        """
        event_type = self.event_type.value if hasattr(self.event_type, 'value') else str(self.event_type)
        json_data = self.model_dump_json()
        return f"event: {event_type}\ndata: {json_data}\n\n"


# Backward compatibility aliases
SSEEventType = StreamEventType
SSEEvent = StreamEvent
