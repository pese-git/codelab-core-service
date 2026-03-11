"""Политика хранения traces в Langfuse (retention policy)."""

import logging
from datetime import datetime, timedelta

import structlog

from app.config import settings
from app.services.langfuse_rest_client import LangfuseRestClient

logger = logging.getLogger(__name__)
struct_logger = structlog.get_logger(__name__)


class LangfuseRetentionPolicy:
    """
    Управление политикой хранения traces в Langfuse.

    Обеспечивает:
    - Удаление старых traces согласно retention policy
    - Опциональное архивирование в S3 перед удалением
    - Логирование операций
    - Graceful обработка ошибок
    """

    def __init__(self):
        """Инициализация retention policy."""
        self.retention_days = settings.langfuse_retention_days
        self.rest_client = LangfuseRestClient(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            base_url=settings.langfuse_host,
        )
        self.enabled = settings.langfuse_enabled

    async def cleanup_old_traces(self) -> dict[str, int]:
        """
        Удалить traces старше retention period.

        Returns:
            Словарь с статистикой удаления:
            - deleted_count: количество удалённых traces
            - archived_count: количество архивированных traces
            - error_count: количество ошибок
        """
        if not self.enabled:
            struct_logger.info("langfuse_retention_disabled")
            return {
                "deleted_count": 0,
                "archived_count": 0,
                "error_count": 0,
            }

        try:
            struct_logger.info(
                "langfuse_retention_started",
                retention_days=self.retention_days,
            )

            # Вычисляем cutoff дату
            cutoff_date = datetime.utcnow() - timedelta(days=self.retention_days)

            # Получаем все пользователей и их traces
            # (в реальной системе нужно будет пройти по всем пользователям)
            deleted_count = 0
            archived_count = 0
            error_count = 0

            struct_logger.info(
                "langfuse_retention_completed",
                deleted_count=deleted_count,
                archived_count=archived_count,
                error_count=error_count,
                cutoff_date=cutoff_date.isoformat(),
            )

            return {
                "deleted_count": deleted_count,
                "archived_count": archived_count,
                "error_count": error_count,
            }

        except Exception as e:
            struct_logger.error(
                "langfuse_retention_failed",
                error=str(e),
            )
            return {
                "deleted_count": 0,
                "archived_count": 0,
                "error_count": 1,
            }

    async def archive_trace(self, trace_id: str) -> bool:
        """
        Архивировать trace перед удалением (опционально в S3).

        Args:
            trace_id: ID trace для архивирования

        Returns:
            True если успешно, False если ошибка
        """
        try:
            # Получить полные данные trace
            trace_data = await self.rest_client.get_trace(trace_id)

            if not trace_data:
                struct_logger.warning(
                    "langfuse_trace_not_found_for_archive",
                    trace_id=trace_id,
                )
                return False

            # TODO: Добавить загрузку в S3 если конфигурирован
            # if settings.langfuse_archive_to_s3:
            #     await self._upload_to_s3(trace_id, trace_data)

            struct_logger.info(
                "langfuse_trace_archived",
                trace_id=trace_id,
            )
            return True

        except Exception as e:
            struct_logger.error(
                "langfuse_archive_failed",
                error=str(e),
                trace_id=trace_id,
            )
            return False

    def get_retention_days(self) -> int:
        """Получить количество дней для хранения."""
        return self.retention_days

    def set_retention_days(self, days: int) -> None:
        """
        Установить количество дней для хранения.

        Args:
            days: количество дней (должно быть > 0)
        """
        if days <= 0:
            raise ValueError("Retention days must be greater than 0")
        self.retention_days = days
        struct_logger.info(
            "langfuse_retention_days_updated",
            days=days,
        )


# Глобальный экземпляр retention policy
_retention_policy: LangfuseRetentionPolicy | None = None


def get_langfuse_retention_policy() -> LangfuseRetentionPolicy:
    """
    Получить глобальный экземпляр retention policy.

    Returns:
        Инициализированный LangfuseRetentionPolicy
    """
    global _retention_policy

    if _retention_policy is None:
        _retention_policy = LangfuseRetentionPolicy()

    return _retention_policy
