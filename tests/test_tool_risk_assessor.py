"""Unit tests for RiskAssessor"""

import pytest
from app.core.tools.risk_assessor import RiskAssessor, RiskLevel


@pytest.fixture
def assessor():
    """Create RiskAssessor instance"""
    return RiskAssessor()


class TestRiskAssessorReadFile:
    """Tests for read_file risk assessment"""

    def test_read_file_is_low_risk(self, assessor):
        """Test that read_file is always LOW risk"""
        risk = assessor.assess_tool_risk("read_file", {"path": "file.txt"})
        assert risk == RiskLevel.LOW

    def test_read_file_no_approval(self, assessor):
        """Test that read_file doesn't require approval"""
        risk = assessor.assess_tool_risk("read_file", {"path": "file.txt"})
        assert not assessor.requires_approval(risk)


class TestRiskAssessorListDirectory:
    """Tests for list_directory risk assessment"""

    def test_list_directory_is_low_risk(self, assessor):
        """Test that list_directory is always LOW risk"""
        risk = assessor.assess_tool_risk("list_directory", {"path": "."})
        assert risk == RiskLevel.LOW

    def test_list_directory_no_approval(self, assessor):
        """Test that list_directory doesn't require approval"""
        risk = assessor.assess_tool_risk("list_directory", {"path": "."})
        assert not assessor.requires_approval(risk)


class TestRiskAssessorWriteFile:
    """Tests for write_file risk assessment"""

    def test_write_python_file_is_medium_risk(self, assessor):
        """Test that writing .py file is MEDIUM risk"""
        risk = assessor.assess_tool_risk("write_file", {"path": "script.py"})
        assert risk == RiskLevel.MEDIUM

    def test_write_json_file_is_medium_risk(self, assessor):
        """Test that writing .json file is MEDIUM risk"""
        risk = assessor.assess_tool_risk("write_file", {"path": "config.json"})
        assert risk == RiskLevel.MEDIUM

    def test_write_markdown_file_is_medium_risk(self, assessor):
        """Test that writing .md file is MEDIUM risk"""
        risk = assessor.assess_tool_risk("write_file", {"path": "README.md"})
        assert risk == RiskLevel.MEDIUM

    def test_write_exe_file_is_high_risk(self, assessor):
        """Test that writing .exe file is HIGH risk"""
        risk = assessor.assess_tool_risk("write_file", {"path": "app.exe"})
        assert risk == RiskLevel.HIGH

    def test_write_dll_file_is_high_risk(self, assessor):
        """Test that writing .dll file is HIGH risk"""
        risk = assessor.assess_tool_risk("write_file", {"path": "lib.dll"})
        assert risk == RiskLevel.HIGH

    def test_write_unknown_extension_is_medium_risk(self, assessor):
        """Test that unknown extension defaults to MEDIUM"""
        risk = assessor.assess_tool_risk("write_file", {"path": "file.unknown"})
        assert risk == RiskLevel.MEDIUM


class TestRiskAssessorExecuteCommand:
    """Tests for execute_command risk assessment"""

    def test_grep_is_low_risk(self, assessor):
        """Test that grep is LOW risk"""
        risk = assessor.assess_tool_risk("execute_command", {"command": "grep"})
        assert risk == RiskLevel.LOW

    def test_find_is_low_risk(self, assessor):
        """Test that find is LOW risk"""
        risk = assessor.assess_tool_risk("execute_command", {"command": "find"})
        assert risk == RiskLevel.LOW

    def test_ls_is_low_risk(self, assessor):
        """Test that ls is LOW risk"""
        risk = assessor.assess_tool_risk("execute_command", {"command": "ls"})
        assert risk == RiskLevel.LOW

    def test_git_is_medium_risk(self, assessor):
        """Test that git is MEDIUM risk"""
        risk = assessor.assess_tool_risk("execute_command", {"command": "git"})
        assert risk == RiskLevel.MEDIUM

    def test_npm_is_medium_risk(self, assessor):
        """Test that npm is MEDIUM risk"""
        risk = assessor.assess_tool_risk("execute_command", {"command": "npm"})
        assert risk == RiskLevel.MEDIUM

    def test_python_is_medium_risk(self, assessor):
        """Test that python is MEDIUM risk"""
        risk = assessor.assess_tool_risk("execute_command", {"command": "python"})
        assert risk == RiskLevel.MEDIUM

    def test_gcc_is_high_risk(self, assessor):
        """Test that gcc is HIGH risk"""
        risk = assessor.assess_tool_risk("execute_command", {"command": "gcc"})
        assert risk == RiskLevel.HIGH

    def test_make_is_high_risk(self, assessor):
        """Test that make is HIGH risk"""
        risk = assessor.assess_tool_risk("execute_command", {"command": "make"})
        assert risk == RiskLevel.HIGH

    def test_tar_is_high_risk(self, assessor):
        """Test that tar is HIGH risk"""
        risk = assessor.assess_tool_risk("execute_command", {"command": "tar"})
        assert risk == RiskLevel.HIGH

    def test_unknown_command_is_high_risk(self, assessor):
        """Test that unknown command defaults to HIGH"""
        risk = assessor.assess_tool_risk("execute_command", {"command": "unknowncmd"})
        assert risk == RiskLevel.HIGH


