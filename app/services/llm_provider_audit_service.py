"""Service for auditing LLM provider operations."""

import logging
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.llm_provider_audit_log import LLMProviderAuditLog

logger = logging.getLogger(__name__)


class LLMProviderAuditService:
    """
    Сервис для логирования всех операций с LLM провайдерами.
    
    Поддерживаемые action values:
    - create: Создание провайдера
    - update: Обновление конфигурации провайдера
    - delete: Удаление провайдера
    - test: Тестирование подключения к провайдеру
    - use: Использование провайдера агентом
    - provider_reassigned: Переназначение провайдера для агента
    """

    # Валидные значения action
    VALID_ACTIONS = {"create", "update", "delete", "test", "use", "provider_reassigned"}

    def __init__(self, db_session: AsyncSession):
        """
        Initialize audit service.
        
        Args:
            db_session: AsyncSession для работы с БД
        """
        self.db_session = db_session

    async def log_action(
        self,
        user_id: UUID,
        action: str,
        provider_id: UUID | None = None,
        old_values: dict[str, Any] | None = None,
        new_values: dict[str, Any] | None = None,
        success: bool = True,
        error_message: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> LLMProviderAuditLog:
        """
        Логирует операцию с LLM провайдером.
        
        Args:
            user_id: ID пользователя, выполнившего действие
            action: Тип действия (create, update, delete, test, use, provider_reassigned)
            provider_id: ID провайдера (опционально)
            old_values: Старые значения при обновлении
            new_values: Новые значения при создании/обновлении
            success: Была ли операция успешна
            error_message: Сообщение об ошибке (если action failed)
            ip_address: IP адрес запроса
            user_agent: User agent запроса
            
        Returns:
            Созданный LLMProviderAuditLog объект
            
        Raises:
            ValueError: Если action невалидный
        """
        # Валидируем action
        if action not in self.VALID_ACTIONS:
            raise ValueError(
                f"Invalid action '{action}'. Must be one of: {', '.join(self.VALID_ACTIONS)}"
            )

        # Создаём запись в audit log
        audit_log = LLMProviderAuditLog(
            user_id=user_id,
            provider_id=provider_id,
            action=action,
            old_values=old_values,
            new_values=new_values,
            success=success,
            error_message=error_message,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        self.db_session.add(audit_log)
        await self.db_session.flush()  # Flush to ensure ID is generated

        logger.info(
            f"Audit log created: user={user_id}, action={action}, "
            f"provider={provider_id}, success={success}"
        )

        return audit_log

    async def get_audit_log(
        self,
        user_id: UUID,
        provider_id: UUID | None = None,
        action: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[LLMProviderAuditLog], int]:
        """
        Получает историю операций пользователя.
        
        Args:
            user_id: ID пользователя
            provider_id: Фильтровать по провайдеру (опционально)
            action: Фильтровать по типу действия (опционально)
            limit: Максимум записей
            offset: Смещение для пагинации
            
        Returns:
            Кортеж (список записей, общее количество)
        """
        # Построить базовый query
        query = select(LLMProviderAuditLog).where(
            LLMProviderAuditLog.user_id == user_id
        )

        # Добавить фильтры
        if provider_id is not None:
            query = query.where(LLMProviderAuditLog.provider_id == provider_id)

        if action is not None:
            if action not in self.VALID_ACTIONS:
                logger.warning(f"Invalid action filter: {action}")
            else:
                query = query.where(LLMProviderAuditLog.action == action)

        # Получить общее количество
        count_query = select(func.count()).select_from(LLMProviderAuditLog).where(
            LLMProviderAuditLog.user_id == user_id
        )
        if provider_id is not None:
            count_query = count_query.where(LLMProviderAuditLog.provider_id == provider_id)
        if action is not None:
            count_query = count_query.where(LLMProviderAuditLog.action == action)

        total = await self.db_session.scalar(count_query)

        # Сортировка по времени (новые сверху)
        query = query.order_by(LLMProviderAuditLog.created_at.desc())

        # Пагинация
        query = query.limit(limit).offset(offset)

        # Выполнить query
        result = await self.db_session.execute(query)
        logs = result.scalars().all()

        return logs, total or 0

    async def get_provider_actions_summary(
        self, provider_id: UUID, user_id: UUID
    ) -> dict[str, int]:
        """
        Получает статистику операций для провайдера.
        
        Args:
            provider_id: ID провайдера
            user_id: ID пользователя (для проверки доступа)
            
        Returns:
            Словарь с количеством каждого типа операции
        """
        logs, _ = await self.get_audit_log(
            user_id=user_id,
            provider_id=provider_id,
            limit=10000,
        )

        summary = dict.fromkeys(self.VALID_ACTIONS, 0)
        for log in logs:
            summary[log.action] += 1

        return summary
