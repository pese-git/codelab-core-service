# langfuse-integration Specification

## Назначение

Интеграция Langfuse v4 SDK обеспечивает LLM-native observability для отслеживания, отладки и оптимизации LLM операций. Система использует декораторный подход и автоматический захват через `langfuse.openai.AsyncOpenAI` wrapper. OpenTelemetry полностью удалена (16 марта 2026).

## Требования

### Requirement: Singleton LangfuseClient для управления трейсингом

Приложение ДОЛЖНО иметь глобальный singleton LangfuseClient для управления Langfuse SDK.

#### Scenario: Инициализация сервиса
- **WHEN** приложение запускается
- **THEN** [`LangfuseClient`](app/services/langfuse_client.py:14) инициализируется с LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST из [`app/config.py`](app/config.py:114-119)
- **AND** если Langfuse недоступен или отключен (LANGFUSE_ENABLED=false), сервис переходит в режим disabled (enabled=False)
- **AND** все методы gracefully return None если disabled

#### Scenario: Получение экземпляра клиента
- **WHEN** код вызывает [`get_langfuse_client()`](app/services/langfuse_client.py:134)
- **THEN** возвращается глобальный singleton экземпляр [`LangfuseClient`](app/services/langfuse_client.py:14)

#### Scenario: Обработка ошибок
- **WHEN** Langfuse API вернет ошибку
- **THEN** ошибка логируется но не пробрасывается (fail-safe)
- **AND** приложение продолжает работу без трейсинга

### Requirement: Автоматическое логирование LLM вызовов через langfuse.openai.AsyncOpenAI

LLM вызовы ДОЛЖНЫ автоматически захватываться через Langfuse OpenAI wrapper.

#### Scenario: Автоматический захват LLM вызовов
- **WHEN** агент использует [`langfuse.openai.AsyncOpenAI`](app/agents/contextual_agent.py:9) client
- **THEN** LLM запросы автоматически захватываются: {model, prompt_tokens, completion_tokens, latency, cost}
- **AND** данные отправляются в Langfuse без дополнительной конфигурации

#### Scenario: Интеграция в ContextualAgent
- **WHEN** [`ContextualAgent`](app/agents/contextual_agent.py:28) инициализируется с [`openai.AsyncOpenAI`](app/agents/contextual_agent.py:71)
- **THEN** клиент подключен к LiteLLM через base_url (`settings.litellm_url`)
- **AND** Langfuse wrapper автоматически захватывает все `chat.completions.create()` вызовы

#### Scenario: Логирование ошибок LLM
- **WHEN** LLM запрос завершается с ошибкой (timeout, API error)
- **THEN** ошибка логируется через struktured logging без прерывания workflow

### Requirement: Декораторы @observe для трейсинга workflow'ов

Система ДОЛЖНА использовать `@observe` декораторы для трейсинга компонентов.

#### Scenario: Трейсинг Chat endpoint
- **WHEN** функция [`send_project_message`](app/routes/project_chat.py:194-196) вызывается с декоратором `@observe(name="ChatMessage")`
- **THEN** создается trace с именем "ChatMessage"
- **AND** metadata обновляется через [`langfuse_client.client.update_current_trace()`](app/routes/project_chat.py:219-222)

#### Scenario: Трейсинг Agent Executor
- **WHEN** метод [`execute`](app/agents/contextual_agent.py:147-148) на ContextualAgent вызывается с `@observe(name="Executor")`
- **THEN** создается trace для выполнения агента
- **AND** все дочерние операции (LLM, tools) захватываются как child spans

#### Scenario: Трейсинг Tool Execution
- **WHEN** Tool executor вызывает инструменты с декоратором `@observe(as_type="tool")`
- **THEN** каждый инструмент отслеживается как отдельный span
- **AND** результаты и ошибки логируются в Langfuse

### Requirement: Метаданные traces

Traces ДОЛЖНЫ содержать полный контекст пользователя и проекта.

#### Scenario: Обновление метаданных trace
- **WHEN** функция [`update_trace_metadata`](app/services/langfuse_client.py:79-115) вызывается с user_id, project_id, tags
- **THEN** текущий trace обновляется с:
  - `user_id`: идентификатор пользователя
  - `session_id`: ID проекта (используется как session_id для группировки)
  - `tags`: включают версию ("v0.2.0") и кастомные теги
- **AND** данные пропагируются в Langfuse

#### Scenario: Контекст в Chat endpoint
- **WHEN** [`send_project_message`](app/routes/project_chat.py:215-224) вызывается
- **THEN** метаданные устанавливаются для текущего trace с user_id и project_id
- **AND** gracefully degradation если Langfuse отключен

### Requirement: Graceful degradation

Система ДОЛЖНА продолжать работу если Langfuse недоступен.

#### Scenario: Отключение Langfuse
- **WHEN** LANGFUSE_ENABLED=false или отсутствуют ключи
- **THEN** [`LangfuseClient.enabled`](app/services/langfuse_client.py:20) = False
- **AND** все вызовы методов gracefully return без ошибок
- **AND** приложение работает нормально без трейсинга

#### Scenario: Asynchronous flush
- **WHEN** приложение завершает работу
- **THEN** вызывается [`langfuse_client.flush()`](app/services/langfuse_client.py:117-127)
- **AND** оставшиеся traces отправляются в Langfuse

## Текущая реализация

### LangfuseClient Singleton

Файл: [`app/services/langfuse_client.py`](app/services/langfuse_client.py)

**Компоненты:**
- [`LangfuseClient`](app/services/langfuse_client.py:14) - основной класс для управления SDK
- [`get_langfuse_client()`](app/services/langfuse_client.py:134) - функция для получения singleton
- Конфигурация из [`app/config.py`](app/config.py:114-119)

