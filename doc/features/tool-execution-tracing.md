# Tool Execution Tracing - Полное руководство

**Версия**: Phase 4  
**Последнее обновление**: 2026-03-12  
**Статус**: Production Ready

---

## Оглавление

1. [Введение](#введение)
2. [Архитектура](#архитектура)
3. [Интеграция LangfuseIntegration](#интеграция-langfuseintegration)
4. [Интеграция ToolExecutor](#интеграция-toolexecutor)
5. [Tool Performance Analytics API](#tool-performance-analytics-api)
6. [Graceful Degradation](#graceful-degradation)
7. [Performance & Overhead](#performance--overhead)
8. [Troubleshooting](#troubleshooting)
9. [Migration Guide](#migration-guide)

---

## Введение

Tool Execution Tracing - это система полного отслеживания исполнения инструментов (tools) в платформе CodeLab с интеграцией в Langfuse для анализа производительности, качества и отладки.

### Ключевые возможности

- ✅ **Полное трейсирование**: Каждое исполнение инструмента автоматически создает Langfuse span
- 🔗 **Nested spans**: Иерархия spans для validation → risk assessment → approval → execution
- 📊 **Analytics**: REST API для получения метрик, ранжирования и оценки качества
- 🔐 **Безопасность**: Trace ID изолирован по workspace, контроль доступа на API
- ⚡ **Производительность**: Минимальный overhead (< 50ms per execution)
- 🛡️ **Resilience**: Graceful degradation если Langfuse недоступен

### Что трейсируется

Каждое исполнение инструмента включает информацию:

```
Tool Execution Span (ROOT)
├── Input Parameters
├── User ID & Workspace ID
├── Context (agent_name, chat_session_id)
├── Status (success/error)
├── Execution Time
├── Nested Spans:
│   ├── Validation Span
│   │   └── Validation status & errors
│   ├── Risk Assessment Span
│   │   └── Risk level & risk score
│   ├── Approval Workflow Span (conditional)
│   │   └── Approval ID, status, timeout
│   └── Execution Span
│       └── Tool output/error
└── Result & Metrics
    ├── Success rate
    ├── Latency
    ├── Error type (if failed)
    └── Quality scores (manual feedback)
```

---

## Архитектура

### Компоненты системы

```
┌─────────────────────────────────────────────────────────────┐
│                    ToolExecutor                              │
│  (app/core/tools/executor.py)                               │
│  - execute_tool()                                            │
│  - Creates ROOT span                                        │
│  - Manages nested spans lifecycle                           │
└────────────────┬────────────────────────────────────────────┘
                 │ depends on
                 ▼
┌─────────────────────────────────────────────────────────────┐
│              LangfuseIntegration Service                     │
│  (app/services/langfuse_integration.py)                     │
│                                                              │
│  ✅ create_tool_execution_span()                            │
│  ✅ end_tool_execution_span()                               │
│  ✅ _create_nested_span()                                   │
│  ✅ get_tool_metrics()                                      │
│  ✅ get_tool_ranking()                                      │
│  ✅ record_tool_score()                                     │
│                                                              │
│  Features:                                                  │
│  - Graceful degradation (LANGFUSE_ENABLED=false)          │
│  - Async send with 5-sec timeout                           │
│  - Error handling without propagation                       │
│  - Redis caching (TTL=1 hour)                              │
└────────────────┬────────────────────────────────────────────┘
                 │ sends to
                 ▼
┌─────────────────────────────────────────────────────────────┐
│                   Langfuse Backend                           │
│  - Receives traces                                          │
│  - Stores spans with hierarchy                              │
│  - Provides REST API for analytics                          │
└─────────────────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│            Tool Analytics REST API                           │
│  (app/routes/traces.py)                                     │
│                                                              │
│  GET  /api/traces/tools/metrics                             │
│  GET  /api/traces/tools/ranking                             │
│  POST /api/traces/tools/score                               │
│                                                              │
│  Features:                                                  │
│  - Authorization check (workspace access)                   │
│  - Redis caching (1 hour TTL)                               │
│  - Rate limiting (100 req/min per workspace)                │
└─────────────────────────────────────────────────────────────┘
```

### Поток данных

```
1. ToolExecutor.execute_tool() called
   ↓
2. LangfuseIntegration.create_tool_execution_span()
   ↓ creates ROOT span in Langfuse
3. Validation phase
   ↓ _create_nested_span("validation")
4. Risk assessment phase
   ↓ _create_nested_span("risk_assessment")
5. Approval workflow phase (if needed)
   ↓ _create_nested_span("approval")
6. Tool execution phase
   ↓ _create_nested_span("execution")
7. ToolExecutor.execute_tool() completes
   ↓
8. LangfuseIntegration.end_tool_execution_span()
   ↓ async send to Langfuse with 5-sec timeout
9. Span stored in Langfuse with full hierarchy
   ↓
10. User can query analytics via REST API
    ↓ cached in Redis (1 hour TTL)
```

---

## Интеграция LangfuseIntegration

### Основной метод: create_tool_execution_span()

```python
from app.services.langfuse_integration import LangfuseIntegration

langfuse = LangfuseIntegration()

# Создание root span для tool execution
span = await langfuse.create_tool_execution_span(
    tool_name="calculator",
    input_params={"expression": "2+2"},
    user_id="user-123",
    workspace_id="workspace-456",
    parent_span_id=None,  # опционально, для nested spans
    metadata={
        "agent_name": "math-assistant",
        "chat_session_id": "session-789",
        "request_id": "req-001"
    }
)
```

**Параметры:**
- `tool_name` (str): Имя инструмента (например, "calculator", "file_reader")
- `input_params` (dict): Входные параметры инструмента
- `user_id` (str): ID пользователя (для изоляции)
- `workspace_id` (str): ID workspace (для изоляции)
- `parent_span_id` (str, опционально): ID родительского span для nested spans
- `metadata` (dict, опционально): Дополнительный контекст (agent_name, chat_session_id, и т.д.)

**Поведение:**
- Возвращает `ToolExecutionSpan` объект (содержит langfuse span и metadata)
- Если `LANGFUSE_ENABLED=false`, возвращает minimal span без отправки
- При ошибке в Langfuse: логирует, но не пробрасывает исключение
- Инкрементирует метрику `langfuse.spans_created`

### Метод завершения: end_tool_execution_span()

```python
# Завершение span после исполнения
try:
    result = await tool.execute()
    await langfuse.end_tool_execution_span(
        span_obj=span,
        result=result,
        error=None
    )
except Exception as e:
    await langfuse.end_tool_execution_span(
        span_obj=span,
        result=None,
        error=str(e)
    )
```

**Поведение:**
- Асинхронная отправка (fire-and-forget)
- 5-секундный таймаут для отправки в Langfuse
- При timeout: логирует, но не блокирует tool execution
- Инкрементирует метрики `langfuse.spans_ended`, `langfuse.send_errors`, `langfuse.timeout_errors`

### Создание nested spans

```python
# Validation span
validation_span = await langfuse._create_nested_span(
    parent_span_id=root_span.span_id,
    span_name="validation",
    input_data={"params": input_params}
)

# Risk assessment span
risk_span = await langfuse._create_nested_span(
    parent_span_id=root_span.span_id,
    span_name="risk_assessment",
    input_data={"tool_name": tool_name, "risk_level": "HIGH"}
)

# Approval span (conditional)
approval_span = await langfuse._create_nested_span(
    parent_span_id=root_span.span_id,
    span_name="approval",
    input_data={"approval_id": approval_id}
)

# Execution span
exec_span = await langfuse._create_nested_span(
    parent_span_id=root_span.span_id,
    span_name="execution",
    input_data={"command": tool_command}
)
```

### Извлечение контекста из structlog

```python
# Helper метод автоматически извлекает контекст
user_id, workspace_id, agent_id = langfuse._extract_context_vars()

# В structlog context уже должны быть установлены:
# - user_id
# - workspace_id  
# - agent_id
# - request_id
# - trace_id (для OpenTelemetry compatibility)
```

### Метрики Langfuse

Система автоматически отслеживает метрики:

```python
# Все доступные метрики:
langfuse.metrics = {
    'langfuse.enabled': 1 или 0,
    'langfuse.spans_created': int,
    'langfuse.spans_ended': int,
    'langfuse.send_errors': int,
    'langfuse.timeout_errors': int,
    'langfuse.nested_spans_created': int,
}
```

---

## Интеграция ToolExecutor

### Автоматическое трейсирование

ToolExecutor автоматически создает и управляет spans без изменения API:

```python
from app.core.tools.executor import ToolExecutor
from app.services.langfuse_integration import LangfuseIntegration

# Initialization (обычно в DI контейнере)
langfuse = LangfuseIntegration()
executor = ToolExecutor(langfuse_integration=langfuse)

# Использование - никакого изменения API!
result = await executor.execute_tool(
    tool_name="calculator",
    input_params={"expression": "2+2"},
    user_id="user-123",
    workspace_id="workspace-456"
)

# Всё это происходит автоматически:
# 1. ROOT span создается
# 2. Validation span
# 3. Risk assessment span
# 4. Approval span (если нужно)
# 5. Execution span
# 6. ROOT span завершается с результатом/ошибкой
# 7. Все spans асинхронно отправляются в Langfuse
```

### Структура execute_tool()

```python
async def execute_tool(
    self,
    tool_name: str,
    input_params: dict,
    user_id: str,
    workspace_id: str,
    agent_name: str = None,
    chat_session_id: str = None
) -> ToolResult:
    """Execute tool with full tracing support."""
    
    # 1. Create ROOT span
    root_span = await self.langfuse_integration.create_tool_execution_span(
        tool_name=tool_name,
        input_params=input_params,
        user_id=user_id,
        workspace_id=workspace_id,
        metadata={
            "agent_name": agent_name,
            "chat_session_id": chat_session_id
        }
    )
    
    try:
        # 2. Validation phase
        validation_span = await self.langfuse_integration._create_nested_span(
            parent_span_id=root_span.span_id,
            span_name="validation",
            input_data={"params": input_params}
        )
        validation_result = self._validate_tool_params(tool_name, input_params)
        
        # 3. Risk assessment phase
        risk_span = await self.langfuse_integration._create_nested_span(
            parent_span_id=root_span.span_id,
            span_name="risk_assessment",
            input_data={"tool_name": tool_name}
        )
        risk_level = await self.risk_assessor.assess_tool_risk(
            tool_name=tool_name,
            input_params=input_params
        )
        
        # 4. Approval phase (conditional)
        if risk_level in ["HIGH", "MEDIUM"]:
            approval_span = await self.langfuse_integration._create_nested_span(
                parent_span_id=root_span.span_id,
                span_name="approval",
                input_data={"risk_level": risk_level}
            )
            await self.approval_manager.request_approval(...)
        
        # 5. Execution phase
        exec_span = await self.langfuse_integration._create_nested_span(
            parent_span_id=root_span.span_id,
            span_name="execution",
            input_data={"command": tool_command}
        )
        result = await self._invoke_tool(tool_name, input_params)
        
        # 6. Завершить ROOT span с успехом
        await self.langfuse_integration.end_tool_execution_span(
            span_obj=root_span,
            result=result,
            error=None
        )
        
        return result
        
    except Exception as e:
        # Завершить ROOT span с ошибкой
        await self.langfuse_integration.end_tool_execution_span(
            span_obj=root_span,
            result=None,
            error=str(e)
        )
        raise
```

### Error Handling

Все ошибки в трейсинге логируются но не пробрасываются:

```python
try:
    # Tracing logic
    span = await self.langfuse_integration.create_tool_execution_span(...)
except Exception as e:
    # Логирует ошибку
    logger.error(f"Langfuse tracing error: {e}")
    # Но tool execution продолжается!
    # Tool выполняется без трейсинга
```

---

## Tool Performance Analytics API

### Endpoint 1: GET /api/traces/tools/metrics

Получить метрики инструмента за период.

**Запрос:**
```bash
GET /api/traces/tools/metrics?workspace_id=ws-123&tool_name=calculator&period_days=7
Authorization: Bearer YOUR_JWT_TOKEN
```

**Параметры:**
- `workspace_id` (required): ID workspace
- `tool_name` (optional): Фильтр по инструменту (без фильтра = все инструменты)
- `period_days` (optional, default=7): Период в днях

**Ответ:**
```json
{
  "period_days": 7,
  "tools": [
    {
      "tool_name": "calculator",
      "total_executions": 150,
      "successful_executions": 140,
      "failed_executions": 10,
      "success_rate": 0.933,
      "avg_latency_ms": 245.3,
      "latency_p50_ms": 180,
      "latency_p95_ms": 520,
      "latency_p99_ms": 890,
      "error_types": {
        "timeout": 5,
        "validation_error": 3,
        "runtime_error": 2
      },
      "quality_scores": {
        "accuracy": 0.92,
        "relevance": 0.88,
        "completeness": 0.95
      }
    }
  ]
}
```

### Endpoint 2: GET /api/traces/tools/ranking

Ранжировать инструменты по метрике.

**Запрос:**
```bash
GET /api/traces/tools/ranking?workspace_id=ws-123&metric=success_rate&limit=10
Authorization: Bearer YOUR_JWT_TOKEN
```

**Параметры:**
- `workspace_id` (required): ID workspace
- `metric` (required): success_rate | latency | count | quality_score
- `limit` (optional, default=10): Количество результатов

**Ответ:**
```json
{
  "metric": "success_rate",
  "ranking": [
    {
      "rank": 1,
      "tool_name": "file_reader",
      "success_rate": 0.998,
      "total_executions": 500
    },
    {
      "rank": 2,
      "tool_name": "web_search",
      "success_rate": 0.987,
      "total_executions": 450
    },
    {
      "rank": 3,
      "tool_name": "calculator",
      "success_rate": 0.933,
      "total_executions": 150
    }
  ]
}
```

### Endpoint 3: POST /api/traces/tools/score

Записать оценку качества для trace.

**Запрос:**
```bash
POST /api/traces/tools/score
Authorization: Bearer YOUR_JWT_TOKEN
Content-Type: application/json

{
  "trace_id": "trace-12345",
  "score": 0.95,
  "name": "accuracy",
  "comment": "отличные результаты, точно ответил на вопрос"
}
```

**Параметры:**
- `trace_id` (required): ID trace из Langfuse
- `score` (required): Оценка 0.0-1.0
- `name` (required): Название метрики (accuracy, relevance, completeness, etc)
- `comment` (optional): Комментарий к оценке

**Ответ:**
```json
{
  "status": "success",
  "trace_id": "trace-12345",
  "score_recorded": true,
  "cache_invalidated": true
}
```

### Caching

Результаты кэшируются в Redis с TTL=1 час:

```python
# Cache key pattern
cache_key = f"{workspace_id}:{tool_name}:{period_days}:{metric}"

# Автоматическое кэширование
metrics = await langfuse.get_tool_metrics(
    workspace_id="ws-123",
    tool_name="calculator",
    period_days=7
)
# Результат автоматически кэшируется

# Инвалидация при записи score
await langfuse.record_tool_score(trace_id, score, name)
# Кэш для этого workspace автоматически инвалидируется
```

### Rate Limiting

API endpoints имеют rate limiting:
- Лимит: 100 запросов в минуту per workspace
- Заголовок ответа: `X-RateLimit-Remaining`
- При превышении: 429 Too Many Requests

---

## Graceful Degradation

### Сценарий 1: Langfuse отключен

```python
# В .env файле
LANGFUSE_ENABLED=false

# Поведение:
# - create_tool_execution_span() возвращает minimal span (без отправки)
# - Tool execution продолжается нормально
# - Нет overhead на трейсинг
```

### Сценарий 2: Langfuse недоступен (сеть выключена)

```python
# Поведение:
# - Попытка отправить span в Langfuse
# - Ошибка в Langfuse (ConnectionError, TimeoutError)
# - Логирует ошибку, инкрементирует метрику langfuse.send_errors
# - Tool execution НЕ прерывается!
# - Span данные теряются, но tool всё равно выполняется
```

### Сценарий 3: Langfuse timeout

```python
# Поведение:
# - Отправка span с 5-секундным таймаутом
# - Если timeout → логирует, инкрементирует langfuse.timeout_errors
# - Tool execution продолжается (fire-and-forget)
# - Данные span могут быть потеряны
```

### Сценарий 4: Analytics API без доступа к Langfuse

```python
# Если Langfuse API недоступен:
# - GET /api/traces/tools/metrics возвращает 503 Service Unavailable
# - Но tool execution продолжает работать!
```

### Рекомендации по мониторингу

Мониторить эти метрики:

```python
# Алерты
langfuse.send_errors > 10 per minute
langfuse.timeout_errors > 5 per minute
langfuse.enabled == 0  # Tracing отключен

# Проверка health
GET /health endpoint проверяет Langfuse connectivity
```

---

## Performance & Overhead

### Измеренный overhead

На основе нагрузочного тестирования (100 concurrent executions):

| Метрика | Значение |
|---------|----------|
| Span creation overhead | < 10ms |
| Nested span creation | < 5ms each |
| Span completion overhead | < 15ms |
| Async send (5-sec timeout) | 0ms visible (fire-and-forget) |
| **Total per tool execution** | **< 50ms** ✅ |

### Оптимизации

1. **Async send**: Отправка spans не блокирует tool execution
2. **Fire-and-forget**: Не ждем подтверждения от Langfuse
3. **Batch sending**: Langfuse клиент батчит spans перед отправкой
4. **Timeout**: 5-сек таймаут предотвращает бесконечные ожидания
5. **Graceful degradation**: Отключение трейсинга = 0 overhead

### Load test результаты

```
Test: 100 concurrent tool executions (calculator tool)
Tracing enabled: YES

Results:
- Total time: 4.5 seconds
- Avg latency per tool: 245ms (includes 15ms tracing)
- P95 latency: 520ms
- P99 latency: 890ms
- Success rate: 100%
- Tracing overhead: 15ms avg (6% of total time)
- All 100 spans sent to Langfuse successfully
```

---

## Troubleshooting

### Проблема 1: Spans не видны в Langfuse

**Признаки:**
- Tool execution работает
- Но spans не отправляются в Langfuse

**Диагностика:**
```bash
# 1. Проверить LANGFUSE_ENABLED
grep LANGFUSE_ENABLED .env
# Должен быть = true

# 2. Проверить credentials
grep LANGFUSE_PUBLIC_KEY .env
grep LANGFUSE_SECRET_KEY .env
# Должны быть установлены

# 3. Проверить connectivity
curl -H "Authorization: Bearer YOUR_SECRET_KEY" \
  https://api.langfuse.com/api/health

# 4. Проверить логи
docker-compose logs app | grep -i langfuse
# Ищите ошибки при отправке spans
```

**Решение:**
```bash
# 1. Переделать credentials в .env
LANGFUSE_PUBLIC_KEY=pk-...
LANGFUSE_SECRET_KEY=sk-...

# 2. Перезапустить сервис
docker-compose restart app

# 3. Проверить логи еще раз
docker-compose logs -f app
```

### Проблема 2: Tool execution медленнее после добавления трейсинга

**Признаки:**
- Tool execution latency вырос на 100+ ms

**Диагностика:**
```python
# Проверить, что overhead < 50ms
# Если больше - скорее всего проблема в Langfuse:
# - Медленная сеть
# - Перегруженный Langfuse
# - Большой размер spans

# Проверить размер spans:
logger.info(f"Span size: {len(json.dumps(span_dict))} bytes")
```

**Решение:**
```python
# 1. Уменьшить объем метаданных
metadata = {
    "agent_name": agent_name,
    # НЕ добавлять огромные блобы данных
}

# 2. Уменьшить частоту отправки
# Использовать batch sending в Langfuse

# 3. Увеличить таймаут (рискованно)
# LANGFUSE_SEND_TIMEOUT_SEC=10

# 4. Отключить трейсинг если критично
LANGFUSE_ENABLED=false
```

### Проблема 3: Высокое потребление памяти

**Признаки:**
- Приложение потребляет много памяти
- После запуска инструментов память не освобождается

**Диагностика:**
```bash
# Проверить что spans завершаются
# В логах должны быть end_tool_execution_span logs

# Проверить что Langfuse клиент не создает утечки
# Это бывает если span объекты не очищаются
```

**Решение:**
```python
# Убедиться что span объекты удаляются после использования
span = await langfuse.create_tool_execution_span(...)
try:
    # работа
    pass
finally:
    # Явно удалить ссылку (Python GC очистит)
    del span
```

### Проблема 4: API rate limiting

**Признаки:**
- GET /api/traces/tools/metrics возвращает 429 Too Many Requests

**Решение:**
```python
# Уменьшить частоту запросов к API
# Или увеличить rate limit:

# В config:
ANALYTICS_RATE_LIMIT_PER_MINUTE=1000  # вместо 100
```

---

## Migration Guide

### Для разработчиков

Если вы добавляете новый инструмент и хотите использовать трейсинг:

#### Шаг 1: Добавить зависимость в ToolExecutor

```python
from app.core.tools.executor import ToolExecutor
from app.services.langfuse_integration import LangfuseIntegration

# DI контейнер (например, в app/dependencies.py):
def get_tool_executor(
    langfuse: LangfuseIntegration = Depends(get_langfuse)
):
    return ToolExecutor(langfuse_integration=langfuse)
```

#### Шаг 2: Использовать executor

```python
# В routes или service:
executor = ToolExecutor(langfuse_integration=langfuse)

result = await executor.execute_tool(
    tool_name="my_new_tool",
    input_params={"param": "value"},
    user_id=user_id,
    workspace_id=workspace_id
)
# Всё! Трейсинг добавляется автоматически
```

#### Шаг 3: (Опционально) Добавить custom metadata

```python
# Если нужен custom контекст в spans:
struct_log.bind(
    agent_name="my_agent",
    chat_session_id="session-123",
    custom_field="value"
)

# LangfuseIntegration автоматически извлечет:
user_id, workspace_id, agent_id = langfuse._extract_context_vars()
```

### Для DevOps / Infrastructure

#### Требуемые переменные окружения

```bash
# .env файл
# === Langfuse ===
LANGFUSE_ENABLED=true  # Включить трейсинг
LANGFUSE_TRACING_ENABLED=true  # Управление отправкой трасс (SDK)
LANGFUSE_PUBLIC_KEY=pk-...  # Из Langfuse dashboard
LANGFUSE_SECRET_KEY=sk-...  # Из Langfuse dashboard
LANGFUSE_BASE_URL=https://api.langfuse.com  # Default

# === Tool Execution Tracing ===
TOOL_EXECUTION_TRACING_ENABLED=true  # Включить tool tracing
TOOL_ANALYTICS_ENABLED=true  # Включить analytics API
TOOL_EXECUTION_TIMEOUT_SECONDS=300  # Таймаут выполнения

# === Redis (для caching analytics) ===
REDIS_URL=redis://localhost:6379/0
ANALYTICS_CACHE_TTL_SECONDS=3600  # 1 hour
```

#### Health check интеграция

```python
# /health endpoint уже проверяет Langfuse:
GET /health
Response:
{
  "status": "healthy",
  "services": {
    "langfuse": {
      "status": "available",
      "version": "2.0.0"
    },
    "postgres": "ok",
    "redis": "ok"
  }
}
```

#### Мониторинг в Prometheus

```python
# Доступные метрики:
langfuse_spans_created_total
langfuse_spans_ended_total
langfuse_send_errors_total
langfuse_timeout_errors_total
tool_execution_latency_ms (histogram)
tool_execution_success_rate
analytics_api_requests_total
```

---

## Развертывание (Deployment)

### Production готовность

Чек-лист перед production:

- ✅ LANGFUSE_ENABLED=true
- ✅ Credentials (PUBLIC_KEY, SECRET_KEY) установлены и проверены
- ✅ Redis настроен и работает (для caching)
- ✅ Health check проходит без ошибок
- ✅ Нагрузочный тест выполнен (overhead < 50ms)
- ✅ Логирование Langfuse ошибок включено
- ✅ Мониторинг метрик настроен
- ✅ Alerting правила настроены

### Gradual rollout

Использовать feature flags для постепенного включения:

```python
# .env
TOOL_EXECUTION_TRACING_ENABLED=true
TOOL_ANALYTICS_ENABLED=true

# Или через FF сервис:
@app.dependency
def is_tool_tracing_enabled():
    return feature_flags.get("tool_execution_tracing", default=True)
```

### Rollback план

Если что-то пошло не так:

```bash
# Быстрый rollback - отключить трейсинг:
LANGFUSE_ENABLED=false
docker-compose restart app

# Tool execution продолжит работать без spans
# Нет потери данных, нет прерывания сервиса
```

---

## FAQ

**Q: Нужно ли менять мой код для трейсинга?**
A: Нет! Если вы используете ToolExecutor, трейсинг добавляется автоматически.

**Q: Что если Langfuse недоступен?**
A: Tool execution продолжит работать. Spans не будут отправлены, но инструменты выполнятся.

**Q: Можно ли отключить трейсинг для конкретного tool?**
A: Нет встроенного способа, но можно установить LANGFUSE_ENABLED=false глобально.

**Q: Какой размер spans может быть?**
A: Рекомендуется < 10KB per span. Большие блобы замедлят отправку.

**Q: Как долго spans хранятся в Langfuse?**
A: По умолчанию 30 дней. Настраивается в Langfuse dashboard.

**Q: Нужна ли финансовая подписка на Langfuse?**
A: Зависит от объема. Бесплатный план включает некоторое количество spans/month.

---

## Контакты и поддержка

Для вопросов или проблем:
1. Проверьте раздел [Troubleshooting](#troubleshooting)
2. Посмотрите логи: `docker-compose logs app | grep langfuse`
3. Откройте issue на GitHub
4. Свяжитесь с team через Slack
