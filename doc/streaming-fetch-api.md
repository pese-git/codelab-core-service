# Streaming Fetch API

## Обзор

Streaming Fetch API Event Streaming обеспечивает real-time коммуникацию между сервером и клиентами для получения обновлений о состоянии агентов, выполнении задач и других событиях системы.

## Архитектура

### Компоненты

1. **StreamManager** (`app/core/stream_manager.py`)
   - Управление streaming connections
   - Broadcasting событий
   - Event buffering в Redis
   - Heartbeat механизм

2. **SSE Endpoint** (`app/routes/streaming.py`)
   - `GET /my/chat/{session_id}/events/` - подключение к event stream
   - `GET /my/chat/stats/` - статистика streaming connections

3. **Event Schemas** (`app/schemas/event.py`)
   - `StreamEvent` - базовая схема события
   - `StreamEventType` - типы событий

## Типы событий

### 1. direct_agent_call
Прямой вызов агента (direct mode).

**Payload:**
```json
{
  "agent_id": "user123_coder",
  "task_id": "task_abc123",
  "timestamp": "2026-02-12T14:00:00Z"
}
```

### 2. agent_status_changed
Изменение статуса агента.

**Payload:**
```json
{
  "agent_id": "user123_coder",
  "old_status": "ready",
  "new_status": "busy",
  "timestamp": "2026-02-12T14:00:00Z"
}
```

### 3. task_plan_created
Создан план задач оркестратором.

**Payload:**
```json
{
  "plan_id": "plan_xyz789",
  "tasks": [
    {"task_id": "task_1", "agent_id": "coder", "description": "Fix bug"},
    {"task_id": "task_2", "agent_id": "tester", "description": "Test fix"}
  ],
  "estimated_cost": 0.05,
  "estimated_duration": 120
}
```

### 4. task_started
Задача начала выполняться.

**Payload:**
```json
{
  "task_id": "task_abc123",
  "agent_id": "user123_coder",
  "timestamp": "2026-02-12T14:00:00Z"
}
```

### 5. task_progress
Промежуточный прогресс выполнения задачи.

**Payload:**
```json
{
  "task_id": "task_abc123",
  "progress_percent": 50,
  "message": "Analyzing code..."
}
```

### 6. task_completed
Задача завершена.

**Payload:**
```json
{
  "task_id": "task_abc123",
  "result": "Bug fixed successfully",
  "duration": 45.2,
  "timestamp": "2026-02-12T14:00:45Z"
}
```

### 7. tool_request
Запрос на подтверждение использования tool.

**Payload:**
```json
{
  "approval_id": "approval_123",
  "tool_name": "file_write",
  "parameters": {
    "path": "/app/config.py",
    "content": "..."
  },
  "agent_id": "user123_coder"
}
```

### 8. plan_request
Запрос на подтверждение плана выполнения.

**Payload:**
```json
{
  "approval_id": "approval_456",
  "plan": {...},
  "estimated_cost": 0.15,
  "estimated_duration": 300
}
```

### 9. context_retrieved
Получен RAG контекст из Qdrant.

**Payload:**
```json
{
  "agent_id": "user123_coder",
  "context_items_count": 5,
  "relevance_scores": [0.95, 0.87, 0.82, 0.78, 0.71]
}
```

### 10. approval_required
Требуется подтверждение пользователя.

**Payload:**
```json
{
  "approval_id": "approval_789",
  "type": "tool_approval",
  "details": {...},
  "timeout": 300
}
```

## Использование

### Подключение к event stream

```python
import httpx

async with httpx.AsyncClient() as client:
    headers = {"Authorization": f"Bearer {jwt_token}"}
    
    async with client.stream(
        "GET",
        f"http://localhost:8000/my/chat/{session_id}/events/",
        headers=headers,
    ) as response:
        async for line in response.aiter_lines():
            if line.startswith("data: "):
                data = json.loads(line[6:])
                print(f"Event: {data['event_type']}")
                print(f"Payload: {data['payload']}")
```

### JavaScript/Browser

```javascript
const eventSource = new EventSource(
  `/my/chat/${sessionId}/events/`,
  {
    headers: {
      'Authorization': `Bearer ${jwtToken}`
    }
  }
);

// Слушать все события
eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Event:', data.event_type);
  console.log('Payload:', data.payload);
};

// Слушать конкретный тип события
eventSource.addEventListener('task_completed', (event) => {
  const data = JSON.parse(event.data);
  console.log('Task completed:', data.payload);
});

// Обработка ошибок
eventSource.onerror = (error) => {
  console.error('SSE error:', error);
  // EventSource автоматически переподключится
};

// Закрыть соединение
eventSource.close();
```

## Особенности реализации

### 1. Множественные connections

Система поддерживает множественные streaming connections для одной сессии (например, несколько вкладок браузера).

```python
# Все connections получат событие
await stream_manager.broadcast_event(session_id, event)
```

### 2. Event Buffering

События буферизуются в Redis для обработки временных отключений:

- **Размер буфера:** 100 событий (FIFO)
- **TTL:** 5 минут
- **Восстановление:** При reconnect клиент получает пропущенные события

```python
# События автоматически буферизуются
await stream_manager.broadcast_event(session_id, event, buffer=True)
```

### 3. Heartbeat

Heartbeat отправляется каждые 30 секунд для поддержания connection:

```
: heartbeat

```

### 4. Connection Timeout

Неактивные connections закрываются через 5 минут.

