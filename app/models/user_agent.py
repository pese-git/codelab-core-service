"""UserAgent model."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, JSON, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UserAgent(Base):
    """User agent model."""

    __tablename__ = "user_agents"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4, index=True)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("user_projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    config: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default="ready", nullable=False, index=True
    )  # ready, busy, error
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="agents")
    project: Mapped["UserProject"] = relationship("UserProject", back_populates="agents")
    messages: Mapped[list["Message"]] = relationship(
        "Message", back_populates="agent", cascade="all, delete-orphan"
    )
    tasks: Mapped[list["Task"]] = relationship(
        "Task", back_populates="agent", cascade="all, delete-orphan"
    )

    # Indexes
    __table_args__ = (
        Index("ix_user_agents_user_id_project_id_name", "user_id", "project_id", "name"),
        Index("ix_user_agents_project_id_status", "project_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<UserAgent(id={self.id}, user_id={self.user_id}, name={self.name}, status={self.status})>"

    @property
    def agent_id(self) -> str:
        """Generate unique agent ID."""
        return f"user{self.user_id}_{self.name}_{self.id}"
