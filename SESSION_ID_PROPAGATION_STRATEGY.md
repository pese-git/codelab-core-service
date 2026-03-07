# Стратегия пропагации session_id - Гарантированная доставка событий

## Текущая ситуация

Проблема: `session_id=None` приводит к потере событий `TOOL_EXECUTION_SIGNAL`, `TOOL_APPROVAL_REQUEST` и `TOOL_RESULT_ACK`.

**Решение:** Fallback механизм использует `broadcast_to_user()` когда `session_id=None`. Но это не идеально - лучше гарантировать, что `session_id` всегда правильно передается.

## Рекомендуемая стратегия

### 1. REST API: Сделать session_id обязательным

**Текущее состояние** (`app/routes/project_tools.py:91`):
```python
session_id=request.session_id or request.chat_session_id,  # ← Может быть None
```

**Что нужно сделать:**
Требовать `session_id` в `ToolExecutionRequest`:

```python
# app/schemas/tool.py
class ToolExecutionRequest(BaseModel):
    tool_name: str
    tool_params: dict
    session_id: Optional[UUID] = Field(
        None, 
        description="Chat session ID (required for SSE delivery)"
    )
    chat_session_id: Optional[UUID] = None  # Backward compat
```

**В эндпоинте:**
```python
# app/routes/project_tools.py:88
session_id = request.session_id or request.chat_session_id
if not session_id:
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="session_id is required for tool execution with event streaming"
    )

result = await worker_space.executor.execute_tool(
    tool_name=request.tool_name,
    tool_params=request.tool_params,
    session_id=session_id,
)
```

### 2. Агент: Всегда передавать session_id из контекста чата

**Текущее состояние** (`app/agents/contextual_agent.py:569`):
```python
response = await self.tool_executor.execute_tool(
    tool_name=tool_name,
    tool_params=tool_params,
    session_id=session_id,  # ← Может быть None
)
```

**Что нужно сделать:**
Агент должен знать `session_id` при работе в контексте чата.

**Проверить вызов агента в `project_chat.py:299`:**
```python
exec_result = await workspace.handle_message(
    message_content=message_request.content,
    target_agent_id=target_agent_id,
    session_history=session_history,
    task_id=str(session_id),
    session_id=session_id,  # ← Уже передается!
)
```

Значит, агент должен получать `session_id` и передавать его в `execute_tool()`.

### 3. Фоновые операции: Использовать broadcast_to_user

Если инструмент вызывается вне контекста чата (например, фоновая задача):
- `session_id` будет `None` - это нормально
- Fallback автоматически отправит событие всем активным сессиям пользователя
- Логирование покажет: `session_id=all_user_sessions`

## Пошаговое внедрение

### Шаг 1: Обновить ToolExecutionRequest (опционально)

Сделать явно, что `session_id` требуется для streaming:

```python
# app/schemas/tool.py
class ToolExecutionRequest(BaseModel):
    tool_name: str = Field(..., description="Name of tool to execute")
    tool_params: dict = Field(..., description="Tool parameters")
    session_id: Optional[UUID] = Field(
        None,
        description="Chat session ID (required for event streaming to work properly)"
    )
    chat_session_id: Optional[UUID] = Field(
        None,
        description="Alternative field for session_id (backward compatibility)"
    )
```

### Шаг 2: Добавить валидацию в REST API (рекомендуется)

```python
# app/routes/project_tools.py:88
session_id = request.session_id or request.chat_session_id

logger.info(
    "tool_execution_request_received",
    project_id=str(project_id),
    tool_name=request.tool_name,
    session_id=str(session_id) if session_id else "MISSING",
    user_id=str(user_id),
)

if not session_id:
    logger.warning(
        "tool_execution_without_session_id",
        project_id=str(project_id),
        tool_name=request.tool_name,
    )
    # Option 1: Требовать session_id
    # raise HTTPException(
    #     status_code=status.HTTP_400_BAD_REQUEST,
    #     detail="session_id is required for proper event streaming"
    # )
    # Option 2: Разрешить, но логировать (текущий fallback будет использован)
```

### Шаг 3: Проверить агент передает session_id

В `app/agents/contextual_agent.py`, агент вызывается с `session_id`:
```python
async def _execute_tools(
    self,
    tool_calls: Any,
    session_id: UUID | None = None,  # ← Принимает session_id
) -> dict[str, Any]:
    for tool_call in tool_calls:
        response = await self.tool_executor.execute_tool(
            tool_name=tool_name,
            tool_params=tool_params,
            session_id=session_id,  # ← Передает session_id
        )
```

Проверить, что `session_id` правильно передается от `run_async()` → `_execute_tools()`.

## Мониторинг и диагностика

### Что смотреть в логах

**Хорошо (session_id не None):**
```
tool_execution_signal_sent 
  tool_id=5bda5763-7d25-42ce-ac8d-355d0e2ec523 
  tool_name=read_file 
  session_id=765ebfa9-0a58-4ef3-8de8-82210c52f699
  sent_to_connections=1
```

**Fallback (session_id=None, но работает):**
```
tool_execution_signal_sent 
  tool_id=5bda5763-7d25-42ce-ac8d-355d0e2ec523 
  tool_name=read_file 
  session_id=all_user_sessions
  sent_to_connections=1
```

**Плохо (никому не доставлено):**
```
Event broadcasted: session=None, type=StreamEventType.TOOL_EXECUTION_SIGNAL, sent_to=0/0
```

### Проверить в коде

```python
# app/core/approval_manager.py - поиск вызовов с session_id
grep -n "send_tool_execution_signal\|send_tool_result_ack\|_send_tool_approval_notification" app/core/tools/executor.py

# Убедиться, что session_id передается
# Если видим None в логах - значит проблема выше в call stack
```

## Итоговая рекомендация

1. **Оставить fallback механизм** (уже реализован) - это страховка
2. **Обновить документацию** - указать что session_id требуется для streaming
3. **Добавить логирование** - чтобы видеть когда session_id=None
4. **Во время отладки** - проверять, передается ли session_id от эндпоинта или агента до ToolExecutor

## Текущие улучшения (уже сделаны)

✅ Добавлен fallback в `send_tool_execution_signal()` - использует `broadcast_to_user()` когда session_id=None
✅ Добавлен fallback в `_send_tool_approval_notification()` 
✅ Добавлен fallback в `send_tool_result_ack()`
✅ Улучшено логирование - показывает `session_id=all_user_sessions` вместо None

## Что осталось сделать (опционально)

- [ ] Требовать session_id в REST API (может быть breaking change)
- [ ] Документировать в API spec что session_id требуется
- [ ] Добавить пример клиентского кода с session_id
- [ ] Мониторить логи в продакшене чтобы видеть частоту fallback'ов
