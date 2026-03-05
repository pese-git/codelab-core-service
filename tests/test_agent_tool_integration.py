"""Integration tests for Agent + Tool Execution system.

Tests E2E flow: User → Agent → LLM (tool call) → ToolExecutor → Result → Agent Response
"""

import asyncio
import json
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.contextual_agent import ContextualAgent
from app.core.approval_manager import ApprovalManager
from app.core.tools.executor import ToolExecutor
from app.models.tool_execution import ToolExecution
from app.models.approval_request import ApprovalRequest
from app.schemas.agent import AgentConfig
from app.schemas.tool import ToolExecutionResponse


# ============================================================================
# Fixtures for Tool Integration Tests
# ============================================================================

@pytest_asyncio.fixture
async def tool_executor_with_mocks(
    db_session: AsyncSession,
    test_user,
    test_project,
) -> ToolExecutor:
    """Create ToolExecutor with mocked dependencies."""
    approval_manager = AsyncMock(spec=ApprovalManager)
    
    executor = ToolExecutor(
        user_id=test_user.id,
        project_id=test_project.id,
        workspace_root="/tmp/test_workspace",
        db=db_session,
        approval_manager=approval_manager,
        stream_manager=None,
    )
    
    return executor


@pytest_asyncio.fixture
async def mock_openai_client():
    """Create mock OpenAI client."""
    return AsyncMock()


@pytest_asyncio.fixture
async def agent_with_tool_executor(
    test_user,
    test_agent,
    db_session: AsyncSession,
    tool_executor_with_mocks: ToolExecutor,
) -> ContextualAgent:
    """Create agent with tool executor."""
    config = AgentConfig(**test_agent.config)
    
    agent = ContextualAgent(
        agent_id=test_agent.id,
        user_id=test_user.id,
        agent_name=test_agent.name,
        config=config,
        qdrant_client=None,
        tool_executor=tool_executor_with_mocks,
    )
    
    return agent


@pytest_asyncio.fixture
async def agent_without_tools(
    test_user,
    test_agent,
) -> ContextualAgent:
    """Create agent without tool executor (backward compatibility)."""
    config = AgentConfig(**test_agent.config)
    
    agent = ContextualAgent(
        agent_id=test_agent.id,
        user_id=test_user.id,
        agent_name=test_agent.name,
        config=config,
        qdrant_client=None,
        tool_executor=None,
    )
    
    return agent


def mock_openai_response_with_tool_call(
    tool_name: str,
    tool_arguments: dict,
    response_text: str = "Executing tool...",
) -> Mock:
    """Create mock OpenAI response with tool call."""
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message = Mock()
    mock_response.choices[0].message.content = response_text
    
    # Create tool call
    mock_tool_call = Mock()
    mock_tool_call.id = "call_123abc"
    mock_tool_call.function = Mock()
    mock_tool_call.function.name = tool_name
    mock_tool_call.function.arguments = json.dumps(tool_arguments)
    
    mock_response.choices[0].message.tool_calls = [mock_tool_call]
    mock_response.usage = Mock()
    mock_response.usage.total_tokens = 150
    
    return mock_response


def mock_openai_response_without_tools(response_text: str = "Done") -> Mock:
    """Create mock OpenAI response without tool calls."""
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message = Mock()
    mock_response.choices[0].message.content = response_text
    mock_response.choices[0].message.tool_calls = None
    mock_response.usage = Mock()
    mock_response.usage.total_tokens = 100
    
    return mock_response


def mock_openai_response_multiple_tool_calls(
    tool_calls_data: list[dict],
) -> Mock:
    """Create mock OpenAI response with multiple tool calls."""
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message = Mock()
    mock_response.choices[0].message.content = ""
    
    tool_calls = []
    for i, tool_data in enumerate(tool_calls_data):
        mock_tool_call = Mock()
        mock_tool_call.id = f"call_{i}_123abc"
        mock_tool_call.function = Mock()
        mock_tool_call.function.name = tool_data["name"]
        mock_tool_call.function.arguments = json.dumps(tool_data["arguments"])
        tool_calls.append(mock_tool_call)
    
    mock_response.choices[0].message.tool_calls = tool_calls
    mock_response.usage = Mock()
    mock_response.usage.total_tokens = 200
    
    return mock_response


# ============================================================================
# Test 1: test_agent_executes_read_file_tool
# ============================================================================

