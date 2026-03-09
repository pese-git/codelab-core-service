"""LiteLLM HTTP client for managing models and API keys."""

import asyncio
import logging
import secrets
import string
from typing import Any
from uuid import UUID

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


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
        self.retry_delay = 1.0  # exponential backoff startregion

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
        model_id = self._build_model_id(provider_type, litellm_model_name)

        payload = {
            "model_name": litellm_model_name,
            "model_id": model_id,
            "api_key": api_key,
            "provider": provider_type,
        }

        if config:
            payload.update(config)

        await self._http_request(
            method="POST",
            endpoint="/models/add",
            payload=payload,
        )

        logger.info(
            f"Model {litellm_model_name} registered in LiteLLM for user {user_id}"
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

        logger.info(f"Model {litellm_model_name} deleted from LiteLLM")

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
            logger.error(f"Failed to test model {litellm_model_name}: {str(e)}")
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

            except (httpx.TimeoutException, httpx.NetworkError) as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (2 ** attempt)
                    logger.warning(
                        f"Request failed (attempt {attempt + 1}/{self.max_retries}), "
                        f"retrying in {wait_time}s: {str(e)}"
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"Request failed after {self.max_retries} attempts: {str(e)}")

            except httpx.HTTPStatusError as e:
                last_error = e
                logger.error(
                    f"LiteLLM API error: {e.response.status_code} - {e.response.text}"
                )
                # Don't retry on HTTP errors (400, 401, etc.)
                raise

        raise last_error or httpx.NetworkError("Unknown error")
