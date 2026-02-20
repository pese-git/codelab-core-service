# Agent Tools System - Детальный план всех 6 фаз

## 📋 Содержание
1. [Phase 1: Tool Signatures & Definitions](#phase-1-tool-signatures--definitions)
2. [Phase 2: Security & Validation](#phase-2-security--validation)
3. [Phase 3: Risk Assessment](#phase-3-risk-assessment)
4. [Phase 4: Approval Manager Integration](#phase-4-approval-manager-integration)
5. [Phase 5: Tool Executor & REST API](#phase-5-tool-executor--rest-api)
6. [Phase 6: Testing](#phase-6-testing)

---

## Phase 1: Tool Signatures & Definitions

### 📌 Цель
Определить структуру всех 4 tools с Pydantic схемами и Python типами.

### 🎯 Tasks (8.1.1 - 8.1.4)

#### 8.1.1 Tool Definitions
**Файл**: `app/core/tools/definitions.py`

```python
from enum import Enum
from typing import Optional, List
from dataclasses import dataclass

class ToolName(str, Enum):
    READ_FILE = "read_file"
    WRITE_FILE = "write_file"
    EXECUTE_COMMAND = "execute_command"
    LIST_DIRECTORY = "list_directory"

@dataclass
class ToolDefinition:
    """Base tool definition"""
    name: ToolName
    description: str
    parameters: dict
    requires_approval: bool
    
# Tool: read_file
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
TOOL_WRITE_FILE = ToolDefinition(
    name=ToolName.WRITE_FILE,
    description="Write or append content to file",
    parameters={
        "path": {"type": "string"},
        "content": {"type": "string"},
        "mode": {
            "type": "string",
            "enum": ["write", "append"],
            "default": "write"
        }
    },
    requires_approval=True  # HIGH risk, requires approval
)

# Tool: execute_command
TOOL_EXECUTE_COMMAND = ToolDefinition(
    name=ToolName.EXECUTE_COMMAND,
    description="Execute shell command",
    parameters={
        "command": {"type": "string"},
        "args": {
            "type": "array",
            "items": {"type": "string"},
            "default": []
        },
        "timeout": {
            "type": "integer",
            "default": 30,
            "maximum": 300
        }
    },
    requires_approval=True  # Risk level dependent
)

# Tool: list_directory
TOOL_LIST_DIRECTORY = ToolDefinition(
    name=ToolName.LIST_DIRECTORY,
    description="List files in directory",
    parameters={
        "path": {"type": "string"},
        "recursive": {
            "type": "boolean",
            "default": False
        },
        "pattern": {
            "type": "string",
            "default": "*"
        }
    },
    requires_approval=False
)

AVAILABLE_TOOLS = {
    ToolName.READ_FILE: TOOL_READ_FILE,
    ToolName.WRITE_FILE: TOOL_WRITE_FILE,
    ToolName.EXECUTE_COMMAND: TOOL_EXECUTE_COMMAND,
    ToolName.LIST_DIRECTORY: TOOL_LIST_DIRECTORY,
}
```

#### 8.1.2 Tool Schemas
**Файл**: `app/schemas/tool.py`

```python
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Any, Literal
from uuid import UUID

class ToolReadFileRequest(BaseModel):
    """Request to read file"""
    path: str = Field(..., description="File path")
    
class ToolReadFileResponse(BaseModel):
    """Response from read_file tool"""
    success: bool
    content: Optional[str] = None
    encoding: str = "utf-8"
    size: int = 0
    error: Optional[str] = None

class ToolWriteFileRequest(BaseModel):
    """Request to write file"""
    path: str = Field(..., description="File path")
    content: str = Field(..., description="Content to write")
    mode: Literal["write", "append"] = "write"

class ToolWriteFileResponse(BaseModel):
    """Response from write_file tool"""
    success: bool
    path: str
    size: int = 0
    error: Optional[str] = None

class ToolExecuteCommandRequest(BaseModel):
    """Request to execute command"""
    command: str = Field(..., description="Command to execute")
    args: List[str] = Field(default_factory=list)
    timeout: int = Field(default=30, le=300)

class ToolExecuteCommandResponse(BaseModel):
    """Response from execute_command tool"""
    success: bool
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    exit_code: Optional[int] = None
    execution_time: float = 0.0
    error: Optional[str] = None

class ToolListDirectoryRequest(BaseModel):
    """Request to list directory"""
    path: str = Field(..., description="Directory path")
    recursive: bool = False
    pattern: str = "*"

class FileInfo(BaseModel):
    """File information"""
    name: str
    path: str
    type: Literal["file", "directory"]
    size: int = 0
    modified: str  # ISO 8601

class ToolListDirectoryResponse(BaseModel):
    """Response from list_directory tool"""
    success: bool
    files: List[FileInfo] = Field(default_factory=list)
    total_count: int = 0
    error: Optional[str] = None

# Union type for all tool requests/responses
ToolRequest = (
    ToolReadFileRequest | 
    ToolWriteFileRequest | 
    ToolExecuteCommandRequest | 
    ToolListDirectoryRequest
)

ToolResponse = (
    ToolReadFileResponse |
    ToolWriteFileResponse |
    ToolExecuteCommandResponse |
    ToolListDirectoryResponse
)

class ToolExecutionRequest(BaseModel):
    """Full tool execution request"""
    tool_name: str
    tool_params: dict
    session_id: Optional[UUID] = None
    chat_session_id: Optional[UUID] = None

class ToolExecutionResponse(BaseModel):
    """Full tool execution response"""
    tool_id: str  # UUID-like string
    tool_name: str
    status: Literal["pending", "approved", "rejected", "completed", "failed"]
    approval_id: Optional[UUID] = None
    requires_approval: bool = False
    result: Optional[ToolResponse] = None
    error: Optional[str] = None
    created_at: str  # ISO 8601
    completed_at: Optional[str] = None
```

#### 8.1.3 Tool Executor Models (Optional DB logging)
**Файл**: `app/core/tools/models.py` (optional, если требуется логирование в БД)

```python
from sqlalchemy import Column, String, JSON, DateTime, Integer, UUID
from sqlalchemy.orm import declarative_base
from datetime import datetime
import uuid

Base = declarative_base()

class ToolExecution(Base):
    """Tool execution log (optional)"""
    __tablename__ = "tool_executions"
    
    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID, index=True)
    session_id = Column(UUID, index=True)
    tool_name = Column(String, index=True)
    tool_params = Column(JSON)  # Masked sensitive data
    result = Column(JSON)
    risk_level = Column(String)  # LOW, MEDIUM, HIGH
    required_approval = Column(String)
    approval_id = Column(UUID, nullable=True)
    status = Column(String)  # pending, approved, rejected, completed, failed
    error = Column(String, nullable=True)
    execution_time = Column(Integer)  # milliseconds
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    completed_at = Column(DateTime, nullable=True)
```

#### 8.1.4 Tool Initialization
**Файл**: `app/core/tools/__init__.py`

```python
from app.core.tools.definitions import (
    ToolName,
    AVAILABLE_TOOLS,
    TOOL_READ_FILE,
    TOOL_WRITE_FILE,
    TOOL_EXECUTE_COMMAND,
    TOOL_LIST_DIRECTORY,
)

__all__ = [
    "ToolName",
    "AVAILABLE_TOOLS",
    "TOOL_READ_FILE",
    "TOOL_WRITE_FILE",
    "TOOL_EXECUTE_COMMAND",
    "TOOL_LIST_DIRECTORY",
]
```

### 📊 Интеграция с существующим кодом

**`app/schemas/__init__.py`**: Добавить импорты из `tool.py`
```python
from app.schemas.tool import (
    ToolExecutionRequest,
    ToolExecutionResponse,
    ToolReadFileRequest,
    ToolWriteFileRequest,
    ToolExecuteCommandRequest,
    ToolListDirectoryRequest,
)
```

---

## Phase 2: Security & Validation

### 📌 Цель
Реализовать три валидатора: пути, команды, размеры.

### 🎯 Tasks (8.2.1 - 8.2.7)

#### 8.2.1 Path Validator
**Файл**: `app/core/tools/validator.py`

```python
import os
from pathlib import Path
from typing import Tuple
from uuid import UUID
from app.logging_config import get_logger

logger = get_logger(__name__)

class PathValidator:
    """Validates file paths for safety"""
    
    # Dangerous extensions for write operations
    FORBIDDEN_EXTENSIONS = {".exe", ".bin", ".so", ".dll", ".dylib", 
                           ".sh", ".bat", ".cmd", ".scr", ".msi"}
    MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
    
    def __init__(self, workspace_root: str):
        self.workspace_root = Path(workspace_root).resolve()
        logger.info(f"PathValidator initialized with workspace: {self.workspace_root}")
    
    def validate_read_path(self, path: str) -> Tuple[bool, str]:
        """Validate path for read operation"""
        try:
            file_path = self._resolve_path(path)
            
            # Check if path is within workspace
            if not self._is_within_workspace(file_path):
                return False, f"Path {path} is outside workspace boundary"
            
            # Check if file exists
            if not file_path.exists():
                return False, f"File not found: {path}"
            
            # Check if it's a file (not directory)
            if not file_path.is_file():
                return False, f"Path is not a file: {path}"
            
            # Check file size
            file_size = file_path.stat().st_size
            if file_size > self.MAX_FILE_SIZE:
                return False, f"File too large: {file_size} bytes (max {self.MAX_FILE_SIZE})"
            
            return True, str(file_path)
        except Exception as e:
            logger.error(f"Error validating read path {path}: {e}")
            return False, str(e)
    
    def validate_write_path(self, path: str) -> Tuple[bool, str]:
        """Validate path for write operation"""
        try:
            file_path = self._resolve_path(path)
            
            # Check if path is within workspace
            if not self._is_within_workspace(file_path):
                return False, f"Path {path} is outside workspace boundary"
            
            # Check extension
            ext = file_path.suffix.lower()
            if ext in self.FORBIDDEN_EXTENSIONS:
                return False, f"Writing to .{ext[1:]} files is not allowed"
            
            # Check if parent directory exists (or can be created)
            parent = file_path.parent
            if not parent.exists():
                try:
                    parent.mkdir(parents=True, exist_ok=True)
                except PermissionError:
                    return False, f"Permission denied creating parent directory: {parent}"
            
            return True, str(file_path)
        except Exception as e:
            logger.error(f"Error validating write path {path}: {e}")
            return False, str(e)
    
    def validate_directory_path(self, path: str) -> Tuple[bool, str]:
        """Validate path for directory listing"""
        try:
            dir_path = self._resolve_path(path)
            
            # Check if path is within workspace
            if not self._is_within_workspace(dir_path):
                return False, f"Path {path} is outside workspace boundary"
            
            # Check if directory exists
            if not dir_path.exists():
                return False, f"Directory not found: {path}"
            
            # Check if it's a directory
            if not dir_path.is_dir():
                return False, f"Path is not a directory: {path}"
            
            return True, str(dir_path)
        except Exception as e:
            logger.error(f"Error validating directory path {path}: {e}")
            return False, str(e)
    
    def _resolve_path(self, path: str) -> Path:
        """Resolve path safely"""
        # Treat path as relative to workspace root
        abs_path = self.workspace_root / path
        return abs_path.resolve()
    
    def _is_within_workspace(self, path: Path) -> bool:
        """Check if path is within workspace"""
        try:
            # Resolve both paths to absolute
            resolved = path.resolve()
            workspace = self.workspace_root.resolve()
            
            # Check if resolved path starts with workspace path
            resolved.relative_to(workspace)
            return True
        except ValueError:
            return False
```

#### 8.2.2 & 8.2.3 Command Validator (Whitelist/Blacklist)
**Файл**: `app/core/tools/command_whitelist.py`

```python
import shlex
from typing import Tuple, Set
from app.logging_config import get_logger

logger = get_logger(__name__)

class CommandValidator:
    """Validates commands against whitelist/blacklist"""
    
    # WHITELIST: Safe commands for execution
    ALLOWED_COMMANDS = {
        # Search utilities
        "grep", "find", "locate",
        # File utilities
        "ls", "cat", "head", "tail", "wc", "file",
        # Git operations
        "git",
        # Package managers (for installation)
        "npm", "pip", "yarn", "pnpm",
        # Interpreters
        "node", "python", "python3", "ruby", "php",
        # Compilers
        "gcc", "g++", "cc", "make",
        # Archiving
        "zip", "unzip", "tar", "gzip", "gunzip",
        # System utilities
        "echo", "date", "pwd", "whoami", "uname",
        # Text processing
        "sed", "awk", "sort", "uniq", "cut",
        # Others
        "diff", "patch", "test",
    }
    
    # BLACKLIST: Dangerous commands (explicit deny)
    FORBIDDEN_COMMANDS = {
        # Destructive operations
        "rm", "rmdir", "dd", "mkfs", "fsck", "fdisk", "parted",
        # Privilege escalation
        "sudo", "su", "doas", "runuser",
        # Dangerous downloaders
        "curl", "wget", "nc", "ncat",
        # Dangerous system commands
        "reboot", "poweroff", "shutdown", "halt", "kill", "killall",
        # Key generation (security risk)
        "ssh-keygen", "openssl", "gpg",
        # Package installation (except npm, pip)
        "apt", "apt-get", "yum", "dnf", "pacman", "brew", "emerge",
        # Network tools (potential security risks)
        "nmap", "netstat", "iptables", "ifconfig", "ip",
        # Dangerous shells
        "bash", "sh", "zsh", "ksh",  # Direct shell invocation
    }
    
    def __init__(self):
        self.logger = logger
    
    def validate_command(self, command: str) -> Tuple[bool, str]:
        """Validate if command is allowed"""
        # Normalize command (lowercase, strip)
        cmd = command.strip().lower()
        
        # Handle path-based commands (e.g., /usr/bin/python)
        if "/" in cmd:
            base_cmd = cmd.split("/")[-1]  # Get last part
        else:
            base_cmd = cmd
        
        # Remove version numbers (python3 → python, node18 → node)
        base_cmd = self._strip_version(base_cmd)
        
        # Check blacklist first (explicit deny)
        if base_cmd in self.FORBIDDEN_COMMANDS:
            self.logger.warning(f"Command blocked by blacklist: {command}")
            return False, f"Command '{base_cmd}' is not allowed"
        
        # Check whitelist
        if base_cmd not in self.ALLOWED_COMMANDS:
            self.logger.warning(f"Command not in whitelist: {command}")
            return False, f"Command '{base_cmd}' is not in allowed list"
        
        return True, base_cmd
    
    def validate_command_safety(self, command: str, args: list) -> Tuple[bool, str]:
        """Validate command + arguments for safety"""
        is_allowed, msg = self.validate_command(command)
        if not is_allowed:
            return False, msg
        
        # Get normalized command
        base_cmd = self._strip_version(command.strip().lower().split("/")[-1])
        
        # Special handling for dangerous argument patterns
        if base_cmd in {"curl", "wget"}:
            # These should be blocked anyway, but extra check
            return False, f"Command '{base_cmd}' is not allowed due to security risks"
        
        if base_cmd == "git":
            # Allow git clone, pull, commit, etc.
            if args and args[0] in {"clone", "pull", "fetch", "push", "commit", "add", 
                                    "status", "log", "branch", "checkout", "merge"}:
                return True, "git command allowed"
            elif not args:
                return True, "git command allowed"
            else:
                return False, f"git subcommand '{args[0]}' not allowed"
        
        if base_cmd == "npm":
            # Allow npm install, run, etc.
            if args and args[0] in {"install", "i", "run", "start", "test", "build", 
                                    "list", "info"}:
                return True, "npm command allowed"
            else:
                return False, f"npm subcommand not allowed"
        
        if base_cmd in {"python", "python3", "node"}:
            # Allow interpreters with scripts
            return True, "script interpreter allowed"
        
        return True, "command allowed"
    
    @staticmethod
    def _strip_version(cmd: str) -> str:
        """Remove version numbers from command"""
        # python3.11 → python
        # node18 → node
        # gcc-12 → gcc
        import re
        return re.sub(r'[\d\.\-]+$', '', cmd)
    
    @staticmethod
    def parse_command_safely(command: str) -> Tuple[str, list]:
        """Parse command string into command + args"""
        try:
            parts = shlex.split(command)
            if not parts:
                raise ValueError("Empty command")
            return parts[0], parts[1:]
        except ValueError as e:
            raise ValueError(f"Invalid command syntax: {e}")
```

#### 8.2.4-8.2.7 Size Limiter
**Файл**: `app/core/tools/size_limiter.py`

```python
from typing import Tuple

class SizeLimiter:
    """Manage size limits for tool operations"""
    
    MAX_FILE_READ_SIZE = 100 * 1024 * 1024  # 100MB
    MAX_FILE_WRITE_SIZE = 100 * 1024 * 1024  # 100MB
    MAX_OUTPUT_SIZE = 1 * 1024 * 1024  # 1MB
    MAX_COMMAND_TIMEOUT = 300  # 300 seconds
    MAX_DIRECTORY_ITEMS = 1000  # Max items to list
    
    @staticmethod
    def validate_read_size(file_size: int) -> Tuple[bool, str]:
        """Validate file size for reading"""
        if file_size > SizeLimiter.MAX_FILE_READ_SIZE:
            return False, f"File too large ({file_size} > {SizeLimiter.MAX_FILE_READ_SIZE})"
        return True, ""
    
    @staticmethod
    def validate_write_size(content_size: int) -> Tuple[bool, str]:
        """Validate content size for writing"""
        if content_size > SizeLimiter.MAX_FILE_WRITE_SIZE:
            return False, f"Content too large ({content_size} > {SizeLimiter.MAX_FILE_WRITE_SIZE})"
        return True, ""
    
    @staticmethod
    def validate_output_size(output_size: int) -> Tuple[bool, str]:
        """Validate command output size"""
        if output_size > SizeLimiter.MAX_OUTPUT_SIZE:
            return False, f"Output too large ({output_size} > {SizeLimiter.MAX_OUTPUT_SIZE})"
        return True, ""
    
    @staticmethod
    def validate_timeout(timeout: int) -> Tuple[bool, str]:
        """Validate command timeout"""
        if timeout <= 0:
            return False, "Timeout must be positive"
        if timeout > SizeLimiter.MAX_COMMAND_TIMEOUT:
            return False, f"Timeout too long ({timeout} > {SizeLimiter.MAX_COMMAND_TIMEOUT})"
        return True, ""
    
    @staticmethod
    def validate_directory_count(count: int) -> Tuple[bool, str]:
        """Validate directory item count"""
        if count > SizeLimiter.MAX_DIRECTORY_ITEMS:
            return False, f"Too many items ({count} > {SizeLimiter.MAX_DIRECTORY_ITEMS})"
        return True, ""
    
    @staticmethod
    def truncate_output(output: str, max_size: int = MAX_OUTPUT_SIZE) -> str:
        """Truncate output to max size"""
        output_bytes = output.encode('utf-8')
        if len(output_bytes) > max_size:
            # Decode safely (handle UTF-8 boundaries)
            truncated = output_bytes[:max_size].decode('utf-8', errors='ignore')
            return truncated + "\n... [output truncated]"
        return output
```

---

## Phase 3: Risk Assessment

### 📌 Цель
Классифицировать tools по risk level (LOW/MEDIUM/HIGH) и определить таймауты.

### 🎯 Tasks (8.3.1 - 8.3.4)

#### 8.3.1-8.3.2 Risk Assessor
**Файл**: `app/core/tools/risk_assessor.py`

```python
from enum import Enum
from typing import Tuple
from app.core.tools.command_whitelist import CommandValidator
from app.logging_config import get_logger

logger = get_logger(__name__)

class RiskLevel(str, Enum):
    """Risk levels for tool execution"""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

class RiskAssessor:
    """Assess risk level of tool execution"""
    
    # Risk matrix for tools
    READ_FILE_RISK = RiskLevel.LOW  # Always safe
    LIST_DIRECTORY_RISK = RiskLevel.LOW  # Always safe
    
    # Write file risks by extension
    WRITE_FILE_LOW_RISK_EXTENSIONS = {
        ".txt", ".md", ".json", ".yaml", ".yml", ".toml",
        ".py", ".js", ".ts", ".jsx", ".tsx", ".vue",
        ".css", ".html", ".xml", ".sql", ".sh",
        ".c", ".cpp", ".h", ".java", ".go", ".rs",
    }
    
    WRITE_FILE_HIGH_RISK_EXTENSIONS = {
        ".exe", ".bin", ".so", ".dll", ".dylib",
        ".sys", ".drv", ".conf", ".config",
    }
    
    # Command risks by command name
    COMMAND_LOW_RISK = {
        "grep", "find", "locate", "ls", "cat", "head", "tail", "wc",
        "echo", "date", "pwd", "whoami", "uname", "file",
        "sed", "awk", "sort", "uniq", "cut", "diff",
    }
    
    COMMAND_MEDIUM_RISK = {
        "git", "npm", "pip", "yarn", "pnpm",
        "node", "python", "python3", "ruby", "php",
    }
    
    COMMAND_HIGH_RISK = {
        "gcc", "g++", "cc", "make",  # Compilers
        "zip", "unzip", "tar",  # Archiving
    }
    
    def assess_tool_risk(self, tool_name: str, params: dict) -> RiskLevel:
        """Assess overall risk of tool execution"""
        if tool_name == "read_file":
            return self.READ_FILE_RISK
        elif tool_name == "list_directory":
            return self.LIST_DIRECTORY_RISK
        elif tool_name == "write_file":
            return self._assess_write_file_risk(params)
        elif tool_name == "execute_command":
            return self._assess_command_risk(params)
        else:
            return RiskLevel.HIGH  # Unknown tools are HIGH risk
    
    def _assess_write_file_risk(self, params: dict) -> RiskLevel:
        """Assess risk of write_file operation"""
        path = params.get("path", "")
        
        # Extract extension
        import os
        _, ext = os.path.splitext(path)
        ext = ext.lower()
        
        # Check extension
        if ext in self.WRITE_FILE_HIGH_RISK_EXTENSIONS:
            return RiskLevel.HIGH
        elif ext in self.WRITE_FILE_LOW_RISK_EXTENSIONS:
            return RiskLevel.MEDIUM  # Writing code files = MEDIUM risk
        else:
            # Unknown extension
            return RiskLevel.MEDIUM
    
    def _assess_command_risk(self, params: dict) -> RiskLevel:
        """Assess risk of execute_command operation"""
        command = params.get("command", "").lower().strip()
        
        # Parse command (get base command name)
        if "/" in command:
            base_cmd = command.split("/")[-1]
        else:
            base_cmd = command.split()[0] if command else ""
        
        # Remove version numbers
        base_cmd = CommandValidator._strip_version(base_cmd)
        
        # Assess risk
        if base_cmd in self.COMMAND_LOW_RISK:
            return RiskLevel.LOW
        elif base_cmd in self.COMMAND_MEDIUM_RISK:
            return RiskLevel.MEDIUM
        elif base_cmd in self.COMMAND_HIGH_RISK:
            return RiskLevel.HIGH
        else:
            # Default to HIGH for unknown commands
            return RiskLevel.HIGH
    
    def get_timeout_for_risk_level(self, risk_level: RiskLevel) -> int:
        """Get approval timeout in seconds for risk level"""
        timeouts = {
            RiskLevel.LOW: 0,          # No approval needed
            RiskLevel.MEDIUM: 300,     # 5 minutes
            RiskLevel.HIGH: 600,       # 10 minutes
        }
        return timeouts.get(risk_level, 300)
    
    def requires_approval(self, risk_level: RiskLevel) -> bool:
        """Check if tool requires approval"""
        return risk_level != RiskLevel.LOW
```

#### 8.3.3 Risk Documentation
**Файл**: `doc/tool-risk-assessment-matrix.md`

```markdown
# Tool Risk Assessment Matrix

## read_file
- **Risk Level**: LOW
- **Requires Approval**: NO
- **Timeout**: N/A
- **Rationale**: Read-only operation, no system modifications
- **Examples**:
  - read_file(path="src/main.py") → LOW
  - read_file(path="config.json") → LOW

## list_directory
- **Risk Level**: LOW
- **Requires Approval**: NO
- **Timeout**: N/A
- **Rationale**: Information-only, no modifications

## write_file

### By File Extension
| Extension | Risk Level | Timeout |
|-----------|-----------|---------|
| .txt, .md, .json | MEDIUM | 5 min |
| .py, .js, .ts, .jsx, .tsx | MEDIUM | 5 min |
| .yaml, .yml, .toml | MEDIUM | 5 min |
| .xml, .html, .css | MEDIUM | 5 min |
| .exe, .bin, .so, .dll | HIGH | 10 min |
| .conf, .config, .sys | HIGH | 10 min |
| .sh (shell scripts) | MEDIUM | 5 min |

### Examples
- write_file(path="config.json", ...) → MEDIUM (5 min timeout)
- write_file(path="script.exe", ...) → HIGH (10 min timeout)

## execute_command

### By Command Category

#### Category: Search (LOW RISK)
- grep, find, locate
- **Risk Level**: LOW
- **Requires Approval**: NO
- **Examples**:
  - execute_command("grep", ["error", "*.log"])
  - execute_command("find", [".", "-name", "*.js"])

#### Category: File Tools (LOW RISK)
- ls, cat, head, tail, wc, file
- **Risk Level**: LOW
- **Requires Approval**: NO

#### Category: Text Processing (LOW RISK)
- sed, awk, sort, uniq, cut, diff
- **Risk Level**: LOW
- **Requires Approval**: NO

#### Category: Version Control (MEDIUM RISK)
- git
- **Risk Level**: MEDIUM
- **Requires Approval**: YES (5 min timeout)
- **Allowed Subcommands**: clone, pull, fetch, push, commit, add, status, log, branch, checkout, merge

#### Category: Package Managers (MEDIUM RISK)
- npm, pip, yarn, pnpm
- **Risk Level**: MEDIUM
- **Requires Approval**: YES (5 min timeout)
- **Examples**:
  - execute_command("npm", ["install", "express"])
  - execute_command("pip", ["install", "requests"])

#### Category: Interpreters (MEDIUM RISK)
- node, python, python3, ruby, php
- **Risk Level**: MEDIUM
- **Requires Approval**: YES (5 min timeout)
- **Examples**:
  - execute_command("python", ["script.py"])
  - execute_command("node", ["server.js"])

#### Category: Compilers (HIGH RISK)
- gcc, g++, cc, make
- **Risk Level**: HIGH
- **Requires Approval**: YES (10 min timeout)
- **Rationale**: Can create executables and modify system

#### Category: Archiving (HIGH RISK)
- zip, unzip, tar
- **Risk Level**: HIGH
- **Requires Approval**: YES (10 min timeout)

### Risk Override Rules
1. If command is in BLACKLIST → **REJECT** (no approval can override)
2. If risk level is HIGH → 10 min timeout
3. If risk level is MEDIUM → 5 min timeout
4. If risk level is LOW → no approval needed
```

---

## Phase 4: Approval Manager Integration

### 📌 Цель
Расширить ApprovalManager для работы с tools.

### 🎯 Tasks (8.4.1 - 8.4.5)

#### 8.4.1-8.4.5 ApprovalManager Extension
**Файл**: `app/core/approval_manager.py` (EXTEND)

```python
# Add these methods to existing ApprovalManager class

async def request_tool_approval(
    self,
    tool_name: str,
    tool_params: dict,
    risk_level: "RiskLevel",  # from risk_assessor
    timeout_seconds: int,
    session_id: Optional[UUID] = None,
) -> ApprovalRequest:
    """Request approval for tool execution"""
    from app.schemas.approval import ApprovalType
    
    self.logger.info(
        "request_tool_approval",
        tool_name=tool_name,
        risk_level=risk_level,
        timeout=timeout_seconds,
    )
    
    # Mask sensitive params before storing
    masked_params = self._mask_tool_params(tool_name, tool_params)
    
    # Create approval request
    approval_request = ApprovalRequest(
        user_id=self.user_id,
        project_id=self.project_id,
        type=ApprovalType.TOOL_EXECUTION,
        payload={
            "tool_name": tool_name,
            "tool_params": masked_params,
            "risk_level": risk_level,
            "session_id": str(session_id) if session_id else None,
        },
        status="pending",
        expires_at=datetime.utcnow() + timedelta(seconds=timeout_seconds),
    )
    
    # Save to DB
    self.db.add(approval_request)
    await self.db.commit()
    await self.db.refresh(approval_request)
    
    # Send notification through SSE
    if self.stream_manager:
        await self.stream_manager.broadcast_event(
            session_id=session_id,
            event=StreamEvent(
                event_type=StreamEventType.APPROVAL_REQUIRED,
                payload={
                    "approval_id": str(approval_request.id),
                    "tool_name": tool_name,
                    "risk_level": risk_level,
                    "timeout_seconds": timeout_seconds,
                },
            ),
        )
    
    return approval_request

async def auto_approve_tool_if_low_risk(
    self,
    risk_level: "RiskLevel",
) -> bool:
    """Check if LOW_RISK tool should be auto-approved"""
    from app.core.tools.risk_assessor import RiskLevel
    return risk_level == RiskLevel.LOW

def _mask_tool_params(self, tool_name: str, params: dict) -> dict:
    """Mask sensitive parameters before storing"""
    masked = params.copy()
    
    # For write_file, don't store actual content (too large)
    if tool_name == "write_file" and "content" in masked:
        content_size = len(masked["content"])
        masked["content"] = f"[CONTENT {content_size} bytes]"
    
    return masked

async def wait_for_tool_approval(
    self,
    approval_id: UUID,
    timeout_seconds: int,
) -> Tuple[bool, Optional[str]]:
    """Wait for user approval decision with timeout"""
    import asyncio
    
    start_time = time.time()
    
    while time.time() - start_time < timeout_seconds:
        # Check approval status
        approval = await self.db.get(ApprovalRequest, approval_id)
        
        if not approval:
            return False, "Approval request not found"
        
        if approval.status == "approved":
            return True, None
        
        if approval.status == "rejected":
            reason = approval.payload.get("rejection_reason", "User rejected")
            return False, reason
        
        # Wait before checking again
        await asyncio.sleep(1)
    
    # Timeout occurred
    approval.status = "rejected"
    approval.payload["rejection_reason"] = "Approval timeout"
    await self.db.commit()
    
    return False, "Approval timeout"
```

---

## Phase 5: Tool Executor & REST API

### 📌 Цель
Создать главный оркестратор tool execution и REST endpoints.

### 🎯 Tasks (8.5.1 - 8.5.5 Backend, 13.5 REST API)

#### 8.5.1 Tool Executor
**Файл**: `app/core/tools/executor.py`

```python
from uuid import UUID, uuid4
from typing import Optional
from app.core.tools.risk_assessor import RiskAssessor, RiskLevel
from app.core.tools.validator import PathValidator
from app.core.tools.command_whitelist import CommandValidator
from app.core.tools.size_limiter import SizeLimiter
from app.core.approval_manager import ApprovalManager
from app.core.stream_manager import StreamManager
from app.schemas.tool import ToolExecutionRequest, ToolExecutionResponse
from app.logging_config import get_logger

logger = get_logger(__name__)

class ToolExecutor:
    """Orchestrates tool execution with approval workflow"""
    
    def __init__(
        self,
        user_id: UUID,
        project_id: UUID,
        workspace_root: str,
        approval_manager: ApprovalManager,
        stream_manager: Optional[StreamManager] = None,
    ):
        self.user_id = user_id
        self.project_id = project_id
        self.workspace_root = workspace_root
        self.approval_manager = approval_manager
        self.stream_manager = stream_manager
        
        # Validators
        self.path_validator = PathValidator(workspace_root)
        self.command_validator = CommandValidator()
        self.risk_assessor = RiskAssessor()
    
    async def execute_tool(
        self,
        tool_name: str,
        tool_params: dict,
        session_id: Optional[UUID] = None,
    ) -> ToolExecutionResponse:
        """Main entry point for tool execution"""
        tool_id = str(uuid4())
        created_at = datetime.utcnow().isoformat()
        
        try:
            logger.info(
                "tool_execution_started",
                tool_id=tool_id,
                tool_name=tool_name,
                user_id=str(self.user_id),
            )
            
            # 1. Validate parameters
            is_valid, error = await self._validate_tool_params(tool_name, tool_params)
            if not is_valid:
                return ToolExecutionResponse(
                    tool_id=tool_id,
                    tool_name=tool_name,
                    status="failed",
                    error=error,
                    created_at=created_at,
                )
            
            # 2. Assess risk level
            risk_level = self.risk_assessor.assess_tool_risk(tool_name, tool_params)
            
            # 3. Handle approval if needed
            approval_id = None
            if not await self.approval_manager.auto_approve_tool_if_low_risk(risk_level):
                # Request approval
                timeout = self.risk_assessor.get_timeout_for_risk_level(risk_level)
                approval = await self.approval_manager.request_tool_approval(
                    tool_name=tool_name,
                    tool_params=tool_params,
                    risk_level=risk_level,
                    timeout_seconds=timeout,
                    session_id=session_id,
                )
                approval_id = approval.id
                
                # Wait for approval
                approved, reason = await self.approval_manager.wait_for_tool_approval(
                    approval_id=approval_id,
                    timeout_seconds=timeout,
                )
                
                if not approved:
                    logger.warning(
                        "tool_execution_rejected",
                        tool_id=tool_id,
                        approval_id=str(approval_id),
                        reason=reason,
                    )
                    return ToolExecutionResponse(
                        tool_id=tool_id,
                        tool_name=tool_name,
                        status="rejected",
                        approval_id=approval_id,
                        error=f"Approval rejected: {reason}",
                        created_at=created_at,
                    )
            
            # 4. Send TOOL_EXECUTION_REQUEST to client
            # This is where VS Code Extension would intercept and execute
            result = await self._send_tool_to_client(
                tool_id=tool_id,
                tool_name=tool_name,
                tool_params=tool_params,
                session_id=session_id,
            )
            
            logger.info(
                "tool_execution_completed",
                tool_id=tool_id,
                tool_name=tool_name,
                status="completed",
            )
            
            return ToolExecutionResponse(
                tool_id=tool_id,
                tool_name=tool_name,
                status="completed",
                approval_id=approval_id,
                result=result,
                created_at=created_at,
                completed_at=datetime.utcnow().isoformat(),
            )
        
        except Exception as e:
            logger.error(
                "tool_execution_error",
                tool_id=tool_id,
                tool_name=tool_name,
                error=str(e),
            )
            return ToolExecutionResponse(
                tool_id=tool_id,
                tool_name=tool_name,
                status="failed",
                error=str(e),
                created_at=created_at,
            )
    
    async def _validate_tool_params(
        self,
        tool_name: str,
        params: dict,
    ) -> Tuple[bool, Optional[str]]:
        """Validate tool parameters"""
        try:
            if tool_name == "read_file":
                path = params.get("path")
                if not path:
                    return False, "Missing 'path' parameter"
                is_valid, resolved_path = self.path_validator.validate_read_path(path)
                return is_valid, None if is_valid else resolved_path
            
            elif tool_name == "write_file":
                path = params.get("path")
                content = params.get("content")
                if not path or content is None:
                    return False, "Missing 'path' or 'content' parameter"
                
                is_valid, msg = self.path_validator.validate_write_path(path)
                if not is_valid:
                    return False, msg
                
                is_valid, msg = SizeLimiter.validate_write_size(len(content))
                return is_valid, msg
            
            elif tool_name == "execute_command":
                command = params.get("command")
                args = params.get("args", [])
                timeout = params.get("timeout", 30)
                
                if not command:
                    return False, "Missing 'command' parameter"
                
                is_valid, msg = self.command_validator.validate_command(command)
                if not is_valid:
                    return False, msg
                
                is_valid, msg = self.command_validator.validate_command_safety(command, args)
                if not is_valid:
                    return False, msg
                
                is_valid, msg = SizeLimiter.validate_timeout(timeout)
                return is_valid, msg
            
            elif tool_name == "list_directory":
                path = params.get("path")
                if not path:
                    return False, "Missing 'path' parameter"
                is_valid, msg = self.path_validator.validate_directory_path(path)
                return is_valid, msg
            
            else:
                return False, f"Unknown tool: {tool_name}"
        
        except Exception as e:
            logger.error(f"Validation error for {tool_name}: {e}")
            return False, str(e)
    
    async def _send_tool_to_client(
        self,
        tool_id: str,
        tool_name: str,
        tool_params: dict,
        session_id: Optional[UUID] = None,
    ):
        """Send TOOL_EXECUTION_REQUEST to client (VS Code Extension)"""
        # This would be implemented with your StreamManager / event system
        # The client receives this and executes the tool locally
        
        if self.stream_manager:
            await self.stream_manager.broadcast_event(
                session_id=session_id,
                event=StreamEvent(
                    event_type=StreamEventType.TOOL_EXECUTION_REQUEST,
                    payload={
                        "tool_id": tool_id,
                        "tool_name": tool_name,
                        "tool_params": tool_params,
                    },
                ),
            )
        
        # Wait for client response (implement with event listener)
        # return await self._wait_for_tool_result(tool_id, timeout=30)
```

#### 13.5 REST API Endpoints
**Файл**: `app/routes/project_tools.py` (NEW)

```python
from fastapi import APIRouter, Depends, HTTPException
from uuid import UUID
from app.dependencies import get_worker_space, get_current_user
from app.schemas.tool import ToolExecutionRequest, ToolExecutionResponse
from app.logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/my/tools", tags=["tools"])

@router.post("/execute")
async def execute_tool(
    project_id: UUID,
    request: ToolExecutionRequest,
    worker_space = Depends(get_worker_space),
    user_id: UUID = Depends(get_current_user),
) -> ToolExecutionResponse:
    """Execute a tool (read_file, write_file, execute_command, list_directory)"""
    try:
        result = await worker_space.executor.execute_tool(
            tool_name=request.tool_name,
            tool_params=request.tool_params,
            session_id=request.session_id,
        )
        return result
    except Exception as e:
        logger.error(f"Tool execution error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{tool_id}")
async def get_tool_execution_status(
    tool_id: str,
    project_id: UUID,
    user_id: UUID = Depends(get_current_user),
) -> dict:
    """Get status of tool execution"""
    # Implementation depends on how you store tool execution state
    pass

@router.get("/history")
async def get_tool_execution_history(
    project_id: UUID,
    limit: int = 50,
    offset: int = 0,
    user_id: UUID = Depends(get_current_user),
) -> dict:
    """Get history of tool executions"""
    pass
```

---

## Phase 6: Testing

### 📌 Цель
Полное покрытие unit и integration тестами.

### 🎯 Tasks (8.6.1 - 8.6.5)

#### 8.6.1 Unit Tests - PathValidator
**Файл**: `tests/test_tool_path_validator.py`

#### 8.6.2 Unit Tests - RiskAssessor
**Файл**: `tests/test_tool_risk_assessor.py`

#### 8.6.3 Integration Tests - Tool Execution
**Файл**: `tests/test_tool_execution_flow.py`

#### 8.6.4 Integration Tests - Approval Workflow
**Файл**: `tests/test_tool_approval_workflow.py`

#### 8.6.5 Security Tests
**Файл**: `tests/test_tool_security.py`

---

## 📊 Зависимости между фазами

```
Phase 1 (Definitions) ← baseline
         ↓
Phase 2 (Validation) ← depends on Phase 1
         ↓
Phase 3 (Risk Assessment) ← depends on Phase 1-2
         ↓
Phase 4 (Approval Integration) ← depends on Phase 1-3
         ↓
Phase 5 (Executor & REST API) ← depends on Phase 1-4
         ↓
Phase 6 (Testing) ← depends on Phase 1-5
```

## ✅ Готово к реализации

Каждая фаза полностью описана с примерами кода, типизацией и интеграционными моментами. Можно начинать Phase 1!