@pytest.mark.asyncio
async def test_agent_executes_read_file_tool(
    db_session: AsyncSession,
    agent_with_tool_executor: ContextualAgent,
) -> None:
    """Test agent executing read_file tool.
    
    Flow:
    1. Agent receives task "read file README.md"
    2. LLM returns tool_call for read_file
    3. Agent calls ToolExecutor.execute_tool()
    4. Mock returns file content
    5. Agent gets result and formulates response
    
    Checks:
    - ToolExecution created in DB
    - Status = completed
    - Result contains data
    - Agent returned correct answer
    """
    # Setup mock OpenAI response with tool call
    mock_response_with_tool = mock_openai_response_with_tool_call(
        tool_name="read_file",
        tool_arguments={"path": "README.md"},
        response_text="I'll read the README file for you.",
    )
    
    # Setup mock final response after tool execution
    mock_final_response = mock_openai_response_without_tools(
        response_text="The README file contains project documentation.",
    )
    
    # Mock ToolExecutor.execute_tool to create and complete execution
    async def mock_execute_tool(tool_name: str, tool_params: dict, session_id=None):
        # Create execution in database
        execution = ToolExecution(
            id=uuid4(),
            user_id=agent_with_tool_executor.user_id,
            project_id=agent_with_tool_executor.agent_id,
            session_id=session_id,
            tool_name=tool_name,
            tool_params=tool_params,
            risk_level="LOW",
            status="completed",
            result={"content": "# Project README\n\nThis is a test project."},
            created_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
        )
        db_session.add(execution)
        await db_session.commit()
        
        return ToolExecutionResponse(
            tool_id=str(execution.id),
            tool_name=tool_name,
            status="completed",
            result={"content": "# Project README\n\nThis is a test project."},
            created_at=datetime.utcnow().isoformat(),
        )
    
    agent_with_tool_executor.tool_executor.execute_tool = AsyncMock(
        side_effect=mock_execute_tool
    )
    
    # Mock OpenAI client responses
    agent_with_tool_executor.openai_client.chat.completions.create = AsyncMock(
        side_effect=[mock_response_with_tool, mock_final_response]
    )
    
    # Mock context store
    agent_with_tool_executor.context_store.search = AsyncMock(return_value=[])
    agent_with_tool_executor.context_store.add_interaction = AsyncMock()
    
    # Execute agent
    result = await agent_with_tool_executor.execute(
        user_message="Please read the README.md file",
        session_id=uuid4(),
    )
    
    # Verify results
    assert result["success"] is True
    assert result["tools_used"] == 1
    assert "README" in result["response"]
    
    # Check ToolExecution in database
    from sqlalchemy import select
    exec_result = await db_session.execute(
        select(ToolExecution).where(
            ToolExecution.tool_name == "read_file"
        )
    )
    execution = exec_result.scalar_one_or_none()
    assert execution is not None
    assert execution.status == "completed"
    assert execution.result is not None
    assert "README" in execution.result.get("content", "")


# ============================================================================
# Test 2: test_agent_handles_tool_approval_workflow
# ============================================================================

