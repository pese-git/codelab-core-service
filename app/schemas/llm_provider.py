"""LLM Provider schemas."""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


# Available LLM provider types
class LLMProviderType(str, Enum):
    """Supported LLM provider types."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    COHERE = "cohere"
    TOGETHER = "together"
    OLLAMA = "ollama"
    AZURE_OPENAI = "azure_openai"
    OPENROUTER = "openrouter"


class LLMProviderTypeInfo(BaseModel):
    """Information about an LLM provider type."""

    type: LLMProviderType = Field(..., description="Provider type identifier")
    display_name: str = Field(..., description="Human-readable provider name")
    description: str = Field(..., description="Provider description")
    requires_api_key: bool = Field(default=True, description="Whether API key is required")
    requires_base_url: bool = Field(default=False, description="Whether base URL is required")

    model_config = {"json_schema_extra": {
        "example": {
            "type": "openai",
            "display_name": "OpenAI",
            "description": "OpenAI API with GPT-4 and GPT-3.5 models",
            "requires_api_key": True,
            "requires_base_url": False
        }
    }}


class LLMProviderCreate(BaseModel):
    """Schema for creating a new LLM provider."""

    provider_type: LLMProviderType = Field(..., description="Type of LLM provider")
    display_name: str = Field(..., min_length=1, max_length=255, description="User-friendly name for the provider")
    api_key: str = Field(..., description="API key for the provider (sent separately to LiteLLM)")
    config: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional provider configuration (e.g., model name, base URL, etc.)"
    )

    model_config = {"json_schema_extra": {
        "example": {
            "provider_type": "openai",
            "display_name": "My OpenAI Account",
            "api_key": "sk-...",
            "config": {"model": "gpt-4o", "max_tokens": 2048}
        }
    }}


class LLMProviderUpdate(BaseModel):
    """Schema for updating an LLM provider."""

    display_name: str = Field(None, min_length=1, max_length=255, description="Updated provider name")
    config: dict[str, Any] = Field(None, description="Updated provider configuration")

    model_config = {"json_schema_extra": {
        "example": {
            "display_name": "My OpenAI Account - Updated",
            "config": {"model": "gpt-4-turbo", "max_tokens": 4096}
        }
    }}


class LLMProviderResponse(BaseModel):
    """Schema for returning LLM provider data."""

    id: UUID = Field(..., description="Provider UUID")
    user_id: UUID = Field(..., description="User ID who owns this provider")
    provider_type: LLMProviderType = Field(..., description="Provider type")
    display_name: str = Field(..., description="Display name for the provider")
    litellm_model_name: str = Field(..., description="Unique model name registered in LiteLLM")
    config: dict[str, Any] | None = Field(None, description="Provider configuration (without API keys)")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    last_used_at: datetime | None = Field(None, description="Last usage timestamp")
    use_count: int = Field(..., description="Number of times this provider was used")

    model_config = {"from_attributes": True}


class LLMProviderListResponse(BaseModel):
    """Schema for returning a list of LLM providers with pagination."""

    providers: list[LLMProviderResponse] = Field(..., description="List of LLM providers")
    total: int = Field(..., description="Total number of providers for this user")
    page: int = Field(..., ge=1, description="Current page number")
    page_size: int = Field(..., ge=1, le=100, description="Items per page")
    total_pages: int = Field(..., description="Total number of pages")

    model_config = {"json_schema_extra": {
        "example": {
            "providers": [
                {
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "user_id": "123e4567-e89b-12d3-a456-426614174000",
                    "provider_type": "openai",
                    "display_name": "My OpenAI",
                    "litellm_model_name": "user550e8400_openai_abc123",
                    "config": {"model": "gpt-4o"},
                    "created_at": "2026-03-09T08:00:00Z",
                    "updated_at": "2026-03-09T08:00:00Z",
                    "last_used_at": "2026-03-09T08:10:00Z",
                    "use_count": 5
                }
            ],
            "total": 1,
            "page": 1,
            "page_size": 10,
            "total_pages": 1
        }
    }}


class LLMProviderTestRequest(BaseModel):
    """Schema for testing LLM provider connection."""

    test_prompt: str = Field(
        default="Hello, how are you?",
        description="Test prompt to send to the LLM provider"
    )
    max_tokens: int = Field(
        default=100,
        ge=1,
        le=4096,
        description="Max tokens for test response"
    )

    model_config = {"json_schema_extra": {
        "example": {
            "test_prompt": "Write a haiku about coding",
            "max_tokens": 150
        }
    }}


class LLMProviderTestResponse(BaseModel):
    """Schema for LLM provider test result."""

    success: bool = Field(..., description="Whether the test was successful")
    message: str = Field(..., description="Test result message")
    response: str | None = Field(None, description="LLM response if successful")
    error: str | None = Field(None, description="Error message if test failed")
    latency_ms: float | None = Field(None, description="Response latency in milliseconds")

    model_config = {"json_schema_extra": {
        "example": {
            "success": True,
            "message": "Provider is working correctly",
            "response": "I am functioning well, thank you for asking!",
            "error": None,
            "latency_ms": 324.5
        }
    }}


class LLMProviderAuditLogEntry(BaseModel):
    """Schema for audit log entry of LLM provider operations."""

    id: UUID = Field(..., description="Audit log entry UUID")
    user_id: UUID = Field(..., description="User ID who performed the action")
    provider_id: UUID | None = Field(None, description="Provider ID (if applicable)")
    action: str = Field(
        ...,
        description="Action type: create, update, delete, test, use, provider_reassigned"
    )
    old_values: dict[str, Any] | None = Field(None, description="Old values before update")
    new_values: dict[str, Any] | None = Field(None, description="New values after update")
    success: bool = Field(..., description="Whether the action was successful")
    error_message: str | None = Field(None, description="Error message if action failed")
    ip_address: str | None = Field(None, description="IP address of the requester")
    user_agent: str | None = Field(None, description="User agent of the requester")
    created_at: datetime = Field(..., description="Timestamp of the action")

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440001",
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "provider_id": "550e8400-e29b-41d4-a716-446655440000",
                "action": "create",
                "old_values": None,
                "new_values": {
                    "display_name": "My OpenAI",
                    "provider_type": "openai"
                },
                "success": True,
                "error_message": None,
                "ip_address": "192.168.1.1",
                "user_agent": "Mozilla/5.0...",
                "created_at": "2026-03-09T08:00:00Z"
            }
        }
    }


class LLMProviderAuditLogListResponse(BaseModel):
    """Schema for returning a list of audit log entries."""

    entries: list[LLMProviderAuditLogEntry] = Field(..., description="Audit log entries")
    total: int = Field(..., description="Total number of entries")
    page: int = Field(..., ge=1, description="Current page number")
    page_size: int = Field(..., ge=1, le=100, description="Items per page")
    total_pages: int = Field(..., description="Total number of pages")


def get_provider_types() -> list[LLMProviderTypeInfo]:
    """Get list of all available provider types."""
    return [
        LLMProviderTypeInfo(
            type=LLMProviderType.OPENAI,
            display_name="OpenAI",
            description="OpenAI API with GPT-4 and GPT-3.5 models",
            requires_api_key=True,
            requires_base_url=False,
        ),
        LLMProviderTypeInfo(
            type=LLMProviderType.ANTHROPIC,
            display_name="Anthropic",
            description="Anthropic Claude models",
            requires_api_key=True,
            requires_base_url=False,
        ),
        LLMProviderTypeInfo(
            type=LLMProviderType.GOOGLE,
            display_name="Google",
            description="Google Gemini and PaLM models",
            requires_api_key=True,
            requires_base_url=False,
        ),
        LLMProviderTypeInfo(
            type=LLMProviderType.COHERE,
            display_name="Cohere",
            description="Cohere API models",
            requires_api_key=True,
            requires_base_url=False,
        ),
        LLMProviderTypeInfo(
            type=LLMProviderType.TOGETHER,
            display_name="Together AI",
            description="Together AI inference platform",
            requires_api_key=True,
            requires_base_url=False,
        ),
        LLMProviderTypeInfo(
            type=LLMProviderType.OLLAMA,
            display_name="Ollama",
            description="Local Ollama instance",
            requires_api_key=False,
            requires_base_url=True,
        ),
        LLMProviderTypeInfo(
            type=LLMProviderType.AZURE_OPENAI,
            display_name="Azure OpenAI",
            description="Azure OpenAI Service",
            requires_api_key=True,
            requires_base_url=True,
        ),
    ]
