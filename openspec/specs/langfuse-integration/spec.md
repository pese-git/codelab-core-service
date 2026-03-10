# langfuse-integration Specification

## Назначение

Интеграция Langfuse обеспечивает LLM-native observability для полного отслеживания, отладки и оптимизации LLM операций. Система должна автоматически захватывать промпты, ответы, токены, стоимость и метаметрики через LiteLLM callbacks и custom instrumentation SDK.

## Требования

### Requirement: Автоматическое логирование LLM вызовов через LiteLLM callbacks

LiteLLM ДОЛЖЕН отправлять данные о LLM операциях в Langfuse через встроенные callbacks.

#### Scenario: Успешное логирование LLM вызова
- **WHEN** агент вызывает litellm.completion(model="gpt-4", messages=[...])
- **THEN** LiteLLM автоматически отправляет в Langfuse: {model, prompt_tokens, completion_tokens, latency, cost, user_id, workspace_id}

#### Scenario: Логирование ошибок LLM
- **WHEN** LLM запрос завершается с ошибкой (timeout, API error, invalid key)
- **THEN** LiteLLM отправляет в Langfuse: {error_type, error_message, stack_trace, timestamp}

#### Scenario: Метаданные обогащаются в callbacks
- **WHEN** LiteLLM callback срабатывает
- **THEN** callback содержит: user_id (из structlog context), workspace_id, agent_name, metadata

### Requirement: Создание и управление traces для агентных workflow'ов

Система ДОЛЖНА поддерживать явное создание traces для отслеживания multi-step агентных операций.

#### Scenario: Создание root trace для агента
- **WHEN** агент начинает обработку сообщения пользователя
- **THEN** система создает trace с name=f"agent_{agent_name}", user_id, session_id=f"workspace_{workspace_id}", metadata={agent, model, ...}

#### Scenario: Создание spans для шагов агента
- **WHEN** агент выполняет шаги: prepare_context → generate_response → save_interaction
- **THEN** для каждого шага создается span с input, output, metadata и end_time

#### Scenario: Группировка traces в sessions
- **WHEN** пользователь проводит разговор с агентом
- **THEN** все traces для этого workspace группируются в session_id=f"workspace_{workspace_id}"

### Requirement: Запись оценок качества (scores) для traces

Система ДОЛЖНА позволять записывать feedback и оценки качества для traces.

#### Scenario: Запись оценки пользователя
- **WHEN** пользователь оставляет feedback на ответ агента (rating 1-5)
- **THEN** система записывает score в trace: {name: "user_satisfaction", value: rating/5.0, comment: feedback_text}

#### Scenario: Запись метрик качества
- **WHEN** система завершает LLM операцию
- **THEN** система может записать scores: {relevance: 0.95, accuracy: 0.88, helpfulness: 1.0}

### Requirement: Получение traces для аналитики

Система ДОЛЖНА предоставлять API для получения traces с фильтрацией и пагинацией.

#### Scenario: Получение traces пользователя
- **WHEN** клиент отправляет GET /traces?user_id=uuid&workspace_id=uuid&limit=100
- **THEN** Langfuse возвращает список traces с metadata и spans

#### Scenario: Фильтрация traces по критериям
- **WHEN** клиент отправляет GET /traces?metadata.agent=research_agent&limit=50
- **THEN** Langfuse возвращает только traces с agent="research_agent"

### Requirement: LangfuseIntegration service

Приложение ДОЛЖНО иметь обертку (service) вокруг Langfuse SDK для unified интеграции.

#### Scenario: Инициализация сервиса
- **WHEN** приложение запускается
- **THEN** LangfuseIntegration читает LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST из config
- **AND** если Langfuse недоступен, сервис переходит в режим disabled (enabled=False)
- **AND** все методы gracefully return None если disabled

#### Scenario: Методы сервиса
- **WHEN** код вызывает langfuse.create_trace(), langfuse.create_span(), langfuse.record_score()
- **THEN** методы направляют запросы в Langfuse API или return None если disabled

#### Scenario: Обработка ошибок
- **WHEN** Langfuse API вернет ошибку
- **THEN** ошибка логируется но не пробрасывается (fail-safe)
- **AND** приложение продолжает работу без трейсинга

### Requirement: Интеграция с agent service

Agent service ДОЛЖЕН использовать LangfuseIntegration для трейсинга workflows.

#### Scenario: Трейсинг процесса обработки сообщения
- **WHEN** agent.process_message() вызывается
- **THEN** создается root trace с agent_name, user_id, workspace_id
- **AND** создается span для prepare_context
- **AND** создается span для generate_response (LiteLLM auto-captures через callback)
- **AND** создается span для save_interaction
- **AND** trace завершается с успехом

#### Scenario: Обработка ошибок в трейсе
- **WHEN** во время process_message() возникает исключение
- **THEN** trace обновляется с metadata={error: str(e)}, level="ERROR"
- **AND** исключение пробрасывается дальше

### Requirement: Docker Compose для Langfuse

Система ДОЛЖНА поддерживать развертывание self-hosted Langfuse через Docker Compose.

#### Scenario: Развертывание Langfuse stack
- **WHEN** выполняется docker-compose up -d langfuse
- **THEN** запускаются: langfuse-postgres (PostgreSQL 16), langfuse (web app), Redis (кэш)
- **AND** healthchecks настроены для каждого сервиса
- **AND** environment variables загружаются из .env

#### Scenario: Конфигурация базы данных
- **WHEN** Langfuse инициализируется
- **THEN** DATABASE_URL=postgresql://langfuse:${LANGFUSE_DB_PASSWORD}@langfuse-postgres:5432/langfuse
- **AND** таблицы автоматически создаются при первом запуске

