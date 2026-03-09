# REST API Спецификация
## Personal Multi-Agent AI Platform v0.2.0
**Документация обновлена:** 28 февраля 2026 (Event Logging System добавлена)
**Base URL:** `/my/` (пользовательское API с полной изоляцией)

---

## 📋 Содержание
- [Общие принципы](#общие-принципы)
- [Аутентификация](#аутентификация)
- [Projects API](#projects-api)
- [Agents API](#agents-api)
- [Chat API](#chat-api)
- [LLM Providers API](#llm-providers-api)
- [Analytics API](#analytics-api)
- [Health API](#health-api)
- [Коды ошибок](#коды-ошибок)

---

## 🎯 Общие принципы

### Base Endpoint
```
Production: https://api.example.com/my
Development: http://localhost:8000/my
```

### Основные правила
- ✅ **Изоляция:** Только собственные ресурсы (проекты, агенты, чаты)
- ✅ **JWT Auth:** Bearer токен в заголовке `Authorization`
- ✅ **JSON:** Все endpoints используют `application/json`
- ✅ **Async:** Все операции неблокирующие
- ✅ **Структура:** Project-based (все под `/my/projects/{project_id}/`)

### Архитектура Workspace и Backend ресурсов

**Ключевое разделение ответственности:**
- **Workspace (файловая система пользователя)**: находится на стороне пользователя (client), управляется пользователем через client приложение
- **Backend ресурсы**: управляются User Worker Space backend компонентой (agent_cache, Agent Bus, Qdrant collections)
- **User Worker Space**: создается для каждого проекта при первом запросе и инициализирует все backend ресурсы

**Endpoints, инициализирующие User Worker Space backend ресурсы:**
- `POST /my/projects/` - создает новый проект и инициализирует User Worker Space с 4 default агентами
- `POST /my/projects/{project_id}/agents/` - регистрирует нового агента в существующем Worker Space
- Первый запрос к любому endpoint проекта инициирует User Worker Space если его еще нет

**Все операции с файлами workspace происходят через tools:**
- Tools (tool_read_file, tool_write_file, tool_list_directory) получают от backend путь и user_id
- CLIENT валидирует пути (проверяет что находятся в пределах workspace границ)
- CLIENT выполняет операцию с локальной файловой системой пользователя
- Результат возвращается на backend

---

## 🔐 Аутентификация

### JWT Bearer Token

Все защищенные endpoints требуют JWT токен в заголовке:

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

**Claims:**
- `sub` (subject) - UUID пользователя
- `exp` (expiration) - время истечения (Unix timestamp)
- `iat` (issued at) - время выдачи (Unix timestamp)

### Получение тестового токена

```bash
python scripts/generate_test_jwt.py --user-id <UUID> --expire 3600
```

### Ошибки аутентификации

| Код | Описание |
|-----|----------|
| 401 | Missing or invalid Authorization header |
| 401 | Invalid or expired token |
| 403 | Access denied to resource |

---

## 📁 Projects API

### Создание проекта

**POST** `/my/projects/`

Создает новый проект с default Starter Pack агентами (CodeAssistant, DataAnalyst, DocumentWriter).

**Request:**
```json
{
  "name": "My Awesome Project",
  "workspace_path": "/Users/john/projects/awesome"
}
```

**Response: 201 Created**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": "123e4567-e89b-12d3-a456-426614174000",
  "name": "My Awesome Project",
  "workspace_path": "/Users/john/projects/awesome",
  "created_at": "2026-02-18T05:30:00Z",
  "updated_at": "2026-02-18T05:30:00Z"
}
```

---

### Список проектов

**GET** `/my/projects/`

Получить все проекты текущего пользователя.

**Response: 200 OK**
```json
{
  "projects": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "user_id": "123e4567-e89b-12d3-a456-426614174000",
      "name": "My Awesome Project",
      "workspace_path": "/Users/john/projects/awesome",
      "created_at": "2026-02-18T05:30:00Z",
      "updated_at": "2026-02-18T05:30:00Z"
    }
  ],
  "total": 1
}
```

---

### Получить проект

**GET** `/my/projects/{project_id}`

Получить детали конкретного проекта.

**Response: 200 OK**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": "123e4567-e89b-12d3-a456-426614174000",
  "name": "My Awesome Project",
  "workspace_path": "/Users/john/projects/awesome",
  "created_at": "2026-02-18T05:30:00Z",
  "updated_at": "2026-02-18T05:30:00Z"
}
```

**Ошибки:**
- 404: Project not found
- 403: Access denied

---

### Обновить проект

**PUT** `/my/projects/{project_id}`

Обновить информацию о проекте.

**Request:**
```json
{
  "name": "Updated Project Name",
  "workspace_path": "/Users/john/projects/updated"
}
```

**Response: 200 OK**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": "123e4567-e89b-12d3-a456-426614174000",
  "name": "Updated Project Name",
  "workspace_path": "/Users/john/projects/updated",
  "created_at": "2026-02-18T05:30:00Z",
  "updated_at": "2026-02-18T05:35:00Z"
}
```

---

### Удалить проект

**DELETE** `/my/projects/{project_id}`

Удалить проект со всеми его агентами и сессиями.

**Response: 204 No Content**

---

## 🤖 Agents API

Все agents операции выполняются в контексте конкретного проекта.

### Создать агента

**POST** `/my/projects/{project_id}/agents/`

Создать нового агента в проекте.

**Request:**
```json
{
  "name": "coder",
  "system_prompt": "You are an expert Python developer specializing in backend architecture",
  "model": "openrouter/openai/gpt-4.1",
  "tools": ["code_executor", "file_reader"],
  "concurrency_limit": 3,
  "temperature": 0.7,
  "max_tokens": 4096,
  "metadata": {
    "specialty": "backend",
    "experience_level": "senior"
  }
}
```

**Response: 201 Created**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "coder",
  "status": "ready",
  "created_at": "2026-02-18T05:30:00Z",
  "config": {
    "name": "coder",
    "system_prompt": "You are an expert Python developer...",
    "model": "openrouter/openai/gpt-4.1",
    "tools": ["code_executor", "file_reader"],
    "concurrency_limit": 3,
    "temperature": 0.7,
    "max_tokens": 4096,
    "metadata": {
      "specialty": "backend",
      "experience_level": "senior"
    }
  }
}
```

---

### Список агентов

**GET** `/my/projects/{project_id}/agents/`

Получить всех агентов проекта.

**Response: 200 OK**
```json
{
  "agents": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "coder",
      "status": "ready",
      "created_at": "2026-02-18T05:30:00Z",
      "config": { "..." }
    },
    {
      "id": "550e8400-e29b-41d4-a716-446655440001",
      "name": "analyst",
      "status": "ready",
      "created_at": "2026-02-18T05:31:00Z",
      "config": { "..." }
    }
  ],
  "total": 2
}
```

---

### Получить агента

**GET** `/my/projects/{project_id}/agents/{agent_id}`

Получить детали конкретного агента.

**Response: 200 OK**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "coder",
  "status": "ready",
  "created_at": "2026-02-18T05:30:00Z",
  "config": {
    "name": "coder",
    "system_prompt": "You are an expert Python developer...",
    "model": "openrouter/openai/gpt-4.1",
    "tools": ["code_executor", "file_reader"],
    "concurrency_limit": 3,
    "temperature": 0.7,
    "max_tokens": 4096,
    "metadata": {
      "specialty": "backend",
      "experience_level": "senior"
    }
  }
}
```

---

### Обновить агента

**PUT** `/my/projects/{project_id}/agents/{agent_id}`

Обновить конфигурацию агента.

**Request:**
```json
{
  "config": {
    "name": "coder",
    "system_prompt": "Updated system prompt...",
    "model": "openrouter/openai/gpt-4.1",
    "tools": ["code_executor", "file_reader", "web_search"],
    "concurrency_limit": 5,
    "temperature": 0.5,
    "max_tokens": 8192,
    "metadata": {
      "specialty": "backend",
      "experience_level": "senior"
    }
  }
}
```

**Response: 200 OK**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "coder",
  "status": "ready",
  "created_at": "2026-02-18T05:30:00Z",
  "config": { "..." }
}
```

---

### Удалить агента

**DELETE** `/my/projects/{project_id}/agents/{agent_id}`

Удалить агента из проекта.

**Response: 204 No Content**

---

## 💬 Chat API

Чаты работают в контексте проекта и могут использовать агентов проекта.

### Создать сессию чата

**POST** `/my/projects/{project_id}/chat/sessions/`

Создать новую чат-сессию в проекте.

**Request:**
```json
{}
```

**Response: 201 Created**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "created_at": "2026-02-18T05:30:00Z",
  "message_count": 0
}
```

---

### Список сессий

**GET** `/my/projects/{project_id}/chat/sessions/`

Получить все сессии проекта.

**Response: 200 OK**
```json
{
  "sessions": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "created_at": "2026-02-18T05:30:00Z",
      "message_count": 5
    },
    {
      "id": "550e8400-e29b-41d4-a716-446655440001",
      "created_at": "2026-02-18T05:31:00Z",
      "message_count": 0
    }
  ],
  "total": 2
}
```

---

### Получить сообщения сессии

**GET** `/my/projects/{project_id}/chat/sessions/{session_id}/messages/`

Получить историю сообщений в сессии.

**Response: 200 OK**
```json
{
  "messages": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "role": "user",
      "content": "Fix the bug in auth.py",
      "agent_id": null,
      "timestamp": "2026-02-18T05:30:00Z"
    },
    {
      "id": "550e8400-e29b-41d4-a716-446655440001",
      "role": "assistant",
      "content": "I found the bug! In auth.py line 42...",
      "agent_id": "550e8400-e29b-41d4-a716-446655440100",
      "timestamp": "2026-02-18T05:30:05Z"
    }
  ],
  "total": 2,
  "session_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

