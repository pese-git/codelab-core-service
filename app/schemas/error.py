"""Error schemas."""

from datetime import datetime

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """Error response schema."""

    detail: str = Field(..., description="Error detail message")
    error_code: str = Field(..., description="Error code")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Error timestamp")

    model_config = {"json_schema_extra": {
        "example": {
            "detail": "User not authorized to access this resource",
            "error_code": "UNAUTHORIZED",
            "timestamp": "2026-02-11T07:00:00Z"
        }
    }}
