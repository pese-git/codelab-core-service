"""Tests for SSE (Server-Sent Events) functionality."""

import asyncio
import json
from datetime import datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.sse_manager import SSEManager, SSEConnection
from app.models.chat_session import ChatSession
from app.models.user import User
from app.schemas.event import SSEEvent, SSEEventType


class TestSSEConnection:
    """Tests for SSEConnection class."""

    @pytest.mark.asyncio
    async def test_connection_creation(self):
        """Test SSE connection creation."""
        session_id = uuid4()
        user_id = uuid4()
        queue = asyncio.Queue()

        conn = SSEConnection(session_id, user_id, queue)

        assert conn.session_id == session_id
        assert conn.user_id == user_id
        assert conn.queue == queue
        assert conn.connected_at is not None
        assert conn.last_heartbeat is not None

    @pytest.mark.asyncio
    async def test_send_event(self):
        """Test sending event to connection."""
        session_id = uuid4()
        user_id = uuid4()
        queue = asyncio.Queue()

        conn = SSEConnection(session_id, user_id, queue)

        event = SSEEvent(
            event_type=SSEEventType.TASK_STARTED,
            payload={"task_id": "test_task"},
            session_id=session_id,
        )

        result = await conn.send_event(event)
        assert result is True

        # Check event is in queue
        queued_event = await queue.get()
        assert queued_event == event

    @pytest.mark.asyncio
    async def test_send_heartbeat(self):
        """Test sending heartbeat."""
        session_id = uuid4()
        user_id = uuid4()
        queue = asyncio.Queue()

        conn = SSEConnection(session_id, user_id, queue)
        old_heartbeat = conn.last_heartbeat

        await asyncio.sleep(0.01)  # Small delay
        result = await conn.send_heartbeat()
        assert result is True

        # Check heartbeat is in queue
        heartbeat = await queue.get()
        assert heartbeat == ": heartbeat\n\n"

        # Check timestamp updated
        assert conn.last_heartbeat > old_heartbeat


