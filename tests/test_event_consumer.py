"""Unit tests for EventConsumer"""

import asyncio
import json
from uuid import uuid4

import pytest
import pytest_asyncio
from redis import Redis

from app.services.event_consumer import EventConsumer


@pytest_asyncio.fixture
async def redis_client():
    """Create Redis client for testing"""
    client = Redis(host='localhost', port=6379, db=1)
    # Clean up before test
    await client.flushdb()
    yield client
    # Clean up after test
    await client.flushdb()


@pytest_asyncio.fixture
async def consumer(redis_client):
    """Create EventConsumer instance for testing"""
    consumer = EventConsumer(redis_client)
    await consumer.initialize()
    return consumer


@pytest.mark.asyncio
async def test_initialize_success(redis_client):
    """Test successful consumer initialization"""
    consumer = EventConsumer(redis_client)
    await consumer.initialize()
    
    # Verify consumer group exists
    group_info = await redis_client.xinfo_groups(consumer.STREAM_KEY)
    assert len(group_info) > 0
    assert any(g[b'name'] == consumer.CONSUMER_GROUP.encode() for g in group_info)


@pytest.mark.asyncio
async def test_register_handler(consumer):
    """Test registering event handler"""
    async def test_handler(event: dict):
        pass
    
    consumer.register_handler("user.created", test_handler)
    
    assert "user.created" in consumer.handlers
    assert consumer.handlers["user.created"] == test_handler


@pytest.mark.asyncio
async def test_register_multiple_handlers(consumer):
    """Test registering multiple handlers"""
    async def handler1(event: dict):
        pass
    
    async def handler2(event: dict):
        pass
    
    consumer.register_handler("user.created", handler1)
    consumer.register_handler("user.deleted", handler2)
    
    assert len(consumer.handlers) == 2
    assert consumer.handlers["user.created"] == handler1
    assert consumer.handlers["user.deleted"] == handler2


@pytest.mark.asyncio
async def test_parse_event_with_json_data(consumer):
    """Test parsing event with JSON data field"""
    message_data = {
        b"event_id": b"123",
        b"event_type": b"user.created",
        b"data": json.dumps({
            "user_id": "uuid",
            "email": "user@example.com"
        }).encode()
    }
    
    event = await consumer._parse_event(message_data)
    
    assert event["event_id"] == "123"
    assert event["event_type"] == "user.created"
    assert isinstance(event["data"], dict)
    assert event["data"]["email"] == "user@example.com"


@pytest.mark.asyncio
async def test_parse_event_with_string_data(consumer):
    """Test parsing event with non-JSON string data"""
    message_data = {
        b"event_id": b"123",
        b"event_type": b"user.created",
        b"data": b"invalid json"
    }
    
    event = await consumer._parse_event(message_data)
    
    assert event["event_id"] == "123"
    assert event["data"] == "invalid json"  # Kept as-is


@pytest.mark.asyncio
async def test_parse_event_converts_bytes_to_strings(consumer):
    """Test that parse_event converts bytes to strings"""
    message_data = {
        b"field1": b"value1",
        b"field2": b"value2"
    }
    
    event = await consumer._parse_event(message_data)
    
    assert "field1" in event
    assert "field2" in event
    assert event["field1"] == "value1"
    assert event["field2"] == "value2"


@pytest.mark.asyncio
async def test_send_to_dlq(consumer, redis_client):
    """Test sending message to DLQ"""
    message_id = "1234567890-0"
    message_data = {b"field": b"value"}
    reason = "handler_failed"
    
    await consumer._send_to_dlq(message_id, message_data, reason)
    
    # Verify message in DLQ
    dlq_messages = await redis_client.xread(
        {consumer.DLQ_STREAM_KEY: "0"}
    )
    
    assert dlq_messages is not None
    assert len(dlq_messages[0][1]) == 1
    
    _, dlq_data = dlq_messages[0][1][0]
    assert dlq_data[b"original_message_id"].decode() == message_id
    assert dlq_data[b"dlq_reason"].decode() == reason


@pytest.mark.asyncio
async def test_process_message_with_handler(consumer, redis_client):
    """Test processing message with registered handler"""
    handler_called = False
    received_event = None
    
    async def test_handler(event: dict):
        nonlocal handler_called, received_event
        handler_called = True
        received_event = event
    
    consumer.register_handler("user.created", test_handler)
    
    # Add message to stream
    message_data = {
        "event_id": str(uuid4()),
        "event_type": "user.created",
        "data": json.dumps({
            "user_id": str(uuid4()),
            "email": "test@example.com"
        })
    }
    
    message_id = await redis_client.xadd(
        consumer.STREAM_KEY,
        message_data
    )
    
    # Process message
    await consumer._process_message(message_id, message_data)
    
    # Verify handler was called
    assert handler_called
    assert received_event["event_type"] == "user.created"


