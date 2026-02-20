"""TaskPlanTask model for individual tasks within a plan."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String, Float, JSON
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TaskPlanTask(Base):
    """Task within a task plan."""

    __tablename__ = "task_plan_tasks"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4, index=True)
    plan_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("task_plans.id", ondelete="CASCADE"), nullable=False, index=True
    )
    task_id: Mapped[str] = mapped_column(String(50), nullable=False)  # logical ID: task_0, task_1, ...
    description: Mapped[str] = mapped_column(String, nullable=False)
    agent_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("user_agents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    dependencies: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)  # list of task_ids
    estimated_cost: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    estimated_duration: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    risk_level: Mapped[str] = mapped_column(
        String(10), default="LOW", nullable=False
    )  # LOW, MEDIUM, HIGH
    status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False, index=True
    )  # pending, executing, completed, failed, aborted
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    plan: Mapped["TaskPlan"] = relationship("TaskPlan", back_populates="tasks")
    agent: Mapped["UserAgent"] = relationship("UserAgent")

    def __repr__(self) -> str:
        return f"<TaskPlanTask(id={self.id}, plan_id={self.plan_id}, task_id={self.task_id}, status={self.status})>"
