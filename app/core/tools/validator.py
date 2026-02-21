"""Path Validator for safe file operations"""

import os
from pathlib import Path
from typing import Tuple
from app.logging_config import get_logger

logger = get_logger(__name__)


class PathValidator:
    """Validates file paths for safety and prevents path traversal attacks"""
    
    # Dangerous file extensions that should not be written
    FORBIDDEN_EXTENSIONS = {
        ".exe", ".bin", ".so", ".dll", ".dylib",
        ".sh", ".bat", ".cmd", ".scr", ".msi",
        ".app", ".deb", ".rpm"
    }
    
    # Maximum file size for read operations (100MB)
    MAX_FILE_SIZE = 100 * 1024 * 1024
    
    def __init__(self, workspace_root: str):
        """Initialize validator with workspace root directory
        
        Args:
            workspace_root: Absolute path to workspace root
        """
        self.workspace_root = Path(workspace_root).resolve()
        logger.info(f"PathValidator initialized with workspace: {self.workspace_root}")
    
    def validate_read_path(self, path: str) -> Tuple[bool, str]:
        """Validate path for read operation
        
        Args:
            path: Relative path to file
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            file_path = self._resolve_path(path)
            
            # Check if path is within workspace boundary
            if not self._is_within_workspace(file_path):
                error = f"Path {path} is outside workspace boundary"
                logger.warning(f"Path validation failed: {error}")
                return False, error
            
            # Check if file exists
            if not file_path.exists():
                error = f"File not found: {path}"
                logger.warning(f"Path validation failed: {error}")
                return False, error
            
            # Check if it's a file (not directory)
            if not file_path.is_file():
                error = f"Path is not a file: {path}"
                logger.warning(f"Path validation failed: {error}")
                return False, error
            
            # Check file size
            file_size = file_path.stat().st_size
            if file_size > self.MAX_FILE_SIZE:
                error = f"File too large: {file_size} bytes (max {self.MAX_FILE_SIZE})"
                logger.warning(f"Path validation failed: {error}")
                return False, error
            
            logger.debug(f"Path validation passed for read: {path}")
            return True, str(file_path)
        
        except Exception as e:
            error = f"Error validating read path {path}: {str(e)}"
            logger.error(error)
            return False, error
    
    def validate_write_path(self, path: str) -> Tuple[bool, str]:
        """Validate path for write operation
        
        Args:
            path: Relative path to file
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            file_path = self._resolve_path(path)
            
            # Check if path is within workspace boundary
            if not self._is_within_workspace(file_path):
                error = f"Path {path} is outside workspace boundary"
                logger.warning(f"Path validation failed: {error}")
                return False, error
            
            # Check file extension (prevent writing executables)
            ext = file_path.suffix.lower()
            if ext in self.FORBIDDEN_EXTENSIONS:
                error = f"Writing to {ext} files is not allowed"
                logger.warning(f"Path validation failed: {error}")
                return False, error
            
            # Check if parent directory exists or can be created
            parent = file_path.parent
            if not parent.exists():
                try:
                    parent.mkdir(parents=True, exist_ok=True)
                    logger.debug(f"Created parent directory: {parent}")
                except PermissionError:
                    error = f"Permission denied creating parent directory: {parent}"
                    logger.error(error)
                    return False, error
            
            logger.debug(f"Path validation passed for write: {path}")
            return True, str(file_path)
        
        except Exception as e:
            error = f"Error validating write path {path}: {str(e)}"
            logger.error(error)
            return False, error
    
    def validate_directory_path(self, path: str) -> Tuple[bool, str]:
        """Validate path for directory listing
        
        Args:
            path: Relative path to directory
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            dir_path = self._resolve_path(path)
            
            # Check if path is within workspace boundary
            if not self._is_within_workspace(dir_path):
                error = f"Path {path} is outside workspace boundary"
                logger.warning(f"Path validation failed: {error}")
                return False, error
            
            # Check if directory exists
            if not dir_path.exists():
                error = f"Directory not found: {path}"
                logger.warning(f"Path validation failed: {error}")
                return False, error
            
            # Check if it's a directory
            if not dir_path.is_dir():
                error = f"Path is not a directory: {path}"
                logger.warning(f"Path validation failed: {error}")
                return False, error
            
            logger.debug(f"Path validation passed for directory: {path}")
            return True, str(dir_path)
        
        except Exception as e:
            error = f"Error validating directory path {path}: {str(e)}"
            logger.error(error)
            return False, error
    
    def _resolve_path(self, path: str) -> Path:
        """Resolve path safely relative to workspace root
        
        Args:
            path: Potentially unsafe path string
            
        Returns:
            Resolved absolute Path object
        """
        # Treat path as relative to workspace root
        abs_path = self.workspace_root / path
        return abs_path.resolve()
    
    def _is_within_workspace(self, path: Path) -> bool:
        """Check if path is within workspace boundary
        
        Prevents path traversal attacks (../, symlinks, etc.)
        
        Args:
            path: Path to check
            
        Returns:
            True if path is within workspace, False otherwise
        """
        try:
            # Resolve both paths to absolute
            resolved = path.resolve()
            workspace = self.workspace_root.resolve()
            
            # Check if resolved path starts with workspace path
            # This prevents directory traversal
            resolved.relative_to(workspace)
            return True
        except ValueError:
            # relative_to raises ValueError if path is not relative
            return False
