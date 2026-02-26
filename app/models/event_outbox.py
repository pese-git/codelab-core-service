"""Event Outbox model for transactional event publishing."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, String, Index, Integer, TIMESTAMP, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class EventOutbox(Base):
    """Event Outbox model.
    
    Stores events in a transactional outbox buffer to ensure consistency between
    domain writes (e.g., messages) and event publishing to streaming channels.
    
    Events flow:
    1. Request-path: event written in same transaction as messages
    2. Publisher: OutboxPublisher picks pending events and publishes to stream
    3. Streaming: events delivered to clients
    
    Attributes:
        id: Unique event identifier (used as event_id in payload)
        aggregate_type: Type of aggregate (e.g., "chat_message")
        aggregate_id: ID of the aggregate (e.g., message_id)
        user_id: User who triggered the event (for isolation)
        project_id: Project context (for isolation)
        event_type: Type of event (e.g., "message_created", "agent_switched")
        payload: Event data as JSON object
        status: Event status (pending, published, failed)
        retry_count: Number of publish attempts
        next_retry_at: When to retry if published failed
        created_at: When event was recorded
        published_at: When event was successfully published
        last_error: Error message from last failed publish attempt
    """

    __tablename__ = "event_outbox"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        index=True
    )
    aggregate_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True
    )
    aggregate_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True
    )
    project_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True
    )
    event_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )
    payload: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        index=True
    )  # pending, published, failed
    retry_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0
    )
    next_retry_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
        index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default=datetime.utcnow,
        nullable=False,
        index=True
    )
    published_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True
    )
    last_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    # Composite indexes for efficient querying
    __table_args__ = (
        Index("ix_event_outbox_status_next_retry_created", "status", "next_retry_at", "created_at"),
        Index("ix_event_outbox_aggregate_id_created", "aggregate_id", "created_at"),
        Index("ix_event_outbox_project_id_created", "project_id", "created_at"),
        Index("ix_event_outbox_user_id_created", "user_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<EventOutbox(id={self.id}, event_type={self.event_type}, status={self.status})>"
