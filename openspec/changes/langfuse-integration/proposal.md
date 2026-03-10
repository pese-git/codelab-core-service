# Proposal: Langfuse Integration

## Why

Текущая система observability (OpenTelemetry + structlog) не охватывает LLM-специфичные метрики: промпты, ответы, токены, стоимость операций и latency LLM вызовов. Это критически ограничивает возможность отладки, оптимизации и анализа качества работы агентов. Langfuse предоставляет специализированную платформу для LLM observability с полной видимостью цепочек LLM запросов, стоимостью и производительностью.

## What Changes

- Добавляется интеграция с Langfuse (self-hosted) для LLM-native observability
- LiteLLM callbacks автоматически отправляют данные о каждом LLM вызове в Langfuse (модель, токены, latency, стоимость, ошибки)
- Agent service получает возможность создавать и отслеживать traces для multi-step workflow'ов с поддержкой spans и metadata
- Система поддерживает запись scores (оценок качества) для traces, позволяя собирать feedback пользователей
- Добавляется REST API для получения traces с фильтрацией и пагинацией по user_id, workspace_id, agent_name
- Вся интеграция graceful - при недоступности Langfuse система продолжает работу без трейсинга

## Capabilities

### New Capabilities
- `langfuse-integration`: Обертка (service) вокруг Langfuse SDK для unified интеграции с поддержкой создания traces, spans, записи scores, обработки ошибок и режима disabled при недоступности
- `llm-call-tracing`: Автоматическое захватывание LLM вызовов через LiteLLM callbacks с отправкой в Langfuse (модель, промпты, ответы, токены, стоимость, latency, user_id, workspace_id, metadata)
- `agent-workflow-tracing`: Поддержка создания root traces для агентных operations и spans для каждого шага (prepare_context, generate_response, save_interaction) с автоматической группировкой в sessions по workspace_id
- `traces-quality-feedback`: Возможность записи user feedback и scores (оценок качества) в traces для анализа качества работы агентов
- `traces-analytics-api`: REST API endpoints для получения traces с фильтрацией по user_id, workspace_id, agent_name и metadata, с поддержкой пагинации

### Modified Capabilities
- `agent-llm-provider-binding`: Существующая интеграция между agent service и LLM провайдерами должна быть дополнена поддержкой LiteLLM callbacks для отправки данных в Langfuse

## Impact

- **Agent service** (`app/services/agent_service.py`): Добавляется трейсинг для `process_message()` и других ключевых методов
- **LiteLLM client** (`app/services/llm_provider_service.py`): Добавляются callbacks для автоматической отправки данных о LLM вызовах в Langfuse
- **REST API** (`app/routes/`): Новые endpoints для получения traces и работы с feedback
- **Configuration** (`app/config.py`): Добавляются переменные окружения LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST
- **Dependencies** (`pyproject.toml`): Добавляется зависимость на langfuse SDK
- **Database**: Может потребоваться добавить таблицы для кеширования/синхронизации trace данных (опционально, в зависимости от design)
