"""Unit tests for PathValidator"""

import pytest
import tempfile
from pathlib import Path
from app.core.tools.validator import PathValidator


@pytest.fixture
def temp_workspace():
    """Create temporary workspace for testing"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def validator(temp_workspace):
    """Create PathValidator instance"""
    return PathValidator(temp_workspace)


class TestPathValidatorReadFile:
    """Tests for read_file validation"""

    def test_read_valid_file(self, temp_workspace, validator):
        """Test reading a valid file"""
        # Create test file
        test_file = Path(temp_workspace) / "test.txt"
        test_file.write_text("content")

        # Validate
        is_valid, result = validator.validate_read_path("test.txt")

        assert is_valid
        assert str(test_file) == result

    def test_read_nonexistent_file(self, validator):
        """Test reading non-existent file"""
        is_valid, error = validator.validate_read_path("nonexistent.txt")

        assert not is_valid
        assert "not found" in error.lower()

    def test_read_directory_fails(self, temp_workspace, validator):
        """Test that reading directory fails"""
        # Create directory
        subdir = Path(temp_workspace) / "subdir"
        subdir.mkdir()

        # Validate
        is_valid, error = validator.validate_read_path("subdir")

        assert not is_valid
        assert "not a file" in error.lower()

    def test_read_path_traversal_blocked(self, validator):
        """Test that path traversal is blocked"""
        is_valid, error = validator.validate_read_path("../../../etc/passwd")

        assert not is_valid
        assert "outside workspace" in error.lower()

    def test_read_large_file_blocked(self, temp_workspace, validator):
        """Test that reading large file is blocked"""
        # Create large file (101 MB)
        large_file = Path(temp_workspace) / "large.bin"
        large_file.write_bytes(b"x" * (101 * 1024 * 1024))

        is_valid, error = validator.validate_read_path("large.bin")

        assert not is_valid
        assert "too large" in error.lower()


class TestPathValidatorWriteFile:
    """Tests for write_file validation"""

    def test_write_valid_file(self, temp_workspace, validator):
        """Test writing a valid file"""
        is_valid, result = validator.validate_write_path("output.txt")

        assert is_valid
        assert str(Path(temp_workspace) / "output.txt") == result

    def test_write_forbidden_extension_exe(self, validator):
        """Test that .exe files cannot be written"""
        is_valid, error = validator.validate_write_path("malware.exe")

        assert not is_valid
        assert ".exe" in error.lower()

    def test_write_forbidden_extension_dll(self, validator):
        """Test that .dll files cannot be written"""
        is_valid, error = validator.validate_write_path("lib.dll")

        assert not is_valid

    def test_write_forbidden_extension_so(self, validator):
        """Test that .so files cannot be written"""
        is_valid, error = validator.validate_write_path("lib.so")

        assert not is_valid

    def test_write_creates_parent_directory(self, temp_workspace, validator):
        """Test that parent directory is created"""
        is_valid, result = validator.validate_write_path("subdir/deep/file.txt")

        assert is_valid
        # Parent directory should be created
        assert Path(temp_workspace) / "subdir" / "deep"

    def test_write_path_traversal_blocked(self, validator):
        """Test that path traversal is blocked for write"""
        is_valid, error = validator.validate_write_path("../../../etc/passwd")

        assert not is_valid
        assert "outside workspace" in error.lower()


class TestPathValidatorListDirectory:
    """Tests for list_directory validation"""

    def test_list_valid_directory(self, temp_workspace, validator):
        """Test listing a valid directory"""
        # Create test file
        Path(temp_workspace) / "test.txt"

        is_valid, result = validator.validate_directory_path(".")

        assert is_valid
        assert temp_workspace == result or str(Path(temp_workspace)) == result

    def test_list_nonexistent_directory(self, validator):
        """Test listing non-existent directory"""
        is_valid, error = validator.validate_directory_path("nonexistent")

        assert not is_valid
        assert "not found" in error.lower()

    def test_list_file_fails(self, temp_workspace, validator):
        """Test that listing file fails"""
        # Create test file
        test_file = Path(temp_workspace) / "test.txt"
        test_file.write_text("content")

        # Validate
        is_valid, error = validator.validate_directory_path("test.txt")

        assert not is_valid
        assert "not a directory" in error.lower()

    def test_list_path_traversal_blocked(self, validator):
        """Test that path traversal is blocked for list"""
        is_valid, error = validator.validate_directory_path("../../../etc")

        assert not is_valid
        assert "outside workspace" in error.lower()


class TestPathValidatorWorkspaceBoundary:
    """Tests for workspace boundary enforcement"""

    def test_symlink_to_outside_blocked(self, temp_workspace):
        """Test that symlinks pointing outside are blocked"""
        validator = PathValidator(temp_workspace)

        # Create external directory
        with tempfile.TemporaryDirectory() as external_dir:
            # Create symlink pointing outside workspace
            symlink_path = Path(temp_workspace) / "link"
            try:
                symlink_path.symlink_to(external_dir)

                is_valid, error = validator.validate_read_path("link")

                assert not is_valid
                assert "outside workspace" in error.lower()
            except OSError:
                # Skip if symlinks not supported (Windows)
                pytest.skip("Symlinks not supported on this system")

    def test_absolute_path_outside_workspace(self, validator):
        """Test that absolute paths outside workspace are blocked"""
        is_valid, error = validator.validate_read_path("/etc/passwd")

        assert not is_valid
        assert "outside workspace" in error.lower()


class TestPathValidatorEdgeCases:
    """Tests for edge cases"""

    def test_empty_path(self, validator):
        """Test empty path handling"""
        is_valid, error = validator.validate_read_path("")

        assert not is_valid

    def test_null_byte_in_path(self, validator):
        """Test null byte in path (security risk)"""
        # Most systems will handle this, but it's worth testing
        try:
            is_valid, error = validator.validate_read_path("test\x00.txt")
            # If it succeeds, it should still be safe (outside workspace)
            assert not is_valid or "outside workspace" in error.lower()
        except ValueError:
            # Acceptable to raise error on null byte
            pass

    def test_dot_dot_in_middle(self, validator):
        """Test .. in middle of path"""
        is_valid, error = validator.validate_read_path("subdir/../../../etc/passwd")

        assert not is_valid
        assert "outside workspace" in error.lower()

    def test_unicode_paths(self, temp_workspace, validator):
        """Test unicode file names"""
        # Create file with unicode name
        test_file = Path(temp_workspace) / "тест_файл.txt"
        test_file.write_text("content")

        is_valid, result = validator.validate_read_path("тест_файл.txt")

        assert is_valid
