"""Service for managing user LLM providers."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.logging_config import get_logger
from app.models.user_agent import UserAgent
from app.models.user_llm_provider import UserLLMProvider
from app.services.litellm_client import LiteLLMClient
from app.services.llm_provider_audit_service import LLMProviderAuditService

logger = get_logger(__name__)


class LLMProviderNotFoundError(Exception):
    """
    Исключение, выбрасываемое когда провайдер не найден.
    
    Raised when LLM provider is not found.
    """
    pass


class LLMProviderInUseError(Exception):
    """
    Исключение, выбрасываемое при попытке удалить провайдер,
    который используется агентами.
    
    Raised when trying to delete a provider that is in use by agents.
    """
    pass


class LLMProviderService:
    """
    Сервис для управления LLM провайдерами пользователя.
    
    Отвечает за:
    - Создание/чтение/обновление/удаление провайдеров
    - Интеграцию с LiteLLM для регистрации моделей
    - Тестирование подключения к провайдерам
    - Отслеживание использования провайдеров
    - Аудит всех операций
    """

    def __init__(self, db_session: AsyncSession):
        """
        Initialize LLM provider service.
        
        Args:
            db_session: AsyncSession для работы с БД
        """
        self.db_session = db_session
        self.litellm_client = LiteLLMClient()
        self.audit_service = LLMProviderAuditService(db_session)

    async def create_user_provider(
        self,
        user_id: UUID,
        provider_type: str,
        display_name: str,
        api_key: str,
        config: dict[str, Any] | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> UserLLMProvider:
        """
        Создаёт новый LLM провайдер для пользователя.
        
        Args:
            user_id: ID пользователя
            provider_type: Тип провайдера (openai, anthropic, etc.)
            display_name: Отображаемое имя провайдера
            api_key: API ключ для провайдера
            config: Дополнительная конфигурация
            ip_address: IP адрес запроса (для аудита)
            user_agent: User agent запроса (для аудита)
            
        Returns:
            Созданный UserLLMProvider объект
            
        Raises:
            ValueError: Если конфигурация невалидна
            httpx.HTTPError: Если ошибка при регистрации в LiteLLM
        """
        try:
            # 1. Регистрируем модель в LiteLLM
            litellm_model_name = await self.litellm_client.add_model(
                user_id=user_id,
                provider_type=provider_type,
                api_key=api_key,
                config=config,
            )

            # 2. Создаём запись в БД
            provider = UserLLMProvider(
                user_id=user_id,
                provider_type=provider_type,
                display_name=display_name,
                litellm_model_name=litellm_model_name,
                config=config,
            )

            self.db_session.add(provider)
            await self.db_session.flush()

            # 3. Логируем в аудит
            await self.audit_service.log_action(
                user_id=user_id,
                action="create",
                provider_id=provider.id,
                new_values={
                    "display_name": display_name,
                    "provider_type": provider_type,
                    "litellm_model_name": litellm_model_name,
                },
                success=True,
                ip_address=ip_address,
                user_agent=user_agent,
            )

            logger.info(
                "llm_provider_created",
                user_id=str(user_id),
                provider_id=str(provider.id),
                provider_type=provider_type,
            )

            return provider

        except Exception as e:
            # Логируем ошибку в аудит
            await self.audit_service.log_action(
                user_id=user_id,
                action="create",
                new_values={"display_name": display_name, "provider_type": provider_type},
                success=False,
                error_message=str(e),
                ip_address=ip_address,
                user_agent=user_agent,
            )
            logger.error(
                "failed_to_create_llm_provider",
                user_id=str(user_id),
                error=str(e),
            )
            raise

    async def get_user_provider(
        self, user_id: UUID, provider_id: UUID
    ) -> UserLLMProvider:
        """
        Получает провайдер пользователя.
        
        Args:
            user_id: ID пользователя
            provider_id: ID провайдера
            
        Returns:
            UserLLMProvider объект
            
        Raises:
            LLMProviderNotFoundError: Если провайдер не найден
        """
        query = select(UserLLMProvider).where(
            UserLLMProvider.id == provider_id,
            UserLLMProvider.user_id == user_id,
        )

        result = await self.db_session.execute(query)
        provider = result.scalars().first()

        if not provider:
            raise LLMProviderNotFoundError(
                f"Provider {provider_id} not found for user {user_id}"
            )

        return provider

    async def get_user_providers(
        self, user_id: UUID, limit: int = 100, offset: int = 0
    ) -> tuple[list[UserLLMProvider], int]:
        """
        Получает список провайдеров пользователя.
        
        Args:
            user_id: ID пользователя
            limit: Максимум результатов
            offset: Смещение для пагинации
            
        Returns:
            Кортеж (список провайдеров, общее количество)
        """
        # Получить общее количество
        count_query = select(func.count()).select_from(UserLLMProvider).where(
            UserLLMProvider.user_id == user_id
        )
        total = await self.db_session.scalar(count_query)

        # Получить провайдеры
        query = (
            select(UserLLMProvider)
            .where(UserLLMProvider.user_id == user_id)
            .order_by(UserLLMProvider.created_at.desc())
            .limit(limit)
            .offset(offset)
        )

        result = await self.db_session.execute(query)
        providers = result.scalars().all()

        return providers, total or 0

    async def update_user_provider(
        self,
        user_id: UUID,
        provider_id: UUID,
        display_name: str | None = None,
        config: dict[str, Any] | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> UserLLMProvider:
        """
        Обновляет конфигурацию провайдера.
        
        ВАЖНО: API ключ НЕ может быть изменён через этот метод.
        Для смены ключа нужно удалить и пересоздать провайдер.
        
        Args:
            user_id: ID пользователя
            provider_id: ID провайдера
            display_name: Новое отображаемое имя (опционально)
            config: Новая конфигурация (опционально)
            ip_address: IP адрес запроса (для аудита)
            user_agent: User agent запроса (для аудита)
            
        Returns:
            Обновлённый UserLLMProvider объект
            
        Raises:
            LLMProviderNotFoundError: Если провайдер не найден
            ValueError: Если попытка обновить api_key
        """
        provider = await self.get_user_provider(user_id, provider_id)

        # Валидация: запрещаем обновление API ключа
        if config is not None and "api_key" in config:
            logger.warning(
                f"Attempt to update api_key for provider {provider_id}: user={user_id}"
            )
            raise ValueError(
                "API key cannot be updated. To change API key, delete and recreate the provider."
            )

        # Сохраняем старые значения для аудита
        old_values = {
            "display_name": provider.display_name,
            "config": provider.config,
        }

        # Обновляем поля
        if display_name is not None:
            provider.display_name = display_name

        if config is not None:
            provider.config = config

        provider.updated_at = datetime.utcnow()

        await self.db_session.flush()

        # Логируем в аудит
        new_values = {
            "display_name": provider.display_name,
            "config": provider.config,
        }

        await self.audit_service.log_action(
            user_id=user_id,
            action="update",
            provider_id=provider_id,
            old_values=old_values,
            new_values=new_values,
            success=True,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        logger.info(f"LLM provider updated: user={user_id}, provider={provider_id}")

        return provider

    async def delete_user_provider(
        self,
        user_id: UUID,
        provider_id: UUID,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        """
        Удаляет провайдер пользователя.
        
        Args:
            user_id: ID пользователя
            provider_id: ID провайдера
            ip_address: IP адрес запроса (для аудита)
            user_agent: User agent запроса (для аудита)
            
        Raises:
            LLMProviderNotFoundError: Если провайдер не найден
            LLMProviderInUseError: Если провайдер используется агентами
        """
        provider = await self.get_user_provider(user_id, provider_id)

        # Проверяем, не используется ли провайдер
        agent_count = await self._count_agents_using_provider(provider_id)
        if agent_count > 0:
            raise LLMProviderInUseError(
                f"Cannot delete provider {provider_id}: it's used by {agent_count} agent(s)"
            )

        try:
            # Удаляем модель из LiteLLM
            await self.litellm_client.delete_model(provider.litellm_model_name)

            # Удаляем из БД
            old_values = {
                "display_name": provider.display_name,
                "provider_type": provider.provider_type,
                "use_count": provider.use_count,
            }

            await self.db_session.delete(provider)
            await self.db_session.flush()

            # Логируем в аудит
            await self.audit_service.log_action(
                user_id=user_id,
                action="delete",
                provider_id=provider_id,
                old_values=old_values,
                success=True,
                ip_address=ip_address,
                user_agent=user_agent,
            )

            logger.info(f"LLM provider deleted: user={user_id}, provider={provider_id}")

        except Exception as e:
            # Логируем ошибку в аудит
            await self.audit_service.log_action(
                user_id=user_id,
                action="delete",
                provider_id=provider_id,
                old_values={"display_name": provider.display_name},
                success=False,
                error_message=str(e),
                ip_address=ip_address,
                user_agent=user_agent,
            )
            logger.error(f"Failed to delete LLM provider: {str(e)}")
            raise

    async def test_provider(
        self,
        user_id: UUID,
        provider_id: UUID,
        test_prompt: str = "Hello, how are you?",
        max_tokens: int = 100,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> dict[str, Any]:
        """
        Тестирует подключение к провайдеру.
        
        Args:
            user_id: ID пользователя
            provider_id: ID провайдера
            test_prompt: Тестовый запрос
            max_tokens: Максимум токенов в ответе
            ip_address: IP адрес запроса (для аудита)
            user_agent: User agent запроса (для аудита)
            
        Returns:
            Результат теста (success, response, error, latency_ms, message)
            
        Raises:
            LLMProviderNotFoundError: Если провайдер не найден
        """
        provider = await self.get_user_provider(user_id, provider_id)

        # Тестируем провайдер
        test_result = await self.litellm_client.test_model(
            litellm_model_name=provider.litellm_model_name,
            test_prompt=test_prompt,
            max_tokens=max_tokens,
        )

        # Добавляем message в результат
        if test_result["success"]:
            test_result["message"] = "Provider is working correctly"
        else:
            test_result["message"] = f"Provider test failed: {test_result.get('error', 'Unknown error')}"

        # Логируем в аудит
        await self.audit_service.log_action(
            user_id=user_id,
            action="test",
            provider_id=provider_id,
            success=test_result["success"],
            error_message=test_result.get("error"),
            ip_address=ip_address,
            user_agent=user_agent,
        )

        logger.info(
            f"LLM provider test completed: user={user_id}, provider={provider_id}, "
            f"success={test_result['success']}"
        )

        return test_result

    async def record_provider_usage(
        self,
        user_id: UUID,
        provider_id: UUID,
    ) -> None:
        """
        Записывает использование провайдера.
        
        Обновляет:
        - use_count (количество использований)
        - last_used_at (время последнего использования)
        
        Args:
            user_id: ID пользователя
            provider_id: ID провайдера
            
        Raises:
            LLMProviderNotFoundError: Если провайдер не найден
        """
        provider = await self.get_user_provider(user_id, provider_id)

        provider.use_count += 1
        provider.last_used_at = datetime.utcnow()

        await self.db_session.flush()

        # Логируем в аудит
        await self.audit_service.log_action(
            user_id=user_id,
            action="use",
            provider_id=provider_id,
            new_values={"use_count": provider.use_count, "last_used_at": provider.last_used_at.isoformat() if provider.last_used_at else None},
            success=True,
        )

    async def _count_agents_using_provider(self, provider_id: UUID) -> int:
        """
        Подсчитывает количество агентов, использующих этот провайдер.
        
        Args:
            provider_id: ID провайдера
            
        Returns:
            Количество агентов
        """
        query = select(func.count()).select_from(UserAgent).where(
            UserAgent.llm_provider_id == provider_id
        )

        count = await self.db_session.scalar(query)
        return count or 0
