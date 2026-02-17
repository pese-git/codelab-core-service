"""UserOrchestrator model."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, JSON
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UserOrchestrator(Base):
    """User orchestrator model."""

    __tablename__ = "user_orchestrators"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4, index=True)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("user_projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    config: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="orchestrators")
    project: Mapped["UserProject"] = relationship("UserProject", back_populates="orchestrators")

    # Indexes
    __table_args__ = (
        Index("ix_user_orchestrators_user_id_project_id", "user_id", "project_id"),
    )

    def __repr__(self) -> str:
        return f"<UserOrchestrator(id={self.id}, user_id={self.user_id}, project_id={self.project_id})>"