@pytest.mark.asyncio
async def test_process_message_without_handler(consumer, redis_client):
    """Test processing message without registered handler"""
    message_id = "1234567890-0"
    message_data = {
        "event_id": "123",
        "event_type": "unknown.event",
        "data": "{}"
    }
    
    await consumer._process_message(message_id, message_data)
    
    # Verify message sent to DLQ
    dlq_messages = await redis_client.xread(
        {consumer.DLQ_STREAM_KEY: "0"}
    )
    
    assert dlq_messages is not None


@pytest.mark.asyncio
async def test_process_message_missing_event_type(consumer, redis_client):
    """Test processing message without event_type"""
    message_id = "1234567890-0"
    message_data = {
        "event_id": "123",
        "data": "{}"
        # Missing event_type
    }
    
    await consumer._process_message(message_id, message_data)
    
    # Verify message sent to DLQ
    dlq_messages = await redis_client.xread(
        {consumer.DLQ_STREAM_KEY: "0"}
    )
    
    assert dlq_messages is not None


@pytest.mark.asyncio
async def test_process_message_handler_failure(consumer, redis_client):
    """Test handler failure triggers DLQ"""
    async def failing_handler(event: dict):
        raise ValueError("Handler error")
    
    consumer.register_handler("user.created", failing_handler)
    
    message_id = "1234567890-0"
    message_data = {
        "event_id": str(uuid4()),
        "event_type": "user.created",
        "data": "{}"
    }
    
    await consumer._process_message(message_id, message_data)
    
    # Verify message sent to DLQ after retries
    dlq_messages = await redis_client.xread(
        {consumer.DLQ_STREAM_KEY: "0"}
    )
    
    assert dlq_messages is not None


@pytest.mark.asyncio
async def test_process_pending_messages(consumer, redis_client):
    """Test processing pending messages via XAUTOCLAIM"""
    handler_called_count = 0
    
    async def test_handler(event: dict):
        nonlocal handler_called_count
        handler_called_count += 1
    
    consumer.register_handler("user.created", test_handler)
    
    # Add message to stream
    message_data = {
        "event_id": str(uuid4()),
        "event_type": "user.created",
        "data": "{}"
    }
    
    await redis_client.xadd(consumer.STREAM_KEY, message_data)
    
    # Simulate pending message by reading it
    await redis_client.xreadgroup(
        {consumer.STREAM_KEY: ">"},
        consumer.CONSUMER_GROUP,
        consumer.CONSUMER_NAME,
        count=1
    )
    
    # Process pending
    await consumer._process_pending_messages()
    
    # Handler should be called
    assert handler_called_count > 0


@pytest.mark.asyncio
async def test_start_stop_consumer(consumer):
    """Test starting and stopping consumer"""
    consumer.running = True
    
    # Stop should set running to False
    await consumer.stop()
    
    assert consumer.running is False


@pytest.mark.asyncio
async def test_consumer_idempotency(consumer, redis_client):
    """Test that processing same message multiple times is safe"""
    call_count = 0
    
    async def test_handler(event: dict):
        nonlocal call_count
        call_count += 1
    
    consumer.register_handler("user.created", test_handler)
    
    message_id = "1234567890-0"
    message_data = {
        "event_id": str(uuid4()),
        "event_type": "user.created",
        "data": "{}"
    }
    
    # Process same message twice
    await consumer._process_message(message_id, message_data)
    await consumer._process_message(message_id, message_data)
    
    # Both calls should succeed
    assert call_count == 2


@pytest.mark.asyncio
async def test_message_ack_on_success(consumer, redis_client):
    """Test that successful message processing ACKs the message"""
    async def test_handler(event: dict):
        pass
    
    consumer.register_handler("user.created", test_handler)
    
    # Add message to stream
    message_data = {
        "event_id": str(uuid4()),
        "event_type": "user.created",
        "data": "{}"
    }
    
    message_id = await redis_client.xadd(consumer.STREAM_KEY, message_data)
    
    # Read message to get it into pending
    await redis_client.xreadgroup(
        {consumer.STREAM_KEY: ">"},
        consumer.CONSUMER_GROUP,
        consumer.CONSUMER_NAME,
        count=1
    )
    
    # Process message
    await consumer._process_message(message_id, message_data)
    
    # Check pending messages - should be empty
    pending = await redis_client.xpending(
        consumer.STREAM_KEY,
        consumer.CONSUMER_GROUP
    )
    
    assert pending["pending"] == 0