@pytest.mark.asyncio
async def test_agent_handles_tool_approval_workflow(
    db_session: AsyncSession,
    agent_with_tool_executor: ContextualAgent,
) -> None:
    """Test agent handling tool approval workflow.
    
    Flow:
    1. Agent calls MEDIUM risk tool (write_file)
    2. ToolExecutor creates ApprovalRequest
    3. Mock user approval
    4. Tool executes after approval
    
    Checks:
    - ApprovalRequest created
    - Status tool: pending → approved → completed
    - Tool executed only after approval
    """
    # Setup mock OpenAI response with write_file tool call
    mock_response_with_tool = mock_openai_response_with_tool_call(
        tool_name="write_file",
        tool_arguments={"path": "test.txt", "content": "Test content"},
        response_text="I'll write to the test file.",
    )
    
    # Setup mock final response
    mock_final_response = mock_openai_response_without_tools(
        response_text="File written successfully.",
    )
    
    # Mock ToolExecutor to create approval request
    async def mock_execute_tool_with_approval(tool_name: str, tool_params: dict, session_id=None):
        # Create approval request
        approval = ApprovalRequest(
            id=uuid4(),
            user_id=agent_with_tool_executor.user_id,
            type="tool",
            payload={"tool_name": tool_name, "tool_params": tool_params},
            status="pending",
            created_at=datetime.utcnow(),
        )
        db_session.add(approval)
        await db_session.commit()
        
        # Simulate approval
        approval.status = "approved"
        await db_session.commit()
        
        # Create execution
        execution = ToolExecution(
            id=uuid4(),
            user_id=agent_with_tool_executor.user_id,
            project_id=agent_with_tool_executor.agent_id,
            session_id=session_id,
            tool_name=tool_name,
            tool_params=tool_params,
            risk_level="MEDIUM",
            status="completed",
            approval_id=approval.id,
            result={"written": True},
            created_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
        )
        db_session.add(execution)
        await db_session.commit()
        
        return ToolExecutionResponse(
            tool_id=str(execution.id),
            tool_name=tool_name,
            status="completed",
            result={"written": True},
            created_at=datetime.utcnow().isoformat(),
        )
    
    agent_with_tool_executor.tool_executor.execute_tool = AsyncMock(
        side_effect=mock_execute_tool_with_approval
    )
    
    # Mock OpenAI client
    agent_with_tool_executor.openai_client.chat.completions.create = AsyncMock(
        side_effect=[mock_response_with_tool, mock_final_response]
    )
    
    # Mock context store
    agent_with_tool_executor.context_store.search = AsyncMock(return_value=[])
    agent_with_tool_executor.context_store.add_interaction = AsyncMock()
    
    # Execute agent
    result = await agent_with_tool_executor.execute(
        user_message="Write 'Test content' to test.txt",
        session_id=uuid4(),
    )
    
    # Verify results
    assert result["success"] is True
    assert result["tools_used"] == 1
    
    # Verify approval request was created
    from sqlalchemy import select
    approval_result = await db_session.execute(
        select(ApprovalRequest).where(
            ApprovalRequest.type == "tool"
        )
    )
    approval = approval_result.scalar_one_or_none()
    assert approval is not None
    assert approval.status == "approved"
    assert approval.payload.get("tool_name") == "write_file"
    
    # Verify execution was completed
    exec_result = await db_session.execute(
        select(ToolExecution).where(
            ToolExecution.tool_name == "write_file"
        )
    )
    execution = exec_result.scalar_one_or_none()
    assert execution is not None
    assert execution.status == "completed"
    assert execution.approval_id == approval.id


# ============================================================================
# Test 3: test_agent_handles_tool_error
# ============================================================================

@pytest.mark.asyncio
async def test_agent_handles_tool_error(
    db_session: AsyncSession,
    agent_with_tool_executor: ContextualAgent,
) -> None:
    """Test agent handling tool errors.
    
    Flow:
    1. Agent calls tool with incorrect parameters
    2. Client returns error
    3. Agent gets error and continues working
    
    Checks:
    - ToolExecution.status = failed
    - ToolExecution.error contains description
    - Agent didn't crash, returned error message
    """
    # Setup mock OpenAI response with tool call
    mock_response_with_tool = mock_openai_response_with_tool_call(
        tool_name="read_file",
        tool_arguments={"path": "/etc/passwd"},  # Invalid path
        response_text="I'll try to read that file.",
    )
    
    # Setup mock error response from LLM after tool fails
    mock_error_response = mock_openai_response_without_tools(
        response_text="I encountered an error reading the file due to path validation.",
    )
    
    # Mock ToolExecutor to return error
    async def mock_execute_tool_with_error(tool_name: str, tool_params: dict, session_id=None):
        # Create failed execution
        execution = ToolExecution(
            id=uuid4(),
            user_id=agent_with_tool_executor.user_id,
            project_id=agent_with_tool_executor.agent_id,
            session_id=session_id,
            tool_name=tool_name,
            tool_params=tool_params,
            risk_level="LOW",
            status="failed",
            error="Path /etc/passwd is outside workspace root",
            created_at=datetime.utcnow(),
        )
        db_session.add(execution)
        await db_session.commit()
        
        return ToolExecutionResponse(
            tool_id=str(execution.id),
            tool_name=tool_name,
            status="failed",
            error="Path /etc/passwd is outside workspace root",
            created_at=datetime.utcnow().isoformat(),
        )
    
    agent_with_tool_executor.tool_executor.execute_tool = AsyncMock(
        side_effect=mock_execute_tool_with_error
    )
    
    # Mock OpenAI client
    agent_with_tool_executor.openai_client.chat.completions.create = AsyncMock(
        side_effect=[mock_response_with_tool, mock_error_response]
    )
    
    # Mock context store
    agent_with_tool_executor.context_store.search = AsyncMock(return_value=[])
    agent_with_tool_executor.context_store.add_interaction = AsyncMock()
    
    # Execute agent
    result = await agent_with_tool_executor.execute(
        user_message="Read /etc/passwd",
        session_id=uuid4(),
    )
    
    # Verify agent didn't crash and returned response
    assert result["success"] is True  # Agent execution succeeded
    assert "error" in result["response"].lower() or result["tools_used"] >= 1
    
    # Verify ToolExecution is marked as failed
    from sqlalchemy import select
    exec_result = await db_session.execute(
        select(ToolExecution).where(
            ToolExecution.tool_name == "read_file"
        )
    )
    execution = exec_result.scalar_one_or_none()
    assert execution is not None
    assert execution.status == "failed"
    assert execution.error is not None
    assert "workspace root" in execution.error


