"""Pydantic schemas."""

from app.schemas.agent import AgentConfig, AgentCreate, AgentResponse, AgentStatus, AgentUpdate
from app.schemas.approval import ApprovalRequest, ApprovalResponse, ApprovalStatus, ApprovalType
from app.schemas.chat import ChatSessionResponse, MessageRequest, MessageResponse, MessageRole
from app.schemas.error import ErrorResponse
from app.schemas.event import StreamEvent, StreamEventType, SSEEvent, SSEEventType
from app.schemas.task import TaskPlan, TaskStatus

__all__ = [
    "AgentConfig",
    "AgentCreate",
    "AgentResponse",
    "AgentStatus",
    "AgentUpdate",
    "ApprovalRequest",
    "ApprovalResponse",
    "ApprovalStatus",
    "ApprovalType",
    "ChatSessionResponse",
    "MessageRequest",
    "MessageResponse",
    "MessageRole",
    "ErrorResponse",
    "StreamEvent",
    "StreamEventType",
    "SSEEvent",  # Backward compatibility
    "SSEEventType",  # Backward compatibility
    "TaskPlan",
    "TaskStatus",
]
