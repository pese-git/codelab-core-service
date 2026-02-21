"""Risk Assessment for Tool Execution"""

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
    """Assess risk level of tool execution and determine approval requirements
    
    Risk matrix:
    - read_file: LOW (read-only)
    - list_directory: LOW (read-only)
    - write_file: MEDIUM/HIGH (depends on file extension)
    - execute_command: LOW/MEDIUM/HIGH (depends on command type)
    """
    
    # ========================================================================
    # RISK LEVELS FOR EACH TOOL
    # ========================================================================
    
    # Read operations are always LOW risk
    READ_FILE_RISK = RiskLevel.LOW
    LIST_DIRECTORY_RISK = RiskLevel.LOW
    
    # ========================================================================
    # WRITE_FILE RISK BY FILE EXTENSION
    # ========================================================================
    
    # Safe file extensions (text/code files)
    WRITE_FILE_LOW_RISK_EXTENSIONS = {
        ".txt", ".md", ".json", ".yaml", ".yml", ".toml",
        ".py", ".js", ".ts", ".jsx", ".tsx", ".vue",
        ".css", ".html", ".xml", ".sql", ".sh",
        ".c", ".cpp", ".h", ".hpp", ".cc", ".cxx",
        ".java", ".go", ".rs", ".rb", ".php",
        ".log", ".csv", ".tsv", ".xml", ".ini",
    }
    
    # Dangerous file extensions (executables/system files)
    WRITE_FILE_HIGH_RISK_EXTENSIONS = {
        ".exe", ".bin", ".so", ".dll", ".dylib",
        ".sys", ".drv", ".conf", ".config",
        ".app", ".deb", ".rpm", ".msi",
    }
    
    # ========================================================================
    # COMMAND RISK BY COMMAND NAME
    # ========================================================================
    
    # Safe read-only commands (LOW RISK)
    COMMAND_LOW_RISK = {
        # Search utilities
        "grep", "find", "locate",
        # File utilities
        "ls", "cat", "head", "tail", "wc", "file",
        # System info
        "echo", "date", "pwd", "whoami", "uname",
        # Text processing
        "sed", "awk", "sort", "uniq", "cut",
        # Comparison
        "diff", "patch", "test",
    }
    
    # Moderate risk commands (MEDIUM RISK)
    COMMAND_MEDIUM_RISK = {
        # Version control
        "git",
        # Package managers
        "npm", "pip", "yarn", "pnpm",
        # Interpreters (can execute arbitrary code)
        "node", "python", "python3", "ruby", "php",
    }
    
    # High risk commands (HIGH RISK)
    COMMAND_HIGH_RISK = {
        # Compilers (can create executables)
        "gcc", "g++", "cc", "make", "clang",
        # Archiving (can extract arbitrary files)
        "zip", "unzip", "tar", "gzip", "gunzip",
    }
    
    def __init__(self):
        """Initialize risk assessor"""
        self.logger = logger
    
    def assess_tool_risk(self, tool_name: str, params: dict) -> RiskLevel:
        """Assess overall risk level of tool execution
        
        Args:
            tool_name: Name of tool being executed
            params: Tool parameters
            
        Returns:
            RiskLevel (LOW, MEDIUM, HIGH)
        """
        if tool_name == "read_file":
            return self.READ_FILE_RISK
        
        elif tool_name == "list_directory":
            return self.LIST_DIRECTORY_RISK
        
        elif tool_name == "write_file":
            return self._assess_write_file_risk(params)
        
        elif tool_name == "execute_command":
            return self._assess_command_risk(params)
        
        else:
            # Unknown tools are HIGH risk by default
            self.logger.warning(f"Unknown tool '{tool_name}' - assuming HIGH risk")
            return RiskLevel.HIGH
    
    def _assess_write_file_risk(self, params: dict) -> RiskLevel:
        """Assess risk of write_file operation based on file extension
        
        Args:
            params: Tool parameters containing 'path'
            
        Returns:
            RiskLevel
        """
        path = params.get("path", "")
        
        # Extract file extension
        import os
        _, ext = os.path.splitext(path)
        ext = ext.lower()
        
        self.logger.debug(f"Assessing write_file risk for extension: {ext}")
        
        # Check extension against high-risk list
        if ext in self.WRITE_FILE_HIGH_RISK_EXTENSIONS:
            self.logger.info(f"write_file risk: HIGH (extension: {ext})")
            return RiskLevel.HIGH
        
        # Check extension against safe list
        elif ext in self.WRITE_FILE_LOW_RISK_EXTENSIONS:
            self.logger.info(f"write_file risk: MEDIUM (code file: {ext})")
            return RiskLevel.MEDIUM
        
        else:
            # Unknown extension defaults to MEDIUM
            self.logger.info(f"write_file risk: MEDIUM (unknown extension: {ext})")
            return RiskLevel.MEDIUM
    
    def _assess_command_risk(self, params: dict) -> RiskLevel:
        """Assess risk of execute_command based on command name
        
        Args:
            params: Tool parameters containing 'command' and optional 'args'
            
        Returns:
            RiskLevel
        """
        command = params.get("command", "").lower().strip()
        
        # Parse command to get base name
        if "/" in command:
            # Handle path-based commands (e.g., /usr/bin/python)
            base_cmd = command.split("/")[-1]
        else:
            # Get first word (before any spaces)
            base_cmd = command.split()[0] if command else ""
        
        # Remove version numbers
        base_cmd = CommandValidator._strip_version(base_cmd)
        
        self.logger.debug(f"Assessing command risk for: {base_cmd}")
        
        # Assess risk
        if base_cmd in self.COMMAND_LOW_RISK:
            self.logger.info(f"command risk: LOW (command: {base_cmd})")
            return RiskLevel.LOW
        
        elif base_cmd in self.COMMAND_MEDIUM_RISK:
            self.logger.info(f"command risk: MEDIUM (command: {base_cmd})")
            return RiskLevel.MEDIUM
        
        elif base_cmd in self.COMMAND_HIGH_RISK:
            self.logger.info(f"command risk: HIGH (command: {base_cmd})")
            return RiskLevel.HIGH
        
        else:
            # Unknown commands are HIGH risk by default
            self.logger.warning(f"command risk: HIGH (unknown command: {base_cmd})")
            return RiskLevel.HIGH
    
    def get_timeout_for_risk_level(self, risk_level: RiskLevel) -> int:
        """Get approval timeout in seconds for risk level
        
        Args:
            risk_level: RiskLevel enum
            
        Returns:
            Timeout in seconds
        """
        timeouts = {
            RiskLevel.LOW: 0,          # No approval needed
            RiskLevel.MEDIUM: 300,     # 5 minutes
            RiskLevel.HIGH: 600,       # 10 minutes
        }
        return timeouts.get(risk_level, 300)
    
    def requires_approval(self, risk_level: RiskLevel) -> bool:
        """Check if tool requires user approval based on risk level
        
        Args:
            risk_level: RiskLevel enum
            
        Returns:
            True if approval is required
        """
        return risk_level != RiskLevel.LOW
    
    def get_risk_description(self, risk_level: RiskLevel) -> str:
        """Get human-readable description of risk level
        
        Args:
            risk_level: RiskLevel enum
            
        Returns:
            Description string
        """
        descriptions = {
            RiskLevel.LOW: "No approval needed - safe operation",
            RiskLevel.MEDIUM: "Requires approval - moderate risk (5 min timeout)",
            RiskLevel.HIGH: "Requires approval - high risk (10 min timeout)",
        }
        return descriptions.get(risk_level, "Unknown risk level")
    
    def get_full_risk_assessment(
        self,
        tool_name: str,
        params: dict
    ) -> dict:
        """Get comprehensive risk assessment
        
        Args:
            tool_name: Name of tool
            params: Tool parameters
            
        Returns:
            Dict with risk assessment details
        """
        risk_level = self.assess_tool_risk(tool_name, params)
        timeout = self.get_timeout_for_risk_level(risk_level)
        requires_approval = self.requires_approval(risk_level)
        description = self.get_risk_description(risk_level)
        
        return {
            "tool_name": tool_name,
            "risk_level": risk_level.value,
            "requires_approval": requires_approval,
            "approval_timeout_seconds": timeout,
            "description": description,
        }