class TestRiskAssessorTimeout:
    """Tests for timeout determination"""

    def test_low_risk_timeout_is_zero(self, assessor):
        """Test that LOW risk has zero timeout (no approval)"""
        timeout = assessor.get_timeout_for_risk_level(RiskLevel.LOW)
        assert timeout == 0

    def test_medium_risk_timeout_is_300(self, assessor):
        """Test that MEDIUM risk has 300s timeout"""
        timeout = assessor.get_timeout_for_risk_level(RiskLevel.MEDIUM)
        assert timeout == 300

    def test_high_risk_timeout_is_600(self, assessor):
        """Test that HIGH risk has 600s timeout"""
        timeout = assessor.get_timeout_for_risk_level(RiskLevel.HIGH)
        assert timeout == 600


class TestRiskAssessorApprovalRequirement:
    """Tests for approval requirement determination"""

    def test_low_risk_no_approval(self, assessor):
        """Test that LOW risk doesn't require approval"""
        assert not assessor.requires_approval(RiskLevel.LOW)

    def test_medium_risk_requires_approval(self, assessor):
        """Test that MEDIUM risk requires approval"""
        assert assessor.requires_approval(RiskLevel.MEDIUM)

    def test_high_risk_requires_approval(self, assessor):
        """Test that HIGH risk requires approval"""
        assert assessor.requires_approval(RiskLevel.HIGH)


class TestRiskAssessorPathHandling:
    """Tests for path-based commands"""

    def test_full_path_command(self, assessor):
        """Test command with full path"""
        risk = assessor.assess_tool_risk(
            "execute_command",
            {"command": "/usr/bin/python"}
        )
        assert risk == RiskLevel.MEDIUM

    def test_version_stripped_from_command(self, assessor):
        """Test that version numbers are stripped"""
        risk = assessor.assess_tool_risk(
            "execute_command",
            {"command": "python3.11"}
        )
        assert risk == RiskLevel.MEDIUM


class TestRiskAssessorFullAssessment:
    """Tests for full risk assessment"""

    def test_full_assessment_structure(self, assessor):
        """Test that full assessment returns required fields"""
        assessment = assessor.get_full_risk_assessment(
            "write_file",
            {"path": "config.json"}
        )

        assert "tool_name" in assessment
        assert "risk_level" in assessment
        assert "requires_approval" in assessment
        assert "approval_timeout_seconds" in assessment
        assert "description" in assessment

    def test_full_assessment_low_risk(self, assessor):
        """Test full assessment for LOW risk tool"""
        assessment = assessor.get_full_risk_assessment(
            "read_file",
            {"path": "file.txt"}
        )

        assert assessment["risk_level"] == "LOW"
        assert not assessment["requires_approval"]
        assert assessment["approval_timeout_seconds"] == 0

    def test_full_assessment_medium_risk(self, assessor):
        """Test full assessment for MEDIUM risk tool"""
        assessment = assessor.get_full_risk_assessment(
            "write_file",
            {"path": "script.py"}
        )

        assert assessment["risk_level"] == "MEDIUM"
        assert assessment["requires_approval"]
        assert assessment["approval_timeout_seconds"] == 300

    def test_full_assessment_high_risk(self, assessor):
        """Test full assessment for HIGH risk tool"""
        assessment = assessor.get_full_risk_assessment(
            "execute_command",
            {"command": "gcc"}
        )

        assert assessment["risk_level"] == "HIGH"
        assert assessment["requires_approval"]
        assert assessment["approval_timeout_seconds"] == 600


class TestRiskAssessorEdgeCases:
    """Tests for edge cases"""

    def test_unknown_tool_is_high_risk(self, assessor):
        """Test that unknown tool defaults to HIGH"""
        risk = assessor.assess_tool_risk("unknown_tool", {})
        assert risk == RiskLevel.HIGH

    def test_case_insensitive_assessment(self, assessor):
        """Test that assessment is case insensitive"""
        risk1 = assessor.assess_tool_risk("execute_command", {"command": "python"})
        risk2 = assessor.assess_tool_risk("execute_command", {"command": "PYTHON"})
        assert risk1 == risk2

    def test_empty_params(self, assessor):
        """Test assessment with empty parameters"""
        # Should handle gracefully
        risk = assessor.assess_tool_risk("write_file", {})
        assert risk in [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH]
