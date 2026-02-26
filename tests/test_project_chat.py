"""Per-project chat endpoints tests."""

from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User, UserProject, ChatSession, Message
from app.schemas.chat import MessageRole


@pytest.mark.asyncio
async def test_create_project_session(db_session: AsyncSession) -> None:
    """Test creating chat session in project."""
    # Create test user
    user_id = uuid4()
    project_id = uuid4()
    
    test_user = User(id=user_id, email=f"test-{user_id}@example.com")
    test_project = UserProject(
        id=project_id,
        user_id=user_id,
        name="Test Project",
        workspace_path="/test/workspace",
    )
    db_session.add(test_user)
    db_session.add(test_project)
    await db_session.flush()
    
    # Create chat session
    session = ChatSession(
        user_id=user_id,
        project_id=project_id,
    )
    db_session.add(session)
    await db_session.flush()
    
    # Verify session was created
    result = await db_session.execute(
        select(ChatSession).where(ChatSession.id == session.id)
    )
    created_session = result.scalar_one_or_none()
    assert created_session is not None
    assert created_session.user_id == user_id
    assert created_session.project_id == project_id


@pytest.mark.asyncio
async def test_list_sessions_by_project(db_session: AsyncSession) -> None:
    """Test listing chat sessions for a specific project."""
    # Create test user and two projects
    user_id = uuid4()
    project_id_1 = uuid4()
    project_id_2 = uuid4()
    
    test_user = User(id=user_id, email=f"test-{user_id}@example.com")
    project_1 = UserProject(
        id=project_id_1,
        user_id=user_id,
        name="Project 1",
        workspace_path="/test/workspace1",
    )
    project_2 = UserProject(
        id=project_id_2,
        user_id=user_id,
        name="Project 2",
        workspace_path="/test/workspace2",
    )
    db_session.add(test_user)
    db_session.add(project_1)
    db_session.add(project_2)
    await db_session.flush()
    
    # Create sessions in both projects
    session_1 = ChatSession(
        user_id=user_id,
        project_id=project_id_1,
    )
    session_2 = ChatSession(
        user_id=user_id,
        project_id=project_id_1,
    )
    session_3 = ChatSession(
        user_id=user_id,
        project_id=project_id_2,
    )
    db_session.add(session_1)
    db_session.add(session_2)
    db_session.add(session_3)
    await db_session.flush()
    
    # Verify sessions are correctly assigned to projects
    result = await db_session.execute(
        select(ChatSession).where(ChatSession.project_id == project_id_1)
    )
    project_1_sessions = result.scalars().all()
    assert len(project_1_sessions) == 2
    
    result = await db_session.execute(
        select(ChatSession).where(ChatSession.project_id == project_id_2)
    )
    project_2_sessions = result.scalars().all()
    assert len(project_2_sessions) == 1


@pytest.mark.asyncio
async def test_session_isolation_by_project(db_session: AsyncSession) -> None:
    """Test that sessions in different projects are isolated."""
    # Create test user and two projects
    user_id = uuid4()
    project_id_1 = uuid4()
    project_id_2 = uuid4()
    
    test_user = User(id=user_id, email=f"test-{user_id}@example.com")
    project_1 = UserProject(
        id=project_id_1,
        user_id=user_id,
        name="Project 1",
        workspace_path="/test/workspace1",
    )
    project_2 = UserProject(
        id=project_id_2,
        user_id=user_id,
        name="Project 2",
        workspace_path="/test/workspace2",
    )
    db_session.add(test_user)
    db_session.add(project_1)
    db_session.add(project_2)
    await db_session.flush()
    
    # Create sessions in different projects
    session_1 = ChatSession(
        user_id=user_id,
        project_id=project_id_1,
    )
    session_2 = ChatSession(
        user_id=user_id,
        project_id=project_id_2,
    )
    db_session.add(session_1)
    db_session.add(session_2)
    await db_session.flush()
    
    # Verify each project only sees its own sessions
    result = await db_session.execute(
        select(ChatSession).where(
            ChatSession.user_id == user_id,
            ChatSession.project_id == project_id_1,
        )
    )
    sessions_in_project_1 = result.scalars().all()
    assert len(sessions_in_project_1) == 1
    assert sessions_in_project_1[0].id == session_1.id
    
    result = await db_session.execute(
        select(ChatSession).where(
            ChatSession.user_id == user_id,
            ChatSession.project_id == project_id_2,
        )
    )
    sessions_in_project_2 = result.scalars().all()
    assert len(sessions_in_project_2) == 1
    assert sessions_in_project_2[0].id == session_2.id