### 5. Event Size Limit

Максимальный размер события: **10KB**

Если payload превышает лимит, он заменяется на:
```json
{
  "error": "Payload too large, fetch via API"
}
```

## Broadcasting Events

### Broadcast к сессии

```python
from app.core.stream_manager import get_stream_manager
from app.schemas.event import StreamEvent, StreamEventType

# Получить SSE manager
stream_manager = await get_stream_manager(redis)

# Создать событие
event = StreamEvent(
    event_type=StreamEventType.TASK_STARTED,
    payload={
        "task_id": "task_123",
        "agent_id": "user123_coder"
    },
    session_id=session_id,
)

# Broadcast к всем connections сессии
sent_count = await stream_manager.broadcast_event(session_id, event)
```

### Broadcast к пользователю

```python
# Broadcast ко всем сессиям пользователя
sent_count = await stream_manager.broadcast_to_user(user_id, event)
```

## Мониторинг

### Получение статистики

```bash
curl -H "Authorization: Bearer $JWT_TOKEN" \
  http://localhost:8000/my/chat/stats/
```

**Response:**
```json
{
  "status": "ok",
  "stats": {
    "total_connections": 15,
    "total_sessions": 8,
    "total_users": 5,
    "connections_per_session": {
      "session_1": 2,
      "session_2": 1,
      "session_3": 3
    }
  }
}
```

### Метрики

SSE Manager собирает следующие метрики:

- `total_connections` - Общее количество активных connections
- `total_sessions` - Количество активных сессий
- `total_users` - Количество активных пользователей
- `connections_per_session` - Breakdown по сессиям

## Performance

### SLA

- **Event delivery latency:** P99 < 100ms
- **Throughput:** 1000+ events/sec per connection
- **Concurrent connections:** 1000+ per user
- **Memory per connection:** < 1MB

### Оптимизация

1. **Redis Pub/Sub** для event distribution
2. **Async/await** для non-blocking I/O
3. **Connection pooling** для Redis
4. **Event buffering** для batch processing

## Безопасность

### User Isolation

- JWT authentication обязателен
- Middleware автоматически фильтрует события по user_id
- Пользователь получает только события своих сессий

### Rate Limiting

- Применяется общий rate limit для `/my/*` endpoints
- 100 requests/min per user

## Troubleshooting

### Connection не устанавливается

**Проблема:** 401 Unauthorized

**Решение:**
- Проверьте JWT token
- Убедитесь что token содержит `sub` claim с user_id

### События не приходят

**Проблема:** Connection установлено, но события не приходят

**Решение:**
1. Проверьте что session_id принадлежит пользователю
2. Проверьте логи SSE Manager
3. Убедитесь что события broadcast'ятся к правильной сессии

### Connection часто разрывается

**Проблема:** EventSource постоянно переподключается

**Решение:**
1. Проверьте network stability
2. Увеличьте timeout на reverse proxy (nginx)
3. Проверьте heartbeat в логах

### Пропущенные события

**Проблема:** После reconnect не все события восстановлены

**Решение:**
1. Проверьте размер буфера (max 100 событий)
2. Проверьте TTL буфера (5 минут)
3. Если disconnect > 5 минут, события потеряны

## Примеры интеграции

### React Hook

```typescript
import { useEffect, useState } from 'react';

interface StreamEvent {
  event_type: string;
  payload: any;
  timestamp: string;
  session_id: string;
}

export function useSSE(sessionId: string, token: string) {
  const [events, setEvents] = useState<StreamEvent[]>([]);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    const eventSource = new EventSource(
      `/my/chat/${sessionId}/events/`,
      {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      }
    );

    eventSource.onopen = () => {
      setConnected(true);
    };

    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setEvents(prev => [...prev, data]);
    };

    eventSource.onerror = () => {
      setConnected(false);
    };

    return () => {
      eventSource.close();
    };
  }, [sessionId, token]);

  return { events, connected };
}
```

### Python Client

```python
import asyncio
import json
import httpx

async def listen_to_events(session_id: str, token: str):
    """Listen to SSE events."""
    headers = {"Authorization": f"Bearer {token}"}
    
    async with httpx.AsyncClient() as client:
        async with client.stream(
            "GET",
            f"http://localhost:8000/my/chat/{session_id}/events/",
            headers=headers,
            timeout=None,  # No timeout for streaming
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("event: "):
                    event_type = line[7:]
                elif line.startswith("data: "):
                    data = json.loads(line[6:])
                    print(f"Received {event_type}: {data}")

# Usage
asyncio.run(listen_to_events("session_123", "your_jwt_token"))
```

## Дальнейшее развитие

### Планируемые улучшения

1. **Event filtering** - Клиент может подписаться только на определенные типы событий
2. **Event replay** - Возможность запросить события за определенный период
3. **Compression** - Сжатие событий для экономии bandwidth
4. **WebSocket fallback** - Для старых браузеров
5. **Metrics dashboard** - Grafana dashboard для мониторинга SSE

### Известные ограничения

1. **Browser limit** - Браузеры ограничивают количество одновременных streaming connections (обычно 6 per domain)
2. **No bidirectional** - SSE только server→client, для client→server используйте REST API
3. **Text only** - SSE передает только текст, бинарные данные нужно кодировать (base64)

## См. также

- [REST API Documentation](rest-api.md)
- [Agent Context Store](agent-context.md)
- [Approval Manager](approval-manager.md)
