"""Pydantic schemas for Tool execution requests and responses"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Any, Literal, Union
from uuid import UUID
from datetime import datetime


def parse_tool_response(
    tool_name: str, 
    result_dict: Optional[dict]
) -> Optional[Union[ToolReadFileResponse, ToolWriteFileResponse, ToolExecuteCommandResponse, ToolListDirectoryResponse]]:
    """Convert raw result dict to proper ToolResponse type based on tool_name.
    
    Args:
        tool_name: Name of the tool
        result_dict: Raw result dict from client
        
    Returns:
        Validated ToolResponse object, or None if validation fails
    """
    if not result_dict:
        return None
    
    try:
        if tool_name == "read_file":
            return ToolReadFileResponse(**result_dict)
        elif tool_name == "write_file":
            return ToolWriteFileResponse(**result_dict)
        elif tool_name == "execute_command":
            return ToolExecuteCommandResponse(**result_dict)
        elif tool_name == "list_directory":
            return ToolListDirectoryResponse(**result_dict)
    except Exception:
        # If validation fails, return None (lenient validation)
        pass
    
    return None


# ============================================================================
# READ_FILE Schemas
# ============================================================================

class ToolReadFileRequest(BaseModel):
    """Request to read file"""
    path: str = Field(..., description="File path (relative to workspace)")


class ToolReadFileResponse(BaseModel):
    """Response from read_file tool"""
    success: bool = Field(..., description="Whether operation succeeded")
    content: Optional[str] = Field(None, description="File contents")
    encoding: str = Field(default="utf-8", description="File encoding")
    size: int = Field(default=0, description="File size in bytes")
    error: Optional[str] = Field(None, description="Error message if failed")


# ============================================================================
# WRITE_FILE Schemas
# ============================================================================

class ToolWriteFileRequest(BaseModel):
    """Request to write file"""
    path: str = Field(..., description="File path (relative to workspace)")
    content: str = Field(..., description="Content to write")
    mode: Literal["write", "append"] = Field(
        default="write",
        description="Write mode: overwrite or append"
    )


class ToolWriteFileResponse(BaseModel):
    """Response from write_file tool"""
    success: bool = Field(..., description="Whether operation succeeded")
    path: str = Field(..., description="Path where file was written")
    size: int = Field(default=0, description="Bytes written")
    error: Optional[str] = Field(None, description="Error message if failed")


# ============================================================================
# EXECUTE_COMMAND Schemas
# ============================================================================

class ToolExecuteCommandRequest(BaseModel):
    """Request to execute command"""
    command: str = Field(..., description="Command to execute")
    args: List[str] = Field(
        default_factory=list,
        description="Command arguments"
    )
    timeout: int = Field(
        default=30,
        ge=1,
        le=300,
        description="Execution timeout in seconds (1-300)"
    )


class ToolExecuteCommandResponse(BaseModel):
    """Response from execute_command tool"""
    success: bool = Field(..., description="Whether command succeeded")
    stdout: Optional[str] = Field(None, description="Standard output")
    stderr: Optional[str] = Field(None, description="Standard error")
    exit_code: Optional[int] = Field(None, description="Process exit code")
    execution_time: float = Field(default=0.0, description="Execution time in seconds")
    error: Optional[str] = Field(None, description="Error message if failed")


# ============================================================================
# LIST_DIRECTORY Schemas
# ============================================================================

class FileInfo(BaseModel):
    """Information about a file or directory"""
    name: str = Field(..., description="File/directory name")
    path: str = Field(..., description="Full path (relative to workspace)")
    type: Literal["file", "directory"] = Field(..., description="File or directory")
    size: int = Field(default=0, description="Size in bytes")
    modified: str = Field(..., description="Last modified timestamp (ISO 8601)")


class ToolListDirectoryRequest(BaseModel):
    """Request to list directory"""
    path: str = Field(..., description="Directory path (relative to workspace)")
    recursive: bool = Field(default=False, description="List recursively")
    pattern: str = Field(default="*", description="File name pattern (glob)")


class ToolListDirectoryResponse(BaseModel):
    """Response from list_directory tool"""
    success: bool = Field(..., description="Whether operation succeeded")
    files: List[FileInfo] = Field(default_factory=list, description="Listed files")
    total_count: int = Field(default=0, description="Total number of items")
    error: Optional[str] = Field(None, description="Error message if failed")


# ============================================================================
# UNION TYPES for polymorphic handling
# ============================================================================

ToolRequest = Union[
    ToolReadFileRequest,
    ToolWriteFileRequest,
    ToolExecuteCommandRequest,
    ToolListDirectoryRequest
]

ToolResponse = Union[
    ToolReadFileResponse,
    ToolWriteFileResponse,
    ToolExecuteCommandResponse,
    ToolListDirectoryResponse
]


# ============================================================================
# EXECUTION REQUEST/RESPONSE (Full Wrapper)
# ============================================================================

class ToolExecutionRequest(BaseModel):
    """Full tool execution request wrapper"""
    tool_name: str = Field(..., description="Name of tool to execute")
    tool_params: dict = Field(..., description="Tool-specific parameters")
    session_id: Optional[UUID] = Field(None, description="Chat session ID")
    chat_session_id: Optional[UUID] = Field(None, description="Chat session ID (alias)")

    class Config:
        json_schema_extra = {
            "example": {
                "tool_name": "read_file",
                "tool_params": {"path": "src/main.py"},
                "session_id": "550e8400-e29b-41d4-a716-446655440000"
            }
        }


class ToolExecutionResponse(BaseModel):
    """Full tool execution response wrapper"""
    tool_id: str = Field(..., description="Unique tool execution ID")
    tool_name: str = Field(..., description="Name of executed tool")
    status: Literal[
        "pending", "approved", "rejected", "completed", "failed"
    ] = Field(..., description="Execution status")
    approval_id: Optional[UUID] = Field(None, description="Approval request ID if needed")
    requires_approval: bool = Field(default=False, description="Whether approval was required")
    result: Optional[ToolResponse] = Field(None, description="Tool-specific result")
    error: Optional[str] = Field(None, description="Error message if failed")
    created_at: str = Field(..., description="Creation timestamp (ISO 8601)")
    completed_at: Optional[str] = Field(None, description="Completion timestamp (ISO 8601)")
    
    @field_validator('result', mode='before')
    @classmethod
    def parse_result(cls, v: Any, info) -> Optional[ToolResponse]:
        """Convert raw dict from DB to proper ToolResponse type based on tool_name.
        
        Args:
            v: Raw value (could be dict from DB or already a ToolResponse object)
            info: Field info with context
            
        Returns:
            Validated ToolResponse object, or None if it's not a dict or validation fails
        """
        # If already a model instance or None, pass through
        if v is None or isinstance(v, (ToolReadFileResponse, ToolWriteFileResponse, 
                                       ToolExecuteCommandResponse, ToolListDirectoryResponse)):
            return v
        
        # If not a dict, can't parse
        if not isinstance(v, dict):
            return None
        
        # Get tool_name from other field data
        tool_name = info.data.get('tool_name')
        if not tool_name:
            return None
        
        # Try to parse and validate
        return parse_tool_response(tool_name, v)

    class Config:
        json_schema_extra = {
            "example": {
                "tool_id": "12345678-1234-1234-1234-123456789012",
                "tool_name": "read_file",
                "status": "completed",
                "requires_approval": False,
                "result": {
                    "success": True,
                    "content": "file contents...",
                    "encoding": "utf-8",
                    "size": 1024
                },
                "created_at": "2026-02-21T05:51:43.419Z",
                "completed_at": "2026-02-21T05:51:44.100Z"
            }
        }


class ToolExecutionResultRequest(BaseModel):
    """Client tool execution result payload."""
    status: Literal["completed", "failed"] = Field(
        ..., description="Final execution status"
    )
    result: Optional[dict] = Field(
        None, description="Tool-specific result payload"
    )
    error: Optional[str] = Field(
        None, description="Error message if execution failed"
    )
    completed_at: Optional[datetime] = Field(
        None, description="Completion timestamp (ISO 8601)"
    )
    session_id: Optional[UUID] = Field(  # ← Добавить
        None, description="Chat session ID for tracing"
    )


# Alias for backward compatibility
ToolResultRequest = ToolExecutionResultRequest
