"""Error schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """Error response schema."""

    detail: str = Field(..., description="Error detail message")
    error_code: str = Field(..., description="Error code")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Error timestamp")
    metadata: dict[str, Any] | None = Field(default=None, description="Additional error metadata")

    model_config = {"json_schema_extra": {
        "example": {
            "detail": "User not authorized to access this resource",
            "error_code": "UNAUTHORIZED",
            "timestamp": "2026-02-11T07:00:00Z",
            "metadata": None
        }
    }}


class LLMProviderError(ErrorResponse):
    """LLM Provider specific error."""

    error_code: str = Field(default="LLM_PROVIDER_ERROR", description="Error code")
    
    model_config = {"json_schema_extra": {
        "example": {
            "detail": "Failed to connect to LLM provider",
            "error_code": "LLM_PROVIDER_ERROR",
            "timestamp": "2026-02-16T15:00:00Z",
            "metadata": {
                "provider": "openrouter",
                "model": "openai/gpt-4.1",
                "error_type": "timeout"
            }
        }
    }}
