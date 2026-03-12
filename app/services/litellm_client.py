"""LiteLLM HTTP client for managing models and API keys."""

import asyncio
import secrets
import string
from typing import Any
from uuid import UUID

import httpx

from app.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)


class LiteLLMAuthError(Exception):
    """Ошибка аутентификации при подключении к LiteLLM."""
    pass


class LiteLLMConnectionError(Exception):
    """Ошибка подключения к LiteLLM."""
    pass


class LiteLLMClient:
    """
    HTTP клиент для интеграции с LiteLLM.
    
    Отвечает за:
    - Регистрацию моделей в LiteLLM (add_model)
    - Удаление моделей из LiteLLM (delete_model)
    - Тестирование подключения к провайдеру (test_model)
    - Генерацию уникальных имён моделей
    """

    def __init__(self):
        """Initialize LiteLLM client."""
        self.base_url = settings.litellm_url
        self.master_key = settings.litellm_master_key
        self.timeout = 60.0
        self.max_retries = 3
        self.retry_delay = 1.0  # exponential backoff
        
        # Validate configuration
        self._validate_configuration()
        
        # Configure Langfuse callbacks for automatic LLM tracing
        self._setup_langfuse_callbacks()

    def _validate_configuration(self) -> None:
        """
        Проверяет корректность конфигурации LiteLLM при инициализации.
        
        Raises:
            LiteLLMConnectionError: Если конфигурация некорректна
        """
        errors = []
        
        # Проверка URL
        if not self.base_url:
            errors.append("LITELLM_URL не установлен")
        elif not self.base_url.startswith("http"):
            errors.append(f"LITELLM_URL должен начинаться с http/https: {self.base_url}")
        
        # Проверка MASTER_KEY
        if not self.master_key:
            errors.append("LITELLM_MASTER_KEY не установлен")
        
        if errors:
            error_message = "; ".join(errors)
            logger.error(
                "litellm_configuration_invalid",
                errors=error_message,
                base_url=self.base_url,
            )
            raise LiteLLMConnectionError(
                f"Ошибка конфигурации LiteLLM: {error_message}"
            )
        
        logger.info(
            "litellm_client_initialized",
            base_url=self.base_url,
        )

    def _setup_langfuse_callbacks(self) -> None:
        """
        Настроить Langfuse callbacks для автоматического трейсинга LLM вызовов.

        LiteLLM имеет встроенную поддержку Langfuse callbacks, которая автоматически
        захватывает все LLM вызовы и отправляет их в Langfuse для observability.
        """
        import os

        if not settings.langfuse_enabled:
            logger.debug("langfuse_callbacks_disabled")
            return

        try:
            import litellm

            # Включить Langfuse callbacks для успешных и ошибочных запросов
            litellm.success_callback = ["langfuse"]
            litellm.failure_callback = ["langfuse"]

            # Установить credentials для Langfuse в environment
            os.environ["LANGFUSE_PUBLIC_KEY"] = settings.langfuse_public_key
            os.environ["LANGFUSE_SECRET_KEY"] = settings.langfuse_secret_key
            os.environ["LANGFUSE_HOST"] = settings.langfuse_host

            logger.info(
                "langfuse_callbacks_configured",
                langfuse_host=settings.langfuse_host,
            )

        except ImportError:
            logger.warning("litellm_module_not_available_for_callbacks")
        except Exception as e:
            logger.error(
                "langfuse_callbacks_setup_failed",
                error=str(e),
            )

    async def add_model(
        self,
        user_id: UUID,
        provider_type: str,
        api_key: str,
        config: dict[str, Any] | None = None,
    ) -> str:
        """
        Регистрирует модель в LiteLLM.
        
        Args:
            user_id: ID пользователя
            provider_type: Тип провайдера (openai, anthropic, etc.)
            api_key: API ключ для провайдера
            config: Дополнительная конфигурация провайдера
            
        Returns:
            Уникальное имя модели в LiteLLM (litellm_model_name)
            
        Raises:
            ValueError: Если конфигурация невалидна
            httpx.HTTPError: Если ошибка при подключении к LiteLLM
        """
        litellm_model_name = self._generate_litellm_model_name(user_id, provider_type)

        # Модель ОБЯЗАТЕЛЬНА - пользователь должен её указать
        if not config or "model" not in config:
            raise ValueError(
                f"Модель не указана для провайдера {provider_type}. "
                f"Пожалуйста, укажите 'model' в конфигурации провайдера. "
                f"Для OpenRouter используйте формат: 'openrouter/openai/gpt-4-turbo', "
                f"'openrouter/anthropic/claude-3-opus' и т.д."
            )
        
        # LiteLLM требует ровно два параметра: model и api_key
        litellm_params = {
            "model": config["model"],
            "api_key": api_key,
        }

        payload = {
            "model_name": litellm_model_name,
            "litellm_params": litellm_params,
        }

        await self._http_request(
            method="POST",
            endpoint="/model/new",
            payload=payload,
        )

        logger.info(
            "model_registered_in_litellm",
            model_name=litellm_model_name,
            user_id=str(user_id),
        )
        return litellm_model_name

    async def delete_model(self, litellm_model_name: str) -> None:
        """
        Удаляет модель из LiteLLM.
        
        Args:
            litellm_model_name: Имя модели в LiteLLM для удаления
            
        Raises:
            httpx.HTTPError: Если ошибка при подключении к LiteLLM
        """
        payload = {"model_name": litellm_model_name}

        await self._http_request(
            method="POST",
            endpoint="/models/delete",
            payload=payload,
        )

        logger.info(
            "model_deleted_from_litellm",
            model_name=litellm_model_name,
        )

    async def test_model(
        self,
        litellm_model_name: str,
        test_prompt: str = "Hello, how are you?",
        max_tokens: int = 100,
    ) -> dict[str, Any]:
        """
        Тестирует подключение к модели провайдера.
        
        Args:
            litellm_model_name: Имя модели в LiteLLM
            test_prompt: Тестовый запрос
            max_tokens: Максимум токенов в ответе
            
        Returns:
            Словарь с результатом теста:
            {
                "success": bool,
                "response": str | None,
                "latency_ms": float | None,
                "error": str | None
            }
        """
        payload = {
            "model": litellm_model_name,
            "messages": [{"role": "user", "content": test_prompt}],
            "max_tokens": max_tokens,
        }

        try:
            import time
            start_time = time.time()

            response = await self._http_request(
                method="POST",
                endpoint="/completions",
                payload=payload,
            )

            latency_ms = (time.time() - start_time) * 1000

            # Extract the response text from LiteLLM format
            response_text = response.get("choices", [{}])[0].get("message", {}).get("content", "")

            return {
                "success": True,
                "response": response_text,
                "latency_ms": latency_ms,
                "error": None,
            }
        except Exception as e:
            logger.error(
                "failed_to_test_model",
                model_name=litellm_model_name,
                error=str(e),
            )
            return {
                "success": False,
                "response": None,
                "latency_ms": None,
                "error": str(e),
            }

    def _generate_litellm_model_name(self, user_id: UUID, provider_type: str) -> str:
        """
        Генерирует уникальное имя модели для LiteLLM.
        
        Формат: user{sanitized_user_id}_{provider_type}_{random_suffix}
        Пример: user550e8400_openai_abc12345
        
        Args:
            user_id: UUID пользователя
            provider_type: Тип провайдера
            
        Returns:
            Уникальное имя модели
        """
        sanitized_user_id = str(user_id).replace("-", "")[:16]
        random_suffix = "".join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(8))
        return f"user{sanitized_user_id}_{provider_type}_{random_suffix}"

    def _get_default_model(self, provider_type: str) -> str:
        """
        Получает дефолтную модель для типа провайдера.
        
        Args:
            provider_type: Тип провайдера
            
        Returns:
            Полное имя модели в формате провайдер/модель
        """
        default_models = {
            "openai": "gpt-4-turbo-preview",
            "anthropic": "claude-3-opus-20240229",
            "openrouter": "openai/gpt-4-turbo-preview",
            "cohere": "command-r-plus",
            "azure": "gpt-4",
        }
        
        model = default_models.get(provider_type, "gpt-4-turbo-preview")
        
        # Для OpenRouter и некоторых других провайдеров может понадобиться префикс
        if provider_type == "openrouter" and not model.startswith(f"{provider_type}/"):
            return model
        elif provider_type not in ["openrouter"] and "/" not in model:
            return f"{provider_type}/{model}"
        
        return model

    def _build_model_id(self, provider_type: str, litellm_model_name: str) -> str:
        """
        Строит полный model ID для LiteLLM.
        
        Args:
            provider_type: Тип провайдера
            litellm_model_name: Имя модели в LiteLLM
            
        Returns:
            Полный model ID (provider_type + "/" + model_name)
        """
        return f"{provider_type}/{litellm_model_name}"

    async def _http_request(
        self,
        method: str,
        endpoint: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Выполняет HTTP запрос к LiteLLM с retry logic.
        
        Args:
            method: HTTP метод (GET, POST, DELETE)
            endpoint: API endpoint
            payload: Данные запроса
            
        Returns:
            JSON ответ от LiteLLM
            
        Raises:
            httpx.HTTPError: Если все попытки неудачны
        """
        url = f"{self.base_url}{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.master_key}",
            "Content-Type": "application/json",
        }

        last_error = None
        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    if method == "POST":
                        response = await client.post(url, json=payload, headers=headers)
                    elif method == "GET":
                        response = await client.get(url, headers=headers)
                    elif method == "DELETE":
                        response = await client.delete(url, headers=headers)
                    else:
                        raise ValueError(f"Unsupported HTTP method: {method}")

                    response.raise_for_status()
                    return response.json()

            except httpx.HTTPStatusError as e:
                # Специальная обработка для 401 Unauthorized
                if e.response.status_code == 401:
                    logger.error(
                        "litellm_authentication_failed",
                        status_code=401,
                        url=url,
                        endpoint=endpoint,
                    )
                    raise LiteLLMAuthError(
                        "Ошибка аутентификации LiteLLM (401 Unauthorized). "
                        "Проверьте значение LITELLM_MASTER_KEY в конфигурации. "
                        "Убедитесь, что он совпадает с LITELLM_MASTER_KEY на сервере litellm."
                    ) from e
                
                # Для других HTTP ошибок логируем и не повторяем попытку
                last_error = e
                logger.error(
                    "litellm_http_error",
                    status_code=e.response.status_code,
                    url=url,
                    endpoint=endpoint,
                    response_text=e.response.text[:500],  # Ограничиваем размер логируемого текста
                )
                # Don't retry on HTTP errors (400, 403, 404, etc.)
                raise

            except (httpx.TimeoutException, httpx.NetworkError) as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (2 ** attempt)
                    logger.warning(
                        "litellm_request_timeout_retrying",
                        attempt=attempt + 1,
                        max_retries=self.max_retries,
                        wait_time=wait_time,
                        error=str(e),
                        url=url,
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(
                        "litellm_request_failed_max_attempts",
                        max_retries=self.max_retries,
                        error=str(e),
                        url=url,
                    )
                    raise LiteLLMConnectionError(
                        f"Не удалось подключиться к LiteLLM ({self.base_url}) "
                        f"после {self.max_retries} попыток. Проверьте доступность сервера. "
                        f"Ошибка: {str(e)}"
                    ) from e

            except Exception as e:
                # Неожиданная ошибка
                logger.error(
                    "litellm_unexpected_error",
                    error=str(e),
                    error_type=type(e).__name__,
                    url=url,
                )
                raise

        # На случай, если цикл завершился без return/raise
        raise last_error or LiteLLMConnectionError("Unknown error connecting to LiteLLM")
