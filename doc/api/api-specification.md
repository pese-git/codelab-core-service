# API Спецификация - CodeLab Core Service v0.2.0

## 📖 Обзор

Это архитектурный справочник API. Для полной документации с примерами см. [`doc/rest-api.md`](../rest-api.md).

---

## 📋 Содержание

- [Общие принципы](#общие-принципы)
- [Аутентификация](#аутентификация)
- [Структура endpoints](#структура-endpoints)
- [Коды ошибок](#коды-ошибок)
- [Схемы данных](#схемы-данных)

---

## 🎯 Общие принципы

### Базовые сведения

| Параметр | Значение |
|----------|----------|
| **Base URL** | `/my` (все user-specific endpoints) |
| **Аутентификация** | JWT Bearer Token в заголовке `Authorization` |
| **Content-Type** | `application/json` (кроме SSE: `text/event-stream`) |
| **Версионирование** | Неявное v1 (в будущем `/v1/`, `/v2/`) |
| **Response** | JSON с единообразной структурой ошибок |

### Принципы API дизайна

1. **User Isolation** - Все endpoints автоматически фильтруют по user_id
2. **Project Scoping** - Все ресурсы (кроме Projects) привязаны к проекту
3. **Consistency** - Одинаковая структура для всех CRUD операций
4. **Stateless** - API не хранит состояние сессии
5. **Idempotent** - Повторные запросы дают тот же результат

---

## 🔐 Аутентификация

### JWT Bearer Token

```http
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### Структура токена

```json
{
  "sub": "550e8400-e29b-41d4-a716-446655440000",  // UUID пользователя
  "iat": 1707998200,                               // Issued at (Unix timestamp)
  "exp": 1708000000                                // Expires (Unix timestamp)
}
```

### Получение токена

```bash
python scripts/generate_test_jwt.py --user-id <UUID> --expire 3600
```

### Ошибки аутентификации

| Код | Условие |
|-----|---------|
| 401 | Missing Authorization header |
| 401 | Invalid Bearer token format |
| 401 | Invalid or expired token |
| 401 | Invalid user ID in token |

---

## 🗂️ Структура endpoints

### Kategories

```
/my/projects/                               # Project Management
├─ POST   /                                 # Create project
├─ GET    /                                 # List projects
├─ GET    /{project_id}/                    # Get project
├─ PUT    /{project_id}/                    # Update project
└─ DELETE /{project_id}/                    # Delete project

/my/projects/{project_id}/agents/           # Agent Management
├─ POST   /                                 # Create agent
├─ GET    /                                 # List agents
├─ GET    /{agent_id}                       # Get agent
├─ PUT    /{agent_id}                       # Update agent
└─ DELETE /{agent_id}                       # Delete agent

/my/projects/{project_id}/chat/             # Chat & Messaging
├─ POST   /sessions/                        # Create session
├─ GET    /sessions/                        # List sessions
├─ POST   /{session_id}/message/            # Send message (Main Endpoint)
├─ GET    /{session_id}/messages/           # Get history
├─ GET    /{session_id}/events/             # SSE stream
└─ DELETE /sessions/{session_id}            # Delete session

/health                                     # Health Check (no auth)
/ready                                      # Readiness Check (no auth)
```

---

## 📋 Детальные endpoints

### Projects API

#### POST /my/projects/
Создать новый проект с Starter Pack агентами.

**Request**: `ProjectCreate`
```json
{
  "name": "string",              // (required, 1-255 chars)
  "workspace_path": "string"     // (optional, 0-500 chars)
}
```

**Response**: `ProjectResponse` (201 Created)
```json
{
  "id": "uuid",
  "user_id": "uuid",
  "name": "string",
  "workspace_path": "string|null",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

---

#### GET /my/projects/
Список всех проектов пользователя.

**Query Parameters**: Нет

**Response**: `ProjectListResponse` (200 OK)
```json
{
  "projects": [
    { "ProjectResponse" },
    { "ProjectResponse" }
  ],
  "total": "int"
}
```

---

#### GET /my/projects/{project_id}
Детали конкретного проекта.

**Path**: `project_id` (UUID)

**Response**: `ProjectResponse` (200 OK)

**Ошибки**:
- 404: Project not found
- 403: Access denied

---

#### PUT /my/projects/{project_id}
Обновить проект.

**Path**: `project_id` (UUID)

**Request**: `ProjectUpdate`
```json
{
  "name": "string|null",
  "workspace_path": "string|null"
}
```

**Response**: `ProjectResponse` (200 OK)

---

#### DELETE /my/projects/{project_id}
Удалить проект со всеми агентами и сессиями.

**Path**: `project_id` (UUID)

**Response**: (204 No Content)

---

### Agents API

#### POST /my/projects/{project_id}/agents/
Создать агента в проекте.

**Request**: `AgentConfig`
```json
{
  "name": "string",                    // 1-100 chars
  "system_prompt": "string",           // 1+ chars
  "model": "string",                   // default: openrouter/openai/gpt-4.1
  "tools": ["string"],                 // default: []
  "concurrency_limit": "int",          // 1-10, default: 3
  "temperature": "float",              // 0.0-2.0, default: 0.7
  "max_tokens": "int",                 // 1-128000, default: 4096
  "metadata": {                        // optional
    "key": "value"
  }
}
```

**Response**: `AgentResponse` (201 Created)
```json
{
  "id": "uuid",
  "name": "string",
  "status": "enum(ready|busy|error)",
  "created_at": "datetime",
  "config": { "AgentConfig" }
}
```

---

#### GET /my/projects/{project_id}/agents/
Список агентов проекта.

**Response**: `AgentListResponse` (200 OK)
```json
{
  "agents": [
    { "AgentResponse" },
    { "AgentResponse" }
  ],
  "total": "int"
}
```

---

#### GET /my/projects/{project_id}/agents/{agent_id}
Детали агента.

**Response**: `AgentResponse` (200 OK)

**Ошибки**:
- 404: Agent not found
- 403: Access denied

---

#### PUT /my/projects/{project_id}/agents/{agent_id}
Обновить конфигурацию агента.

**Request**: `AgentUpdate`
```json
{
  "config": { "AgentConfig" }
}
```

**Response**: `AgentResponse` (200 OK)

---

#### DELETE /my/projects/{project_id}/agents/{agent_id}
Удалить агента.

**Response**: (204 No Content)

---

### Chat API

#### POST /my/projects/{project_id}/chat/sessions/
Создать новую чат-сессию.

**Request**: (empty JSON)
```json
{}
```

**Response**: `ChatSessionResponse` (201 Created)
```json
{
  "id": "uuid",
  "created_at": "datetime",
  "message_count": "int"
}
```

---

#### GET /my/projects/{project_id}/chat/sessions/
Список сессий проекта.

**Response**: `ChatSessionListResponse` (200 OK)
```json
{
  "sessions": [
    { "ChatSessionResponse" },
    { "ChatSessionResponse" }
  ],
  "total": "int"
}
```

---

#### POST /my/projects/{project_id}/chat/{session_id}/message/
**💎 ГЛАВНЫЙ ENDPOINT** - Отправить сообщение.

Поддерживает два режима:
1. **Direct Call** (⚡ 1-2 сек): с `target_agent`
2. **Orchestrated** (🧠 5-10 сек): без `target_agent`

**Request**: `MessageRequest`
```json
{
  "content": "string",                 // (required, 1+ chars)
  "target_agent": "string|null"        // (optional, agent name)
}
```

**Response**: `MessageResponse` (200 OK)
```json
{
  "id": "uuid",
  "role": "enum(user|assistant|system)",
  "content": "string",
  "agent_id": "uuid|null",
  "timestamp": "datetime"
}
```

**Modes**:

**Mode 1: Direct Call** (если `target_agent` указан)
```json
{
  "content": "Write a Python function",
  "target_agent": "CodeAssistant"
}
```
→ Быстро вызывает конкретного агента, обходит оркестратор

**Mode 2: Orchestrated** (если `target_agent` не указан)
```json
{
  "content": "Design and implement REST API with authentication"
}
```
→ Оркестратор планирует задачу и координирует агентов

---

#### GET /my/projects/{project_id}/chat/sessions/{session_id}/messages/
История сообщений сессии.

**Query Parameters**: Нет

**Response**: `MessageListResponse` (200 OK)
```json
{
  "messages": [
    { "MessageResponse" },
    { "MessageResponse" }
  ],
  "total": "int",
  "session_id": "uuid"
}
```

---

#### GET /my/projects/{project_id}/chat/{session_id}/events/
**Server-Sent Events** - подписка на события сессии.

**Response**: (200 OK, Content-Type: text/event-stream)

**Event Format** (NDJSON):
```json
data: {
  "type": "message_received|agent_started|agent_response|agent_completed|...",
  "agent_id": "uuid|null",
  "content": "string|null",
  "timestamp": "datetime",
  "metadata": { }
}
```

**Event Types**:
- `message_received` - сообщение получено от пользователя
- `agent_started` - агент начал работу
- `agent_status_changed` - статус агента изменился
- `agent_response` - агент отправил ответ
- `agent_completed` - агент завершил работу
- `orchestration_started` - оркестратор начал планирование
- `orchestration_plan_created` - план создан
- `orchestration_completed` - оркестрация завершена

---

#### DELETE /my/projects/{project_id}/chat/sessions/{session_id}
Удалить сессию со всеми сообщениями.

**Response**: (204 No Content)

---

### Health API

#### GET /health
Проверка здоровья сервиса.

**Auth**: Не требуется

**Response**: (200 OK)
```json
{
  "status": "ok"
}
```

---

#### GET /ready
Проверка готовности (доступность всех зависимостей).

**Auth**: Не требуется

**Response**: (200 OK)
```json
{
  "status": "ready"
}
```

**Returns**:
- 200: Все зависимости доступны
- 503: Одна или несколько зависимостей недоступны

---

## ⚠️ Коды ошибок

### Standard HTTP Codes

| Код | Описание | Когда возвращается |
|-----|---------|-------------------|
| 200 | OK | Успешный запрос (GET, PUT, POST с ответом) |
| 201 | Created | Ресурс успешно создан (POST) |
| 204 | No Content | Успешно удалено или обновлено без ответа (DELETE, PUT) |
| 400 | Bad Request | Некорректный формат запроса |
| 401 | Unauthorized | Отсутствует или невалидный токен |
| 403 | Forbidden | Доступ запрещен (не собственный ресурс) |
| 404 | Not Found | Ресурс не найден |
| 422 | Unprocessable Entity | Ошибка валидации данных |
| 500 | Internal Server Error | Ошибка сервера |
| 503 | Service Unavailable | Зависимость недоступна (БД, Redis, Qdrant) |

### Error Response Format

```json
{
  "detail": "string",  // Описание ошибки
  "type": "string"     // Тип ошибки (опционально)
}
```

**Примеры**:

```json
// 401 Unauthorized
{
  "detail": "Invalid or expired token"
}

// 404 Not Found
{
  "detail": "Project not found"
}

// 422 Validation Error
{
  "detail": [
    {
      "loc": ["body", "name"],
      "msg": "ensure this value has at most 255 characters",
      "type": "value_error.string.max_length"
    }
  ]
}
```

---

## 📦 Схемы данных

### Enums

**AgentStatus**:
```python
enum:
  - "ready"   # Агент свободен и готов к работе
  - "busy"    # Агент выполняет задачу
  - "error"   # Агент в состоянии ошибки
```

**MessageRole**:
```python
enum:
  - "user"       # Сообщение от пользователя
  - "assistant"  # Ответ агента/оркестратора
  - "system"     # Системное сообщение
```

### Base Types

**UUID**: RFC 4122 UUID string
```
550e8400-e29b-41d4-a716-446655440000
```

**DateTime**: ISO 8601 format
```
2026-02-18T05:30:00Z
```

---

## 📊 Tool Execution Tracing - Структура данных

### Обзор

Tool Execution Tracing автоматически захватывает все выполнения инструментов через `@observe` декораторы Langfuse SDK. Данные структурированы иерархически с root span и вложенными spans для различных этапов выполнения.

### Tool Execution Span (Root)

**Тип**: `tool`  
**Имя**: `ExecuteTool`  
**Автоматическое создание**: Через `@observe` декоратор на `ToolExecutor.execute_tool()`

#### Input Payload

```json
{
  "tool_name": "read_file",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "param_keys": ["path", "mode"],
  "path": "/workspace/data.txt",
  "content_length": null,
  "user_id": "user-123",
  "project_id": "project-456"
}
```

**Поля**:
- `tool_name` (string): Имя исполняемого инструмента
- `session_id` (UUID|null): ID сессии чата (если есть)
- `param_keys` (array[string]): Список ключей параметров инструмента
- `path` (string, optional): Путь (усечено до 300 символов)
- `content_length` (int, optional): Длина содержимого файла (без самого содержимого)
- `user_id` (UUID): Из JWT токена
- `project_id` (UUID): Из JWT токена

#### Output Payload

```json
{
  "status": "success",
  "tool_id": "abc123",
  "result": "File contents...",
  "execution_time_ms": 125,
  "risk_level": "medium",
  "risk_score": 4.5,
  "approval_required": true,
  "approval_status": "approved",
  "validation_passed": true
}
```

**Поля**:
- `status` (string): `success`, `failed`, `rejected`, `error`
- `tool_id` (UUID): Уникальный ID выполнения инструмента
- `result` (string): Результат выполнения (санитизованный)
- `execution_time_ms` (int): Время выполнения в миллисекундах
- `risk_level` (string): `low`, `medium`, `high`, `critical`
- `risk_score` (float): Числовая оценка риска (0.0-10.0)
- `approval_required` (bool): Требовалось ли одобрение
- `approval_status` (string): `pending`, `approved`, `rejected`
- `validation_passed` (bool): Результат валидации параметров

### Вложенные Spans (Child Spans)

#### ValidateTool Span

**Тип**: `tool`  
**Имя**: `ValidateTool`  
**Родитель**: `ExecuteTool`

```json
{
  "input": {
    "tool_name": "read_file",
    "param_keys": ["path"]
  },
  "output": {
    "validation_status": "passed",
    "errors": []
  }
}
```

#### Validation Errors Example

Если валидация не пройдена:

```json
{
  "output": {
    "validation_status": "failed",
    "errors": [
      {
        "field": "path",
        "error": "Path outside workspace",
        "details": "Path: /etc/passwd (outside: /workspace)"
      }
    ]
  }
}
```

### Context Propagation (Метаданные Span)

Каждый span автоматически получает метаданные контекста:

```json
{
  "metadata": {
    "user_id": "550e8400-e29b-41d4-a716-446655440000",
    "project_id": "550e8400-e29b-41d4-a716-446655440001",
    "session_id": "550e8400-e29b-41d4-a716-446655440002",
    "timestamp": "2026-03-19T15:30:00Z",
    "request_id": "req-123456"
  }
}
```

### Пример полной трассировки (в Langfuse)

```
ExecuteTool (root span, 125ms)
├── Input:
│   ├── tool_name: "read_file"
│   ├── param_keys: ["path"]
│   ├── path: "/workspace/data.txt"
│   └── session_id: "session-123"
│
├── Output:
│   ├── status: "success"
│   ├── tool_id: "tool-456"
│   ├── result: "File contents"
│   ├── execution_time_ms: 125
│   ├── risk_level: "low"
│   └── validation_passed: true
│
├── Metadata:
│   ├── user_id: "user-123"
│   ├── project_id: "project-456"
│   ├── session_id: "session-123"
│   └── timestamp: "2026-03-19T15:30:00Z"
│
└── Child Spans:
    └── ValidateTool (5ms)
        ├── Input: {tool_name: "read_file", param_keys: ["path"]}
        └── Output: {validation_status: "passed", errors: []}
```

### Санитизация данных

**Исключены из трассировки**:
- Полное содержимое файлов (`content` поле)
- Полные команды оболочки (`command` поле)
- API ключи и токены
- Пароли и учетные данные

**Включены в трассировку**:
- Имена параметров (`param_keys`)
- Пути файлов (урезаны до 300 символов)
- Паттерны поиска (урезаны до 120 символов)
- Размеры данных (длины содержимого)
- Статусы и результаты

### Обработка ошибок в трассировке

При ошибке выполнения:

```json
{
  "output": {
    "status": "error",
    "error_type": "file_not_found",
    "error_message": "File does not exist",
    "execution_time_ms": 5
  }
}
```

**Типы ошибок**:
- `validation_failed`: Параметры не прошли валидацию
- `unknown_tool`: Неизвестный инструмент
- `approval_rejected`: Одобрение отклонено
- `execution_error`: Ошибка при выполнении инструмента
- `timeout`: Превышено время ожидания

### Просмотр данных

Данные трассировки доступны через:

1. **Langfuse Dashboard** (https://cloud.langfuse.com/)
   - Визуальное отображение spans
   - Иерархия операций
   - Поиск по параметрам

2. **API (Langfuse REST API)**
   - Программный доступ к traces
   - Фильтрация и агрегация
   - Аналитика и метрики

3. **Логи приложения**
   - `DEBUG` уровень при `LANGFUSE_DEBUG=true`
   - Информация о ошибках обновления spans

---

## 🔗 Полная документация

Для полной документации с примерами cURL и Python смотрите [`doc/rest-api.md`](../rest-api.md).

## 📚 Связанные документы

- [REST API полная документация](../rest-api.md)
- [Tool Execution Tracing User Guide](../guides/tool-execution-tracing.md)
- [Setup Guide](../setup-guide.md)
- [System Overview](./system-overview.md)
- [Developer Guide](./developer-guide.md)
- [Code Examples](../samples.md)
