"""Tests for OutboxPublisher service."""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.outbox_publisher import OutboxPublisher
from app.core.outbox_repository import OutboxRepository
from app.core.stream_manager import StreamManager
from app.models import EventOutbox


@pytest.mark.asyncio
async def test_outbox_publisher_lifecycle(async_session: AsyncSession):
    """Test publisher start/stop lifecycle."""
    # This is an integration test that requires full setup
    # For now, test that OutboxPublisher can be instantiated
    
    async_session_factory = lambda: async_session
    
    # Create a mock stream manager
    stream_manager = AsyncMockStreamManager()
    
    publisher = OutboxPublisher(
        session_factory=async_session_factory,
        stream_manager=stream_manager,
        poll_interval_seconds=1,
    )
    
    assert not publisher._running
    assert publisher.metrics["published_total"] == 0


@pytest.mark.asyncio
async def test_outbox_publisher_backoff_calculation():
    """Test exponential backoff calculation."""
    stream_manager = AsyncMockStreamManager()
    
    publisher = OutboxPublisher(
        session_factory=None,
        stream_manager=stream_manager,
        initial_retry_delay_seconds=5,
        max_retry_delay_seconds=300,
    )
    
    # Test backoff progression
    assert publisher._calculate_backoff(0) == 5  # 5 * 2^0 = 5
    assert publisher._calculate_backoff(1) == 10  # 5 * 2^1 = 10
    assert publisher._calculate_backoff(2) == 20  # 5 * 2^2 = 20
    assert publisher._calculate_backoff(3) == 40  # 5 * 2^3 = 40
    assert publisher._calculate_backoff(4) == 80  # 5 * 2^4 = 80
    assert publisher._calculate_backoff(5) == 160  # 5 * 2^5 = 160
    assert publisher._calculate_backoff(10) == 300  # capped at max


@pytest.mark.asyncio
async def test_outbox_publisher_get_metrics():
    """Test metrics collection."""
    stream_manager = AsyncMockStreamManager()
    
    publisher = OutboxPublisher(
        session_factory=None,
        stream_manager=stream_manager,
    )
    
    metrics = publisher.get_metrics()
    
    assert "published_total" in metrics
    assert "failed_total" in metrics
    assert "pending_count" in metrics
    assert metrics["published_total"] == 0
    assert metrics["failed_total"] == 0
    assert metrics["pending_count"] == 0


@pytest.mark.asyncio
async def test_outbox_mark_published(async_session: AsyncSession):
    """Test marking event as published."""
    user_id = uuid4()
    project_id = uuid4()
    
    # Create pending event
    event = EventOutbox(
        aggregate_type="chat_message",
        aggregate_id=uuid4(),
        user_id=user_id,
        project_id=project_id,
        event_type="message_created",
        payload={"content": "Test"},
        status="pending",
    )
    
    async_session.add(event)
    await async_session.commit()
    event_id = event.id
    
    # Mark as published
    await OutboxRepository.mark_published(async_session, event_id)
    await async_session.commit()
    
    # Verify
    updated_event = await async_session.get(EventOutbox, event_id)
    assert updated_event.status == "published"
    assert updated_event.published_at is not None
    assert updated_event.retry_count == 0
    assert updated_event.next_retry_at is None


@pytest.mark.asyncio
async def test_outbox_mark_failed_with_retry(async_session: AsyncSession):
    """Test marking event as failed with retry scheduling."""
    user_id = uuid4()
    project_id = uuid4()
    
    # Create pending event
    event = EventOutbox(
        aggregate_type="chat_message",
        aggregate_id=uuid4(),
        user_id=user_id,
        project_id=project_id,
        event_type="message_created",
        payload={"content": "Test"},
        status="pending",
    )
    
    async_session.add(event)
    await async_session.commit()
    event_id = event.id
    
    # Mark as failed with retry
    next_retry = datetime.utcnow() + timedelta(seconds=10)
    await OutboxRepository.mark_failed(
        async_session,
        event_id,
        error="Connection timeout",
        next_retry_at=next_retry,
    )
    await async_session.commit()
    
    # Verify
    updated_event = await async_session.get(EventOutbox, event_id)
    assert updated_event.status == "pending"  # Still pending for retry
    assert updated_event.retry_count == 1
    assert updated_event.last_error == "Connection timeout"
    assert updated_event.next_retry_at is not None


@pytest.mark.asyncio
async def test_outbox_mark_failed_permanent(async_session: AsyncSession):
    """Test marking event as permanently failed."""
    user_id = uuid4()
    project_id = uuid4()
    
    # Create pending event
    event = EventOutbox(
        aggregate_type="chat_message",
        aggregate_id=uuid4(),
        user_id=user_id,
        project_id=project_id,
        event_type="message_created",
        payload={"content": "Test"},
        status="pending",
    )
    
    async_session.add(event)
    await async_session.commit()
    event_id = event.id
    
    # Mark as failed without retry (permanent failure)
    await OutboxRepository.mark_failed(
        async_session,
        event_id,
        error="Permanent error",
        next_retry_at=None,
    )
    await async_session.commit()
    
    # Verify
    updated_event = await async_session.get(EventOutbox, event_id)
    assert updated_event.status == "pending"  # Status doesn't change to "failed" automatically
    assert updated_event.retry_count == 1
    assert updated_event.last_error == "Permanent error"
    assert updated_event.next_retry_at is None  # No retry scheduled


@pytest.mark.asyncio
async def test_outbox_record_event(async_session: AsyncSession):
    """Test recording event via repository."""
    user_id = uuid4()
    project_id = uuid4()
    aggregate_id = uuid4()
    
    event = await OutboxRepository.record_event(
        session=async_session,
        aggregate_type="chat_message",
        aggregate_id=aggregate_id,
        user_id=user_id,
        project_id=project_id,
        event_type="message_created",
        payload={"content": "Test message", "role": "user"},
    )
    
    await async_session.commit()
    
    # Verify
    assert event.id is not None
    assert event.status == "pending"
    assert event.retry_count == 0
    assert event.user_id == user_id
    assert event.project_id == project_id
    assert event.payload["content"] == "Test message"


@pytest.mark.asyncio
async def test_outbox_get_pending_events(async_session: AsyncSession):
    """Test querying pending events."""
    user1_id = uuid4()
    user2_id = uuid4()
    project1_id = uuid4()
    project2_id = uuid4()
    
    # Create events for different users/projects
    event1 = EventOutbox(
        aggregate_type="chat_message",
        aggregate_id=uuid4(),
        user_id=user1_id,
        project_id=project1_id,
        event_type="message_created",
        payload={"content": "Test 1"},
        status="pending",
    )
    
    event2 = EventOutbox(
        aggregate_type="chat_message",
        aggregate_id=uuid4(),
        user_id=user2_id,
        project_id=project2_id,
        event_type="message_created",
        payload={"content": "Test 2"},
        status="pending",
    )
    
    event3 = EventOutbox(
        aggregate_type="chat_message",
        aggregate_id=uuid4(),
        user_id=user1_id,
        project_id=project1_id,
        event_type="message_created",
        payload={"content": "Test 3"},
        status="published",  # Already published
    )
    
    async_session.add_all([event1, event2, event3])
    await async_session.commit()
    
    # Get pending events for user1
    pending = await OutboxRepository.get_pending_events(
        async_session,
        user_id=user1_id,
    )
    
    assert len(pending) == 1
    assert pending[0].payload["content"] == "Test 1"


# Mock for testing
class AsyncMockStreamManager:
    """Mock StreamManager for testing."""
    
    async def broadcast_event(self, session_id, event):
        """Mock broadcast_event method."""
        pass
