# Tool Execution Tracing - Руководство пользователя

**Версия**: Phase 4 Part 1  
**Последнее обновление**: 2026-03-19  
**Статус**: Production Ready

---

## Оглавление

1. [Обзор](#обзор)
2. [Ключевые концепции](#ключевые-концепции)
3. [Использование @observe декораторов](#использование-observe-декораторов)
4. [Интеграция с Langfuse](#интеграция-с-langfuse)
5. [Распространение контекста](#распространение-контекста)
6. [Graceful Degradation](#graceful-degradation)
7. [Конфигурация](#конфигурация)
8. [Troubleshooting](#troubleshooting)

---

## Обзор

Tool Execution Tracing - это система, которая автоматически захватывает и логирует каждое выполнение инструмента в платформе CodeLab в Langfuse для анализа производительности, мониторинга качества и отладки.

### Ключевые возможности

- **Автоматический захват**: Каждое выполнение инструмента автоматически трейсируется через `@observe` декораторы Langfuse
- **Сохранение контекста**: ID пользователя, Project ID и Session ID автоматически включаются в трассировки
- **Вложенные spans**: Поток выполнения инструмента (валидация → оценка риска → одобрение → выполнение) захватывается как вложенные spans
- **Graceful Degradation**: Система продолжает работать нормально, если Langfuse недоступен
- **Нулевая конфигурация**: Работает из коробки с переменными окружения
- **Производительность**: Минимальный overhead (~O(1) на выполнение)

### Что трейсируется

Каждое выполнение инструмента автоматически захватывает:

```
Tool Execution Span
├── Input: Санитизованные имя инструмента, параметры, ID сессии
├── Context: User ID, Project ID из JWT
├── Validation: Статус валидации параметров
├── Risk Assessment: Уровень риска и оценка риска
├── Approval: Статус одобрения (если требуется)
├── Output: Статус выполнения, результаты, ошибки
└── Metadata: Время выполнения, временные метки
```

---

## Ключевые концепции

### Spans (трассировки)

**Span** - это запись одной операции. Tool Execution Tracing создает spans для:

1. **Root Span**: `ExecuteTool` - захватывает всё выполнение инструмента
2. **Child Spans**: Вложенные операции в рамках выполнения инструмента (валидация, оценка риска)

### Санитизация входных данных

Параметры инструмента санитизируются перед отправкой в Langfuse:

- **Исключённые**: Полный контент команд, содержимое файлов, чувствительные API ключи
- **Включённые**: Имена инструментов, ключи параметров, пути, паттерны, статус выполнения, ID контекста

Пример:

```python
# Исходные параметры (чувствительные)
{
    "path": "/home/user/secret.txt",
    "content": "SECRET_API_KEY=xyz...",
    "command": "curl -H 'Authorization: Bearer token123' https://api.example.com"
}

# Санитизованные для Langfuse (безопасные)
{
    "tool_name": "write_file",
    "param_keys": ["path", "content"],
    "path": "/home/user/secret.txt",
    "content_length": 18
}
```

### Распространение контекста

Три значения контекста автоматически включаются в каждую трассировку:

- **User ID**: Извлекается из JWT токена
- **Project ID**: Извлекается из JWT токена
- **Session ID**: Передается как параметр `session_id` в `execute_tool()`

---

## Использование @observe декораторов

`@observe` декоратор из Langfuse SDK автоматически создает и управляет spans.

### Базовое использование

```python
from langfuse import observe

@observe(as_type="tool", name="ExecuteTool", capture_input=False, capture_output=False)
async def execute_tool(
    self,
    tool_name: str,
    tool_params: dict,
    session_id: Optional[UUID] = None
) -> ToolExecutionResponse:
    """Выполнить инструмент с автоматической трассировкой."""
    # Логика выполнения инструмента
    pass
```

### Параметры декоратора

- `as_type="tool"`: Тип span для панели управления Langfuse
- `name="ExecuteTool"`: Имя span в трассировках
- `capture_input=False`: Не захватывать входные данные автоматически (мы делаем ручную санитизацию)
- `capture_output=False`: Не захватывать выходные данные автоматически (мы контролируем логирование)

### Ручное обновление spans

После создания span декоратором, вручную добавьте данные используя `_update_langfuse_span()`:

```python
from app.core.tools.executor import _update_langfuse_span, _safe_tool_input

# Обновить входные данные
_update_langfuse_span(input_data=_safe_tool_input(
    tool_name="read_file",
    tool_params={"path": "/home/user/data.txt"},
    session_id=uuid.uuid4()
))

# ... выполнение инструмента ...

# Обновить выходные данные
_update_langfuse_span(output_data={
    "status": "success",
    "tool_id": "abc123",
    "result": "Содержимое файла",
    "execution_time_ms": 45
})
```

### Обработка ошибок

Декоратор автоматически обрабатывает ошибки без их распространения:

```python
def _update_langfuse_span(*, input_data: dict | None = None, output_data: dict | None = None) -> None:
    """Безопасно присоединить санитизованные IO данные к текущему Langfuse span."""
    try:
        get_client().update_current_span(input=input_data, output=output_data)
    except Exception:
        logger.debug("langfuse_span_update_skipped", exc_info=True)
        # Выполнение продолжается нормально - исключения не распространяются
```

---

## Интеграция с Langfuse

### Архитектура

```
┌─────────────────────────────────────────────┐
│         Запрос на выполнение инструмента    │
│      (через ToolExecutor.execute_tool)      │
└────────────────┬────────────────────────────┘
                 │
                 ▼
        ┌────────────────────────────────────┐
        │ @observe Декоратор создает Span   │
        └────────────────┬───────────────────┘
                         │
                         ▼
        ┌────────────────────────────────────┐
        │ _update_langfuse_span() Добавляет  │
        │ - Input: санитизованные параметры │
        │ - Output: результат/информация об │
        │           ошибке                   │
        └────────────────┬───────────────────┘
                         │
                         ▼
        ┌────────────────────────────────────┐
        │  Langfuse SDK (Асинхронная отправка)
        │  на бэкэнд Langfuse                │
        └────────────────────────────────────┘
```

### Иерархия spans

Для типичного выполнения инструмента Langfuse получает:

```
ExecuteTool (root span)
├── Input: {tool_name: "read_file", param_keys: ["path"], path: "..."}
├── Output: {status: "success", tool_id: "...", result: "..."}
├── Metadata:
│   ├── user_id: "user-123"
│   ├── project_id: "project-456"
│   ├── session_id: "session-789"
│   ├── risk_level: "medium"
│   ├── execution_time_ms: 125
│   └── timestamp: "2026-03-19T15:30:00Z"
└── Child Spans (созданные внутренне):
    ├── ValidateTool span
    │   └── validation_status: "passed"
    └── Future: ApprovalWorkflow span (когда будет реализовано)
```

---

## Распространение контекста

### Как контекст распространяется

1. **JWT Token** содержит информацию пользователя и проекта
2. **ToolExecutor** извлекает ID из JWT через FastAPI dependencies
3. **execute_tool()** получает параметр `session_id`
4. **_safe_tool_input()** создает payload со всеми контекстными данными
5. **Langfuse SDK** включает контекст в метаданные span

### Пример потока запроса

```python
# В API endpoint (FastAPI маршрут)
@router.post("/execute-tool")
async def execute_tool_endpoint(
    user: User = Depends(get_current_user),  # Из JWT
    project_id: UUID = Depends(get_project_id),  # Из JWT
    request: ToolExecutionRequest
):
    executor = ToolExecutor(
        user_id=user.id,
        project_id=project_id,
        workspace_root=...
    )
    
    # session_id из запроса или контекста чата
    result = await executor.execute_tool(
        tool_name=request.tool_name,
        tool_params=request.params,
        session_id=request.session_id  # Распространяется в трассировку
    )
    
    # Трассировка автоматически включает:
    # - user_id (из JWT)
    # - project_id (из JWT)
    # - session_id (из параметра execute_tool)
```

### Просмотр контекста в Langfuse

В панели управления Langfuse контекст виден в:

1. **Вкладке метаданных span**: Показывает user_id, project_id, session_id
2. **Вкладке Input**: Содержит param_keys для параметров инструмента
3. **Вкладке Output**: Показывает результаты выполнения

---

## Graceful Degradation

### Что происходит, когда Langfuse недоступен

Если Langfuse недоступен, недостижим или отключен:

1. **Выполнение инструмента продолжается нормально** - блокирования нет
2. **Трассировка пропускается** - исключение перехватывается и логируется на DEBUG уровне
3. **Производительность системы** - не затронута (минимальный overhead в любом случае)
4. **Опыт пользователя** - не изменён

### Конфигурация

Отключите трассировку с переменными окружения:

```bash
# Полностью отключить Langfuse клиент
LANGFUSE_ENABLED=false

# Или отключить только трассировку (сохранить клиент)
LANGFUSE_TRACING_ENABLED=false

# Или временно отключить для отладки
LANGFUSE_DEBUG=true  # Включает подробное логирование
```

### Схема поведения

```
Запрос на выполнение инструмента
      │
      ▼
Langfuse ENABLED в конфиге?
      │
      ├─ НЕТ → Пропустить всю трассировку, выполнить инструмент нормально
      │
      ├─ ДА → Попытаться создать/обновить span
            │
            ├─ УСПЕХ → Выполнение инструмента с полной трассировкой
            │
            ├─ ОШИБКА → Логировать на DEBUG, выполнить инструмент нормально
            │          (исключение не распространяется)
            │
            └─ TIMEOUT → Логировать ошибку, продолжить (Langfuse SDK обрабатывает таймауты)
```

### Пример: Отключить трассировку

```python
# В .env
LANGFUSE_ENABLED=false

# Инструмент всё ещё выполняется нормально
result = await executor.execute_tool(
    tool_name="read_file",
    tool_params={"path": "/tmp/data.txt"}
)
# Результат идентичен, просто нет трассировки в Langfuse
```

---

## Конфигурация

### Переменные окружения

```bash
# Основные настройки Langfuse
LANGFUSE_ENABLED=true
LANGFUSE_TRACING_ENABLED=true
LANGFUSE_PUBLIC_KEY=your_public_key_here
LANGFUSE_SECRET_KEY=your_secret_key_here
LANGFUSE_BASE_URL=https://cloud.langfuse.com
LANGFUSE_HOST=https://cloud.langfuse.com
LANGFUSE_DEBUG=false

# Опционально: Таймаут flush (секунды)
LANGFUSE_FLUSH_TIMEOUT=5
```

### Валидация настроек

Система валидирует конфигурацию при запуске:

```python
# В LangfuseClient.__init__
if not settings.langfuse_public_key or not settings.langfuse_secret_key:
    logger.warning("Учетные данные Langfuse отсутствуют")
    enabled = False
```

### Development vs Production

**Development (.env.example)**:
```bash
LANGFUSE_ENABLED=true
LANGFUSE_DEBUG=true
LANGFUSE_PUBLIC_KEY=test_public_key
LANGFUSE_SECRET_KEY=test_secret_key
```

**Production (.env.production.example)**:
```bash
LANGFUSE_ENABLED=true
LANGFUSE_DEBUG=false
LANGFUSE_PUBLIC_KEY=${LANGFUSE_PUBLIC_KEY}
LANGFUSE_SECRET_KEY=${LANGFUSE_SECRET_KEY}
```

---

## Troubleshooting

### Проблема: Spans не появляются в Langfuse

**Проверка 1: Langfuse включен?**

```python
from app.services.langfuse_client import get_langfuse_client

client = get_langfuse_client()
print(f"Enabled: {client.enabled}")
```

**Проверка 2: Учетные данные действительны?**

```bash
# В логах ищите:
# - langfuse_client_initialized → учетные данные действительны
# - langfuse_initialization_failed → проверьте учетные данные
# - langfuse_disabled → проверьте настройку LANGFUSE_ENABLED
```

**Проверка 3: Сеть доступна?**

```bash
curl -I https://cloud.langfuse.com
# Должна вернуть 200 OK
```

### Проблема: Деградация производительности

**Нормальный overhead**: < 5ms на выполнение (асинхронно, без блокирования)

**Проверьте**:
- Таймаут сети к Langfuse (установите `LANGFUSE_FLUSH_TIMEOUT=10`)
- Высокий объём одновременных выполнений (должно быть OK, асинхронность справляется)

### Проблема: Отсутствующий контекст в трассировках

**Убедитесь, что контекст передается**:

```python
# Проверьте, что session_id предоставлен
result = await executor.execute_tool(
    tool_name="...",
    tool_params={...},
    session_id=some_session_id  # ← Должен быть предоставлен
)
```

**Убедитесь, что JWT содержит user_id и project_id**:

```python
# В API endpoint, проверьте токен
from app.dependencies import get_current_user
user = await get_current_user(token)
print(f"User ID: {user.id}")
```

### Проблема: Чувствительные данные просачиваются в Langfuse

**Санитизация параметров инструмента** автоматична:

```python
# Исключены из трассировок:
# - поле "content" (содержимое файлов)
# - поле "command" (полная команда)
# - другие пользовательские чувствительные поля (должны быть конфигурированы)

# Включены в трассировки:
# - "path" (урезано до 300 символов)
# - "pattern" (урезано до 120 символов)
# - ключи параметров (список имён параметров)
```

**Чтобы добавить дополнительную санитизацию**:

```python
# В app/core/tools/executor.py, измените _safe_tool_input()
def _safe_tool_input(tool_name: str, tool_params: dict, session_id: Optional[UUID]) -> dict:
    # ... существующий код ...
    
    # Добавьте пользовательскую санитизацию
    if "my_sensitive_field" in tool_params:
        payload["my_sensitive_field"] = "***REDACTED***"
    
    return payload
```

### Отладка логирования

Включите подробное логирование для трассировки:

```bash
# В .env
LANGFUSE_DEBUG=true
```

Это включает:
- Подробное логирование инициализации
- Логи создания spans
- Логи операций обновления
- Детали ошибок (включая stack traces)

---

## Best Practices

1. **Всегда предоставляйте session_id** при вызове `execute_tool()` для лучшей корреляции трассировок

2. **Добавьте пользовательский контекст** если необходимо:
   ```python
   payload = _safe_tool_input(tool_name, tool_params, session_id)
   payload["custom_field"] = "custom_value"
   _update_langfuse_span(input_data=payload)
   ```

3. **Не используйте `@observe` для чувствительных операций** - он разработан только для выполнения инструментов

4. **Регулярно проверяйте панель управления Langfuse** для:
   - Процентных показателей успеха/отказа инструментов
   - Метрик производительности
   - Паттернов ошибок
   - Анализа поведения пользователей

5. **Мониторьте overhead** - должен быть минимальным:
   ```bash
   # Проверьте логи для времён выполнения
   grep "execution_time_ms" app.log
   ```

---

## Связанная документация

- [`doc/guides/developer-guide.md`](./developer-guide.md) - Руководство разработчика для интеграции
- [`doc/api/api-specification.md`](../api/api-specification.md) - Спецификация данных трассировки API
- [`doc/architecture/`](../architecture/) - Детали архитектуры системы
- [`openspec/specs/tool-execution-trace/spec.md`](../../openspec/specs/tool-execution-trace/spec.md) - Детальная спецификация

---

**Последнее обновление**: 2026-03-19  
**Ведётся**: CodeLab Team