---

### Отправить сообщение

**POST** `/my/projects/{project_id}/chat/{session_id}/message/`

💎 **ГЛАВНЫЙ ENDPOINT** для взаимодействия с агентами.

Поддерживает два режима:

#### Режим 1: Прямой вызов ⚡ (1-2 сек)

Вызов конкретного агента по имени, обходит оркестратор.

**Request:**
```json
{
  "content": "Fix the bug in auth.py",
  "target_agent": "coder"
}
```

**Response: 200 OK**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440001",
  "role": "assistant",
  "content": "I found the bug! In auth.py line 42...",
  "agent_id": "550e8400-e29b-41d4-a716-446655440100",
  "timestamp": "2026-02-18T05:30:05Z"
}
```

#### Режим 2: Автоматический 🧠 (5-10 сек)

Оркестратор анализирует запрос, создает план и координирует агентов.

**Request:**
```json
{
  "content": "Спланируй и реализуй систему авторизации с JWT для нашего API"
}
```

**Response: 200 OK**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440001",
  "role": "assistant",
  "content": "Task orchestrated across multiple agents. Results:\n1. Architecture design by architect\n2. Implementation by coder\n3. Tests by tester",
  "agent_id": "orchestrator",
  "timestamp": "2026-02-18T05:30:15Z"
}
```

