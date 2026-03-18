"""Role-based tool policy helpers.

This module centralizes tool access rules per agent role and validates
tool calls before execution.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.schemas.agent import AgentConfig
from app.schemas.agent_role import AgentRole


@dataclass(slots=True)
class ToolPolicy:
    """Effective tool policy for an agent."""

    allowed_tools: set[str]
    denied_tools: set[str]
    write_file_path_regex: str | None = None


def _default_policy_for_role(role: str | None, available_tools: set[str]) -> ToolPolicy:
    """Return default policy by role.

    Mirrors RooCode-like behavior where modes define tool capabilities.
    """
    if role == AgentRole.ARCHITECT.value:
        return ToolPolicy(
            allowed_tools={"read_file", "list_directory", "write_file"} & available_tools,
            denied_tools={"execute_command"} & available_tools,
            write_file_path_regex=r"\.(md|mdx)$",
        )
    if role == AgentRole.ASK.value:
        return ToolPolicy(
            allowed_tools={"read_file", "list_directory"} & available_tools,
            denied_tools={"write_file", "execute_command"} & available_tools,
        )
    if role == AgentRole.ORCHESTRATOR.value:
        return ToolPolicy(
            allowed_tools=set(),
            denied_tools=set(available_tools),
        )

    # code/debug/custom/default: no additional restrictions
    return ToolPolicy(
        allowed_tools=set(available_tools),
        denied_tools=set(),
    )


def build_tool_policy(config: AgentConfig, available_tools: set[str]) -> ToolPolicy:
    """Build effective tool policy from role defaults + optional metadata override."""
    role = None
    if config.metadata:
        role = config.metadata.get("role")

    policy = _default_policy_for_role(role, available_tools)

    custom = config.metadata.get("tool_policy", {}) if config.metadata else {}
    if not isinstance(custom, dict):
        return policy

    allowed = custom.get("allowed_tools")
    if isinstance(allowed, list):
        policy.allowed_tools = {str(t) for t in allowed if str(t) in available_tools}

    denied = custom.get("denied_tools")
    if isinstance(denied, list):
        policy.denied_tools = {str(t) for t in denied if str(t) in available_tools}

    regex = custom.get("write_file_path_regex")
    if isinstance(regex, str) and regex.strip():
        policy.write_file_path_regex = regex.strip()

    # denied takes precedence
    policy.allowed_tools -= policy.denied_tools
    return policy


def filter_tool_schemas_by_policy(
    tools: list[dict[str, Any]],
    policy: ToolPolicy,
) -> list[dict[str, Any]]:
    """Filter OpenAI tool schemas to include only allowed tools."""
    filtered: list[dict[str, Any]] = []
    for tool in tools:
        function = tool.get("function", {})
        name = function.get("name")
        if isinstance(name, str) and name in policy.allowed_tools:
            filtered.append(tool)
    return filtered


def validate_tool_call(
    tool_name: str,
    tool_params: dict[str, Any],
    policy: ToolPolicy,
) -> tuple[bool, str | None]:
    """Validate a tool call against policy."""
    if tool_name in policy.denied_tools or tool_name not in policy.allowed_tools:
        return False, f"Tool '{tool_name}' is not allowed for this agent"

    if tool_name == "write_file" and policy.write_file_path_regex:
        path = tool_params.get("path")
        if not isinstance(path, str) or not path.strip():
            return False, "Tool 'write_file' requires non-empty 'path' parameter"

        if re.search(policy.write_file_path_regex, path, flags=re.IGNORECASE) is None:
            return (
                False,
                "Tool 'write_file' is restricted for this agent "
                f"(path must match: {policy.write_file_path_regex})",
            )

    return True, None
