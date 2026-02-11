"""Chat schemas."""

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class MessageRole(str, Enum):
    """Message role enum."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class MessageRequest(BaseModel):
    """Message request schema."""

    content: str = Field(..., min_length=1, description="Message content")
    target_agent: str | None = Field(
        default=None, description="Target agent name for direct mode (optional)"
    )

    model_config = {"json_schema_extra": {
        "example": {
            "content": "Fix the bug in auth.py",
            "target_agent": "coder"
        }
    }}


class MessageResponse(BaseModel):
    """Message response schema."""

    id: UUID = Field(..., description="Message UUID")
    role: MessageRole = Field(..., description="Message role")
    content: str = Field(..., description="Message content")
    agent_id: UUID | None = Field(default=None, description="Agent UUID (if from agent)")
    timestamp: datetime = Field(..., description="Message timestamp")

    model_config = {"from_attributes": True}


class ChatSessionResponse(BaseModel):
    """Chat session response schema."""

    id: UUID = Field(..., description="Session UUID")
    created_at: datetime = Field(..., description="Creation timestamp")
    message_count: int = Field(default=0, description="Number of messages in session")

    model_config = {"from_attributes": True}


class ChatSessionListResponse(BaseModel):
    """Chat session list response schema."""

    sessions: list[ChatSessionResponse] = Field(..., description="List of sessions")
    total: int = Field(..., description="Total number of sessions")


class MessageListResponse(BaseModel):
    """Message list response schema."""

    messages: list[MessageResponse] = Field(..., description="List of messages")
    total: int = Field(..., description="Total number of messages")
    session_id: UUID = Field(..., description="Session UUID")