---

### Получить события (SSE Stream)

**GET** `/my/projects/{project_id}/chat/{session_id}/events/`

Получить поток событий сессии в формате Server-Sent Events (NDJSON).

**Response: 200 OK (text/event-stream)**

```
data: {"type": "message_received", "content": "Fix the bug", "timestamp": "2026-02-18T05:30:00Z"}
data: {"type": "agent_started", "agent_id": "coder", "timestamp": "2026-02-18T05:30:01Z"}
data: {"type": "agent_status_changed", "agent_id": "coder", "status": "busy", "timestamp": "2026-02-18T05:30:01Z"}
data: {"type": "agent_response", "agent_id": "coder", "content": "I found the bug...", "timestamp": "2026-02-18T05:30:05Z"}
data: {"type": "agent_status_changed", "agent_id": "coder", "status": "ready", "timestamp": "2026-02-18T05:30:05Z"}
```

**События:**
- `message_received` - сообщение получено
- `agent_started` - агент начал выполнение
- `agent_status_changed` - статус агента изменился
- `agent_response` - агент отправил ответ
- `agent_completed` - агент завершил работу

---

### Удалить сессию

**DELETE** `/my/projects/{project_id}/chat/sessions/{session_id}`

Удалить сессию со всеми сообщениями.

**Response: 204 No Content**

---

## 📊 Analytics API

### Получить события проекта

**GET** `/my/projects/{project_id}/events`

Получить список событий проекта с поддержкой фильтрации и пагинации.

**Query Parameters:**
- `event_type` (optional) - фильтр по типу события (message_created, agent_switched, etc.)
- `aggregate_type` (optional) - фильтр по типу агрегата (chat_session, task_plan, etc.)
- `status` (optional) - фильтр по статусу события (pending, published, failed)
- `limit` (optional, default=50) - количество результатов (1-100)
- `offset` (optional, default=0) - смещение для пагинации

**Response: 200 OK**
```json
{
  "events": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "event_type": "message_created",
      "aggregate_type": "chat_session",
      "aggregate_id": "550e8400-e29b-41d4-a716-446655440001",
      "payload": {
        "content": "Hello assistant",
        "role": "user",
        "event_id": "550e8400-e29b-41d4-a716-446655440000"
      },
      "status": "published",
      "created_at": "2026-02-28T07:30:00Z",
      "published_at": "2026-02-28T07:30:02Z"
    }
  ],
  "total": 150,
  "limit": 50,
  "offset": 0
}
```

---

### Получить события сессии

**GET** `/my/projects/{project_id}/analytics/sessions/{session_id}/events`

Получить все события для конкретной сессии чата.

**Query Parameters:**
- `event_type` (optional) - фильтр по типу события
- `limit` (optional, default=50) - количество результатов
- `offset` (optional, default=0) - смещение для пагинации