class TestSSEManager:
    """Tests for SSEManager class."""

    @pytest_asyncio.fixture
    async def sse_manager(self, mock_redis):
        """Create SSE manager instance."""
        manager = SSEManager(mock_redis)
        await manager.start()
        yield manager
        await manager.stop()

    @pytest.mark.asyncio
    async def test_manager_start_stop(self, mock_redis):
        """Test SSE manager start and stop."""
        manager = SSEManager(mock_redis)

        # Start manager
        await manager.start()
        assert manager._heartbeat_task is not None

        # Stop manager
        await manager.stop()
        assert manager._heartbeat_task is None

    @pytest.mark.asyncio
    async def test_register_connection(self, sse_manager):
        """Test registering SSE connection."""
        session_id = uuid4()
        user_id = uuid4()

        queue = await sse_manager.register_connection(session_id, user_id)

        assert queue is not None
        assert session_id in sse_manager.connections
        assert len(sse_manager.connections[session_id]) == 1
        assert user_id in sse_manager.user_sessions
        assert session_id in sse_manager.user_sessions[user_id]

    @pytest.mark.asyncio
    async def test_unregister_connection(self, sse_manager):
        """Test unregistering SSE connection."""
        session_id = uuid4()
        user_id = uuid4()

        queue = await sse_manager.register_connection(session_id, user_id)
        await sse_manager.unregister_connection(session_id, user_id, queue)

        assert session_id not in sse_manager.connections
        assert user_id not in sse_manager.user_sessions

    @pytest.mark.asyncio
    async def test_multiple_connections_same_session(self, sse_manager):
        """Test multiple connections for same session."""
        session_id = uuid4()
        user_id = uuid4()

        queue1 = await sse_manager.register_connection(session_id, user_id)
        queue2 = await sse_manager.register_connection(session_id, user_id)

        assert len(sse_manager.connections[session_id]) == 2
        assert queue1 != queue2

    @pytest.mark.asyncio
    async def test_broadcast_event(self, sse_manager):
        """Test broadcasting event to session."""
        session_id = uuid4()
        user_id = uuid4()

        # Register two connections
        queue1 = await sse_manager.register_connection(session_id, user_id)
        queue2 = await sse_manager.register_connection(session_id, user_id)

        # Broadcast event
        event = SSEEvent(
            event_type=SSEEventType.TASK_STARTED,
            payload={"task_id": "test_task"},
            session_id=session_id,
        )

        sent_count = await sse_manager.broadcast_event(session_id, event, buffer=False)
        assert sent_count == 2

        # Check both queues received event
        event1 = await queue1.get()
        event2 = await queue2.get()
        assert event1 == event
        assert event2 == event

    @pytest.mark.asyncio
    async def test_broadcast_to_user(self, sse_manager):
        """Test broadcasting event to all user sessions."""
        user_id = uuid4()
        session1_id = uuid4()
        session2_id = uuid4()

        # Register connections for two sessions
        queue1 = await sse_manager.register_connection(session1_id, user_id)
        queue2 = await sse_manager.register_connection(session2_id, user_id)

        # Broadcast to user
        event = SSEEvent(
            event_type=SSEEventType.AGENT_STATUS_CHANGED,
            payload={"agent_id": "test_agent", "status": "busy"},
        )

        sent_count = await sse_manager.broadcast_to_user(user_id, event, buffer=False)
        assert sent_count == 2

        # Check both queues received event
        event1 = await queue1.get()
        event2 = await queue2.get()
        assert event1 == event
        assert event2 == event

    @pytest.mark.asyncio
    async def test_event_buffering(self, sse_manager, mock_redis):
        """Test event buffering in Redis."""
        session_id = uuid4()
        user_id = uuid4()

        # Mock Redis methods
        mock_redis.lpush = AsyncMock(return_value=1)
        mock_redis.ltrim = AsyncMock(return_value=True)
        mock_redis.expire = AsyncMock(return_value=True)
        mock_redis.lrange = AsyncMock(return_value=[])

        # Broadcast event (will be buffered)
        event = SSEEvent(
            event_type=SSEEventType.TASK_COMPLETED,
            payload={"task_id": "test_task", "result": "success"},
            session_id=session_id,
        )

        await sse_manager.broadcast_event(session_id, event, buffer=True)

        # Verify Redis methods were called
        mock_redis.lpush.assert_called_once()
        mock_redis.ltrim.assert_called_once()
        mock_redis.expire.assert_called_once()

    @pytest.mark.asyncio
    async def test_buffered_events_on_reconnect(self, sse_manager, mock_redis):
        """Test sending buffered events on reconnect."""
        session_id = uuid4()
        user_id = uuid4()

        # Mock buffered events
        buffered_events = [
            json.dumps({
                "event_type": "task_progress",
                "payload": {"task_id": "test_task", "progress": i * 33},
                "timestamp": datetime.utcnow().isoformat(),
                "session_id": str(session_id),
            })
            for i in range(3)
        ]
        mock_redis.lrange = AsyncMock(return_value=buffered_events)

        # Register connection (should receive buffered events)
        queue = await sse_manager.register_connection(session_id, user_id)

        # Wait a bit for buffered events to be sent
        await asyncio.sleep(0.1)

        # Check queue has buffered events
        events = []
        while not queue.empty():
            events.append(await queue.get())

        assert len(events) == 3

    @pytest.mark.asyncio
    async def test_buffer_size_limit(self, sse_manager, mock_redis):
        """Test buffer size limit enforcement."""
        session_id = uuid4()

        # Mock Redis methods
        mock_redis.lpush = AsyncMock(return_value=1)
        mock_redis.ltrim = AsyncMock(return_value=True)
        mock_redis.expire = AsyncMock(return_value=True)

        # Buffer more than max size
        for i in range(SSEManager.MAX_BUFFER_SIZE + 10):
            event = SSEEvent(
                event_type=SSEEventType.TASK_PROGRESS,
                payload={"task_id": "test_task", "progress": i},
                session_id=session_id,
            )
            await sse_manager._buffer_event(session_id, event)

        # Verify ltrim was called to limit size
        assert mock_redis.ltrim.call_count == SSEManager.MAX_BUFFER_SIZE + 10

    @pytest.mark.asyncio
    async def test_close_session(self, sse_manager):
        """Test closing all connections for a session."""
        session_id = uuid4()
        user_id = uuid4()

        # Register connections
        queue1 = await sse_manager.register_connection(session_id, user_id)
        queue2 = await sse_manager.register_connection(session_id, user_id)

        # Close session
        await sse_manager.close_session(session_id)

        # Check connections removed
        assert session_id not in sse_manager.connections

        # Check close signal sent to queues
        signal1 = await queue1.get()
        signal2 = await queue2.get()
        # First should be close event, second should be None (close signal)
        assert signal1.event_type == SSEEventType.TASK_COMPLETED
        assert await queue1.get() is None
        assert signal2.event_type == SSEEventType.TASK_COMPLETED
        assert await queue2.get() is None

    @pytest.mark.asyncio
    async def test_get_stats(self, sse_manager):
        """Test getting SSE statistics."""
        user1_id = uuid4()
        user2_id = uuid4()
        session1_id = uuid4()
        session2_id = uuid4()

        # Register connections
        await sse_manager.register_connection(session1_id, user1_id)
        await sse_manager.register_connection(session1_id, user1_id)  # 2nd connection
        await sse_manager.register_connection(session2_id, user2_id)

        stats = await sse_manager.get_stats()

        assert stats["total_connections"] == 3
        assert stats["total_sessions"] == 2
        assert stats["total_users"] == 2
        assert str(session1_id) in stats["connections_per_session"]
        assert stats["connections_per_session"][str(session1_id)] == 2

    @pytest.mark.asyncio
    async def test_large_event_truncation(self, sse_manager):
        """Test large event payload truncation."""
        session_id = uuid4()
        user_id = uuid4()

        queue = await sse_manager.register_connection(session_id, user_id)

        # Create event with large payload
        large_payload = {"data": "x" * (SSEManager.MAX_EVENT_SIZE + 1000)}
        event = SSEEvent(
            event_type=SSEEventType.TASK_COMPLETED,
            payload=large_payload,
            session_id=session_id,
        )

        await sse_manager.broadcast_event(session_id, event, buffer=False)

        # Get event from queue
        received_event = await queue.get()

        # Check payload was truncated
        assert "error" in received_event.payload
        assert "too large" in received_event.payload["error"].lower()


