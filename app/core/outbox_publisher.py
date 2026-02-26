"""Outbox Publisher Service for reliable event delivery.

Implements the outbox pattern to ensure consistency between domain writes
and event publishing to streaming channels.

Architecture:
- Request-path: events written to outbox in same transaction as messages
- Publisher: background service polls outbox and publishes to stream
- Streaming: events delivered to clients with guaranteed delivery
"""

import asyncio
import logging
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.outbox_repository import OutboxRepository
from app.core.stream_manager import StreamManager
from app.models import EventOutbox
from app.schemas.event import StreamEvent, StreamEventType


logger = logging.getLogger(__name__)


class OutboxPublisher:
    """Background publisher for event outbox.
    
    Responsibilities:
    - Periodically fetch pending events from outbox
    - Publish to StreamManager with retry/backoff
    - Update event status (published/failed)
    - Track metrics and logs
    
    Configuration:
        batch_size: Number of events to process per cycle (default: 100)
        max_retries: Maximum retry attempts before marking as failed (default: 5)
        initial_retry_delay_seconds: Initial backoff delay (default: 5)
        max_retry_delay_seconds: Maximum backoff delay (default: 300)
        poll_interval_seconds: How often to poll for pending events (default: 5)
    """

    def __init__(
        self,
        session_factory: sessionmaker,
        stream_manager: StreamManager,
        batch_size: int = 100,
        max_retries: int = 5,
        initial_retry_delay_seconds: int = 5,
        max_retry_delay_seconds: int = 300,
        poll_interval_seconds: int = 5,
    ):
        """Initialize OutboxPublisher.
        
        Args:
            session_factory: SQLAlchemy sessionmaker for DB access
            stream_manager: StreamManager for publishing events
            batch_size: Events to process per cycle
            max_retries: Maximum retry attempts
            initial_retry_delay_seconds: Initial backoff delay
            max_retry_delay_seconds: Maximum backoff delay
            poll_interval_seconds: Poll frequency
        """
        self.session_factory = session_factory
        self.stream_manager = stream_manager
        self.batch_size = batch_size
        self.max_retries = max_retries
        self.initial_retry_delay_seconds = initial_retry_delay_seconds
        self.max_retry_delay_seconds = max_retry_delay_seconds
        self.poll_interval_seconds = poll_interval_seconds
        
        self._running = False
        self._task: asyncio.Task | None = None
        
        # Metrics
        self.metrics = {
            "published_total": 0,
            "failed_total": 0,
            "pending_count": 0,
        }

    async def start(self) -> None:
        """Start the publisher background task."""
        if self._running:
            logger.warning("OutboxPublisher already running")
            return
        
        self._running = True
        self._task = asyncio.create_task(self._run())
        logger.info("OutboxPublisher started")

    async def stop(self) -> None:
        """Stop the publisher background task."""
        if not self._running:
            logger.warning("OutboxPublisher not running")
            return
        
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        logger.info("OutboxPublisher stopped")

    async def _run(self) -> None:
        """Main publisher loop."""
        logger.info("OutboxPublisher loop started")
        
        while self._running:
            try:
                await self._process_batch()
            except Exception as e:
                logger.error(f"Error in publisher loop: {e}", exc_info=True)
            
            await asyncio.sleep(self.poll_interval_seconds)
        
        logger.info("OutboxPublisher loop stopped")

    async def _process_batch(self) -> None:
        """Process one batch of pending events."""
        async with self.session_factory() as session:
            # Fetch pending events
            query = select(EventOutbox).where(
                and_(
                    EventOutbox.status == "pending",
                    or_(
                        EventOutbox.next_retry_at == None,
                        EventOutbox.next_retry_at <= datetime.utcnow(),
                    ),
                )
            ).order_by(EventOutbox.created_at).limit(self.batch_size)
            
            result = await session.execute(query)
            events = result.scalars().all()
            
            if not events:
                self.metrics["pending_count"] = 0
                return
            
            self.metrics["pending_count"] = len(events)
            logger.debug(f"Processing {len(events)} pending events")
            
            for event in events:
                await self._publish_event(session, event)

    async def _publish_event(
        self,
        session: AsyncSession,
        event: EventOutbox,
    ) -> None:
        """Publish a single event to stream.
        
        Args:
            session: AsyncSession for DB updates
            event: EventOutbox record to publish
        """
        try:
            # Create StreamEvent from outbox event
            stream_event = StreamEvent(
                event_type=StreamEventType(event.event_type),
                payload={
                    **event.payload,
                    "event_id": str(event.id),
                    "aggregate_type": event.aggregate_type,
                    "aggregate_id": str(event.aggregate_id),
                },
                session_id=event.payload.get("session_id"),
            )
            
            # Publish to stream
            await self.stream_manager.broadcast_event(
                session_id=stream_event.session_id,
                event=stream_event,
            )
            
            # Mark as published
            await OutboxRepository.mark_published(session, event.id)
            await session.commit()
            
            self.metrics["published_total"] += 1
            logger.info(
                f"Event published: event_id={event.id}, "
                f"event_type={event.event_type}, "
                f"user_id={event.user_id}"
            )
            
        except Exception as e:
            logger.error(
                f"Failed to publish event: event_id={event.id}, "
                f"event_type={event.event_type}, error={e}",
                exc_info=True
            )
            
            # Calculate next retry time with exponential backoff
            retry_delay = self._calculate_backoff(event.retry_count)
            next_retry_at = datetime.utcnow() + timedelta(seconds=retry_delay)
            
            # Check if exceeded max retries
            if event.retry_count >= self.max_retries:
                await OutboxRepository.mark_failed(
                    session,
                    event.id,
                    error=str(e),
                    next_retry_at=None,  # Stop retrying
                )
                await session.commit()
                
                self.metrics["failed_total"] += 1
                logger.error(
                    f"Event permanently failed: event_id={event.id}, "
                    f"retry_count={event.retry_count}, error={e}"
                )
            else:
                # Schedule retry
                await OutboxRepository.mark_failed(
                    session,
                    event.id,
                    error=str(e),
                    next_retry_at=next_retry_at,
                )
                await session.commit()
                
                logger.info(
                    f"Event scheduled for retry: event_id={event.id}, "
                    f"retry_count={event.retry_count + 1}, "
                    f"next_retry_at={next_retry_at}"
                )

    def _calculate_backoff(self, retry_count: int) -> int:
        """Calculate backoff delay with exponential growth.
        
        Formula: min(initial_delay * 2^retry_count, max_delay)
        
        Args:
            retry_count: Number of previous retries
            
        Returns:
            Delay in seconds
        """
        delay = self.initial_retry_delay_seconds * (2 ** retry_count)
        return min(delay, self.max_retry_delay_seconds)

    def get_metrics(self) -> dict:
        """Get publisher metrics.
        
        Returns:
            Dict with published_total, failed_total, pending_count
        """
        return self.metrics.copy()

    async def reprocess_failed(
        self,
        session: AsyncSession,
        event_id: UUID,
    ) -> None:
        """Reprocess a permanently failed event.
        
        Operator can call this to retry events that exceeded max_retries.
        
        Args:
            session: AsyncSession for DB update
            event_id: ID of failed event to reprocess
        """
        event = await session.get(EventOutbox, event_id)
        if not event:
            logger.warning(f"Event not found for reprocess: event_id={event_id}")
            return
        
        if event.status == "failed":
            event.status = "pending"
            event.retry_count = 0
            event.next_retry_at = None
            event.last_error = None
            await session.commit()
            logger.info(f"Event reprocessed: event_id={event_id}")
        else:
            logger.warning(
                f"Cannot reprocess non-failed event: event_id={event_id}, "
                f"status={event.status}"
            )
