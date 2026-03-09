"""UserLLMProvider model."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, Integer, JSON, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UserLLMProvider(Base):
    """
    Пользовательский LLM провайдер.
    
    Хранит метаданные о LLM провайдере пользователя (display_name, provider_type, config).
    API ключи хранятся безопасно в LiteLLM, а не в Core Service.
    """

    __tablename__ = "user_llm_providers"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4, index=True
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )  # e.g., "openai", "anthropic", "google", etc.
    display_name: Mapped[str] = mapped_column(
        String(255), nullable=False
    )  # Пользовательское имя провайдера
    litellm_model_name: Mapped[str] = mapped_column(
        String(255), nullable=False
    )  # Уникальное имя модели в LiteLLM (e.g., user550e8400_openai_abc12345)
    config: Mapped[dict | None] = mapped_column(
        JSON, nullable=True
    )  # Конфигурация без API ключей
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    use_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="llm_providers")
    audit_logs: Mapped[list["LLMProviderAuditLog"]] = relationship(
        "LLMProviderAuditLog", back_populates="provider", cascade="all, delete-orphan"
    )
    agents: Mapped[list["UserAgent"]] = relationship(
        "UserAgent", back_populates="llm_provider"
    )

    # Indexes
    __table_args__ = (
        Index("ix_user_llm_providers_user_created", "user_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<UserLLMProvider(id={self.id}, user_id={self.user_id}, provider_type={self.provider_type}, display_name={self.display_name})>"