**API методы:**
- `__init__()` - инициализация с валидацией ключей и graceful degradation
- `observe_openai_client()` - подготовка OpenAI client для обертывания (v4 API)
- `update_trace_metadata()` - обновление метаданных текущего trace
- `flush()` - асинхронная отправка оставшихся spans

### Инструментированные компоненты

1. **Chat endpoints** ([`app/routes/project_chat.py`](app/routes/project_chat.py))
   - `@observe(name="ChatMessage")` на [`send_project_message`](app/routes/project_chat.py:194-196)
   - Метаданные: user_id, project_id

2. **Contextual Agent** ([`app/agents/contextual_agent.py`](app/agents/contextual_agent.py))
   - `@observe(name="Executor")` на методе [`execute`](app/agents/contextual_agent.py:147-148)
   - Автоматический захват LLM вызовов через [`openai.AsyncOpenAI`](app/agents/contextual_agent.py:71)

3. **Tool Execution** ([`app/core/tools/executor.py`](app/core/tools/executor.py:73-74,100-101))
   - `@observe(as_type="tool")` декораторы на методах исполнения инструментов
   - Захват результатов и ошибок

### Конфигурация

Файл: [`app/config.py`](app/config.py:114-119)

```python
langfuse_enabled: bool = Field(default=True)
langfuse_public_key: str | None = Field(default=None)
langfuse_secret_key: str | None = Field(default=None)
langfuse_host: str = Field(default="http://localhost:3000")
langfuse_debug: bool = Field(default=False)
```

**Environment переменные:**
```bash
LANGFUSE_ENABLED=true          # Включить/отключить трейсинг
LANGFUSE_PUBLIC_KEY=pk-...     # Public API key
LANGFUSE_SECRET_KEY=sk-...     # Secret API key
LANGFUSE_HOST=http://localhost:3000  # Langfuse server URL (может быть https://cloud.langfuse.com)
LANGFUSE_DEBUG=false           # Debug режим для логирования
```

## Ограничения текущей реализации

1. **Нет REST API endpoints** - аналитика доступна через Langfuse web UI, не через приложение
2. **Нет health check** - Langfuse здоровье не проверяется в `/health`
3. **Нет Prometheus метрик** - метрики доступны через Langfuse dashboard
4. **Нет LiteLLM callbacks** - планируется на будущее (используется langfuse.openai wrapper вместо этого)
5. **Нет retention политики** - управляется через Langfuse конфигурацию
6. **Нет Docker Compose** - для self-hosted Langfuse (используется их официальный deployment)

## Roadmap

### Phase 1: LiteLLM callbacks (будущее)
- Интеграция LiteLLM callbacks для дополнительного контекста
- Автоматический захват всех LLM параметров из LiteLLM
- Приоритет: средний (текущая реализация через OpenAI wrapper достаточна)

### Phase 2: REST API для аналитики (будущее)
- Endpoints для получения traces с фильтрацией
- Endpoints для записи feedback и scores
- Интеграция с dashboard приложения
- Приоритет: высокий

### Phase 3: Prometheus метрики (будущее)
- Экспорт метрик из Langfuse в Prometheus
- Dashboard в Grafana
- Alerts на аномалии
- Приоритет: средний

### Phase 4: Advanced context propagation (будущее)
- Propagation через микросервисы
- Distributed tracing
- Correlation IDs
- Приоритет: средний

## Архитектура

```mermaid
graph TB
    subgraph "Application"
        FastAPI["FastAPI App"]
        ChatEndpoint["Chat Endpoint<br/>@observe"]
        Agent["Agent<br/>@observe"]
        ToolExec["Tool Executor<br/>@observe"]
    end
    
    subgraph "LLM Integration"
        OpenAIWrapper["langfuse.openai.AsyncOpenAI<br/>(auto-capture)"]
    end
    
    subgraph "Langfuse SDK"
        LFClient["LangfuseClient<br/>(singleton)"]
        LFSDKClient["Langfuse SDK<br/>Client"]
    end
    
    subgraph "Langfuse Backend"
        LFAPI["Langfuse API"]
        LFDB["PostgreSQL"]
        LFUI["Web UI"]
    end
    
    ChatEndpoint -->|update_trace_metadata| LFClient
    Agent -->|@observe auto| LFClient
    OpenAIWrapper -->|auto-capture| LFSDKClient
    ToolExec -->|@observe| LFClient
    
    LFClient -->|SDK calls| LFSDKClient
    LFSDKClient -->|HTTP| LFAPI
    
    LFAPI -->|read/write| LFDB
    LFUI -->|query| LFAPI
```

## Нефункциональные требования

### Performance
- Overhead на LLM запрос: < 50ms (асинхронный wrapper)
- Latency метаданных: < 10ms (in-memory update)
- Fail-safe: если Langfuse down, приложение продолжает работу без задержек

### Reliability
- Graceful degradation если Langfuse недоступен
- Auto-flush при завершении приложения
- Retry logic в SDK (встроенное в Langfuse SDK)

### Security
- HTTPS/TLS для соединений с Langfuse cloud
- Public/Secret API key authentication
- API ключи никогда не логируются (только статус инициализации)
- Row-level security для multi-tenant доступа (через Langfuse)

### Scalability
- Поддержка 100+ traces/минуту
- Batch processing в SDK (по умолчанию)
- In-memory buffering перед отправкой
- Асинхронная обработка не блокирует основной поток

---

**Version**: 2.0 (Actualizado)  
**Status**: Implemented (Langfuse v4 SDK)  
**Last Updated**: 2026-03-16  
**Previous**: v1.0 (удалена OpenTelemetry, REST API, health checks, Prometheus metrics)
