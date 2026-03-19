# Tool Execution Tracing - Архитектура

**Версия**: Phase 4 Part 1  
**Последнее обновление**: 2026-03-19  
**Статус**: Production Ready

---

## Содержание

1. [Общее описание](#общее-описание)
2. [Компоненты системы](#компоненты-системы)
3. [Поток данных](#поток-данных)
4. [Context Propagation](#context-propagation)
5. [Graceful Degradation](#graceful-degradation)
6. [Интеграция с существующими системами](#интеграция-с-существующими-системами)

---

## Общее описание

Tool Execution Tracing - это распределённая система мониторинга выполнения инструментов в платформе CodeLab. Система использует Langfuse SDK для захвата и хранения trace данных с минимальным overhead и полной поддержкой graceful degradation.

### Архитектурные принципы

```
┌─────────────────────────────────────────────────────────────────┐
│                    Tool Execution Request                        │
│                  (ToolExecutor.execute_tool)                    │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
        ┌──────────────────────────────────────────┐
        │   @observe Декоратор (Langfuse SDK)     │
        │   - Автоматическое создание span        │
        │   - Управление жизненным циклом         │
        └──────────────────┬───────────────────────┘
                           │
                           ▼
        ┌──────────────────────────────────────────┐
        │   _update_langfuse_span()                │
        │   - Санитизация данных                   │
        │   - Добавление контекста                 │
        │   - Безопасное обновление span           │
        └──────────────────┬───────────────────────┘
                           │
                           ▼
        ┌──────────────────────────────────────────┐
        │   Langfuse SDK (Async)                   │
        │   - Буферизация spans                    │
        │   - Асинхронная отправка                 │
        │   - Обработка ошибок                     │
        └──────────────────┬───────────────────────┘
                           │
                           ▼
        ┌──────────────────────────────────────────┐
        │   Langfuse Backend                       │
        │   - Хранение spans                       │
        │   - Индексирование                       │
        │   - Анализ и агрегация                   │
        └──────────────────────────────────────────┘
```

---

## Компоненты системы

### 1. LangfuseClient - Инициализация и управление

**Файл**: [`app/services/langfuse_client.py`](../../app/services/langfuse_client.py)

```python
class LangfuseClient:
    """Управляет инициализацией Langfuse SDK и контекстом трассировки."""
    
    def __init__(self) -> None:
        """Инициализировать Langfuse клиент на основе настроек."""
        self.enabled: bool  # Флаг включения/отключения
        self.client: Optional[Langfuse]  # SDK экземпляр
    
    def flush(self) -> None:
        """Отправить все pending spans на сервер Langfuse."""
```

**Ответственность**:
- Инициализация Langfuse SDK при запуске приложения
- Валидация конфигурации (public key, secret key, base URL)
- Управление глобальным экземпляром клиента
- Graceful degradation если конфигурация недоступна

**Graceful Degradation**:
```python
# Если конфигурация отсутствует или неверна
if not settings.langfuse_enabled:
    self.enabled = False
    logger.info("langfuse_disabled")
    return

# Если инициализация не удалась
try:
    self.client = Langfuse(...)
except Exception as e:
    self.enabled = False
    logger.error("langfuse_initialization_failed", error=str(e))
```

### 2. ToolExecutor - Главный оркестратор

**Файл**: [`app/core/tools/executor.py`](../../app/core/tools/executor.py)

#### Две вспомогательные функции

```python
def _safe_tool_input(
    tool_name: str,
    tool_params: dict,
    session_id: Optional[UUID]
) -> dict:
    """Построить санитизованный payload входных данных для Langfuse span.
    
    Исключает:
    - Полное содержимое файлов
    - Полные команды оболочки
    - API ключи
    
    Включает:
    - Имена параметров
    - Длины/размеры
    - Пути (урезанные)
    - Паттерны (урезанные)
    """
    payload = {
        "tool_name": tool_name,
        "session_id": str(session_id) if session_id else None,
        "param_keys": sorted(list(tool_params.keys()))
    }
    # ... дополнительная санитизация ...
    return payload


def _update_langfuse_span(
    *, 
    input_data: dict | None = None,
    output_data: dict | None = None
) -> None:
    """Безопасно присоединить санитизованный IO payload к текущему Langfuse span.
    
    Гарантии:
    - Исключения не распространяются
    - Логируется на DEBUG уровне
    - Выполнение инструмента не блокируется
    """
    try:
        get_client().update_current_span(
            input=input_data,
            output=output_data
        )
    except Exception:
        logger.debug("langfuse_span_update_skipped", exc_info=True)
        # Ошибка не распространяется - выполнение продолжается
```

#### Главный метод - execute_tool()

```python
class ToolExecutor:
    
    @observe(
        as_type="tool",
        name="ExecuteTool",
        capture_input=False,
        capture_output=False
    )
    async def execute_tool(
        self,
        tool_name: str,
        tool_params: dict,
        session_id: Optional[UUID] = None
    ) -> ToolExecutionResponse:
        """Выполнить инструмент с полной валидацией и workflow одобрения.
        
        Workflow:
        1. Создать root span через @observe
        2. Обновить input payload (санитизованные параметры)
        3. Валидировать параметры
        4. Оценить риск
        5. Обработать одобрение (если нужно)
        6. Выполнить инструмент
        7. Обновить output payload (результат/ошибка)
        8. Вернуть ответ (span отправляется асинхронно)
        """
        
        # 1. Создать root span (автоматически через @observe)
        _update_langfuse_span(
            input_data=_safe_tool_input(tool_name, tool_params, session_id)
        )
        
        # 2-6. Валидация, оценка риска, одобрение, выполнение
        # (логика здесь)
        
        # 7. Обновить output
        _update_langfuse_span(output_data={
            "status": result_status,
            "tool_id": str(tool_id),
            "execution_time_ms": elapsed_ms,
            # ... другие поля ...
        })
        
        # 8. Вернуть ответ
        return ToolExecutionResponse(...)
```

---

## Поток данных

### Пример полного потока

```
User API Request
    │ tool_name="read_file"
    │ tool_params={"path": "/workspace/data.txt"}
    │ session_id="session-123"
    │
    ▼
ToolExecutor.execute_tool()
    │
    ├─ @observe создает root span (ExecuteTool)
    │
    ├─ _update_langfuse_span(input_data={
    │    "tool_name": "read_file",
    │    "param_keys": ["path"],
    │    "path": "/workspace/data.txt",
    │    "session_id": "session-123"
    │  })
    │
    ├─ Валидация параметров
    │  └─ _validate_tool_params() создает child span (ValidateTool)
    │
    ├─ Оценка риска
    │  └─ risk_assessor.assess_tool_risk() → risk_level
    │
    ├─ Обработка одобрения (если needed)
    │  └─ approval_manager.require_approval() → approval_status
    │
    ├─ Выполнение инструмента
    │  └─ execute_read_file("/workspace/data.txt")
    │
    ├─ _update_langfuse_span(output_data={
    │    "status": "success",
    │    "tool_id": "abc123",
    │    "result": "File contents",
    │    "execution_time_ms": 125,
    │    "risk_level": "low",
    │    "approval_required": false
    │  })
    │
    ▼
Langfuse SDK
    │ (Асинхронная буферизация и отправка)
    │
    ▼
Langfuse Backend
    │ (Хранение, индексирование, анализ)
    │
    ▼
Langfuse Dashboard
    └─ Визуализация spans, метрик, аналитики
```

### Иерархия spans в Langfuse

```
ExecuteTool (root, 125ms)
├── @observe(as_type="tool", name="ExecuteTool")
├── Input:
│   ├── tool_name
│   ├── param_keys
│   ├── path
│   └── session_id
├── Output:
│   ├── status
│   ├── tool_id
│   ├── result
│   ├── execution_time_ms
│   ├── risk_level
│   └── approval_required
├── Metadata (automatic):
│   ├── user_id
│   ├── project_id
│   ├── session_id
│   ├── timestamp
│   └── request_id
│
└── Child Spans:
    └── ValidateTool (5ms)
        ├── Input: {tool_name, param_keys}
        └── Output: {validation_status, errors}
```

---

## Context Propagation

### Как контекст распространяется

```
┌──────────────────────────────────────┐
│   HTTP Request + JWT Token           │
│   Authorization: Bearer <token>      │
└──────────────┬───────────────────────┘
               │
               ▼
┌──────────────────────────────────────┐
│   FastAPI Dependency (get_current_user)
│   Extract: user_id, project_id       │
└──────────────┬───────────────────────┘
               │
               ▼
┌──────────────────────────────────────┐
│   ToolExecutor.__init__()            │
│   Store: self.user_id                │
│   Store: self.project_id             │
└──────────────┬───────────────────────┘
               │
               ▼
┌──────────────────────────────────────┐
│   execute_tool(session_id=...)       │
│   Receive: session_id parameter      │
└──────────────┬───────────────────────┘
               │
               ▼
┌──────────────────────────────────────┐
│   _safe_tool_input()                 │
│   Build payload with:                │
│   - tool_name, param_keys            │
│   - session_id (параметр)            │
│   - user_id (из JWT)                 │
│   - project_id (из JWT)              │
└──────────────┬───────────────────────┘
               │
               ▼
┌──────────────────────────────────────┐
│   _update_langfuse_span(input_data)  │
│   Langfuse SDK добавляет:            │
│   - Все поля из payload              │
│   - Automatic metadata (timestamp)   │
└──────────────┬───────────────────────┘
               │
               ▼
┌──────────────────────────────────────┐
│   Langfuse Backend                   │
│   Store with full context:           │
│   ✓ user_id                          │
│   ✓ project_id                       │
│   ✓ session_id                       │
│   ✓ All execution details            │
└──────────────────────────────────────┘
```

### Структура контекста в span

```json
{
  "metadata": {
    "user_id": "550e8400-e29b-41d4-a716-446655440000",
    "project_id": "550e8400-e29b-41d4-a716-446655440001",
    "session_id": "550e8400-e29b-41d4-a716-446655440002"
  },
  "input": {
    "tool_name": "read_file",
    "session_id": "550e8400-e29b-41d4-a716-446655440002",
    "user_id": "550e8400-e29b-41d4-a716-446655440000",
    "project_id": "550e8400-e29b-41d4-a716-446655440001",
    "param_keys": ["path"]
  }
}
```

---

## Graceful Degradation

### Слои деградации

**Слой 1: Конфигурация**
```python
# Если LANGFUSE_ENABLED=false
if not settings.langfuse_enabled:
    client.enabled = False
    # Вся система трассировки отключена
```

**Слой 2: Инициализация**
```python
# Если конфигурация неверна или сервис недоступен
try:
    self.client = Langfuse(...)
except Exception:
    self.enabled = False
    # Спан не создается, выполнение продолжается
```

**Слой 3: Обновление span**
```python
# Если Langfuse недоступен или обновление не удается
try:
    get_client().update_current_span(...)
except Exception:
    logger.debug("langfuse_span_update_skipped", exc_info=True)
    # Выполнение инструмента продолжается без блокирования
```

**Слой 4: Отправка**
```python
# Langfuse SDK автоматически обрабатывает:
# - Сетевые таймауты
# - Переполнение буфера
# - Retry logic с exponential backoff
```

### Диаграмма потока деградации

```
Tool Execution Request
    │
    ▼
Is LANGFUSE_ENABLED?
    │
    ├─ NO  → Skip tracing, execute tool normally ✓
    │
    ├─ YES → Initialize Langfuse
            │
            ▼
        Can initialize?
            │
            ├─ NO  → Log error, skip tracing, execute tool normally ✓
            │
            ├─ YES → Create span
                    │
                    ▼
                Can update span?
                    │
                    ├─ NO  → Log DEBUG, execute tool normally ✓
                    │
                    ├─ YES → Update with data
                            │
                            ▼
                        Can send to Langfuse?
                            │
                            ├─ NO (timeout) → SDK retry + buffer
                            │
                            ├─ YES → Store in Langfuse ✓
                            │
                            └─ Network error → SDK auto-retry
```

### Гарантии надёжности

| Компонент | Гарантия | Реализация |
|-----------|---------|-----------|
| **Инициализация** | Не блокирует запуск | try-except в LangfuseClient.__init__ |
| **Span создание** | Не блокирует выполнение | @observe обрабатывает исключения |
| **Span обновление** | Не влияет на инструмент | try-except в _update_langfuse_span() |
| **Отправка** | Асинхронная, non-blocking | Langfuse SDK (async flush) |
| **Таймаут** | Max 5 sec (configurable) | LANGFUSE_FLUSH_TIMEOUT |
| **Ошибки** | Логируются, не распространяются | logger.debug(), no re-raise |

---

## Интеграция с существующими системами

### Интеграция с ApprovalManager

```
Tool Execution Request
    │
    ├─ Risk Assessment
    │  └─ risk_level = high → requires approval
    │
    ├─ Approval Workflow
    │  ├─ ApprovalManager.require_approval()
    │  └─ Wait for approval or timeout
    │
    └─ Update tracing
       ├─ approval_required: true
       ├─ approval_status: "approved" | "rejected"
       └─ approval_id: <uuid>
```

**Span output при требуемом одобрении**:
```json
{
  "output": {
    "status": "success",
    "approval_required": true,
    "approval_status": "approved",
    "approval_id": "appr-123",
    "risk_level": "high",
    "execution_time_ms": 250
  }
}
```

### Интеграция с RiskAssessor

```
Tool Parameters
    │
    ▼
RiskAssessor.assess_tool_risk()
    │
    ├─ path validation
    ├─ command analysis
    ├─ resource limits check
    │
    ▼
Output:
{
  "risk_level": "low" | "medium" | "high" | "critical",
  "risk_score": 0.0-10.0,
  "reasons": [...]
}
    │
    ▼
Update tracing:
{
  "risk_level": "medium",
  "risk_score": 4.5
}
```

### Параллелизм с OpenTelemetry

```
Tool Execution
    │
    ├─ Langfuse tracing (@observe)
    │  └─ Tool-specific spans in Langfuse
    │
    ├─ OpenTelemetry tracing (если включено)
    │  └─ Infrastructure spans (async function calls)
    │
    └─ Структурированное логирование (structlog)
       └─ Events в логах
```

**Важно**: Две системы работают параллельно без конфликтов:
- Langfuse отслеживает бизнес-логику инструментов
- OpenTelemetry отслеживает технические детали (DB queries, HTTP calls)
- structlog собирает события для анализа

---

## Производительность

### Overhead анализ

```
Tool Execution (baseline): 100ms
+ Span creation (@observe): ~1ms (async)
+ Input sanitization: ~2ms
+ Span update (input): ~0.5ms
+ Span update (output): ~0.5ms
+ Langfuse async send: 0ms (non-blocking)
───────────────────────────────────────
Total execution: ~104ms
Overhead: ~4% (acceptable)
```

### Масштабируемость

- **Concurrent executions**: Langfuse SDK использует async, поддерживает 100+ одновременных spans
- **Buffer size**: SDK буферизует spans, переполнение обрабатывается gracefully
- **Network bandwidth**: ~0.5KB per span, minimal impact
- **Memory**: ~100KB per 1000 pending spans (negligible)

---

## Развертывание и конфигурация

### Переменные окружения

```bash
# Включить/отключить tracing
LANGFUSE_ENABLED=true
LANGFUSE_TRACING_ENABLED=true

# Учетные данные
LANGFUSE_PUBLIC_KEY=pk_...
LANGFUSE_SECRET_KEY=sk_...

# Сервер Langfuse
LANGFUSE_BASE_URL=https://cloud.langfuse.com
LANGFUSE_HOST=https://cloud.langfuse.com

# Отладка
LANGFUSE_DEBUG=false
```

### Health check

```python
from app.services.langfuse_client import get_langfuse_client

client = get_langfuse_client()
if client.enabled:
    print("✓ Tracing is operational")
else:
    print("⚠ Tracing is disabled")
```

### Flush при завершении

```python
# В app/main.py, при shutdown
@app.on_event("shutdown")
async def shutdown_event():
    client = get_langfuse_client()
    client.flush()  # Отправить все pending spans
```

---

## Безопасность

### Санитизация данных

**Автоматическое исключение**:
- File contents (поле `content`)
- Shell commands (поле `command`)
- API keys, passwords, tokens

**Ручная санитизация в _safe_tool_input()**:
```python
# Исключить пользовательские чувствительные поля
if "secret_field" in tool_params:
    payload["secret_field"] = "***REDACTED***"
```

### Изоляция данных

- **Workspace isolation**: Каждый workspace имеет свой project_id
- **User isolation**: Traces фильтруются по user_id из JWT
- **Session isolation**: session_id позволяет фильтровать по сессии

### Доступ к данным

- **Langfuse API**: Требует public key + secret key
- **Langfuse Dashboard**: Требует аутентификации в Langfuse
- **Внутренние логи**: DEBUG уровень содержит span данные

---

## Мониторинг и отладка

### Метрики для отслеживания

```
- Количество spans created
- Количество failed updates
- Network errors to Langfuse
- Buffer overflow events
- Average span creation time
```

### Логирование

```python
# Включить для отладки
export LANGFUSE_DEBUG=true

# Логи содержат:
# - langfuse_client_initialized
# - langfuse_span_update_skipped (на DEBUG)
# - langfuse_initialization_failed
# - langfuse_flush_failed
```

### Проверка в Langfuse Dashboard

1. Перейти на https://cloud.langfuse.com/
2. Выбрать проект
3. Перейти на вкладку "Traces"
4. Найти spans с именем "ExecuteTool"
5. Проверить иерархию и метаданные

---

## Будущие расширения

### Phase 4 Part 2 планы

- **Analytics API**: Endpoints для получения метрик инструментов
- **Redis caching**: Кэширование метрик с TTL
- **Rate limiting**: Защита analytics endpoints
- **Performance dashboard**: UI для анализа производительности
- **Custom metrics**: Возможность добавлять кастомные метрики

---

## Ссылки

- [`app/services/langfuse_client.py`](../../app/services/langfuse_client.py) - Инициализация
- [`app/core/tools/executor.py`](../../app/core/tools/executor.py) - Главная реализация
- [`doc/guides/tool-execution-tracing.md`](../guides/tool-execution-tracing.md) - User Guide
- [`doc/api/api-specification.md`](../api/api-specification.md) - API спецификация

---

**Документ создан**: 2026-03-19  
**Версия**: 1.0  
**Ведётся**: CodeLab Team
