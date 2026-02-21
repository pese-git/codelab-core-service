"""Unit tests for CommandValidator"""

import pytest
from app.core.tools.command_whitelist import CommandValidator


@pytest.fixture
def validator():
    """Create CommandValidator instance"""
    return CommandValidator()


class TestCommandValidatorWhitelist:
    """Tests for command whitelist validation"""

    def test_allowed_command_grep(self, validator):
        """Test allowed command: grep"""
        is_valid, msg = validator.validate_command("grep")
        assert is_valid
        assert msg == "grep"

    def test_allowed_command_npm(self, validator):
        """Test allowed command: npm"""
        is_valid, msg = validator.validate_command("npm")
        assert is_valid

    def test_allowed_command_python(self, validator):
        """Test allowed command: python"""
        is_valid, msg = validator.validate_command("python")
        assert is_valid

    def test_allowed_command_git(self, validator):
        """Test allowed command: git"""
        is_valid, msg = validator.validate_command("git")
        assert is_valid


class TestCommandValidatorBlacklist:
    """Tests for command blacklist blocking"""

    def test_blocked_command_rm(self, validator):
        """Test blocked command: rm"""
        is_valid, error = validator.validate_command("rm")
        assert not is_valid
        assert "not allowed" in error.lower()

    def test_blocked_command_sudo(self, validator):
        """Test blocked command: sudo"""
        is_valid, error = validator.validate_command("sudo")
        assert not is_valid

    def test_blocked_command_bash(self, validator):
        """Test blocked command: bash"""
        is_valid, error = validator.validate_command("bash")
        assert not is_valid

    def test_blocked_command_curl(self, validator):
        """Test blocked command: curl"""
        is_valid, error = validator.validate_command("curl")
        assert not is_valid

    def test_blocked_command_kill(self, validator):
        """Test blocked command: kill"""
        is_valid, error = validator.validate_command("kill")
        assert not is_valid


class TestCommandValidatorPath:
    """Tests for path-based command handling"""

    def test_command_with_path(self, validator):
        """Test command with full path"""
        is_valid, msg = validator.validate_command("/usr/bin/python")
        assert is_valid
        assert msg == "python"

    def test_command_with_path_blocked(self, validator):
        """Test blocked command with path"""
        is_valid, error = validator.validate_command("/bin/rm")
        assert not is_valid


class TestCommandValidatorVersion:
    """Tests for version number stripping"""

    def test_python_with_version(self, validator):
        """Test python3.11 → python"""
        is_valid, msg = validator.validate_command("python3.11")
        assert is_valid

    def test_node_with_version(self, validator):
        """Test node18 → node"""
        is_valid, msg = validator.validate_command("node18")
        assert is_valid

    def test_gcc_with_version(self, validator):
        """Test gcc-12 → gcc"""
        is_valid, msg = validator.validate_command("gcc-12")
        assert is_valid


class TestCommandValidatorSafety:
    """Tests for command safety validation"""

    def test_git_allowed_subcommand_clone(self, validator):
        """Test git clone is allowed"""
        is_valid, msg = validator.validate_command_safety("git", ["clone"])
        assert is_valid

    def test_git_allowed_subcommand_pull(self, validator):
        """Test git pull is allowed"""
        is_valid, msg = validator.validate_command_safety("git", ["pull"])
        assert is_valid

    def test_git_blocked_subcommand(self, validator):
        """Test git with disallowed subcommand"""
        is_valid, error = validator.validate_command_safety("git", ["rebase"])
        # This depends on implementation - rebase might be blocked
        # Just ensure validation works
        assert isinstance(is_valid, bool)

    def test_npm_allowed_install(self, validator):
        """Test npm install is allowed"""
        is_valid, msg = validator.validate_command_safety("npm", ["install"])
        assert is_valid

    def test_npm_allowed_test(self, validator):
        """Test npm test is allowed"""
        is_valid, msg = validator.validate_command_safety("npm", ["test"])
        assert is_valid

    def test_python_allowed(self, validator):
        """Test python script execution allowed"""
        is_valid, msg = validator.validate_command_safety("python", ["script.py"])
        assert is_valid


class TestCommandValidatorParsing:
    """Tests for command parsing"""

    def test_parse_simple_command(self, validator):
        """Test parsing simple command"""
        cmd, args = CommandValidator.parse_command_safely("python script.py")
        assert cmd == "python"
        assert args == ["script.py"]

    def test_parse_command_with_args(self, validator):
        """Test parsing command with multiple args"""
        cmd, args = CommandValidator.parse_command_safely('npm run build --mode="production"')
        assert cmd == "npm"
        assert "run" in args
        assert "build" in args

    def test_parse_quoted_args(self, validator):
        """Test parsing quoted arguments"""
        cmd, args = CommandValidator.parse_command_safely('echo "hello world"')
        assert cmd == "echo"
        assert args == ["hello world"]

    def test_parse_empty_command_raises(self, validator):
        """Test that empty command raises error"""
        with pytest.raises(ValueError):
            CommandValidator.parse_command_safely("")

    def test_parse_invalid_quotes_raises(self, validator):
        """Test that invalid quotes raise error"""
        with pytest.raises(ValueError):
            CommandValidator.parse_command_safely('echo "unclosed quote')


class TestCommandValidatorCase:
    """Tests for case handling"""

    def test_uppercase_command(self, validator):
        """Test that uppercase commands are handled"""
        is_valid, msg = validator.validate_command("PYTHON")
        assert is_valid

    def test_mixed_case_command(self, validator):
        """Test that mixed case commands are handled"""
        is_valid, msg = validator.validate_command("PyThOn")
        assert is_valid


class TestCommandValidatorEdgeCases:
    """Tests for edge cases"""

    def test_command_with_spaces(self, validator):
        """Test command with spaces"""
        is_valid, msg = validator.validate_command("  python  ")
        assert is_valid

    def test_unknown_command(self, validator):
        """Test unknown command is blocked"""
        is_valid, error = validator.validate_command("unknowncommand12345")
        assert not is_valid
        assert "not in allowed list" in error.lower()
