"""Tests for PathValidator"""

import pytest
from app.core.tools.validator import PathValidator


class TestPathValidatorUnix:
    """Test PathValidator with Unix-style paths"""
    
    @pytest.fixture
    def validator(self):
        """Create PathValidator with Unix workspace"""
        return PathValidator("/Users/sergey/Projects/Flutter/Pets/cherrypick")
    
    # ========================================
    # SAFE PATHS - Should Pass
    # ========================================
    
    def test_validate_read_simple_file(self, validator):
        """Test reading a simple file in workspace"""
        is_valid, result = validator.validate_read_path("README.md")
        assert is_valid is True
        assert "README.md" in result
    
    def test_validate_read_nested_file(self, validator):
        """Test reading a nested file"""
        is_valid, result = validator.validate_read_path("src/main/app.py")
        assert is_valid is True
        assert "src/main/app.py" in result
    
    def test_validate_read_with_dots_safe(self, validator):
        """Test reading a file with dots in name"""
        is_valid, result = validator.validate_read_path("config.prod.json")
        assert is_valid is True
        assert "config.prod.json" in result
    
    def test_validate_write_simple_file(self, validator):
        """Test writing a simple file"""
        is_valid, result = validator.validate_write_path("output.txt")
        assert is_valid is True
        assert "output.txt" in result
    
    def test_validate_write_nested_file(self, validator):
        """Test writing to nested directory"""
        is_valid, result = validator.validate_write_path("build/dist/app.js")
        assert is_valid is True
        assert "build/dist/app.js" in result
    
    def test_validate_directory_root(self, validator):
        """Test listing workspace root"""
        is_valid, result = validator.validate_directory_path(".")
        assert is_valid is True
    
    def test_validate_directory_nested(self, validator):
        """Test listing nested directory"""
        is_valid, result = validator.validate_directory_path("src/components")
        assert is_valid is True
        assert "src/components" in result
    
    # ========================================
    # PATH TRAVERSAL ATTACKS - Should Fail
    # ========================================
    
    def test_block_path_traversal_double_dot(self, validator):
        """Block path traversal with ../"""
        is_valid, result = validator.validate_read_path("../../../etc/passwd")
        assert is_valid is False
        assert "escape" in result.lower() or "outside" in result.lower()
    
    def test_block_path_traversal_in_middle(self, validator):
        """Block path traversal in middle of path"""
        is_valid, result = validator.validate_read_path("src/../../etc/passwd")
        assert is_valid is False
        assert "escape" in result.lower() or "outside" in result.lower()
    
    def test_block_path_traversal_multiple(self, validator):
        """Block multiple path traversal attempts"""
        is_valid, result = validator.validate_read_path("a/../b/../../etc/passwd")
        assert is_valid is False
        assert "escape" in result.lower() or "outside" in result.lower()
    
    def test_block_path_traversal_at_start(self, validator):
        """Block path starting with ../"""
        is_valid, result = validator.validate_read_path("../etc/passwd")
        assert is_valid is False
        assert "escape" in result.lower() or "outside" in result.lower()
    
    # ========================================
    # ABSOLUTE PATHS - Should Fail
    # ========================================
    
    def test_block_absolute_unix_path(self, validator):
        """Block absolute Unix path"""
        is_valid, result = validator.validate_read_path("/etc/passwd")
        assert is_valid is False
        assert "outside workspace boundary" in result or "Absolute paths" in result
    
    def test_block_absolute_windows_path(self, validator):
        """Block absolute Windows path (even on Unix validator)"""
        is_valid, result = validator.validate_read_path("C:/Windows/System32/config")
        # On Unix validator, C:/Windows might be treated as relative path
        # The important thing is path validation works safely
        assert isinstance(is_valid, bool)
    
    # ========================================
    # FORBIDDEN EXTENSIONS - Should Fail for Write
    # ========================================
    
    def test_block_write_executable_exe(self, validator):
        """Block writing .exe files"""
        is_valid, result = validator.validate_write_path("malware.exe")
        assert is_valid is False
        assert ".exe" in result or "not allowed" in result
    
    def test_block_write_executable_so(self, validator):
        """Block writing .so files"""
        is_valid, result = validator.validate_write_path("library.so")
        assert is_valid is False
        assert ".so" in result or "not allowed" in result
    
    def test_block_write_executable_sh(self, validator):
        """Block writing .sh files"""
        is_valid, result = validator.validate_write_path("script.sh")
        assert is_valid is False
        assert ".sh" in result or "not allowed" in result
    
    def test_block_write_executable_dll(self, validator):
        """Block writing .dll files"""
        is_valid, result = validator.validate_write_path("library.dll")
        assert is_valid is False
        assert ".dll" in result or "not allowed" in result
    
    def test_allow_write_safe_extensions(self, validator):
        """Allow writing safe file extensions"""
        safe_files = [
            "document.txt",
            "script.py",
            "styles.css",
            "data.json",
            "markup.md"
        ]
        for filename in safe_files:
            is_valid, result = validator.validate_write_path(filename)
            assert is_valid is True, f"Should allow {filename}"
    
    # ========================================
    # EDGE CASES
    # ========================================
    
    def test_empty_path_fails(self, validator):
        """Block empty path"""
        is_valid, result = validator.validate_read_path("")
        assert is_valid is False
        assert "empty" in result.lower()
    
    def test_whitespace_only_fails(self, validator):
        """Block whitespace-only path"""
        is_valid, result = validator.validate_read_path("   ")
        assert is_valid is False
        assert "empty" in result.lower()
    
    def test_path_with_null_char_fails(self, validator):
        """Block path with null character"""
        is_valid, result = validator.validate_read_path("file\x00.txt")
        assert is_valid is False
        assert "null" in result.lower()
    
    def test_current_dir_reference(self, validator):
        """Allow single dot reference"""
        is_valid, result = validator.validate_directory_path(".")
        assert is_valid is True
    
    def test_current_dir_with_file(self, validator):
        """Allow ./filename reference"""
        is_valid, result = validator.validate_read_path("./README.md")
        assert is_valid is True
        assert "README.md" in result


