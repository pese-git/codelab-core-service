"""UserProject model."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UserProject(Base):
    """User project model."""

    __tablename__ = "user_projects"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        index=True
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    workspace_path: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Local path to user's workspace directory"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="projects")
    agents: Mapped[list["UserAgent"]] = relationship(
        "UserAgent",
        back_populates="project",
        cascade="all, delete-orphan"
    )
    chat_sessions: Mapped[list["ChatSession"]] = relationship(
        "ChatSession",
        back_populates="project",
        cascade="all, delete-orphan"
    )
    orchestrators: Mapped[list["UserOrchestrator"]] = relationship(
        "UserOrchestrator",
        back_populates="project",
        cascade="all, delete-orphan"
    )
    task_plans: Mapped[list["TaskPlan"]] = relationship(
        "TaskPlan",
        back_populates="project",
        cascade="all, delete-orphan"
    )

    # Indexes and constraints
    __table_args__ = (
        Index("ix_user_projects_user_id_name", "user_id", "name"),
        Index("ix_user_projects_user_id_created_at", "user_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<UserProject(id={self.id}, user_id={self.user_id}, name={self.name})>"