#### Scenario: Интеграция с существующей сетью
- **WHEN** codelab-core-service запускается
- **THEN** LANGFUSE_HOST=http://langfuse:3000 (в той же Docker сети)
- **AND** приложение может подключиться к Langfuse через http://langfuse:3000

### Requirement: Конфигурация LiteLLM для Langfuse

LiteLLM ДОЛЖЕН быть сконфигурирован для отправки callbacks в Langfuse.

#### Scenario: Включение callbacks
- **WHEN** litellm_config.yaml загружается
- **THEN** litellm_settings содержит success_callback: ["langfuse"], failure_callback: ["langfuse"]

#### Scenario: Передача API ключей
- **WHEN** LiteLLM инициализируется
- **THEN** environment содержит LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST
- **AND** LiteLLM использует эти переменные для автоматической отправки данных

#### Scenario: Асинхронная обработка callbacks
- **WHEN** LiteLLM отправляет callback
- **THEN** callback обрабатывается асинхронно (не блокирует LLM запрос)
- **AND** flush_interval=30 (batch отправка каждые 30 сек)
- **AND** если Langfuse недоступен, LiteLLM продолжает работать (fail-open)

### Requirement: Политика хранения данных

Система ДОЛЖНА автоматически удалять старые traces в соответствии с retention policy.

#### Scenario: Удаление traces старше 90 дней
- **WHEN** крон-задача запускается ежедневно в 02:00 UTC
- **THEN** traces созданные более 90 дней назад удаляются из базы
- **AND** перед удалением опционально архивируются в S3

#### Scenario: Конфигурируемый период хранения
- **WHEN** устанавливается LANGFUSE_RETENTION_DAYS=60
- **THEN** retention policy использует 60 дней вместо default 90

### Requirement: Мониторинг и health checks

Система ДОЛЖНА предоставлять health check для Langfuse.

#### Scenario: Health check endpoint
- **WHEN** клиент отправляет GET /health/langfuse
- **THEN** система пытается подключиться к Langfuse и выполнить простой запрос
- **AND** если успех: {status: "healthy", service: "langfuse"}
- **AND** если ошибка: {status: "unhealthy", service: "langfuse", error: "..."}, HTTP 503

#### Scenario: Метрики для мониторинга
- **WHEN** prometheus scrapes метрики
- **THEN** доступны: langfuse_traces_total, langfuse_spans_total, langfuse_callback_failures, langfuse_db_size

### Requirement: API ключи Langfuse НЕ логируются

Система ДОЛЖНА гарантировать что API ключи НИКОГДА не попадают в логи.

#### Scenario: Безопасность при инициализации
- **WHEN** LangfuseIntegration инициализируется с public/secret ключами
- **THEN** ключи НЕ логируются даже если произойдет ошибка
- **AND** логируется только erfolg/fail статус инициализации

#### Scenario: Безопасность при ошибках
- **WHEN** Langfuse API возвращает 401 Unauthorized
- **THEN** error message логируется как "Langfuse authentication failed" но не содержит самих ключей

## Архитектура

```mermaid
graph TB
    subgraph "Application"
        FastAPI["FastAPI App"]
        Agent["Agent Service"]
        LLMClient["LiteLLM Client"]
        LFService["LangfuseIntegration<br/>Service"]
    end
    
    subgraph "Langfuse Integration"
        LiteLLMCB["LiteLLM Callback<br/>(auto-capture)"]
        LFSDKClient["Langfuse SDK<br/>Client"]
    end
    
    subgraph "Langfuse Stack"
        LFAPI["Langfuse API"]
        LFDB["PostgreSQL"]
        LFRedis["Redis"]
        LFUI["Web UI"]
    end
    
    Agent -->|create trace| LFService
    LLMClient -->|async callback| LiteLLMCB
    LFService -->|SDK calls| LFSDKClient
    LiteLLMCB -->|HTTP| LFAPI
    LFSDKClient -->|HTTP| LFAPI
    LFAPI -->|read/write| LFDB
    LFAPI -->|cache| LFRedis
    LFUI -->|query| LFAPI
```

## Файлы реализации

### Новые файлы

- `app/services/langfuse_integration.py` — LangfuseIntegration service class
- `app/routes/feedback.py` — API endpoints для feedback
- `docker-compose.langfuse.yml` — Langfuse stack deployment
- `tests/test_langfuse_integration.py` — Unit тесты
- `tests/test_langfuse_e2e.py` — Integration тесты

### Обновляемые файлы

- `app/services/agent_service.py` — Интеграция с LangfuseIntegration
- `app/config.py` — Добавить LANGFUSE_* переменные
- `pyproject.toml` — Добавить langfuse dependency
- `litellm_config.yaml` — Настроить callbacks

## Нефункциональные требования

### Performance
- Overhead на LLM запрос: < 100ms (async callbacks)
- Latency создания trace: < 50ms
- Fail-safe: если Langfuse down, приложение продолжает работу

### Reliability
- Callback success rate: >= 99%
- Auto-reconnect при сетевых ошибках
- Graceful degradation если Langfuse недоступен

### Security
- HTTPS/TLS для всех соединений
- Public/Secret API key authentication
- API ключи никогда не логируются
- Row-level security для multi-tenant доступа

### Scalability
- Поддержка 1000+ traces/день
- Connection pooling в PostgreSQL
- Redis caching для dashboard queries
- Batch processing (flush every 30 sec)

---

**Version**: 1.0  
**Status**: Ready for Implementation  
**Last Updated**: 2026-03-10
