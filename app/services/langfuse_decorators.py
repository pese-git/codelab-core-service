"""Декораторы для автоматического трейсинга LLM вызовов в Langfuse."""

import time
from functools import wraps
from typing import Any, Callable

import structlog

from app.logging_config import get_logger
from app.services.langfuse_integration import get_langfuse

logger = get_logger(__name__)


def trace_llm_call(
    name: str = "llm_generation",
    capture_input: bool = True,
    capture_output: bool = True,
    include_model: bool = True,
    max_output_length: int | None = None,
):
    """
    Декоратор для автоматического трейсинга LLM вызовов в Langfuse.

    Oборачивает LLM запрос и автоматически создает span в Langfuse с:
    - Input data (messages, model, parameters)
    - Output data (response, tokens, latency) - ПОЛНЫЙ КОНТЕНТ БЕЗ ОБРЕЗАНИЯ
    - Metadata (timing, status, errors)
    - Metrics записываются в Prometheus

    Usage:
        @trace_llm_call(name="agent_llm_generation")
        async def _call_llm(self, messages, langfuse_trace=None):
            return await self.openai_client.chat.completions.create(
                model=model,
                messages=messages,
            )

    Args:
        name: Имя span в Langfuse (по умолчанию "llm_generation")
        capture_input: Захватывать ли input данные (по умолчанию True)
        capture_output: Захватывать ли output данные (по умолчанию True)
        include_model: Включать ли model в метаданные (по умолчанию True)
        max_output_length: Максимальная длина output контента (None = без ограничений)
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            langfuse = get_langfuse()

            # Получить trace из kwargs (если передан в функцию)
            trace = kwargs.get("langfuse_trace")
            if not trace or not langfuse.enabled:
                # Если нет trace или Langfuse disabled, просто выполнить функцию
                return await func(*args, **kwargs)

            # Подготовить input данные
            input_data = None
            if capture_input:
                input_data = {
                    "model": kwargs.get("model"),
                    "temperature": kwargs.get("temperature"),
                    "max_tokens": kwargs.get("max_tokens"),
                    "top_p": kwargs.get("top_p"),
                }

            start_time = time.time()

            try:
                # Выполнить LLM вызов
                result = await func(*args, **kwargs)

                # Подготовить output данные - ПОЛНЫЕ БЕЗ ОБРЕЗАНИЯ
                output_data = None
                if capture_output and result:
                    # Поддержка OpenAI-style response objects
                    if hasattr(result, "choices") and hasattr(result, "usage"):
                        # Захватить все choices, а не только первый
                        choices_data = []
                        for choice in result.choices:
                            choice_content = choice.message.content if choice.message else None
                            
                            # Применить max_output_length ограничение если указано
                            if max_output_length and choice_content and len(choice_content) > max_output_length:
                                choice_content = choice_content[:max_output_length] + f"...[truncated, original length: {len(choice_content)}]"
                            
                            choices_data.append({
                                "content": choice_content,
                                "finish_reason": choice.finish_reason,
                                "index": choice.index,
                            })
                        
                        output_data = {
                            "choices": choices_data,
                            "first_choice_content": choices_data[0]["content"] if choices_data else None,
                            "prompt_tokens": result.usage.prompt_tokens,
                            "completion_tokens": result.usage.completion_tokens,
                            "total_tokens": result.usage.total_tokens,
                        }

                latency_ms = int((time.time() - start_time) * 1000)

                # Создать span в Langfuse
                langfuse.create_span(
                    trace=trace,
                    name=name,
                    input_data=input_data,
                    output_data=output_data,
                    metadata={
                        "latency_ms": latency_ms,
                        "status": "success",
                        "model": kwargs.get("model") if include_model else None,
                    },
                    status="success",
                )

                logger.debug(
                    "llm_call_completed",
                    span_name=name,
                    latency_ms=latency_ms,
                    model=kwargs.get("model"),
                    tokens=output_data.get("total_tokens")
                    if output_data
                    else None,
                )

                return result

            except Exception as e:
                latency_ms = int((time.time() - start_time) * 1000)

                # Записать ошибку
                langfuse.create_span(
                    trace=trace,
                    name=name,
                    input_data=input_data,
                    metadata={
                        "latency_ms": latency_ms,
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "status": "error",
                        "model": kwargs.get("model") if include_model else None,
                    },
                    status="error",
                )

                logger.error(
                    "llm_call_failed",
                    span_name=name,
                    error=str(e),
                    error_type=type(e).__name__,
                    latency_ms=latency_ms,
                    model=kwargs.get("model"),
                )

                raise

        return wrapper

    return decorator


def trace_embedding_call(
    name: str = "embedding_generation",
    capture_input: bool = True,
    capture_output: bool = True,
):
    """
    Декоратор для автоматического трейсинга embedding вызовов в Langfuse.

    Usage:
        @trace_embedding_call(name="agent_embedding")
        async def get_embeddings(self, texts, langfuse_trace=None):
            return await self.embedding_client.create(input=texts)

    Args:
        name: Имя span в Langfuse
        capture_input: Захватывать ли input данные
        capture_output: Захватывать ли output данные
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            langfuse = get_langfuse()

            trace = kwargs.get("langfuse_trace")
            if not trace or not langfuse.enabled:
                return await func(*args, **kwargs)

            input_data = None
            if capture_input:
                # Не логировать сами texts для privacy
                input_data = {
                    "input_count": len(kwargs.get("input", []))
                    if isinstance(kwargs.get("input"), list)
                    else 1,
                    "model": kwargs.get("model"),
                }

            start_time = time.time()

            try:
                result = await func(*args, **kwargs)

                output_data = None
                if capture_output and result:
                    if hasattr(result, "data") and hasattr(result, "usage"):
                        output_data = {
                            "embedding_count": len(result.data),
                            "embedding_dimension": len(result.data[0].embedding)
                            if result.data
                            else None,
                            "prompt_tokens": result.usage.prompt_tokens
                            if hasattr(result.usage, "prompt_tokens")
                            else None,
                        }

                latency_ms = int((time.time() - start_time) * 1000)

                langfuse.create_span(
                    trace=trace,
                    name=name,
                    input_data=input_data,
                    output_data=output_data,
                    metadata={
                        "latency_ms": latency_ms,
                        "status": "success",
                    },
                    status="success",
                )

                return result

            except Exception as e:
                latency_ms = int((time.time() - start_time) * 1000)

                langfuse.create_span(
                    trace=trace,
                    name=name,
                    input_data=input_data,
                    metadata={
                        "latency_ms": latency_ms,
                        "error": str(e),
                        "error_type": type(e).__name__,
                    },
                    status="error",
                )

                raise

        return wrapper

    return decorator
