"""Repository for writing events to the event outbox."""

from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EventOutbox


class OutboxRepository:
    """Repository for managing event_outbox writes.
    
    This repository ensures events are written within the same transaction
    as their triggering domain operations (e.g., message creation).
    
    Usage:
        async with async_session.begin():
            # Write domain model
            async_session.add(message)
            # Write event in same transaction
            await OutboxRepository.record_event(
                session=async_session,
                aggregate_type="chat_message",
                aggregate_id=message.id,
                user_id=user_id,
                project_id=project_id,
                event_type="message_created",
                payload={"content": message.content, "role": message.role}
            )
            # Both commit atomically
    """

    @staticmethod
    async def record_event(
        session: AsyncSession,
        aggregate_type: str,
        aggregate_id: UUID,
        user_id: UUID,
        project_id: UUID,
        event_type: str,
        payload: dict,
    ) -> EventOutbox:
        """Record an event in the outbox within current transaction.
        
        Args:
            session: AsyncSession to use for the write
            aggregate_type: Type of aggregate (e.g., "chat_message")
            aggregate_id: ID of the aggregate instance
            user_id: User ID for isolation
            project_id: Project ID for isolation
            event_type: Type of event (e.g., "message_created")
            payload: Event data as JSON-serializable dict
            
        Returns:
            EventOutbox: Created event record
            
        Note:
            This method does NOT commit. The caller is responsible for
            transaction management to ensure atomicity with domain writes.
        """
        event = EventOutbox(
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            user_id=user_id,
            project_id=project_id,
            event_type=event_type,
            payload=payload,
            status="pending",
            retry_count=0,
        )
        session.add(event)
        return event

    @staticmethod
    async def get_pending_events(
        session: AsyncSession,
        batch_size: int = 100,
        user_id: UUID | None = None,
        project_id: UUID | None = None,
    ) -> list[EventOutbox]:
        """Get pending events for publishing.
        
        Queries events that are pending or due for retry.
        Use with FOR UPDATE SKIP LOCKED for safe concurrent publishing.
        
        Args:
            session: AsyncSession to query from
            batch_size: Maximum number of events to return
            user_id: Optional filter by user
            project_id: Optional filter by project
            
        Returns:
            List of pending EventOutbox records
        """
        from sqlalchemy import and_, or_, select

        query = select(EventOutbox).where(
            or_(
                EventOutbox.status == "pending",
                and_(
                    EventOutbox.status == "pending",
                    EventOutbox.next_retry_at <= datetime.utcnow()
                ),
            )
        )

        if user_id:
            query = query.where(EventOutbox.user_id == user_id)
        if project_id:
            query = query.where(EventOutbox.project_id == project_id)

        query = (
            query.order_by(EventOutbox.created_at)
            .limit(batch_size)
        )

        result = await session.execute(query)
        return result.scalars().all()

    @staticmethod
    async def mark_published(
        session: AsyncSession,
        event_id: UUID,
    ) -> None:
        """Mark an event as successfully published.
        
        Args:
            session: AsyncSession to use
            event_id: ID of event to mark
        """
        event = await session.get(EventOutbox, event_id)
        if event:
            event.status = "published"
            event.published_at = datetime.utcnow()
            event.retry_count = 0
            event.next_retry_at = None
            event.last_error = None

    @staticmethod
    async def mark_failed(
        session: AsyncSession,
        event_id: UUID,
        error: str,
        next_retry_at: datetime | None = None,
    ) -> None:
        """Mark an event as failed and schedule retry.
        
        Args:
            session: AsyncSession to use
            event_id: ID of event to mark
            error: Error message from publish attempt
            next_retry_at: When to retry next (None keeps as pending)
        """
        event = await session.get(EventOutbox, event_id)
        if event:
            event.retry_count += 1
            event.last_error = error
            event.next_retry_at = next_retry_at
            # Keep status as pending for retry

    @staticmethod
    async def get_event(
        session: AsyncSession,
        event_id: UUID,
    ) -> EventOutbox | None:
        """Get a specific event by ID.
        
        Args:
            session: AsyncSession to query from
            event_id: ID of event to retrieve
            
        Returns:
            EventOutbox or None if not found
        """
        return await session.get(EventOutbox, event_id)
