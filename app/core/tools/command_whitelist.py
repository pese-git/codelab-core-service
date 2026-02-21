"""Command Validator with Whitelist/Blacklist for safe command execution"""

import shlex
import re
from typing import Tuple, Set
from app.logging_config import get_logger

logger = get_logger(__name__)


class CommandValidator:
    """Validates commands against whitelist/blacklist to prevent malicious execution"""
    
    # WHITELIST: Safe commands allowed for execution
    # Only commands explicitly in this list can be executed
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
    
    # BLACKLIST: Dangerous commands that are explicitly denied
    # These are never allowed, even if in whitelist
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
        # Package installation (except npm, pip which are whitelisted)
        "apt", "apt-get", "yum", "dnf", "pacman", "brew", "emerge",
        # Network tools (potential security risks)
        "nmap", "netstat", "iptables", "ifconfig", "ip",
        # Dangerous shells
        "bash", "sh", "zsh", "ksh",  # Direct shell invocation
    }
    
    def __init__(self):
        """Initialize command validator"""
        self.logger = logger
    
    def validate_command(self, command: str) -> Tuple[bool, str]:
        """Validate if command is allowed to execute
        
        Args:
            command: Command string (e.g., "python" or "/usr/bin/python3")
            
        Returns:
            Tuple of (is_allowed, normalized_command_or_error)
        """
        # Normalize command (lowercase, strip whitespace)
        cmd = command.strip().lower()
        
        # Handle path-based commands (e.g., /usr/bin/python)
        if "/" in cmd:
            base_cmd = cmd.split("/")[-1]  # Get last part after last /
        else:
            base_cmd = cmd
        
        # Remove version numbers (python3 → python, node18 → node)
        base_cmd = self._strip_version(base_cmd)
        
        # Check blacklist first (explicit deny - highest priority)
        if base_cmd in self.FORBIDDEN_COMMANDS:
            error = f"Command '{base_cmd}' is not allowed (blacklisted)"
            self.logger.warning(f"Command blocked by blacklist: {command}")
            return False, error
        
        # Check whitelist (only allowed commands)
        if base_cmd not in self.ALLOWED_COMMANDS:
            error = f"Command '{base_cmd}' is not in allowed list"
            self.logger.warning(f"Command not in whitelist: {command}")
            return False, error
        
        self.logger.debug(f"Command validation passed: {command}")
        return True, base_cmd
    
    def validate_command_safety(
        self,
        command: str,
        args: list
    ) -> Tuple[bool, str]:
        """Validate command + arguments for safety
        
        Performs additional checks for dangerous argument patterns
        
        Args:
            command: Command to execute
            args: List of arguments
            
        Returns:
            Tuple of (is_safe, message)
        """
        is_allowed, msg = self.validate_command(command)
        if not is_allowed:
            return False, msg
        
        # Get normalized command
        base_cmd = self._strip_version(command.strip().lower().split("/")[-1])
        
        # Special handling for specific commands
        
        # curl/wget should be blocked anyway, but extra check
        if base_cmd in {"curl", "wget"}:
            error = f"Command '{base_cmd}' is not allowed due to security risks"
            self.logger.warning(error)
            return False, error
        
        # git: whitelist specific subcommands
        if base_cmd == "git":
            allowed_subcommands = {
                "clone", "pull", "fetch", "push", "commit", "add",
                "status", "log", "branch", "checkout", "merge",
                "init", "config", "stash", "tag", "show"
            }
            if args:
                subcommand = args[0].lower()
                if subcommand not in allowed_subcommands:
                    error = f"git subcommand '{subcommand}' not allowed"
                    self.logger.warning(error)
                    return False, error
            # Allow bare 'git' (will show usage)
            return True, "git command allowed"
        
        # npm: whitelist specific subcommands
        if base_cmd == "npm":
            allowed_subcommands = {
                "install", "i", "run", "start", "test", "build",
                "list", "info", "search", "view", "outdated"
            }
            if args:
                subcommand = args[0].lower()
                if subcommand not in allowed_subcommands:
                    error = f"npm subcommand '{subcommand}' not allowed"
                    self.logger.warning(error)
                    return False, error
            else:
                # npm without args shows help, which is safe
                return True, "npm command allowed"
        
        # pip: whitelist specific subcommands
        if base_cmd == "pip":
            allowed_subcommands = {
                "install", "list", "show", "search", "freeze",
                "check", "index"
            }
            if args:
                subcommand = args[0].lower()
                if subcommand not in allowed_subcommands:
                    error = f"pip subcommand '{subcommand}' not allowed"
                    self.logger.warning(error)
                    return False, error
            return True, "pip command allowed"
        
        # python/node: allow interpreters with scripts
        if base_cmd in {"python", "python3", "node", "ruby", "php"}:
            return True, f"{base_cmd} script interpreter allowed"
        
        # All other allowed commands are safe
        return True, "command allowed"
    
    @staticmethod
    def _strip_version(cmd: str) -> str:
        """Remove version numbers from command name
        
        Examples:
            python3.11 → python
            node18 → node
            gcc-12 → gcc
            
        Args:
            cmd: Command name with possible version
            
        Returns:
            Command name without version
        """
        # Remove trailing digits, dots, and hyphens
        return re.sub(r'[\d\.\-]+$', '', cmd)
    
    @staticmethod
    def parse_command_safely(command: str) -> Tuple[str, list]:
        """Parse command string into command + args safely
        
        Uses shlex to properly handle quoted arguments
        
        Args:
            command: Command string to parse
            
        Returns:
            Tuple of (command, args)
            
        Raises:
            ValueError: If command syntax is invalid
        """
        try:
            parts = shlex.split(command)
            if not parts:
                raise ValueError("Empty command")
            return parts[0], parts[1:]
        except ValueError as e:
            error = f"Invalid command syntax: {str(e)}"
            logger.error(error)
            raise ValueError(error)
