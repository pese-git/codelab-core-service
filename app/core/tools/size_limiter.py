"""Size Limiter for tool operations to prevent resource exhaustion"""

from typing import Tuple
from app.logging_config import get_logger

logger = get_logger(__name__)


class SizeLimiter:
    """Manage size and resource limits for tool operations
    
    Prevents resource exhaustion attacks by limiting:
    - File sizes for read/write operations
    - Command output sizes
    - Command execution timeout
    - Number of items in directory listings
    """
    
    # Maximum file size for read operations (100MB)
    MAX_FILE_READ_SIZE = 100 * 1024 * 1024
    
    # Maximum file size for write operations (100MB)
    MAX_FILE_WRITE_SIZE = 100 * 1024 * 1024
    
    # Maximum command output size (1MB)
    MAX_OUTPUT_SIZE = 1 * 1024 * 1024
    
    # Maximum command execution timeout (300 seconds = 5 minutes)
    MAX_COMMAND_TIMEOUT = 300
    
    # Minimum command execution timeout (1 second)
    MIN_COMMAND_TIMEOUT = 1
    
    # Maximum items to list in directory (prevents memory exhaustion)
    MAX_DIRECTORY_ITEMS = 1000
    
    @staticmethod
    def validate_read_size(file_size: int) -> Tuple[bool, str]:
        """Validate file size for reading
        
        Args:
            file_size: Size of file in bytes
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if file_size > SizeLimiter.MAX_FILE_READ_SIZE:
            error = (
                f"File too large for read ({file_size:,} bytes > "
                f"{SizeLimiter.MAX_FILE_READ_SIZE:,} bytes)"
            )
            logger.warning(error)
            return False, error
        return True, ""
    
    @staticmethod
    def validate_write_size(content_size: int) -> Tuple[bool, str]:
        """Validate content size for writing
        
        Args:
            content_size: Size of content to write in bytes
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if content_size > SizeLimiter.MAX_FILE_WRITE_SIZE:
            error = (
                f"Content too large for write ({content_size:,} bytes > "
                f"{SizeLimiter.MAX_FILE_WRITE_SIZE:,} bytes)"
            )
            logger.warning(error)
            return False, error
        return True, ""
    
    @staticmethod
    def validate_output_size(output_size: int) -> Tuple[bool, str]:
        """Validate command output size
        
        Args:
            output_size: Size of command output in bytes
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if output_size > SizeLimiter.MAX_OUTPUT_SIZE:
            error = (
                f"Output too large ({output_size:,} bytes > "
                f"{SizeLimiter.MAX_OUTPUT_SIZE:,} bytes)"
            )
            logger.warning(error)
            return False, error
        return True, ""
    
    @staticmethod
    def validate_timeout(timeout: int) -> Tuple[bool, str]:
        """Validate command execution timeout
        
        Args:
            timeout: Timeout in seconds
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if timeout < SizeLimiter.MIN_COMMAND_TIMEOUT:
            error = f"Timeout too short ({timeout}s < {SizeLimiter.MIN_COMMAND_TIMEOUT}s)"
            logger.warning(error)
            return False, error
        
        if timeout > SizeLimiter.MAX_COMMAND_TIMEOUT:
            error = (
                f"Timeout too long ({timeout}s > {SizeLimiter.MAX_COMMAND_TIMEOUT}s)"
            )
            logger.warning(error)
            return False, error
        
        return True, ""
    
    @staticmethod
    def validate_directory_count(count: int) -> Tuple[bool, str]:
        """Validate directory item count
        
        Args:
            count: Number of items in directory
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if count > SizeLimiter.MAX_DIRECTORY_ITEMS:
            error = (
                f"Too many items in directory ({count} > "
                f"{SizeLimiter.MAX_DIRECTORY_ITEMS})"
            )
            logger.warning(error)
            return False, error
        
        return True, ""
    
    @staticmethod
    def truncate_output(
        output: str,
        max_size: int = MAX_OUTPUT_SIZE
    ) -> str:
        """Truncate output to maximum size safely
        
        Handles UTF-8 encoding boundaries to avoid breaking output
        
        Args:
            output: Output string to truncate
            max_size: Maximum size in bytes
            
        Returns:
            Truncated output with notice if truncated
        """
        output_bytes = output.encode('utf-8')
        
        if len(output_bytes) > max_size:
            # Safely truncate at UTF-8 boundary
            truncated = output_bytes[:max_size].decode('utf-8', errors='ignore')
            return truncated + "\n... [output truncated]"
        
        return output
    
    @staticmethod
    def format_size(size_bytes: int) -> str:
        """Format bytes to human-readable size
        
        Args:
            size_bytes: Size in bytes
            
        Returns:
            Human-readable size string (e.g., "1.5 MB")
        """
        units = ['B', 'KB', 'MB', 'GB']
        size = float(size_bytes)
        
        for unit in units[:-1]:
            if size < 1024:
                return f"{size:.2f} {unit}"
            size /= 1024
        
        return f"{size:.2f} {units[-1]}"
    
    @staticmethod
    def is_within_limits(
        file_size: int = 0,
        content_size: int = 0,
        output_size: int = 0,
        timeout: int = 30,
        directory_items: int = 0
    ) -> Tuple[bool, str]:
        """Check all limits at once
        
        Convenience method to validate multiple limits together
        
        Args:
            file_size: Size of file being read
            content_size: Size of content being written
            output_size: Size of command output
            timeout: Command timeout
            directory_items: Number of items to list
            
        Returns:
            Tuple of (all_valid, combined_error_message)
        """
        errors = []
        
        if file_size > 0:
            is_valid, error = SizeLimiter.validate_read_size(file_size)
            if not is_valid:
                errors.append(error)
        
        if content_size > 0:
            is_valid, error = SizeLimiter.validate_write_size(content_size)
            if not is_valid:
                errors.append(error)
        
        if output_size > 0:
            is_valid, error = SizeLimiter.validate_output_size(output_size)
            if not is_valid:
                errors.append(error)
        
        if timeout > 0:
            is_valid, error = SizeLimiter.validate_timeout(timeout)
            if not is_valid:
                errors.append(error)
        
        if directory_items > 0:
            is_valid, error = SizeLimiter.validate_directory_count(directory_items)
            if not is_valid:
                errors.append(error)
        
        if errors:
            combined_error = " | ".join(errors)
            logger.warning(f"Size validation failed: {combined_error}")
            return False, combined_error
        
        return True, ""