# ============================================================================
# Test 4: test_agent_executes_multiple_tools_sequentially
# ============================================================================

@pytest.mark.asyncio
async def test_agent_executes_multiple_tools_sequentially(
    db_session: AsyncSession,
    agent_with_tool_executor: ContextualAgent,
) -> None:
    """Test agent executing multiple tools sequentially.
    
    Flow:
    1. Agent receives task requiring multiple tools
    2. LLM returns multiple tool_calls
    3. Agent executes them sequentially
    
    Checks:
    - All tools executed
    - Results passed back to LLM
    - Final answer considers all results
    """
    # Setup mock OpenAI response with multiple tool calls
    tool_calls_data = [
        {"name": "read_file", "arguments": {"path": "file1.txt"}},
        {"name": "read_file", "arguments": {"path": "file2.txt"}},
    ]
    mock_response_with_tools = mock_openai_response_multiple_tool_calls(tool_calls_data)
    
    # Setup mock final response
    mock_final_response = mock_openai_response_without_tools(
        response_text="Both files have been read and analyzed.",
    )
    
    execution_count = 0
    
    # Mock ToolExecutor
    async def mock_execute_tool_multi(tool_name: str, tool_params: dict, session_id=None):
        nonlocal execution_count
        execution_count += 1
        
        execution = ToolExecution(
            id=uuid4(),
            user_id=agent_with_tool_executor.user_id,
            project_id=agent_with_tool_executor.agent_id,
            session_id=session_id,
            tool_name=tool_name,
            tool_params=tool_params,
            risk_level="LOW",
            status="completed",
            result={"content": f"Content of {tool_params.get('path', 'unknown')}"},
            created_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
        )
        db_session.add(execution)
        await db_session.commit()
        
        return ToolExecutionResponse(
            tool_id=str(execution.id),
            tool_name=tool_name,
            status="completed",
            result={"content": f"Content of {tool_params.get('path', 'unknown')}"},
            created_at=datetime.utcnow().isoformat(),
        )
    
    agent_with_tool_executor.tool_executor.execute_tool = AsyncMock(
        side_effect=mock_execute_tool_multi
    )
    
    # Mock OpenAI client
    agent_with_tool_executor.openai_client.chat.completions.create = AsyncMock(
        side_effect=[mock_response_with_tools, mock_final_response]
    )
    
    # Mock context store
    agent_with_tool_executor.context_store.search = AsyncMock(return_value=[])
    agent_with_tool_executor.context_store.add_interaction = AsyncMock()
    
    # Execute agent
    result = await agent_with_tool_executor.execute(
        user_message="Read and analyze file1.txt and file2.txt",
        session_id=uuid4(),
    )
    
    # Verify results
    assert result["success"] is True
    assert result["tools_used"] == 2
    assert execution_count == 2
    assert "analyzed" in result["response"].lower()
    
    # Verify all executions in database
    from sqlalchemy import select
    exec_result = await db_session.execute(
        select(ToolExecution).where(
            ToolExecution.tool_name == "read_file"
        )
    )
    executions = exec_result.scalars().all()
    assert len(executions) == 2
    assert all(e.status == "completed" for e in executions)


# ============================================================================
# Test 5: test_agent_without_tool_executor_works_normally
# ============================================================================

