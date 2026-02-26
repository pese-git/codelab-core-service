"""Message model."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, JSON
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Message(Base):
    """Message model.
    
    Stores chat messages with optional structured data.
    - content: user-facing text message (always present)
    - payload: structured data (JSON object with additional context, optional)
    """

    __tablename__ = "messages"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4, index=True)
    session_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # user, assistant, system
    content: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict | None] = mapped_column(
        JSON, nullable=True
    )  # Structured data from agent (architecture decisions, analysis, etc.)
    agent_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("user_agents.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    # Relationships
    session: Mapped["ChatSession"] = relationship("ChatSession", back_populates="messages")
    agent: Mapped["UserAgent | None"] = relationship("UserAgent", back_populates="messages")

    # Indexes
    __table_args__ = (
        Index("ix_messages_session_id_created_at", "session_id", "created_at"),
        Index("ix_messages_agent_id_created_at", "agent_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Message(id={self.id}, session_id={self.session_id}, role={self.role})>"