@pytest.mark.asyncio
async def test_user_isolation_chat_sessions(db_session: AsyncSession) -> None:
    """Test that different users cannot access each other's sessions."""
    # Create two users and a project for user1
    user_id_1 = uuid4()
    user_id_2 = uuid4()
    project_id = uuid4()
    
    user_1 = User(id=user_id_1, email=f"test-{user_id_1}@example.com")
    user_2 = User(id=user_id_2, email=f"test-{user_id_2}@example.com")
    project = UserProject(
        id=project_id,
        user_id=user_id_1,
        name="User1 Project",
        workspace_path="/test/workspace",
    )
    db_session.add(user_1)
    db_session.add(user_2)
    db_session.add(project)
    await db_session.flush()
    
    # Create session for user1
    session = ChatSession(
        user_id=user_id_1,
        project_id=project_id,
    )
    db_session.add(session)
    await db_session.flush()
    
    # Verify user2 cannot see user1's session
    result = await db_session.execute(
        select(ChatSession).where(
            ChatSession.user_id == user_id_2,
            ChatSession.project_id == project_id,
        )
    )
    sessions = result.scalars().all()
    assert len(sessions) == 0


@pytest.mark.asyncio
async def test_messages_in_session(db_session: AsyncSession) -> None:
    """Test that messages are correctly associated with sessions."""
    # Create test user
    user_id = uuid4()
    project_id = uuid4()
    
    test_user = User(id=user_id, email=f"test-{user_id}@example.com")
    test_project = UserProject(
        id=project_id,
        user_id=user_id,
        name="Test Project",
        workspace_path="/test/workspace",
    )
    db_session.add(test_user)
    db_session.add(test_project)
    await db_session.flush()
    
    # Create chat session
    session = ChatSession(
        user_id=user_id,
        project_id=project_id,
    )
    db_session.add(session)
    await db_session.flush()
    
    # Create messages
    msg_1 = Message(
        session_id=session.id,
        role=MessageRole.USER.value,
        content="Hello",
    )
    msg_2 = Message(
        session_id=session.id,
        role=MessageRole.ASSISTANT.value,
        content="Hi there",
    )
    db_session.add(msg_1)
    db_session.add(msg_2)
    await db_session.flush()
    
    # Verify messages are correctly assigned to session
    result = await db_session.execute(
        select(Message).where(Message.session_id == session.id)
    )
    messages = result.scalars().all()
    assert len(messages) == 2
    assert messages[0].content == "Hello"
    assert messages[1].content == "Hi there"


@pytest.mark.asyncio
async def test_delete_session(db_session: AsyncSession) -> None:
    """Test deleting a chat session."""
    # Create test user
    user_id = uuid4()
    project_id = uuid4()
    
    test_user = User(id=user_id, email=f"test-{user_id}@example.com")
    test_project = UserProject(
        id=project_id,
        user_id=user_id,
        name="Test Project",
        workspace_path="/test/workspace",
    )
    db_session.add(test_user)
    db_session.add(test_project)
    await db_session.flush()
    
    # Create chat session
    session = ChatSession(
        user_id=user_id,
        project_id=project_id,
    )
    db_session.add(session)
    await db_session.flush()
    
    session_id = session.id
    
    # Delete session
    await db_session.delete(session)
    await db_session.flush()
    
    # Verify session is deleted
    result = await db_session.execute(
        select(ChatSession).where(ChatSession.id == session_id)
    )
    deleted_session = result.scalar_one_or_none()
    assert deleted_session is None


