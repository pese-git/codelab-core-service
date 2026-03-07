# Исправление: Tool Execution Signal - Missing session_id

## Проблема

При запуске инструмента из агента без явно переданного `session_id`, событие `TOOL_EXECUTION_SIGNAL` не отправляется клиенту:

```
2026-03-06T15:41:01.199294Z [info] sending_execution_signal_to_client 
  approval_id=None 
  tool_id=5bda5763-7d25-42ce-ac8d-355d0e2ec523 
  tool_name=read_file

Event broadcasted: session=None, type=StreamEventType.TOOL_EXECUTION_SIGNAL, sent_to=0/0
```

`sent_to=0/0` означает, что нет активных соединений для сессии `None`.

## Корень проблемы

### Механизм доставки событий

1. **Domain Events** (например, `message_created`) используют **Outbox Pattern**:
   - События записываются в таблицу `event_outbox` вместе с основными данными
   - Фоновый `OutboxPublisher` обрабатывает события
   - `session_id` извлекается из `payload.session_id` (строка 166 в `outbox_publisher.py`)
   - Используется `broadcast_event(session_id=...)`

2. **Synchronous Signals** (инструменты, одобрения) отправляются напрямую:
   - `send_tool_execution_signal()` вызывает `broadcast_event(session_id=session_id)`
   - Когда `session_id=None`, соединение не найдено в `self.connections[None]`
   - `sent_to=0/0` - событие потеряно

### Когда session_id=None?

1. **Инструмент вызван из агента** (не из REST API):
   - `app/agents/contextual_agent.py:569` - `await self.tool_executor.execute_tool(..., session_id=session_id)`
   - Если агент работает вне контекста чата, `session_id` может быть `None`

2. **Инструмент вызван без чат-сессии**:
   - Прямой REST API вызов без `session_id` в `ToolExecutionRequest`

## Решение

Добавлен **fallback механизм** в три метода `ApprovalManager`:

### 1. `send_tool_execution_signal()`
```python
if session_id:
    sent_count = await self.stream_manager.broadcast_event(
        session_id=session_id,
        event=event,
    )
else:
    # Fallback: broadcast to all user sessions
    sent_count = await self.stream_manager.broadcast_to_user(
        user_id=self.user_id,
        event=event,
    )
```

### 2. `_send_tool_approval_notification()`
Аналогичный fallback

### 3. `send_tool_result_ack()`
Аналогичный fallback

## Изменённые файлы

- `app/core/approval_manager.py`:
  - Метод `send_tool_execution_signal()` (строка ~1106)
  - Метод `_send_tool_approval_notification()` (строка ~1049)
  - Метод `send_tool_result_ack()` (строка ~1174)

## Логирование

Все методы теперь логируют:
```python
self.logger.info(
    "tool_execution_signal_sent",
    tool_id=tool_id,
    tool_name=tool_name,
    session_id=str(session_id) if session_id else "all_user_sessions",
    sent_to_connections=sent_count,
)
```

Это позволяет отличить:
- `session_id=<uuid>` - доставлено в конкретную сессию
- `session_id=all_user_sessions` - доставлено всем сессиям пользователя

## Проверка

После деплоя проверить логи:
```
tool_execution_signal_sent session_id=all_user_sessions sent_to_connections=1/1
```

Вместо:
```
Event broadcasted: session=None, type=StreamEventType.TOOL_EXECUTION_SIGNAL, sent_to=0/0
```

## Примечание о session_id

Рекомендация: всегда передавать `session_id` при вызове инструментов из контекста чата:
```python
# Правильно
await self.tool_executor.execute_tool(
    tool_name="read_file",
    tool_params={"path": "src/main.py"},
    session_id=session_id  # Явно передаём session_id
)
```

Если `session_id` недоступен, fallback автоматически отправит событие всем активным сессиям пользователя.
