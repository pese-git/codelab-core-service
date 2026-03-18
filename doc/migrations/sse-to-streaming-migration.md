# Миграция с SSE на Streaming Fetch API

## Обзор изменений

Система была переведена с Server-Sent Events (SSE) на Streaming Fetch API для улучшения контроля, безопасности и гибкости.

## Основные изменения

### 1. Формат данных
- **Было**: SSE формат (`data: {...}\n\n`)
- **Стало**: JSON Lines (NDJSON) формат (`{...}\n`)

### 2. Авторизация
- **Было**: JWT токен через query parameters (небезопасно)
- **Стало**: JWT токен через Authorization header

### 3. Heartbeat
- **Было**: SSE комментарий (`: heartbeat\n\n`)
- **Стало**: JSON событие `{"event_type": "heartbeat", "payload": {...}}`

### 4. Content-Type
- **Было**: `text/event-stream`
- **Стало**: `application/x-ndjson`

## Изменения в коде

### Backend

#### Переименованные файлы
- `app/core/sse_manager.py` → `app/core/stream_manager.py`
- `app/routes/sse.py` → `app/routes/streaming.py`
- `doc/sse-event-streaming.md` → `doc/streaming-fetch-api.md`

#### Переименованные классы
- `SSEManager` → `StreamManager`
- `SSEConnection` → `StreamConnection`
- `SSEEvent` → `StreamEvent`
- `SSEEventType` → `StreamEventType`

#### Обратная совместимость
Для плавной миграции добавлены алиасы:
```python
# В app/schemas/event.py
SSEEvent = StreamEvent
SSEEventType = StreamEventType

# В app/core/stream_manager.py
SSEManager = StreamManager
get_sse_manager = get_stream_manager
```

### Frontend (пример клиента)

#### Было (EventSource):
```javascript
const eventSource = new EventSource('/my/chat/session-id/events/?token=jwt');

eventSource.addEventListener('task_started', (e) => {
  const data = JSON.parse(e.data);
  console.log('Task started:', data);
});
```

#### Стало (Fetch API):
```javascript
const response = await fetch('/my/chat/session-id/events/', {
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
    if (event.event_type === 'task_started') {
      console.log('Task started:', event);
    }
  }
}
```

## Преимущества новой реализации

### ✅ Безопасность
- JWT токен в headers, а не в URL
- Токены не попадают в логи и browser history

### ✅ Контроль
- Полный контроль над retry логикой
- Возможность отменить запрос через AbortController
- Доступ к HTTP status codes и headers

### ✅ Гибкость
- Любой формат данных (не только SSE)
- Легче тестировать
- Лучше интеграция с современными инструментами

### ✅ Современность
- Promise-based API (async/await)
- Интеграция с React hooks, RxJS и т.д.
- Лучше поддержка в DevTools

## Что осталось без изменений

- Архитектура (queue-based broadcasting)
- Логика буферизации событий в Redis
- Heartbeat механизм (только формат изменился)
- Connection lifecycle management
- Все типы событий
- API endpoint path: `/my/chat/{session_id}/events/`

## Тестирование

Все тесты обновлены для новой реализации:
- `tests/test_sse.py` - обновлен для StreamManager
- Backward compatibility алиасы позволяют старому коду работать

## Дальнейшие шаги

1. Обновить frontend клиенты для использования Fetch API
2. Удалить backward compatibility алиасы после полной миграции
3. Переименовать `tests/test_sse.py` → `tests/test_streaming.py`
4. Обновить мониторинг и метрики

## Rollback план

Если потребуется откатиться:
1. Старые файлы сохранены: `app/core/sse_manager.py`, `app/routes/sse.py`
2. Backward compatibility алиасы позволяют использовать старые имена
3. Изменить импорты в `app/main.py` обратно на SSE версию
