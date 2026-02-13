"""Agent schemas."""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class AgentStatus(str, Enum):
    """Agent status enum."""

    READY = "ready"
    BUSY = "busy"
    ERROR = "error"


class AgentConfig(BaseModel):
    """Agent configuration schema."""

    name: str = Field(..., min_length=1, max_length=100, description="Agent name")
    system_prompt: str = Field(..., min_length=1, description="System prompt for the agent")
    model: str = Field(default="openrouter/openai/gpt-4.1", description="LLM model to use")
    tools: list[str] = Field(default_factory=list, description="List of available tools")
    concurrency_limit: int = Field(default=3, ge=1, le=10, description="Max concurrent tasks")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Model temperature")
    max_tokens: int = Field(default=4096, ge=1, le=128000, description="Max tokens per response")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    model_config = {"json_schema_extra": {
        "example": {
            "name": "coder",
            "system_prompt": "You are an expert Python developer...",
            "model": "openrouter/openai/gpt-4.1",
            "tools": ["code_executor", "file_reader"],
            "concurrency_limit": 3,
            "temperature": 0.7,
            "max_tokens": 4096,
            "metadata": {"specialty": "backend"}
        }
    }}


class AgentResponse(BaseModel):
    """Agent response schema."""

    id: UUID = Field(..., description="Agent UUID")
    name: str = Field(..., description="Agent name")
    status: AgentStatus = Field(..., description="Current agent status")
    created_at: datetime = Field(..., description="Creation timestamp")
    config: AgentConfig = Field(..., description="Agent configuration")

    model_config = {"from_attributes": True}


class AgentUpdate(BaseModel):
    """Agent update schema."""

    config: AgentConfig = Field(..., description="Updated agent configuration")


class AgentListResponse(BaseModel):
    """Agent list response schema."""

    agents: list[AgentResponse] = Field(..., description="List of agents")
    total: int = Field(..., description="Total number of agents")