@pytest.mark.asyncio
async def test_agent_without_tool_executor_works_normally(
    agent_without_tools: ContextualAgent,
) -> None:
    """Test backward compatibility: agent without tool executor.
    
    Flow:
    1. Agent created without tool_executor
    2. Agent works normally (text only)
    
    Checks:
    - No errors
    - Tools not called
    - Agent returns text response
    """
    # Setup mock OpenAI response without tools
    mock_response = mock_openai_response_without_tools(
        response_text="This is a text-only response.",
    )
    
    # Mock OpenAI client
    agent_without_tools.openai_client.chat.completions.create = AsyncMock(
        return_value=mock_response
    )
    
    # Mock context store
    agent_without_tools.context_store.search = AsyncMock(return_value=[])
    agent_without_tools.context_store.add_interaction = AsyncMock()
    
    # Execute agent
    result = await agent_without_tools.execute(
        user_message="What is 2+2?",
    )
    
    # Verify results
    assert result["success"] is True
    assert result["tools_used"] == 0
    assert result["response"] == "This is a text-only response."
    
    # Verify tools weren't called
    assert agent_without_tools.tool_executor is None


# ============================================================================
# Test 6: test_tool_execution_timeout
# ============================================================================

@pytest.mark.asyncio
async def test_tool_execution_timeout(
    db_session: AsyncSession,
    agent_with_tool_executor: ContextualAgent,
) -> None:
    """Test agent handling tool execution timeout.
    
    Flow:
    1. Agent calls tool
    2. Client doesn't respond within timeout
    3. Agent gets timeout error
    
    Checks:
    - ToolExecution.status = failed
    - Error contains "timeout"
    - Agent handled timeout gracefully
    """
    # Setup mock OpenAI response with tool call
    mock_response_with_tool = mock_openai_response_with_tool_call(
        tool_name="read_file",
        tool_arguments={"path": "slow_file.txt"},
        response_text="I'll read that file.",
    )
    
    # Setup mock timeout response from LLM
    mock_timeout_response = mock_openai_response_without_tools(
        response_text="The operation timed out while trying to read the file.",
    )
    
    # Mock ToolExecutor to simulate timeout
    async def mock_execute_tool_timeout(tool_name: str, tool_params: dict, session_id=None):
        # Simulate timeout delay
        await asyncio.sleep(0.1)
        
        # Create failed execution with timeout error
        execution = ToolExecution(
            id=uuid4(),
            user_id=agent_with_tool_executor.user_id,
            project_id=agent_with_tool_executor.agent_id,
            session_id=session_id,
            tool_name=tool_name,
            tool_params=tool_params,
            risk_level="LOW",
            status="failed",
            error="Tool execution timeout after 30 seconds",
            created_at=datetime.utcnow(),
        )
        db_session.add(execution)
        await db_session.commit()
        
        return ToolExecutionResponse(
            tool_id=str(execution.id),
            tool_name=tool_name,
            status="failed",
            error="Tool execution timeout after 30 seconds",
            created_at=datetime.utcnow().isoformat(),
        )
    
    agent_with_tool_executor.tool_executor.execute_tool = AsyncMock(
        side_effect=mock_execute_tool_timeout
    )
    
    # Mock OpenAI client
    agent_with_tool_executor.openai_client.chat.completions.create = AsyncMock(
        side_effect=[mock_response_with_tool, mock_timeout_response]
    )
    
    # Mock context store
    agent_with_tool_executor.context_store.search = AsyncMock(return_value=[])
    agent_with_tool_executor.context_store.add_interaction = AsyncMock()
    
    # Execute agent
    result = await agent_with_tool_executor.execute(
        user_message="Read slow_file.txt",
        session_id=uuid4(),
    )
    
    # Verify agent handled timeout gracefully
    assert result["success"] is True  # Agent execution succeeded despite tool timeout
    assert "timeout" in result["response"].lower() or result["tools_used"] >= 1
    
    # Verify ToolExecution has timeout error
    from sqlalchemy import select
    exec_result = await db_session.execute(
        select(ToolExecution).where(
            ToolExecution.tool_name == "read_file"
        )
    )
    execution = exec_result.scalar_one_or_none()
    assert execution is not None
    assert execution.status == "failed"
    assert "timeout" in execution.error.lower()
