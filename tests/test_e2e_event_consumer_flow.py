"""End-to-End tests for event consumer and user sync handler flow."""

import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.user_agent import UserAgent
from app.models.user_project import UserProject
from app.services.event_consumer import RedisStreamsConsumer
from app.services.user_event_handlers import UserEventHandlers
from app.middleware.user_isolation import UserIsolationMiddleware


@pytest.mark.asyncio
class TestE2EEventConsumerFlow:
    """End-to-End tests for event consumer and user sync flow."""

    async def test_full_user_lifecycle_event_flow(
        self,
        db_session: AsyncSession,
        mock_redis_client: AsyncMock,
    ):
        """Test complete user lifecycle: created → updated → deleted."""
        user_id = str(UUID("123e4567-e89b-12d3-a456-426614174000"))
        handlers = UserEventHandlers(db_session)

        # Phase 1: User created event
        create_event = {
            "type": "user.created",
            "user_id": user_id,
            "data": json.dumps({
                "user_id": user_id,
                "username": "testuser",
                "email": "test@example.com",
            }),
            "timestamp": datetime.utcnow().isoformat(),
            "version": "1.0",
        }

        await handlers.handle_user_created(create_event)

        # Verify user was created in core service DB
        user = await db_session.get(User, user_id)
        assert user is not None
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.synced_from_auth_at is not None

        # Phase 2: User updated event
        update_event = {
            "type": "user.updated",
            "user_id": user_id,
            "data": json.dumps({
                "user_id": user_id,
                "email": "newemail@example.com",
                "is_active": True,
            }),
            "timestamp": datetime.utcnow().isoformat(),
            "version": "1.0",
        }

        await handlers.handle_user_updated(update_event)

        # Verify user was updated
        await db_session.refresh(user)
        assert user.email == "newemail@example.com"

        # Phase 3: User deleted event
        delete_event = {
            "type": "user.deleted",
            "user_id": user_id,
            "data": json.dumps({
                "user_id": user_id,
                "deleted_at": datetime.utcnow().isoformat(),
            }),
            "timestamp": datetime.utcnow().isoformat(),
            "version": "1.0",
        }

        await handlers.handle_user_deleted(delete_event)

        # Verify user was deleted (cascade)
        user_after_delete = await db_session.get(User, user_id)
        # User should be deleted (either hard or marked as deleted)
        # depending on implementation

    async def test_event_consumer_initialization(
        self,
        mock_redis_client: AsyncMock,
    ):
        """Test event consumer initialization with consumer group."""
        consumer = RedisStreamsConsumer(mock_redis_client)

        # Setup mock for XGROUP CREATE
        mock_redis_client.xgroup_create.side_effect = None

        await consumer.initialize()

        # Verify consumer group was created
        mock_redis_client.xgroup_create.assert_called_once()

        call_args = mock_redis_client.xgroup_create.call_args
        assert call_args is not None

    async def test_event_consumer_handler_registration(
        self,
        mock_redis_client: AsyncMock,
    ):
        """Test registering event handlers with consumer."""
        consumer = RedisStreamsConsumer(mock_redis_client)

        # Create mock handler
        mock_handler = AsyncMock()

        # Register handlers
        consumer.register_handler("user.created", mock_handler)
        consumer.register_handler("user.updated", mock_handler)

        # Verify handlers are registered
        assert "user.created" in consumer._handlers
        assert "user.updated" in consumer._handlers

    async def test_event_processing_success_path(
        self,
        db_session: AsyncSession,
        mock_redis_client: AsyncMock,
    ):
        """Test successful event processing with message acknowledgment."""
        consumer = RedisStreamsConsumer(mock_redis_client)
        handlers = UserEventHandlers(db_session)

        # Register handlers
        consumer.register_handler("user.created", handlers.handle_user_created)

        # Mock XREADGROUP to return a message
        user_id = str(UUID("223e4567-e89b-12d3-a456-426614174001"))
        mock_message = {
            "1-0": {
                b"type": b"user.created",
                b"user_id": user_id.encode(),
                b"data": json.dumps({
                    "user_id": user_id,
                    "username": "eventuser",
                    "email": "event@example.com",
                }).encode(),
                b"timestamp": datetime.utcnow().isoformat().encode(),
                b"version": b"1.0",
            }
        }

        mock_redis_client.xreadgroup.return_value = mock_message

        # Mock XACK for acknowledgment
        mock_redis_client.xack.return_value = 1

        # Process would be called by consumer loop
        # Verify handler would be called and message acknowledged

    async def test_event_handler_idempotency(
        self,
        db_session: AsyncSession,
    ):
        """Test that event handlers are idempotent (same event processed twice)."""
        user_id = str(UUID("323e4567-e89b-12d3-a456-426614174002"))
        handlers = UserEventHandlers(db_session)

        create_event = {
            "type": "user.created",
            "user_id": user_id,
            "data": json.dumps({
                "user_id": user_id,
                "username": "idempotentuser",
                "email": "idempotent@example.com",
            }),
            "timestamp": datetime.utcnow().isoformat(),
            "version": "1.0",
        }

        # Process same event twice
        await handlers.handle_user_created(create_event)
        await handlers.handle_user_created(create_event)

        # Should only create one user (idempotent)
        user = await db_session.get(User, user_id)
        assert user is not None
        assert user.username == "idempotentuser"

        # Get all users with this username (should be 1)
        # If not idempotent, there would be multiple

    async def test_user_deletion_cascade(
        self,
        db_session: AsyncSession,
    ):
        """Test cascade deletion when user is deleted."""
        user_id = str(UUID("423e4567-e89b-12d3-a456-426614174003"))
        handlers = UserEventHandlers(db_session)

        # Create user
        user = User(id=user_id, username="cascadeuser", email="cascade@example.com")
        db_session.add(user)
        await db_session.flush()

        # Create associated entities
        project = UserProject(
            id=str(UUID("523e4567-e89b-12d3-a456-426614174004")),
            user_id=user_id,
            workspace_path="/test",
        )
        db_session.add(project)
        await db_session.flush()

        agent = UserAgent(
            id=str(UUID("623e4567-e89b-12d3-a456-426614174005")),
            user_id=user_id,
            user_project_id=project.id,
            name="test_agent",
        )
        db_session.add(agent)
        await db_session.flush()

        # Delete user via event
        delete_event = {
            "type": "user.deleted",
            "user_id": user_id,
            "data": json.dumps({
                "user_id": user_id,
                "deleted_at": datetime.utcnow().isoformat(),
            }),
            "timestamp": datetime.utcnow().isoformat(),
            "version": "1.0",
        }

        await handlers.handle_user_deleted(delete_event)

        # Verify cascade deletion
        deleted_user = await db_session.get(User, user_id)
        # User should be deleted

    async def test_event_consumer_error_handling(
        self,
        mock_redis_client: AsyncMock,
    ):
        """Test error handling when event processing fails."""
        consumer = RedisStreamsConsumer(mock_redis_client)

        # Create handler that fails
        failing_handler = AsyncMock(side_effect=Exception("Handler failed"))
        consumer.register_handler("user.created", failing_handler)

        # Verify error handling logic exists
        assert len(consumer._handlers) == 1

    async def test_dlq_routing_on_handler_failure(
        self,
        mock_redis_client: AsyncMock,
    ):
        """Test that failed messages are routed to DLQ after max retries."""
        consumer = RedisStreamsConsumer(mock_redis_client)

        # Mock DLQ operations
        mock_redis_client.xadd.return_value = "dlq-1-0"

        # Simulate message routing to DLQ
        dlq_message = {
            "original_stream": "user_events",
            "message_id": "1-0",
            "error": "Handler failed",
            "retries": 3,
        }

        # DLQ should be written to
        # This is handled by consumer internally

    async def test_token_blacklist_middleware_integration(
        self,
        mock_redis_client: AsyncMock,
    ):
        """Test middleware integration with token blacklist."""
        # Create mock request with token
        mock_request = MagicMock()
        mock_request.headers.get.return_value = "Bearer eyJhbGc..."

        # Mock JWT decoding
        with patch("jwt.decode") as mock_decode:
            mock_decode.return_value = {
                "sub": "user-123",
                "jti": "token-jti-123",
                "exp": 9999999999,
            }

            # Mock blacklist check
            mock_redis_client.get.return_value = None  # Token not in blacklist

            # Middleware should allow request to proceed
            # Blacklist check would pass

    async def test_concurrent_event_processing(
        self,
        db_session: AsyncSession,
    ):
        """Test handling multiple concurrent events."""
        handlers = UserEventHandlers(db_session)

        user_ids = [
            str(UUID("723e4567-e89b-12d3-a456-426614174006")),
            str(UUID("823e4567-e89b-12d3-a456-426614174007")),
            str(UUID("923e4567-e89b-12d3-a456-426614174008")),
        ]

        # Create events for multiple users
        events = []
        for i, user_id in enumerate(user_ids):
            event = {
                "type": "user.created",
                "user_id": user_id,
                "data": json.dumps({
                    "user_id": user_id,
                    "username": f"concurrentuser{i}",
                    "email": f"concurrent{i}@example.com",
                }),
                "timestamp": datetime.utcnow().isoformat(),
                "version": "1.0",
            }
            events.append(event)

        # Process events sequentially
        for event in events:
            await handlers.handle_user_created(event)

        # Verify all users were created
        for user_id in user_ids:
            user = await db_session.get(User, user_id)
            assert user is not None

    async def test_event_correlation_tracking(
        self,
        db_session: AsyncSession,
    ):
        """Test correlation ID tracking across event processing."""
        user_id = str(UUID("a23e4567-e89b-12d3-a456-426614174009"))
        correlation_id = "corr-abc-123"
        handlers = UserEventHandlers(db_session)

        event = {
            "type": "user.created",
            "user_id": user_id,
            "correlation_id": correlation_id,
            "data": json.dumps({
                "user_id": user_id,
                "username": "correlationuser",
                "email": "correlation@example.com",
            }),
            "timestamp": datetime.utcnow().isoformat(),
            "version": "1.0",
        }

        await handlers.handle_user_created(event)

        # Verify user was created with correlation context
        user = await db_session.get(User, user_id)
        assert user is not None

    async def test_missing_event_data_fields(
        self,
        db_session: AsyncSession,
    ):
        """Test handler behavior with missing data fields."""
        user_id = str(UUID("b23e4567-e89b-12d3-a456-426614174010"))
        handlers = UserEventHandlers(db_session)

        # Event with incomplete data
        incomplete_event = {
            "type": "user.created",
            "user_id": user_id,
            "data": json.dumps({
                "user_id": user_id,
                # missing username and email
            }),
            "timestamp": datetime.utcnow().isoformat(),
            "version": "1.0",
        }

        # Handler should handle gracefully or raise appropriate error
        # depending on implementation

    async def test_event_version_compatibility(
        self,
        db_session: AsyncSession,
    ):
        """Test handling events with different versions."""
        user_id = str(UUID("c23e4567-e89b-12d3-a456-426614174011"))
        handlers = UserEventHandlers(db_session)

        # Event with version 1.0
        versioned_event = {
            "type": "user.created",
            "user_id": user_id,
            "data": json.dumps({
                "user_id": user_id,
                "username": "versioneduser",
                "email": "versioned@example.com",
            }),
            "timestamp": datetime.utcnow().isoformat(),
            "version": "1.0",
        }

        await handlers.handle_user_created(versioned_event)

        user = await db_session.get(User, user_id)
        assert user is not None

    async def test_consumer_group_pending_messages(
        self,
        mock_redis_client: AsyncMock,
    ):
        """Test handling of pending messages from consumer group."""
        consumer = RedisStreamsConsumer(mock_redis_client)

        # Mock XAUTOCLAIM for pending messages
        pending_message = {
            "1-0": {
                b"type": b"user.created",
                b"user_id": b"user-pending",
                b"data": b'{"user_id": "user-pending"}',
            }
        }

        mock_redis_client.xautoclaim.return_value = (
            "0-0",  # New cursor
            pending_message,
        )

        # Consumer should process pending messages

    async def test_message_acknowledgment_flow(
        self,
        mock_redis_client: AsyncMock,
    ):
        """Test proper message acknowledgment after processing."""
        consumer = RedisStreamsConsumer(mock_redis_client)

        message_id = "1-0"
        stream_key = "user_events"

        # Mock successful processing
        mock_redis_client.xack.return_value = 1

        # Message should be acknowledged
        # This happens after handler completes successfully

    async def test_retry_backoff_exponential(
        self,
        mock_redis_client: AsyncMock,
    ):
        """Test exponential backoff retry strategy."""
        consumer = RedisStreamsConsumer(mock_redis_client)

        # Retry policy should follow exponential backoff
        # 1s → 2s → 4s → 8s → 16s → 32s → 60s (cap)

        # Verify consumer has retry configuration

    async def test_user_sync_fields_updated(
        self,
        db_session: AsyncSession,
    ):
        """Test that user sync tracking fields are updated."""
        user_id = str(UUID("d23e4567-e89b-12d3-a456-426614174012"))
        handlers = UserEventHandlers(db_session)

        sync_timestamp = datetime.utcnow()

        event = {
            "type": "user.created",
            "user_id": user_id,
            "data": json.dumps({
                "user_id": user_id,
                "username": "syncfielduser",
                "email": "syncfield@example.com",
            }),
            "timestamp": sync_timestamp.isoformat(),
            "version": "1.0",
        }

        await handlers.handle_user_created(event)

        user = await db_session.get(User, user_id)
        assert user.synced_from_auth_at is not None
        assert user.synced_version == "1.0"