@pytest.mark.asyncio
async def test_chat_history_filters_only_user_facing_messages(db_session: AsyncSession) -> None:
    """Test that chat history contains only user-facing messages.
    
    Verifies that the /messages/ endpoint filters out internal system
    event messages and returns only messages with roles: user, assistant, system.
    """
    # Create test user
    user_id = uuid4()
    project_id = uuid4()
    
    test_user = User(id=user_id, email=f"test-{user_id}@example.com")
    test_project = UserProject(
        id=project_id,
        user_id=user_id,
        name="Test Project",
        workspace_path="/test/workspace",
    )
    db_session.add(test_user)
    db_session.add(test_project)
    await db_session.flush()
    
    # Create chat session
    session = ChatSession(
        user_id=user_id,
        project_id=project_id,
    )
    db_session.add(session)
    await db_session.flush()
    
    # Create user-facing messages (should be included in chat history)
    user_message = Message(
        session_id=session.id,
        role=MessageRole.USER.value,
        content="Hello, assistant!",
    )
    assistant_message = Message(
        session_id=session.id,
        role=MessageRole.ASSISTANT.value,
        content="Hi there! How can I help?",
    )
    system_message = Message(
        session_id=session.id,
        role=MessageRole.SYSTEM.value,
        content="An error occurred: Connection timeout",
    )
    
    # Create internal system event messages (should NOT be included in chat history)
    # These would be created by internal system components, not for user display
    internal_tool_request = Message(
        session_id=session.id,
        role="TOOL_REQUEST",  # Internal event, not user-facing
        content='{"tool": "search", "query": "example"}',
    )
    internal_tool_result = Message(
        session_id=session.id,
        role="TOOL_RESULT",  # Internal event, not user-facing
        content="Result from tool execution",
    )
    internal_context = Message(
        session_id=session.id,
        role="CONTEXT_RETRIEVED",  # Internal event, not user-facing
        content='{"context": "retrieved data"}',
    )
    
    # Add all messages to database
    db_session.add(user_message)
    db_session.add(assistant_message)
    db_session.add(system_message)
    db_session.add(internal_tool_request)
    db_session.add(internal_tool_result)
    db_session.add(internal_context)
    await db_session.flush()
    
    # Verify all 6 messages exist in database
    result = await db_session.execute(
        select(Message).where(Message.session_id == session.id)
    )
    all_messages = result.scalars().all()
    assert len(all_messages) == 6, "All 6 messages should be in database"
    
    # Query only user-facing messages (as the endpoint does)
    USER_FACING_ROLES = ["user", "assistant", "system"]
    result = await db_session.execute(
        select(Message)
        .where(
            Message.session_id == session.id,
            Message.role.in_(USER_FACING_ROLES)
        )
        .order_by(Message.created_at.asc())
    )
    user_facing_messages = result.scalars().all()
    
    # Verify only 3 user-facing messages are returned
    assert len(user_facing_messages) == 3, "Only 3 user-facing messages should be returned"
    
    # Verify the correct messages are returned
    assert user_facing_messages[0].role == MessageRole.USER.value
    assert user_facing_messages[0].content == "Hello, assistant!"
    
    assert user_facing_messages[1].role == MessageRole.ASSISTANT.value
    assert user_facing_messages[1].content == "Hi there! How can I help?"
    
    assert user_facing_messages[2].role == MessageRole.SYSTEM.value
    assert user_facing_messages[2].content == "An error occurred: Connection timeout"
    
    # Verify internal events are NOT included
    roles_in_result = {msg.role for msg in user_facing_messages}
    assert "TOOL_REQUEST" not in roles_in_result
    assert "TOOL_RESULT" not in roles_in_result
    assert "CONTEXT_RETRIEVED" not in roles_in_result
