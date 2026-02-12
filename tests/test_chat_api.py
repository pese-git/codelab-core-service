"""Tests for chat session REST API endpoints."""

import pytest
from uuid import UUID, uuid4
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.user_agent import UserAgent
from app.models.chat_session import ChatSession
from app.models.message import Message


class TestChatSessionAPI:
    """Test chat session CRUD operations."""
    
    @pytest.mark.asyncio
    async def test_create_session_success(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
    ):
        """Test successful chat session creation."""
        response = await client.post(
            "/my/chat/sessions/",
            headers=auth_headers,
        )
        
        assert response.status_code == 201
        data = response.json()
        
        assert "id" in data
        assert "created_at" in data
        assert data["message_count"] == 0
        assert UUID(data["id"])  # Valid UUID
    
    @pytest.mark.asyncio
    async def test_create_session_unauthorized(self, client: AsyncClient):
        """Test session creation without authentication."""
        response = await client.post("/my/chat/sessions/")
        
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_list_sessions_empty(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
    ):
        """Test listing sessions when none exist."""
        response = await client.get(
            "/my/chat/sessions/",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["sessions"] == []
        assert data["total"] == 0
    
    @pytest.mark.asyncio
    async def test_list_sessions_with_data(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test listing sessions with existing data."""
        # Create test sessions
        session1 = ChatSession(user_id=test_user.id)
        session2 = ChatSession(user_id=test_user.id)
        db_session.add_all([session1, session2])
        await db_session.commit()
        
        response = await client.get(
            "/my/chat/sessions/",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["sessions"]) == 2
        assert data["total"] == 2
        
        for session in data["sessions"]:
            assert "id" in session
            assert "created_at" in session
            assert "message_count" in session
    
    @pytest.mark.asyncio
    async def test_list_sessions_user_isolation(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test that users only see their own sessions."""
        # Create session for test user
        user_session = ChatSession(user_id=test_user.id)
        db_session.add(user_session)
        
        # Create session for another user
        other_user_id = uuid4()
        other_session = ChatSession(user_id=other_user_id)
        db_session.add(other_session)
        
        await db_session.commit()
        
        response = await client.get(
            "/my/chat/sessions/",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should only see own session
        assert len(data["sessions"]) == 1
        assert data["total"] == 1
        assert UUID(data["sessions"][0]["id"]) == user_session.id
    
    @pytest.mark.asyncio
    async def test_delete_session_success(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test successful session deletion."""
        # Create session
        session = ChatSession(user_id=test_user.id)
        db_session.add(session)
        await db_session.commit()
        
        response = await client.delete(
            f"/my/chat/sessions/{session.id}",
            headers=auth_headers,
        )
        
        assert response.status_code == 204
        
        # Verify session is deleted
        list_response = await client.get(
            "/my/chat/sessions/",
            headers=auth_headers,
        )
        assert list_response.json()["total"] == 0
    
    @pytest.mark.asyncio
    async def test_delete_session_not_found(
        self,
        client: AsyncClient,
        auth_headers: dict,
    ):
        """Test deleting non-existent session."""
        fake_id = uuid4()
        response = await client.delete(
            f"/my/chat/sessions/{fake_id}",
            headers=auth_headers,
        )
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    
    @pytest.mark.asyncio
    async def test_delete_session_wrong_user(
        self,
        client: AsyncClient,
        auth_headers: dict,
        db_session: AsyncSession,
    ):
        """Test deleting another user's session."""
        # Create session for another user
        other_user_id = uuid4()
        other_session = ChatSession(user_id=other_user_id)
        db_session.add(other_session)
        await db_session.commit()
        
        response = await client.delete(
            f"/my/chat/sessions/{other_session.id}",
            headers=auth_headers,
        )
        
        assert response.status_code == 404


class TestChatMessagesAPI:
    """Test chat messages operations."""
    
    @pytest.mark.asyncio
    async def test_get_messages_empty_session(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test getting messages from empty session."""
        session = ChatSession(user_id=test_user.id)
        db_session.add(session)
        await db_session.commit()
        
        response = await client.get(
            f"/my/chat/sessions/{session.id}/messages/",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["messages"] == []
        assert data["total"] == 0
        assert UUID(data["session_id"]) == session.id
    
    @pytest.mark.asyncio
    async def test_get_messages_with_history(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test getting messages with existing history."""
        session = ChatSession(user_id=test_user.id)
        db_session.add(session)
        await db_session.flush()
        
        # Add messages
        msg1 = Message(
            session_id=session.id,
            role="user",
            content="Hello",
        )
        msg2 = Message(
            session_id=session.id,
            role="assistant",
            content="Hi there!",
        )
        db_session.add_all([msg1, msg2])
        await db_session.commit()
        
        response = await client.get(
            f"/my/chat/sessions/{session.id}/messages/",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["messages"]) == 2
        assert data["total"] == 2
        assert data["messages"][0]["content"] == "Hello"
        assert data["messages"][1]["content"] == "Hi there!"
    
    @pytest.mark.asyncio
    async def test_get_messages_pagination(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test message pagination."""
        session = ChatSession(user_id=test_user.id)
        db_session.add(session)
        await db_session.flush()
        
        # Add 10 messages
        for i in range(10):
            msg = Message(
                session_id=session.id,
                role="user" if i % 2 == 0 else "assistant",
                content=f"Message {i}",
            )
            db_session.add(msg)
        await db_session.commit()
        
        # Get first 5 messages
        response = await client.get(
            f"/my/chat/sessions/{session.id}/messages/?limit=5&offset=0",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["messages"]) == 5
        assert data["total"] == 10
        
        # Get next 5 messages
        response = await client.get(
            f"/my/chat/sessions/{session.id}/messages/?limit=5&offset=5",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["messages"]) == 5
        assert data["total"] == 10
    
    @pytest.mark.asyncio
    async def test_get_messages_session_not_found(
        self,
        client: AsyncClient,
        auth_headers: dict,
    ):
        """Test getting messages from non-existent session."""
        fake_id = uuid4()
        response = await client.get(
            f"/my/chat/sessions/{fake_id}/messages/",
            headers=auth_headers,
        )
        
        assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_send_message_orchestrated_mode(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test sending message in orchestrated mode (no target_agent)."""
        session = ChatSession(user_id=test_user.id)
        db_session.add(session)
        await db_session.commit()
        
        response = await client.post(
            f"/my/chat/{session.id}/message/",
            headers=auth_headers,
            json={
                "content": "Hello, how are you?",
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "id" in data
        assert data["role"] == "assistant"
        assert "not yet implemented" in data["content"].lower()
        assert data["agent_id"] is None
    
    @pytest.mark.asyncio
    async def test_send_message_invalid_session(
        self,
        client: AsyncClient,
        auth_headers: dict,
    ):
        """Test sending message to non-existent session."""
        fake_id = uuid4()
        response = await client.post(
            f"/my/chat/{fake_id}/message/",
            headers=auth_headers,
            json={
                "content": "Hello",
            },
        )
        
        assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_send_message_empty_content(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test sending message with empty content."""
        session = ChatSession(user_id=test_user.id)
        db_session.add(session)
        await db_session.commit()
        
        response = await client.post(
            f"/my/chat/{session.id}/message/",
            headers=auth_headers,
            json={
                "content": "",
            },
        )
        
        assert response.status_code == 422  # Validation error
    
    @pytest.mark.asyncio
    async def test_send_message_direct_mode_agent_not_found(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test sending message to non-existent agent."""
        session = ChatSession(user_id=test_user.id)
        db_session.add(session)
        await db_session.commit()
        
        response = await client.post(
            f"/my/chat/{session.id}/message/",
            headers=auth_headers,
            json={
                "content": "Hello",
                "target_agent": "non_existent_agent",
            },
        )
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestChatAPIIntegration:
    """Integration tests for complete chat workflows."""
    
    @pytest.mark.asyncio
    async def test_complete_chat_workflow(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
    ):
        """Test complete chat workflow: create session, send messages, list, delete."""
        # 1. Create session
        create_response = await client.post(
            "/my/chat/sessions/",
            headers=auth_headers,
        )
        assert create_response.status_code == 201
        session_id = create_response.json()["id"]
        
        # 2. Send message
        send_response = await client.post(
            f"/my/chat/{session_id}/message/",
            headers=auth_headers,
            json={"content": "Test message"},
        )
        assert send_response.status_code == 200
        
        # 3. Get messages
        messages_response = await client.get(
            f"/my/chat/sessions/{session_id}/messages/",
            headers=auth_headers,
        )
        assert messages_response.status_code == 200
        messages_data = messages_response.json()
        assert messages_data["total"] >= 1  # At least user message
        
        # 4. List sessions
        list_response = await client.get(
            "/my/chat/sessions/",
            headers=auth_headers,
        )
        assert list_response.status_code == 200
        assert list_response.json()["total"] >= 1
        
        # 5. Delete session
        delete_response = await client.delete(
            f"/my/chat/sessions/{session_id}",
            headers=auth_headers,
        )
        assert delete_response.status_code == 204
        
        # 6. Verify deletion
        final_list = await client.get(
            "/my/chat/sessions/",
            headers=auth_headers,
        )
        remaining_sessions = [
            s for s in final_list.json()["sessions"]
            if s["id"] == session_id
        ]
        assert len(remaining_sessions) == 0
    
    @pytest.mark.asyncio
    async def test_multiple_sessions_isolation(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_user: User,
    ):
        """Test that multiple sessions are properly isolated."""
        # Create two sessions
        session1_response = await client.post(
            "/my/chat/sessions/",
            headers=auth_headers,
        )
        session1_id = session1_response.json()["id"]
        
        session2_response = await client.post(
            "/my/chat/sessions/",
            headers=auth_headers,
        )
        session2_id = session2_response.json()["id"]
        
        # Send messages to each session
        await client.post(
            f"/my/chat/{session1_id}/message/",
            headers=auth_headers,
            json={"content": "Message to session 1"},
        )
        
        await client.post(
            f"/my/chat/{session2_id}/message/",
            headers=auth_headers,
            json={"content": "Message to session 2"},
        )
        
        # Verify messages are isolated
        session1_messages = await client.get(
            f"/my/chat/sessions/{session1_id}/messages/",
            headers=auth_headers,
        )
        session2_messages = await client.get(
            f"/my/chat/sessions/{session2_id}/messages/",
            headers=auth_headers,
        )
        
        s1_data = session1_messages.json()
        s2_data = session2_messages.json()
        
        # Each session should have its own messages
        assert any("session 1" in msg["content"] for msg in s1_data["messages"])
        assert any("session 2" in msg["content"] for msg in s2_data["messages"])
        
        # Messages should not cross sessions
        assert not any("session 2" in msg["content"] for msg in s1_data["messages"])
        assert not any("session 1" in msg["content"] for msg in s2_data["messages"])
