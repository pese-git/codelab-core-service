# Исправление: Отсутствие сообщений ассистента в клиенте

## Проблема

Клиент получал события `task_started`, `task_completed` и другие служебные события через streaming API, но не получал само содержимое сообщений от ассистента. В результате:

- В базе данных сообщения сохранялись корректно
- События о начале и завершении задач отправлялись
- Но само сообщение с ответом ассистента не передавалось клиенту через streaming

Пример проблемы:
```
You
18:12:30
привет

Assistant
18:12:48
Processing...

Assistant
18:12:48
Task completed
```

Сообщение "Привет! Чем могу помочь? 😊" было в базе данных, но не отображалось в UI.

## Причина

В [`app/routes/chat.py`](app/routes/chat.py:152) после сохранения сообщения в базу данных отправлялись только служебные события (`TASK_STARTED`, `TASK_COMPLETED`), но не отправлялось событие с самим сообщением.

## Решение

### 1. Добавлен новый тип события `MESSAGE_CREATED`

В [`app/schemas/event.py`](app/schemas/event.py:11):

```python
class StreamEventType(str, Enum):
    """Stream event type enum."""

    MESSAGE_CREATED = "message_created"  # ← Новый тип события
    DIRECT_AGENT_CALL = "direct_agent_call"
    AGENT_STATUS_CHANGED = "agent_status_changed"
    # ... остальные типы
```

### 2. Отправка события при создании сообщения пользователя

В [`app/routes/chat.py`](app/routes/chat.py:190):

```python
# Save user message
user_message = Message(
    session_id=session_id,
    role=MessageRole.USER.value,
    content=message_request.content,
)
db.add(user_message)
await db.flush()

# Send SSE event: user message created
await stream_manager.broadcast_event(
    session_id=session_id,
    event=StreamEvent(
        event_type=StreamEventType.MESSAGE_CREATED,
        payload={
            "message_id": str(user_message.id),
            "role": MessageRole.USER.value,
            "content": user_message.content,
            "timestamp": user_message.created_at.isoformat(),
        },
        session_id=session_id,
    ),
)
```

### 3. Отправка события при создании сообщения ассистента

В [`app/routes/chat.py`](app/routes/chat.py:344):

```python
# Save assistant message
assistant_message = Message(
    session_id=session_id,
    role=MessageRole.ASSISTANT.value,
    content=result["response"],
    agent_id=agent_response.id,
)
db.add(assistant_message)
await db.flush()

# Send SSE event: message created
await stream_manager.broadcast_event(
    session_id=session_id,
    event=StreamEvent(
        event_type=StreamEventType.MESSAGE_CREATED,
        payload={
            "message_id": str(assistant_message.id),
            "role": MessageRole.ASSISTANT.value,
            "content": assistant_message.content,
            "agent_id": str(agent_response.id),
            "agent_name": agent_response.name,
            "timestamp": assistant_message.created_at.isoformat(),
        },
        session_id=session_id,
    ),
)
```

### 4. Обновлена документация

В [`app/routes/streaming.py`](app/routes/streaming.py:95) добавлено описание нового типа события:

```python
**Event Types:**
- `message_created` - New message created (user or assistant)
- `direct_agent_call` - Direct agent invocation
# ... остальные типы
```

## Структура события MESSAGE_CREATED

### Для сообщения пользователя:
```json
{
  "event_type": "message_created",
  "payload": {
    "message_id": "uuid",
    "role": "user",
    "content": "текст сообщения",
    "timestamp": "2026-02-16T19:12:30.123Z"
  },
  "timestamp": "2026-02-16T19:12:30.123Z",
  "session_id": "uuid"
}
```

### Для сообщения ассистента:
```json
{
  "event_type": "message_created",
  "payload": {
    "message_id": "uuid",
    "role": "assistant",
    "content": "текст ответа",
    "agent_id": "uuid",
    "agent_name": "имя агента",
    "timestamp": "2026-02-16T19:12:31.456Z"
  },
  "timestamp": "2026-02-16T19:12:31.456Z",
  "session_id": "uuid"
}
```

## Как работает исправление

1. **Клиент подключается** к streaming endpoint `/my/chat/{session_id}/events/`
2. **Пользователь отправляет сообщение** через POST `/my/chat/{session_id}/message/`
3. **Сервер сохраняет** сообщение пользователя в БД
4. **Сервер отправляет** событие `MESSAGE_CREATED` с сообщением пользователя
5. **Агент обрабатывает** сообщение
6. **Сервер сохраняет** ответ ассистента в БД
7. **Сервер отправляет** событие `MESSAGE_CREATED` с ответом ассистента
8. **Клиент получает** оба события и отображает сообщения в UI

## Тестирование

Создан тестовый скрипт [`scripts/test_message_events.py`](scripts/test_message_events.py) для проверки:

```bash
# Запустить сервер
make dev

# В другом терминале запустить тест
python scripts/test_message_events.py
```

Тест проверяет:
- ✅ Создание сессии
- ✅ Подключение к streaming
- ✅ Отправку сообщения
- ✅ Получение события MESSAGE_CREATED для сообщения пользователя
- ✅ Получение события MESSAGE_CREATED для ответа ассистента
- ✅ Наличие всех необходимых полей в событиях

## Изменённые файлы

1. [`app/schemas/event.py`](app/schemas/event.py) - добавлен тип события `MESSAGE_CREATED`
2. [`app/routes/chat.py`](app/routes/chat.py) - добавлена отправка событий при создании сообщений
3. [`app/routes/streaming.py`](app/routes/streaming.py) - обновлена документация
4. [`scripts/test_message_events.py`](scripts/test_message_events.py) - создан тестовый скрипт
5. [`doc/bugfix-message-events.md`](doc/bugfix-message-events.md) - эта документация

## Обратная совместимость

Изменения полностью обратно совместимы:
- Добавлен новый тип события, существующие события не изменены
- Клиенты, не обрабатывающие `MESSAGE_CREATED`, продолжат работать
- API endpoints не изменены
- Структура базы данных не изменена

## Рекомендации для клиента

Клиент должен обрабатывать событие `message_created`:

```javascript
// Пример обработки в JavaScript
const response = await fetch(`/my/chat/${sessionId}/events/`, {
  headers: { 'Authorization': `Bearer ${token}` }
});

const reader = response.body.getReader();
const decoder = new TextDecoder();

while (true) {
  const {done, value} = await reader.read();
  if (done) break;
  
  const chunk = decoder.decode(value);
  const lines = chunk.split('\n').filter(line => line.trim());
  
  for (const line of lines) {
    const event = JSON.parse(line);
    
    if (event.event_type === 'message_created') {
      // Добавить сообщение в UI
      addMessageToChat({
        id: event.payload.message_id,
        role: event.payload.role,
        content: event.payload.content,
        agentName: event.payload.agent_name,
        timestamp: event.payload.timestamp
      });
    }
  }
}
```

## Дата исправления

2026-02-16
