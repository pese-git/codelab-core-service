"""Path Validator for safe file operations on client filesystem

This validator ensures that requested paths:
1. Don't escape workspace boundaries (path traversal prevention)
2. Have allowed file extensions for write operations
3. Are syntactically valid

NOTE: This validator works with CLIENT-SIDE paths (from VS Code plugin).
It does NOT check filesystem state (existence, symlinks, etc.) because
those are evaluated by the client. The server validates against path traversal.
"""

import os
from pathlib import PureWindowsPath, PurePosixPath, PurePath
from typing import Tuple
from app.logging_config import get_logger

logger = get_logger(__name__)


class PathValidator:
    """Validates file paths for safety and prevents path traversal attacks
    
    Works with client-side paths (e.g., from VS Code plugin).
    The validator prevents path traversal but does not check filesystem state.
    """
    
    # Dangerous file extensions that should not be written
    FORBIDDEN_EXTENSIONS = {
        ".exe", ".bin", ".so", ".dll", ".dylib",
        ".sh", ".bat", ".cmd", ".scr", ".msi",
        ".app", ".deb", ".rpm"
    }
    
    # Maximum file size for read operations (100MB)
    # This is informational only - actual check happens on client
    MAX_FILE_SIZE = 100 * 1024 * 1024
    
    def __init__(self, workspace_root: str):
        """Initialize validator with workspace root directory
        
        Args:
            workspace_root: Workspace root path (from client, may be Windows or Unix-style)
        """
        # Normalize workspace root - it's a CLIENT path, so it may be Windows or Unix
        self.workspace_root_str = workspace_root
        self.logger = logger
        
        self.logger.info(
            "path_validator_initialized",
            workspace_root=workspace_root
        )
    
    def validate_read_path(self, path: str) -> Tuple[bool, str]:
        """Validate path for read operation
        
        Args:
            path: Relative path to file (may contain .. or /)
            
        Returns:
            Tuple of (is_valid, resolved_path_or_error)
            - If valid: (True, resolved_path)
            - If invalid: (False, error_message)
        """
        try:
            # Validate and resolve path
            is_valid, result = self._validate_path(path, allow_directory=False)
            
            if not is_valid:
                self.logger.warning(
                    "read_path_validation_failed",
                    path=path,
                    error=result
                )
                return False, result
            
            self.logger.debug(
                "read_path_validation_passed",
                path=path,
                resolved_path=result
            )
            return True, result
        
        except Exception as e:
            error = f"Error validating read path {path}: {str(e)}"
            self.logger.error(error, exc_info=True)
            return False, error
    
    def validate_write_path(self, path: str) -> Tuple[bool, str]:
        """Validate path for write operation
        
        Args:
            path: Relative path to file
            
        Returns:
            Tuple of (is_valid, resolved_path_or_error)
        """
        try:
            # Validate and resolve path
            is_valid, result = self._validate_path(path, allow_directory=False)
            
            if not is_valid:
                self.logger.warning(
                    "write_path_validation_failed",
                    path=path,
                    error=result
                )
                return False, result
            
            # Check file extension (prevent writing executables)
            ext = self._get_extension(result).lower()
            if ext in self.FORBIDDEN_EXTENSIONS:
                error = f"Writing to {ext} files is not allowed"
                self.logger.warning(
                    "write_forbidden_extension",
                    path=path,
                    extension=ext
                )
                return False, error
            
            self.logger.debug(
                "write_path_validation_passed",
                path=path,
                resolved_path=result
            )
            return True, result
        
        except Exception as e:
            error = f"Error validating write path {path}: {str(e)}"
            self.logger.error(error, exc_info=True)
            return False, error
    
    def validate_directory_path(self, path: str) -> Tuple[bool, str]:
        """Validate path for directory listing
        
        Args:
            path: Relative path to directory
            
        Returns:
            Tuple of (is_valid, resolved_path_or_error)
        """
        try:
            # Validate and resolve path
            is_valid, result = self._validate_path(path, allow_directory=True)
            
            if not is_valid:
                self.logger.warning(
                    "directory_path_validation_failed",
                    path=path,
                    error=result
                )
                return False, result
            
            self.logger.debug(
                "directory_path_validation_passed",
                path=path,
                resolved_path=result
            )
            return True, result
        
        except Exception as e:
            error = f"Error validating directory path {path}: {str(e)}"
            self.logger.error(error, exc_info=True)
            return False, error
    
    def _validate_path(self, path: str, allow_directory: bool = False) -> Tuple[bool, str]:
        """Validate and resolve path relative to workspace
        
        Prevents path traversal attacks by ensuring the resolved path
        stays within workspace boundaries.
        
        Args:
            path: Potentially unsafe path string
            allow_directory: Whether to allow directory paths
            
        Returns:
            Tuple of (is_valid, resolved_path_or_error)
        """
        if not path:
            return False, "Path cannot be empty"
        
        # Reject suspicious patterns early
        if "\x00" in path:
            return False, "Path contains null character"
        
        # Strip whitespace and normalize separators
        path = path.strip()
        if not path:
            return False, "Path cannot be empty after stripping"
        
        # Normalize the path separator based on workspace root style
        # Client might use different separators
        is_windows = "\\" in self.workspace_root_str or (
            len(self.workspace_root_str) > 2 and self.workspace_root_str[1] == ":"
        )
        
        # Use forward slashes internally for path operations
        path = path.replace("\\", "/")
        
        # Use appropriate path class based on workspace root style
        try:
            if is_windows:
                workspace_pure = PureWindowsPath(self.workspace_root_str)
                path_pure = PureWindowsPath(path)
            else:
                workspace_pure = PurePosixPath(self.workspace_root_str)
                path_pure = PurePosixPath(path)
            
            # Check if path is absolute
            if path_pure.is_absolute():
                # Absolute paths are not allowed for security
                return False, f"Absolute paths are not allowed: {path}"
            
            # Normalize workspace and path separately to remove .. and .
            # This is crucial for path traversal prevention
            workspace_parts = []
            for part in workspace_pure.parts:
                if part in (".", ""):
                    continue
                workspace_parts.append(part)
            
            # Normalize the relative path first
            path_parts = []
            for part in path_pure.parts:
                if part == "." or part == "":
                    continue
                elif part == "..":
                    # Pop from path_parts if possible (stay relative)
                    if path_parts:
                        path_parts.pop()
                    else:
                        # .. at root or beyond - potential traversal
                        return False, f"Path {path} attempts to escape workspace with .."
                else:
                    path_parts.append(part)
            
            # Reconstruct the full path
            full_parts = workspace_parts + path_parts
            
            # Check if we went above workspace root
            if len(full_parts) < len(workspace_parts):
                return False, f"Path {path} is outside workspace boundary"
            
            # Verify that resolved path starts with workspace parts
            for i, ws_part in enumerate(workspace_parts):
                if i >= len(full_parts) or full_parts[i] != ws_part:
                    return False, f"Path {path} is outside workspace boundary"
            
            # Reconstruct resolved path
            if is_windows:
                resolved = PureWindowsPath(*full_parts) if full_parts else PureWindowsPath(self.workspace_root_str)
            else:
                # For Unix paths, preserve leading slash
                if full_parts[0] != "/":
                    resolved = PurePosixPath("/".join(full_parts))
                else:
                    resolved = PurePosixPath(*full_parts)
            
            return True, str(resolved)
        
        except (ValueError, TypeError) as e:
            return False, f"Invalid path syntax: {path} - {str(e)}"
    
    def _is_within_workspace(self, resolved: PurePath, workspace: PurePath) -> bool:
        """Check if resolved path is within workspace boundary
        
        Args:
            resolved: Resolved path to check
            workspace: Workspace root path
            
        Returns:
            True if path is within workspace, False otherwise
        """
        try:
            # Check if resolved path is relative to workspace
            resolved.relative_to(workspace)
            return True
        except ValueError:
            # relative_to raises ValueError if path is not relative
            return False
    
    def _get_extension(self, path_str: str) -> str:
        r"""Get file extension from path string
        
        Args:
            path_str: Path string (may use / or \)
            
        Returns:
            File extension (e.g., '.txt') or empty string
        """
        # Extract filename
        filename = path_str.replace("\\", "/").split("/")[-1]
        
        # Extract extension
        if "." in filename and not filename.startswith("."):
            return "." + filename.rsplit(".", 1)[-1]
        
        return ""
