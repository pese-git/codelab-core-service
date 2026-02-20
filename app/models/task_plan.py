"""TaskPlan model for orchestrator task planning."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String, Boolean, Float
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TaskPlan(Base):
    """Task plan model for orchestrator."""

    __tablename__ = "task_plans"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4, index=True)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("user_projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    original_request: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default="created", nullable=False, index=True
    )  # created, pending_approval, executing, completed, failed, partial_success
    total_estimated_cost: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    total_estimated_duration: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    approval_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="task_plans")
    project: Mapped["UserProject"] = relationship("UserProject", back_populates="task_plans")
    session: Mapped["ChatSession"] = relationship("ChatSession", back_populates="task_plans")
    tasks: Mapped[list["TaskPlanTask"]] = relationship(
        "TaskPlanTask", back_populates="plan", cascade="all, delete-orphan"
    )

    # Indexes
    __table_args__ = (
        Index("ix_task_plans_user_id_project_id", "user_id", "project_id"),
        Index("ix_task_plans_session_id", "session_id"),
        Index("ix_task_plans_status_created_at", "status", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<TaskPlan(id={self.id}, user_id={self.user_id}, status={self.status})>"