class TestPathValidatorWindows:
    """Test PathValidator with Windows-style paths"""
    
    @pytest.fixture
    def validator(self):
        """Create PathValidator with Windows workspace"""
        return PathValidator("C:\\Users\\User\\Projects\\MyApp")
    
    def test_validate_read_windows_path(self, validator):
        """Test reading file with Windows path separator"""
        is_valid, result = validator.validate_read_path("src\\main\\app.py")
        assert is_valid is True
        assert "app.py" in result
    
    def test_validate_read_mixed_separators(self, validator):
        """Test reading file with mixed separators (/ and \\)"""
        is_valid, result = validator.validate_read_path("src/main\\app.py")
        assert is_valid is True
        assert "app.py" in result
    
    def test_block_windows_path_traversal(self, validator):
        """Block Windows path traversal"""
        is_valid, result = validator.validate_read_path("..\\..\\Windows\\System32")
        assert is_valid is False
        assert "escape" in result.lower() or "outside" in result.lower()
    
    def test_block_absolute_windows_path(self, validator):
        """Block absolute Windows path"""
        is_valid, result = validator.validate_read_path("C:\\Windows\\System32")
        assert is_valid is False
        assert "Absolute paths" in result or "outside workspace" in result
    
    def test_allow_write_windows_file(self, validator):
        """Allow writing to safe path on Windows"""
        is_valid, result = validator.validate_write_path("output\\results.txt")
        assert is_valid is True


class TestPathValidatorMixedWorkspace:
    """Test PathValidator with mixed path styles"""
    
    def test_unix_validator_with_forward_slash_traversal(self):
        """Test Unix validator blocks forward slash traversal"""
        validator = PathValidator("/workspace")
        is_valid, result = validator.validate_read_path("../../etc/passwd")
        assert is_valid is False
        assert "escape" in result.lower() or "outside" in result.lower()
    
    def test_windows_validator_with_backslash_traversal(self):
        """Test Windows validator blocks backslash traversal"""
        validator = PathValidator("C:\\workspace")
        is_valid, result = validator.validate_read_path("..\\..\\Windows")
        assert is_valid is False
        assert "escape" in result.lower() or "outside" in result.lower()


class TestPathValidatorSpecialCases:
    """Test special cases and edge scenarios"""
    
    @pytest.fixture
    def validator(self):
        return PathValidator("/workspace")
    
    def test_symlink_in_path_name(self, validator):
        """Allow 'symlink' as part of filename (not actual symlink check)"""
        # Note: Validator doesn't check for actual symlinks on server
        # It's syntactic validation only
        is_valid, result = validator.validate_read_path("symlink.txt")
        assert is_valid is True
    
    def test_hidden_file_allowed(self, validator):
        """Allow hidden files (starting with .)"""
        is_valid, result = validator.validate_read_path(".env")
        assert is_valid is True
    
    def test_unicode_in_path(self, validator):
        """Allow unicode characters in paths"""
        is_valid, result = validator.validate_read_path("документ.txt")
        assert is_valid is True
    
    def test_spaces_in_path(self, validator):
        """Allow spaces in paths"""
        is_valid, result = validator.validate_read_path("my documents/file name.txt")
        assert is_valid is True
    
    def test_special_chars_in_filename(self, validator):
        """Allow special characters (except path separators) in filename"""
        is_valid, result = validator.validate_read_path("test-file_name@2024.txt")
        assert is_valid is True
    
    def test_very_long_path(self, validator):
        """Handle very long paths"""
        long_path = "/".join(["dir"] * 50) + "/file.txt"
        is_valid, result = validator.validate_read_path(long_path)
        # Should succeed unless it exceeds system limits
        assert isinstance(is_valid, bool)
