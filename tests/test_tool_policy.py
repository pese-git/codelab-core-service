"""Tests for role-based tool policy."""

from uuid import uuid4

from app.agents.contextual_agent import ContextualAgent
from app.core.tools.policy import build_tool_policy, validate_tool_call
from app.schemas.agent import AgentConfig


def _make_config(role: str, tool_policy: dict | None = None) -> AgentConfig:
    metadata = {"role": role}
    if tool_policy is not None:
        metadata["tool_policy"] = tool_policy
    return AgentConfig(
        system_prompt="test",
        tools=[],
        temperature=0.2,
        max_tokens=512,
        metadata=metadata,
    )


def test_architect_default_policy_allows_read_list_and_markdown_write() -> None:
    config = _make_config("architect")
    policy = build_tool_policy(
        config=config,
        available_tools={"read_file", "list_directory", "write_file", "execute_command"},
    )

    assert "read_file" in policy.allowed_tools
    assert "list_directory" in policy.allowed_tools
    assert "write_file" in policy.allowed_tools
    assert "execute_command" not in policy.allowed_tools
    assert "execute_command" in policy.denied_tools
    assert policy.write_file_path_regex == r"\.(md|mdx)$"


def test_architect_policy_blocks_non_markdown_write_and_command() -> None:
    config = _make_config("architect")
    policy = build_tool_policy(
        config=config,
        available_tools={"read_file", "list_directory", "write_file", "execute_command"},
    )

    ok, err = validate_tool_call("write_file", {"path": "README.md"}, policy)
    assert ok is True
    assert err is None

    ok, err = validate_tool_call("write_file", {"path": "app/main.py"}, policy)
    assert ok is False
    assert err is not None

    ok, err = validate_tool_call("execute_command", {"command": "ls"}, policy)
    assert ok is False
    assert err is not None


def test_architect_custom_policy_override() -> None:
    config = _make_config(
        "architect",
        tool_policy={
            "allowed_tools": ["read_file"],
            "denied_tools": [],
            "write_file_path_regex": r"\.txt$",
        },
    )
    policy = build_tool_policy(
        config=config,
        available_tools={"read_file", "list_directory", "write_file", "execute_command"},
    )

    assert policy.allowed_tools == {"read_file"}


def test_contextual_agent_exposes_tools_by_policy() -> None:
    agent = ContextualAgent(
        agent_id=uuid4(),
        user_id=uuid4(),
        agent_name="Architect",
        config=_make_config("architect"),
        qdrant_client=None,
        tool_executor=object(),
    )

    tools = agent._get_available_tools()
    tool_names = {tool["function"]["name"] for tool in tools}

    assert tool_names == {"read_file", "list_directory", "write_file"}
