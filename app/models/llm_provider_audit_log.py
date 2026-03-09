"""LLMProviderAuditLog model."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class LLMProviderAuditLog(Base):
    """
    Журнал аудита операций с LLM провайдерами.
    
    Логирует все операции с провайдерами для полной истории и отладки:
    - create: создание провайдера
    - update: обновление конфигурации
    - delete: удаление провайдера
    - test: тестирование подключения
    - use: использование провайдера агентом
    """

    __tablename__ = "llm_provider_audit_log"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4, index=True
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("user_llm_providers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    action: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )  # create, update, delete, test, use, provider_reassigned
    old_values: Mapped[dict | None] = mapped_column(
        JSON, nullable=True
    )  # Старые значения при обновлении
    new_values: Mapped[dict | None] = mapped_column(
        JSON, nullable=True
    )  # Новые значения при обновлении
    success: Mapped[bool] = mapped_column(
        nullable=False, default=True
    )  # Была ли операция успешна
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship("User")
    provider: Mapped["UserLLMProvider"] = relationship(
        "UserLLMProvider", back_populates="audit_logs"
    )

    # Indexes
    __table_args__ = (
        Index("ix_llm_provider_audit_log_user_created", "user_id", "created_at"),
        Index("ix_llm_provider_audit_log_action_created", "action", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<LLMProviderAuditLog(id={self.id}, user_id={self.user_id}, action={self.action}, success={self.success})>"