class TestSSEEndpoint:
    """Tests for SSE endpoint."""

    @pytest.mark.asyncio
    async def test_sse_endpoint_requires_auth(self, client: AsyncClient):
        """Test SSE endpoint requires authentication."""
        session_id = uuid4()
        response = await client.get(f"/my/chat/{session_id}/events/")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_sse_endpoint_session_not_found(
        self, client: AsyncClient, auth_headers: dict, test_user: User
    ):
        """Test SSE endpoint with non-existent session."""
        session_id = uuid4()
        response = await client.get(
            f"/my/chat/{session_id}/events/", headers=auth_headers
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_sse_endpoint_success(
        self, client: AsyncClient, auth_headers: dict, test_user: User, db_session: AsyncSession
    ):
        """Test successful SSE connection."""
        # Create session for test user
        session = ChatSession(user_id=test_user.id)
        db_session.add(session)
        await db_session.commit()
        await db_session.refresh(session)

        # Note: AsyncClient with streaming is complex to test
        # This is a basic test to verify endpoint exists and accepts request
        response = await client.get(
            f"/my/chat/{session.id}/events/",
            headers=auth_headers,
        )

        # Should return 200 with text/event-stream content type
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")

    @pytest.mark.asyncio
    async def test_sse_stats_endpoint(
        self, client: AsyncClient, auth_headers: dict, test_user: User
    ):
        """Test SSE stats endpoint."""
        response = await client.get("/my/chat/stats/", headers=auth_headers)
        assert response.status_code == 200

        data = response.json()
        assert "status" in data
        assert "stats" in data
        assert "total_connections" in data["stats"]
        assert "total_sessions" in data["stats"]
        assert "total_users" in data["stats"]


class TestSSEEventSchema:
    """Tests for SSE event schema."""

    def test_event_creation(self):
        """Test creating SSE event."""
        event = SSEEvent(
            event_type=SSEEventType.TASK_STARTED,
            payload={"task_id": "test_task"},
            session_id=uuid4(),
        )

        assert event.event_type == SSEEventType.TASK_STARTED
        assert event.payload == {"task_id": "test_task"}
        assert event.timestamp is not None
        assert event.session_id is not None

    def test_event_to_sse_format(self):
        """Test converting event to SSE format."""
        session_id = uuid4()
        event = SSEEvent(
            event_type=SSEEventType.TASK_COMPLETED,
            payload={"task_id": "test_task", "result": "success"},
            session_id=session_id,
        )

        sse_format = event.to_sse_format()

        assert sse_format.startswith("event: task_completed\n")
        assert "data: " in sse_format
        assert sse_format.endswith("\n\n")

        # Parse data part
        lines = sse_format.split("\n")
        data_line = [line for line in lines if line.startswith("data: ")][0]
        data_json = data_line.replace("data: ", "")
        data = json.loads(data_json)

        assert data["event_type"] == "task_completed"
        assert data["payload"]["task_id"] == "test_task"
        assert data["session_id"] == str(session_id)

    def test_all_event_types(self):
        """Test all event types are valid."""
        event_types = [
            SSEEventType.DIRECT_AGENT_CALL,
            SSEEventType.AGENT_STATUS_CHANGED,
            SSEEventType.TASK_PLAN_CREATED,
            SSEEventType.TASK_STARTED,
            SSEEventType.TASK_PROGRESS,
            SSEEventType.TASK_COMPLETED,
            SSEEventType.TOOL_REQUEST,
            SSEEventType.PLAN_REQUEST,
            SSEEventType.CONTEXT_RETRIEVED,
            SSEEventType.APPROVAL_REQUIRED,
        ]

        for event_type in event_types:
            event = SSEEvent(
                event_type=event_type,
                payload={"test": "data"},
            )
            assert event.event_type == event_type
            assert event.to_sse_format() is not None
