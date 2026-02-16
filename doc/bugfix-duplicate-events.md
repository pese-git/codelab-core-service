# Исправление дублирования событий при переподключении

## Проблема

При переподключении клиента к потоку событий (например, при обновлении страницы или потере соединения) клиент получал дублированные сообщения:

```
You
23:00:14
привет
You
20:00:14
привет          <- Дубликат
Assistant
20:00:14
Orchestrated mode not yet implemented...
```

### Причина

При каждом новом подключении к эндпоинту `/my/chat/{session_id}/events/` метод [`_send_buffered_events()`](../app/core/stream_manager.py:271) отправлял **все** буферизованные события из Redis, включая те, которые клиент уже получил в предыдущем соединении.

Последовательность событий:
1. Клиент подключается к стриму
2. Получает события в реальном времени
3. Соединение разрывается (обновление страницы, потеря сети)
4. Клиент переподключается
5. **Получает все буферизованные события снова** (включая уже полученные)
6. Получает новые события

## Решение

Добавлен параметр `since` в эндпоинт `/my/chat/{session_id}/events/`, который позволяет клиенту указать временную метку последнего полученного события. Сервер отправляет только события с временной меткой **после** указанной.

### Изменения в коде

#### 1. [`app/core/stream_manager.py`](../app/core/stream_manager.py)

**Метод `register_connection`:**
```python
async def register_connection(
    self, session_id: UUID, user_id: UUID, since: datetime | None = None
) -> asyncio.Queue:
    """Register new streaming connection."""
    # ...
    # Send buffered events if any (filtered by timestamp if provided)
    await self._send_buffered_events(session_id, connection, since)
    return queue
```

**Метод `_send_buffered_events`:**
```python
async def _send_buffered_events(
    self, session_id: UUID, connection: StreamConnection, since: datetime | None = None
) -> None:
    """Send buffered events to a newly connected client."""
    # Get all buffered events
    buffered = await self.redis.lrange(buffer_key, 0, -1)
    
    if buffered:
        events_to_send = []
        
        # Filter events by timestamp if 'since' is provided
        for event_json in reversed(buffered):
            event_data = json.loads(event_json)
            event = StreamEvent(**event_data)
            
            # Only send events after 'since' timestamp
            if since is None or event.timestamp > since:
                events_to_send.append(event)
        
        # Send filtered events
        for event in events_to_send:
            await connection.send_event(event)
```

#### 2. [`app/routes/streaming.py`](../app/routes/streaming.py)

**Добавлен параметр запроса `since`:**
```python
async def subscribe_to_events(
    session_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    since: datetime | None = Query(
        default=None,
        description="ISO 8601 timestamp - only return buffered events after this time"
    ),
) -> StreamingResponse:
    # ...
    # Register connection with optional 'since' filter
    queue = await stream_manager.register_connection(session_id, user_id, since)
```

## Использование на клиенте

### JavaScript пример

```javascript
let lastEventTimestamp = null;

async function connectToStream(sessionId) {
  // Build URL with 'since' parameter if we have a last timestamp
  const url = lastEventTimestamp 
    ? `/my/chat/${sessionId}/events/?since=${lastEventTimestamp}`
    : `/my/chat/${sessionId}/events/`;
    
  const response = await fetch(url, {
    headers: {
      'Authorization': 'Bearer ' + token
    },
    signal: abortController.signal
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
      
      // Save timestamp for reconnect
      lastEventTimestamp = event.timestamp;
      
      // Process event
      handleEvent(event);
    }
  }
}

// On reconnect (e.g., after connection loss)
async function reconnect(sessionId) {
  console.log('Reconnecting with since:', lastEventTimestamp);
  await connectToStream(sessionId);
}
```

### Поведение

**Первое подключение (без `since`):**
```
GET /my/chat/{session_id}/events/
```
- Получает все буферизованные события (до 100 последних)
- Получает новые события в реальном времени

**Переподключение (с `since`):**
```
GET /my/chat/{session_id}/events/?since=2026-02-16T20:00:14.123Z
```
- Получает только события с `timestamp > 2026-02-16T20:00:14.123Z`
- Пропускает уже полученные события
- Получает новые события в реальном времени

## Тестирование

Создан тестовый скрипт [`scripts/test_duplicate_prevention.py`](../scripts/test_duplicate_prevention.py):

```bash
# Запуск теста
python scripts/test_duplicate_prevention.py
```

Тест проверяет:
1. ✅ Создание сессии
2. ✅ Первое подключение к стриму
3. ✅ Отправку сообщений и получение событий
4. ✅ Переподключение с параметром `since`
5. ✅ Отсутствие дублированных событий
6. ✅ Получение только новых событий после переподключения

## Преимущества

1. **Устранение дубликатов** - клиент не получает повторно уже обработанные события
2. **Экономия трафика** - не передаются избыточные данные
3. **Улучшенный UX** - пользователь не видит дублированные сообщения
4. **Обратная совместимость** - параметр `since` опциональный, старые клиенты продолжают работать
5. **Простота использования** - клиенту нужно только сохранять timestamp последнего события

## Ограничения

1. **Буфер в Redis** - события хранятся только 5 минут (300 секунд)
2. **Размер буфера** - хранится максимум 100 последних событий
3. **Точность фильтрации** - использует `>` (строго больше), поэтому событие с точно таким же timestamp будет пропущено

## Связанные файлы

- [`app/core/stream_manager.py`](../app/core/stream_manager.py) - менеджер потоковых соединений
- [`app/routes/streaming.py`](../app/routes/streaming.py) - эндпоинты для стриминга
- [`app/schemas/event.py`](../app/schemas/event.py) - схемы событий
- [`scripts/test_duplicate_prevention.py`](../scripts/test_duplicate_prevention.py) - тест
