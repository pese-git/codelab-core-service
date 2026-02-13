# API Спецификация

## Содержание
- [Общие сведения](#общие-сведения)
- [Аутентификация](#аутентификация)
- [Endpoints](#endpoints)
  - [Health](#health-endpoints)
  - [Agents](#agents-endpoints)
  - [Chat](#chat-endpoints)
  - [Streaming](#streaming-endpoints)
- [Схемы данных](#схемы-данных)
- [Коды ошибок](#коды-ошибок)

---

## Общие сведения

### Base URL
```
Production: https://api.codelab.example.com
Development: http://localhost:8000
```

### Content-Type
Все запросы и ответы используют `application/json`, кроме Streaming endpoints (`application/x-ndjson`).

### Версионирование
API версионируется через URL path (в будущем):
```
/v1/my/agents/
/v2/my/agents/
```

Текущая версия: **v1** (неявная, без префикса)

---

## Аутентификация

### JWT Bearer Token

Все защищенные endpoints (с префиксом `/my/`) требуют JWT токен в заголовке:

```http
Authorization: Bearer <jwt_token>
```

### Структура JWT токена

```json
{
  "sub": "550e8400-e29b-41d4-a716-446655440000",
  "exp": 1708000000,
  "iat": 1707998200
}
```

**Claims**:
- `sub` (subject) - UUID пользователя
- `exp` (expiration) - время истечения (Unix timestamp)
- `iat` (issued at) - время выдачи (Unix timestamp)

### Генерация тестового токена

```bash
python scripts/generate_test_jwt.py <user_id>
```

### Ошибки аутентификации

| Код | Описание |
|-----|----------|
| 401 | Missing or invalid Authorization header |
| 401 | Invalid or expired token |
| 401 | Invalid user ID format |

---

## Endpoints

### Health Endpoints

#### GET /health

Проверка состояния сервиса.

**Аутентификация**: Не требуется

**Response**:
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "timestamp": "2026-02-13T10:00:00Z",
  "services": {
    "database": "healthy",
    "redis": "healthy",
    "qdrant": "healthy"
  }
}
```

**Status Codes**:
- `200` - Сервис работает
- `503` - Сервис недоступен

---

### Agents Endpoints

#### POST /my/agents/

Создать нового персонального агента.

**Аутентификация**: Требуется

**Request Body**:
```json
{
  "name": "coder",
  "system_prompt": "You are an expert Python developer...",
  "model": "gpt-4-turbo-preview",
  "tools": ["code_executor", "file_reader"],
  "concurrency_limit": 3
}
```

**Response** (201 Created):
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "coder",
  "status": "ready",
  "created_at": "2026-02-13T10:00:00Z",
  "config": {
    "name": "coder",
    "system_prompt": "You are an expert Python developer...",
    "model": "gpt-4-turbo-preview",
    "tools": ["code_executor", "file_reader"],
    "concurrency_limit": 3
  }
}
```

**Validation**:
- `name`: 1-50 символов, alphanumeric + underscore
- `system_prompt`: 1-10000 символов
- `model`: валидное имя модели
- `tools`: список строк
- `concurrency_limit`: 1-10

---

#### GET /my/agents/

Получить список всех агентов пользователя.

**Аутентификация**: Требуется

**Response** (200 OK):
```json
{
  "agents": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "coder",
      "status": "ready",
      "created_at": "2026-02-13T10:00:00Z",
      "config": { ... }
    },
    {
      "id": "660e8400-e29b-41d4-a716-446655440001",
      "name": "researcher",
      "status": "busy",
      "created_at": "2026-02-13T11:00:00Z",
      "config": { ... }
    }
  ],
  "total": 2
}
```

---

#### GET /my/agents/{agent_id}

Получить информацию о конкретном агенте.

**Аутентификация**: Требуется

**Path Parameters**:
- `agent_id` (UUID) - ID агента

**Response** (200 OK):
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "coder",
  "status": "ready",
  "created_at": "2026-02-13T10:00:00Z",
  "config": { ... }
}
```

**Status Codes**:
- `200` - Успешно
- `404` - Агент не найден

---

#### PUT /my/agents/{agent_id}

Обновить конфигурацию агента.

**Аутентификация**: Требуется

**Path Parameters**:
- `agent_id` (UUID) - ID агента

**Request Body**:
```json
{
  "name": "coder_v2",
  "system_prompt": "Updated prompt...",
  "model": "gpt-4-turbo-preview",
  "tools": ["code_executor"],
  "concurrency_limit": 5
}
```

**Response** (200 OK):
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "coder_v2",
  "status": "ready",
  "created_at": "2026-02-13T10:00:00Z",
  "config": { ... }
}
```

**Status Codes**:
- `200` - Успешно обновлено
- `404` - Агент не найден
- `422` - Ошибка валидации

---

#### DELETE /my/agents/{agent_id}

Удалить агента.

**Аутентификация**: Требуется

**Path Parameters**:
- `agent_id` (UUID) - ID агента

**Response** (204 No Content)

**Status Codes**:
- `204` - Успешно удалено
- `404` - Агент не найден

---

### Chat Endpoints

#### POST /my/chat/sessions/

Создать новую чат-сессию.

**Аутентификация**: Требуется

**Response** (201 Created):
```json
{
  "id": "770e8400-e29b-41d4-a716-446655440000",
  "created_at": "2026-02-13T10:00:00Z",
  "message_count": 0
}
```

---

#### GET /my/chat/sessions/

Получить список всех чат-сессий.

**Аутентификация**: Требуется

**Response** (200 OK):
```json
{
  "sessions": [
    {
      "id": "770e8400-e29b-41d4-a716-446655440000",
      "created_at": "2026-02-13T10:00:00Z",
      "message_count": 15
    },
    {
      "id": "880e8400-e29b-41d4-a716-446655440001",
      "created_at": "2026-02-13T11:00:00Z",
      "message_count": 3
    }
  ],
  "total": 2
}
```

---

#### POST /my/chat/{session_id}/message/

Отправить сообщение в чат (прямой или оркестрированный режим).

**Аутентификация**: Требуется

**Path Parameters**:
- `session_id` (UUID) - ID сессии

**Request Body (Прямой режим)**:
```json
{
  "content": "Напиши FastAPI endpoint для создания пользователя",
  "target_agent": "coder"
}
```

**Request Body (Оркестрированный режим)**:
```json
{
  "content": "Исследуй тему и напиши статью о квантовых компьютерах"
}
```

**Response** (200 OK):
```json
{
  "id": "990e8400-e29b-41d4-a716-446655440000",
  "role": "assistant",
  "content": "Вот FastAPI endpoint:\n\n```python\n@app.post('/users/')\nasync def create_user(...):\n    ...\n```",
  "agent_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2026-02-13T10:00:05Z"
}
```

**Status Codes**:
- `200` - Сообщение обработано
- `404` - Сессия или агент не найдены
- `500` - Ошибка выполнения агента

---

#### GET /my/chat/{session_id}/messages/

Получить историю сообщений сессии.

**Аутентификация**: Требуется

**Path Parameters**:
- `session_id` (UUID) - ID сессии

**Query Parameters**:
- `limit` (int, default=50) - Количество сообщений
- `offset` (int, default=0) - Смещение для пагинации

**Response** (200 OK):
```json
{
  "messages": [
    {
      "id": "990e8400-e29b-41d4-a716-446655440000",
      "role": "user",
      "content": "Привет!",
      "agent_id": null,
      "timestamp": "2026-02-13T10:00:00Z"
    },
    {
      "id": "aa0e8400-e29b-41d4-a716-446655440001",
      "role": "assistant",
      "content": "Здравствуйте! Чем могу помочь?",
      "agent_id": "550e8400-e29b-41d4-a716-446655440000",
      "timestamp": "2026-02-13T10:00:02Z"
    }
  ],
  "total": 2,
  "session_id": "770e8400-e29b-41d4-a716-446655440000"
}
```

---

#### DELETE /my/chat/sessions/{session_id}

Удалить чат-сессию.

**Аутентификация**: Требуется

**Path Parameters**:
- `session_id` (UUID) - ID сессии

**Response** (204 No Content)

**Status Codes**:
- `204` - Успешно удалено
- `404` - Сессия не найдена

---

### Streaming Endpoints

#### GET /my/chat/{session_id}/events/

Подключиться к потоку событий для получения real-time обновлений через Streaming Fetch API.

**Аутентификация**: Требуется (JWT в Authorization header)

**Path Parameters**:
- `session_id` (UUID) - ID чат-сессии

**Request Headers**:
```
Authorization: Bearer <jwt_token>
```

**Response Headers**:
```
Content-Type: application/x-ndjson
Cache-Control: no-cache
Connection: keep-alive
X-Accel-Buffering: no
```

**Event Stream (NDJSON format)**:
```json
{"event_type":"direct_agent_call","payload":{"agent_id":"550e8400-...","agent_name":"coder","message":"..."},"session_id":"...","timestamp":"2026-02-13T18:00:00Z"}
{"event_type":"task_started","payload":{"agent_id":"550e8400-...","task_description":"Processing..."},"session_id":"...","timestamp":"2026-02-13T18:00:01Z"}
{"event_type":"context_retrieved","payload":{"agent_id":"550e8400-...","context_count":5},"session_id":"...","timestamp":"2026-02-13T18:00:02Z"}
{"event_type":"task_completed","payload":{"agent_id":"550e8400-...","status":"success","response_preview":"..."},"session_id":"...","timestamp":"2026-02-13T18:00:03Z"}
{"event_type":"heartbeat","payload":{"timestamp":"2026-02-13T18:00:30Z"},"session_id":"...","timestamp":"2026-02-13T18:00:30Z"}
```

**Event Types**:
- `direct_agent_call` - Начало прямого вызова агента
- `agent_status_changed` - Изменение статуса агента
- `task_plan_created` - План задач создан оркестратором
- `task_started` - Задача начата
- `task_progress` - Прогресс выполнения задачи
- `task_completed` - Задача завершена
- `context_retrieved` - Контекст получен из RAG
- `tool_request` - Запрос на использование инструмента
- `plan_request` - Запрос на утверждение плана
- `approval_required` - Требуется утверждение пользователя
- `heartbeat` - Keep-alive heartbeat (каждые 30 секунд)
- `error` - Ошибка выполнения

**Client Example (JavaScript)**:
```javascript
const response = await fetch('/my/chat/{session_id}/events/', {
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
    console.log('Event:', event);
  }
}
```

**Connection Management**:
- Heartbeat отправляется каждые 30 секунд как JSON событие
- Timeout соединения: 5 минут неактивности
- Буферизация последних 100 событий в Redis (TTL 5 минут)
- Поддержка множественных соединений на одну сессию

---

## Схемы данных

### AgentConfig

```typescript
interface AgentConfig {
  name: string;                    // 1-50 chars
  system_prompt: string;           // 1-10000 chars
  model: string;                   // LLM model name
  tools: string[];                 // List of tool names
  concurrency_limit: number;       // 1-10
}
```

### AgentResponse

```typescript
interface AgentResponse {
  id: string;                      // UUID
  name: string;
  status: "ready" | "busy" | "error";
  created_at: string;              // ISO 8601
  config: AgentConfig;
}
```

### MessageRequest

```typescript
interface MessageRequest {
  content: string;                 // 1-50000 chars
  target_agent?: string;           // Optional, for direct mode
}
```

### MessageResponse

```typescript
interface MessageResponse {
  id: string;                      // UUID
  role: "user" | "assistant" | "system";
  content: string;
  agent_id: string | null;         // UUID or null
  timestamp: string;               // ISO 8601
}
```

### ChatSessionResponse

```typescript
interface ChatSessionResponse {
  id: string;                      // UUID
  created_at: string;              // ISO 8601
  message_count: number;
}
```

### StreamEvent

```typescript
interface StreamEvent {
  event_type: string;              // Event type
  payload: Record<string, any>;    // Event data
  session_id: string;              // UUID
  timestamp: string;               // ISO 8601
}
```

**Примечание**: Для обратной совместимости `SSEEvent` является алиасом для `StreamEvent`.

---

## Коды ошибок

### HTTP Status Codes

| Код | Описание |
|-----|----------|
| 200 | OK - Успешный запрос |
| 201 | Created - Ресурс создан |
| 204 | No Content - Успешно, нет содержимого |
| 400 | Bad Request - Неверный запрос |
| 401 | Unauthorized - Требуется аутентификация |
| 403 | Forbidden - Доступ запрещен |
| 404 | Not Found - Ресурс не найден |
| 422 | Unprocessable Entity - Ошибка валидации |
| 429 | Too Many Requests - Превышен лимит запросов |
| 500 | Internal Server Error - Внутренняя ошибка |
| 503 | Service Unavailable - Сервис недоступен |

### Error Response Format

```json
{
  "detail": "Human-readable error message",
  "error_code": "MACHINE_READABLE_CODE",
  "field_errors": {
    "field_name": ["Error message 1", "Error message 2"]
  }
}
```

### Error Codes

| Код | Описание |
|-----|----------|
| `UNAUTHORIZED` | Отсутствует или неверный токен |
| `INVALID_TOKEN` | Токен истек или невалиден |
| `INVALID_USER_ID` | Неверный формат user ID |
| `RESOURCE_NOT_FOUND` | Ресурс не найден |
| `VALIDATION_ERROR` | Ошибка валидации данных |
| `AGENT_NOT_FOUND` | Агент не найден |
| `SESSION_NOT_FOUND` | Сессия не найдена |
| `AGENT_EXECUTION_FAILED` | Ошибка выполнения агента |
| `RATE_LIMIT_EXCEEDED` | Превышен лимит запросов |
| `INTERNAL_ERROR` | Внутренняя ошибка сервера |

---

## Rate Limiting

### Лимиты

- **По умолчанию**: 100 запросов в минуту на пользователя
- **Burst**: 20 дополнительных запросов

### Response Headers

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1708000060
```

### Превышение лимита

**Response** (429 Too Many Requests):
```json
{
  "detail": "Rate limit exceeded. Try again in 30 seconds.",
  "error_code": "RATE_LIMIT_EXCEEDED",
  "retry_after": 30
}
```

---

## Примеры использования

### Python (httpx)

```python
import httpx

# Создание агента
async with httpx.AsyncClient() as client:
    response = await client.post(
        "http://localhost:8000/my/agents/",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "coder",
            "system_prompt": "You are an expert Python developer",
            "model": "gpt-4-turbo-preview",
            "tools": [],
            "concurrency_limit": 3
        }
    )
    agent = response.json()
    print(f"Created agent: {agent['id']}")

# Отправка сообщения
response = await client.post(
    f"http://localhost:8000/my/chat/{session_id}/message/",
    headers={"Authorization": f"Bearer {token}"},
    json={
        "content": "Напиши Hello World на Python",
        "target_agent": "coder"
    }
)
message = response.json()
print(f"Response: {message['content']}")
```

### JavaScript (fetch)

```javascript
// Создание сессии
const response = await fetch('http://localhost:8000/my/chat/sessions/', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  }
});
const session = await response.json();

// Streaming подключение
const response = await fetch(`http://localhost:8000/my/chat/${session.id}/events/`, {
  headers: {
    'Authorization': `Bearer ${token}`
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
    if (event.event_type === 'task_completed') {
      console.log('Task completed:', event);
    }
  }
}
```

### cURL

```bash
# Создание агента
curl -X POST http://localhost:8000/my/agents/ \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "coder",
    "system_prompt": "You are an expert Python developer",
    "model": "gpt-4-turbo-preview",
    "tools": [],
    "concurrency_limit": 3
  }'

# Получение списка агентов
curl http://localhost:8000/my/agents/ \
  -H "Authorization: Bearer ${TOKEN}"

# Отправка сообщения
curl -X POST http://localhost:8000/my/chat/${SESSION_ID}/message/ \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Напиши Hello World",
    "target_agent": "coder"
  }'
```

---

## Changelog

### v0.1.0 (2026-02-13)
- Начальная версия API
- Endpoints для управления агентами
- Endpoints для чат-сессий
- SSE для real-time обновлений
- JWT аутентификация

---

## Поддержка

Для вопросов и проблем:
- GitHub Issues: https://github.com/pese-git/codelab-core-service/issues
- Email: support@openidealab.com
- Документация: https://codelab.openidealab.com
