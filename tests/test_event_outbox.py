"""Tests for EventOutbox model and outbox functionality."""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EventOutbox, User, UserProject


@pytest.mark.asyncio
async def test_event_outbox_creation(async_session: AsyncSession):
    """Test creating an EventOutbox record."""
    user_id = uuid4()
    project_id = uuid4()
    aggregate_id = uuid4()
    
    event = EventOutbox(
        aggregate_type="chat_message",
        aggregate_id=aggregate_id,
        user_id=user_id,
        project_id=project_id,
        event_type="message_created",
        payload={"content": "Hello", "role": "user"},
        status="pending",
    )
    
    async_session.add(event)
    await async_session.commit()
    
    # Verify event was created
    assert event.id is not None
    assert event.status == "pending"
    assert event.retry_count == 0
    assert event.created_at is not None
    assert event.published_at is None
    assert event.next_retry_at is None
    assert event.last_error is None


@pytest.mark.asyncio
async def test_event_outbox_status_transitions(async_session: AsyncSession):
    """Test status transitions: pending -> published."""
    user_id = uuid4()
    project_id = uuid4()
    
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
    
    # Transition to published
    event.status = "published"
    event.published_at = datetime.utcnow()
    await async_session.commit()
    
    # Verify transition
    await async_session.refresh(event)
    assert event.status == "published"
    assert event.published_at is not None


@pytest.mark.asyncio
async def test_event_outbox_retry_logic(async_session: AsyncSession):
    """Test retry count and next_retry_at tracking."""
    user_id = uuid4()
    project_id = uuid4()
    
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
    
    # Simulate failed publish with retry
    event.retry_count = 1
    event.next_retry_at = datetime.utcnow() + timedelta(seconds=10)
    event.last_error = "Connection timeout"
    await async_session.commit()
    
    # Verify retry state
    await async_session.refresh(event)
    assert event.retry_count == 1
    assert event.next_retry_at is not None
    assert event.last_error == "Connection timeout"
    assert event.status == "pending"


@pytest.mark.asyncio
async def test_event_outbox_payload_jsonb(async_session: AsyncSession):
    """Test JSONB payload storage."""
    user_id = uuid4()
    project_id = uuid4()
    
    complex_payload = {
        "message_id": str(uuid4()),
        "session_id": str(uuid4()),
        "role": "assistant",
        "content": "Complex response",
        "metadata": {
            "agent_id": str(uuid4()),
            "tokens": 150,
            "timestamp": "2026-02-26T20:46:00Z"
        },
        "nested": {
            "level1": {
                "level2": ["a", "b", "c"]
            }
        }
    }
    
    event = EventOutbox(
        aggregate_type="chat_message",
        aggregate_id=uuid4(),
        user_id=user_id,
        project_id=project_id,
        event_type="message_created",
        payload=complex_payload,
        status="pending",
    )
    
    async_session.add(event)
    await async_session.commit()
    
    # Verify complex payload was stored correctly
    await async_session.refresh(event)
    assert event.payload == complex_payload
    assert event.payload["metadata"]["agent_id"] == complex_payload["metadata"]["agent_id"]
    assert event.payload["nested"]["level1"]["level2"] == ["a", "b", "c"]


@pytest.mark.asyncio
async def test_event_outbox_user_project_isolation(async_session: AsyncSession):
    """Test that events are properly isolated by user and project."""
    user1_id = uuid4()
    user2_id = uuid4()
    project1_id = uuid4()
    project2_id = uuid4()
    
    # Create events for different users and projects
    event1 = EventOutbox(
        aggregate_type="chat_message",
        aggregate_id=uuid4(),
        user_id=user1_id,
        project_id=project1_id,
        event_type="message_created",
        payload={"content": "User1 Project1"},
        status="pending",
    )
    
    event2 = EventOutbox(
        aggregate_type="chat_message",
        aggregate_id=uuid4(),
        user_id=user2_id,
        project_id=project2_id,
        event_type="message_created",
        payload={"content": "User2 Project2"},
        status="pending",
    )
    
    async_session.add(event1)
    async_session.add(event2)
    await async_session.commit()
    
    # Query events for user1/project1
    from sqlalchemy import select
    query = select(EventOutbox).where(
        (EventOutbox.user_id == user1_id) & (EventOutbox.project_id == project1_id)
    )
    result = await async_session.execute(query)
    user1_events = result.scalars().all()
    
    assert len(user1_events) == 1
    assert user1_events[0].payload["content"] == "User1 Project1"


@pytest.mark.asyncio
async def test_event_outbox_model_repr(async_session: AsyncSession):
    """Test model string representation."""
    user_id = uuid4()
    project_id = uuid4()
    
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
    
    # Test __repr__
    repr_str = repr(event)
    assert "EventOutbox" in repr_str
    assert "message_created" in repr_str
    assert "pending" in repr_str


@pytest.mark.asyncio
async def test_event_outbox_default_values(async_session: AsyncSession):
    """Test that default values are set correctly."""
    event = EventOutbox(
        aggregate_type="chat_message",
        aggregate_id=uuid4(),
        user_id=uuid4(),
        project_id=uuid4(),
        event_type="message_created",
        payload={"content": "Test"},
    )
    
    async_session.add(event)
    await async_session.commit()
    
    # Verify defaults
    assert event.status == "pending"  # default
    assert event.retry_count == 0  # default
    assert event.created_at is not None  # auto-set
    assert event.published_at is None
    assert event.next_retry_at is None
    assert event.last_error is None