**Response: 200 OK**
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440001",
  "events": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "event_type": "message_created",
      "timestamp": "2026-02-28T07:30:00Z",
      "payload": {
        "content": "Hello",
        "role": "user"
      }
    },
    {
      "id": "550e8400-e29b-41d4-a716-446655440002",
      "event_type": "agent_switched",
      "timestamp": "2026-02-28T07:30:01Z",
      "payload": {
        "from_agent": "orchestrator",
        "to_agent": "coder",
        "routing_score": 0.95
      }
    }
  ],
  "total": 42,
  "limit": 50,
  "offset": 0
}
```

---

### Получить аналитику проекта

**GET** `/my/projects/{project_id}/analytics`

Получить агрегированные метрики события проекта.

**Response: 200 OK**
```json
{
  "period": {
    "start": "2026-02-27T00:00:00Z",
    "end": "2026-02-28T23:59:59Z"
  },
  "events_by_type": {
    "message_created": 245,
    "agent_switched": 87,
    "agent_started": 92,
    "agent_completed": 89
  },
  "events_by_status": {
    "published": 510,
    "pending": 2,
    "failed": 0
  },
  "latency_stats": {
    "avg_latency_ms": 125,
    "max_latency_ms": 3450,
    "min_latency_ms": 15,
    "p95_latency_ms": 890
  },
  "retention": {
    "total_events": 512,
    "oldest_event_age_days": 15,
    "estimated_retention_days": 30
  }
}
```

**Description:**
- `events_by_type` - количество событий по типам
- `events_by_status` - распределение по статусам (pending, published, failed)
- `latency_stats` - статистика по времени доставки событий
- `retention` - информация о хранении событий в outbox

---

## 🏥 Health API

### Health Check

**GET** `/health`

Проверить статус приложения.

**Response: 200 OK**
```json
{
  "status": "ok"
}
```

---

### Readiness Check

**GET** `/ready`

Проверить готовность приложения к работе (доступность БД, Redis, Qdrant).

**Response: 200 OK**
```json
{
  "status": "ready"
}
```

---

## ⚠️ Коды ошибок

| Код | Описание | Пример |
|-----|----------|--------|
| 200 | OK | Успешный запрос |
| 201 | Created | Ресурс создан |
| 204 | No Content | Успешно удалено |
| 400 | Bad Request | Некорректные данные запроса |
| 401 | Unauthorized | Отсутствует или невалидный токен |
| 403 | Forbidden | Доступ запрещен к ресурсу |
| 404 | Not Found | Ресурс не найден |
| 422 | Unprocessable Entity | Ошибка валидации данных |
| 500 | Internal Server Error | Ошибка сервера |
| 503 | Service Unavailable | Сервис недоступен |

---

## 📝 Примеры использования

### cURL - Полный цикл

```bash
# 1. Создать проект
curl -X POST "http://localhost:8000/my/projects/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My AI Project",
    "workspace_path": "/Users/john/projects"
  }' | jq .

# Сохранить ID проекта
PROJECT_ID="550e8400-e29b-41d4-a716-446655440000"

# 2. Создать сессию чата
curl -X POST "http://localhost:8000/my/projects/$PROJECT_ID/chat/sessions/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{}' | jq .

SESSION_ID="550e8400-e29b-41d4-a716-446655440001"

# 3. Отправить сообщение (прямой вызов агента)
curl -X POST "http://localhost:8000/my/projects/$PROJECT_ID/chat/$SESSION_ID/message/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Помоги мне написать функцию для парсинга JSON",
    "target_agent": "coder"
  }' | jq .

# 4. Получить историю
curl -X GET "http://localhost:8000/my/projects/$PROJECT_ID/chat/sessions/$SESSION_ID/messages/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" | jq .

# 5. Подписаться на события (в отдельном терминале)
curl -X GET "http://localhost:8000/my/projects/$PROJECT_ID/chat/$SESSION_ID/events/" \
  -H "Authorization: Bearer $TOKEN" \
  -N  # отключить буферизацию для SSE
```

### Python - Async

```python
import httpx
import json

async def demo():
    token = "your-jwt-token"
    headers = {"Authorization": f"Bearer {token}"}
    
    async with httpx.AsyncClient() as client:
        # Создать проект
        response = await client.post(
            "http://localhost:8000/my/projects/",
            headers=headers,
            json={"name": "My Project", "workspace_path": "/workspace"}
        )
        project = response.json()
        project_id = project["id"]
        
        # Создать сессию
        response = await client.post(
            f"http://localhost:8000/my/projects/{project_id}/chat/sessions/",
            headers=headers
        )
        session = response.json()
        session_id = session["id"]
        
        # Отправить сообщение
        response = await client.post(
            f"http://localhost:8000/my/projects/{project_id}/chat/{session_id}/message/",
            headers=headers,
            json={
                "content": "Write me a Python function",
                "target_agent": "coder"
            }
        )
        message = response.json()
        print(message)
```

---

## 🔗 Интеграция

- Swagger Documentation: `/docs`
- ReDoc Documentation: `/redoc`
- OpenAPI Schema: `/openapi.json`
