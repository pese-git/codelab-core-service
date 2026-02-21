"""Tool Definitions and Signatures for Agent Tools System"""

from enum import Enum
from typing import Optional, List
from dataclasses import dataclass


class ToolName(str, Enum):
    """Available tool names"""
    READ_FILE = "read_file"
    WRITE_FILE = "write_file"
    EXECUTE_COMMAND = "execute_command"
    LIST_DIRECTORY = "list_directory"


@dataclass
class ToolDefinition:
    """Base tool definition with metadata"""
    name: ToolName
    description: str
    parameters: dict
    requires_approval: bool


# Tool: read_file
# Read file contents from workspace (safe operation)
TOOL_READ_FILE = ToolDefinition(
    name=ToolName.READ_FILE,
    description="Read file contents from workspace",
    parameters={
        "path": {
            "type": "string",
            "description": "Path to file (relative to workspace)"
        }
    },
    requires_approval=False
)

# Tool: write_file
# Write or append content to file (requires approval due to modification)
TOOL_WRITE_FILE = ToolDefinition(
    name=ToolName.WRITE_FILE,
    description="Write or append content to file",
    parameters={
        "path": {
            "type": "string",
            "description": "Path to file (relative to workspace)"
        },
        "content": {
            "type": "string",
            "description": "Content to write or append"
        },
        "mode": {
            "type": "string",
            "enum": ["write", "append"],
            "default": "write",
            "description": "Write mode (overwrite or append)"
        }
    },
    requires_approval=True  # HIGH risk - modifies files
)

# Tool: execute_command
# Execute shell commands (risk-dependent approval)
TOOL_EXECUTE_COMMAND = ToolDefinition(
    name=ToolName.EXECUTE_COMMAND,
    description="Execute shell command in workspace",
    parameters={
        "command": {
            "type": "string",
            "description": "Command to execute"
        },
        "args": {
            "type": "array",
            "items": {"type": "string"},
            "default": [],
            "description": "Command arguments"
        },
        "timeout": {
            "type": "integer",
            "default": 30,
            "maximum": 300,
            "description": "Execution timeout in seconds"
        }
    },
    requires_approval=True  # Risk level dependent
)

# Tool: list_directory
# List files in directory (safe operation)
TOOL_LIST_DIRECTORY = ToolDefinition(
    name=ToolName.LIST_DIRECTORY,
    description="List files in directory (with optional recursion and pattern matching)",
    parameters={
        "path": {
            "type": "string",
            "description": "Directory path (relative to workspace)"
        },
        "recursive": {
            "type": "boolean",
            "default": False,
            "description": "List recursively"
        },
        "pattern": {
            "type": "string",
            "default": "*",
            "description": "File name pattern (glob)"
        }
    },
    requires_approval=False
)

# Registry of all available tools
AVAILABLE_TOOLS = {
    ToolName.READ_FILE: TOOL_READ_FILE,
    ToolName.WRITE_FILE: TOOL_WRITE_FILE,
    ToolName.EXECUTE_COMMAND: TOOL_EXECUTE_COMMAND,
    ToolName.LIST_DIRECTORY: TOOL_LIST_DIRECTORY,
}
