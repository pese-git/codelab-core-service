# FINальная REST API СПЕЦИФИКАЦИЯ  
## Personal Multi-Agent AI Platform v1.0  
**Swagger: /my/docs** | **11 февраля 2026**

***

## 1. 📋 ОСНОВНЫЕ ПРИНЦИПЫ API

```
✅ БАЗА: /my/* - только свои ресурсы
✅ JWT AUTH - user_id из токена
✅ User Isolation - автоматическая проверка
✅ SSE Streaming - все события в реальном времени
✅ Async - все операции неблокирующие
✅ JSON Schema - строгая типизация
✅ Rate Limits - 100 req/min per user
```

***

## 2. 🗂️ ПОЛНЫЙ API CATALOG

### **2.1. АГЕНТЫ (CRUD + Status)**

```
=== АГЕНТЫ ===
GET    /my/agents/                          # Список агентов
POST   /my/agents/                          # Создать агента
GET    /my/agents/{agent_id}/               # Детали агента
PUT    /my/agents/{agent_id}/               # Обновить агента
DELETE /my/agents/{agent_id}/               # Удалить агента

GET    /my/agents/{agent_id}/status         # Статус агента
POST   /my/agents/{agent_id}/test           # Тест агента

GET    /my/agents/available/{session_id}/   # Доступные для сессии
POST   /my/agents/{agent_id}/context/       # Управление памятью
```

**POST /my/agents/ → 201 Created**
```json
{
  "agent_id": "user123_coder_v1",
  "name": "Мой кодер",
  "config": {
    "system_prompt": "Senior Python developer",
    "model": {"provider": "openai", "name": "gpt-4o-mini"},
    "tools": [{"tool_id": "code_exec", "enabled": true}]
  }
}
```

### **2.2. ОРКЕСТРАТОРЫ**

```
=== ОРКЕСТРАТОРЫ ===
PUT    /my/orchestrators/                   # Настроить оркестратор
GET    /my/orchestrators/                   # Конфигурация
POST   /my/orchestrators/test               # Тест планирования
```

### **2.3. ЧАТЫ (Core API)**

```
=== ЧАТЫ ===
POST   /my/chat/sessions/                   # Создать сессию
GET    /my/chat/sessions/                   # Список сессий
GET    /my/chat/{session_id}/               # История чата
DELETE /my/chat/{session_id}/               # Удалить сессию

POST   /my/chat/{session_id}/message/       # 💎 ГЛАВНЫЙ ENDPOINT
GET    /my/chat/{session_id}/events/        # SSE поток событий
```

**POST /my/chat/{session_id}/message/ → 200 OK**
```json
// Режим 1: Прямой вызов ⚡
{
  "content": "2+2=?",
  "target_agent": "user123_math"  // Обходит оркестратор
}

// Режим 2: Авто 🧠  
{
  "content": "Спланируй разработку TODO API"
  // Оркестратор создаст граф задач
}
```
```json
Response: {
  "execution_id": "exec_abc123",
  "mode": "direct",  // или "orchestrated"
  "estimated_time": "2s"
}
```

### **2.4. APPROVAL MANAGER (Контроль)**

```
=== APPROVALS ===
POST   /my/tools/{approval_id}/confirm/     # ✅ Подтвердить
POST   /my/tools/{approval_id}/reject/      # ❌ Отклонить
GET    /my/tools/pending/                   # Ожидающие
```

**POST /my/tools/abc123/confirm/**
```json
{
  "approved": true,
  "result": {"base64_image": "..."}  // Результат camera/geolocation
}
```

### **2.5. КОНТЕКСТ (Agent Memory)**

```
=== ПАМЯТЬ АГЕНТОВ ===
POST   /my/agents/{agent_id}/context/       # clear/prune/export
GET    /my/agents/{agent_id}/context/stats/ # Статистика памяти
```

***

## 3. 💎 SSE EVENTS (Event Stream)

**GET /my/chat/{session_id}/events/ → text/event-stream**

```
=== СОБЫТИЯ (JSON) ===
direct_agent_call        # ⚡ Прямой вызов начат
agent_status_changed     # Статус агента (ready/busy/error)
task_plan_created        # 🧠 Оркестратор создал план
task_started             # Задача запущена
task_progress            # 75%
task_completed           # ✅ Результат
tool_request             # 🛡️ Подтверждение tool
plan_request             # 🛡️ Подтверждение плана
tasks_progress           # Общий прогресс графа
approval_required        # Требуется действие
context_retrieved        # RAG контекст использован
```

**Пример события:**
```json
{
  "type": "direct_agent_call",
  "agent_id": "user123_coder",
  "status": "executing",
  "bypassed_orchestrator": true,
  "context_chunks": 5,
  "timestamp": "2026-02-11T10:00:00Z"
}
```

***

## 4. 📄 ПОЛНЫЕ OPENAPI SCHEMAS

### **4.1. ChatMessage (главная модель)**

```yaml
ChatMessage:
  type: object
  required: [content]
  properties:
    content:
      type: string
      maxLength: 4000
    target_agent:
      type: string
      pattern: '^user\d+_.*'  # Только свои агенты
    bypass_orchestrator:
      type: boolean
      default: false
```

### **4.2. AgentConfig**

```yaml
AgentConfig:
  type: object
  required: [name, system_prompt]
  properties:
    name:
      type: string
      maxLength: 100
    system_prompt:
      type: string
      maxLength: 4000
    model:
      type: object
      properties:
        provider: {enum: [openai, anthropic, local]}
        name: {type: string}
        temperature: {type: number, minimum: 0, maximum: 1}
    tools:
      type: array
      items:
        type: object
        properties:
          tool_id: {type: string}
          enabled: {type: boolean}
```

### **4.3. ApprovalResponse**

```yaml
ApprovalResponse:
  type: object
  properties:
    approved: {type: boolean}
    result: {type: object}  # Результат tool (image/file/etc)
    reason: {type: string}  # При отказе
```

***

## 5. 🚀 ПРИМЕРЫ ПОЛНЫХ ЗАПРОСОВ

### **5.1. Создание агента**

```bash
curl -X POST "/my/agents/" \
  -H "Authorization: Bearer <jwt>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Мой математик",
    "system_prompt": "Ты эксперт по математике",
    "model": {"provider": "openai", "name": "gpt-4o-mini"},
    "tools": [{"tool_id": "calculator", "enabled": true}]
  }'
```

**Response 201:**
```json
{
  "agent_id": "user123_math_v1",
  "status": "created",
  "context_collection": "user123_math_v1_context"
}
```

### **5.2. Прямой вызов ⚡**

```bash
curl -X POST "/my/chat/1/message/" \
  -d '{
    "content": "Решить уравнение x^2 - 5x + 6 = 0",
    "target_agent": "user123_math_v1"
  }'
```

### **5.3. Approval Tool**

```javascript
// Клиент подтверждает камеру
fetch("/my/tools/abc123/confirm/", {
  method: "POST",
  body: JSON.stringify({
    "approved": true,
    "result": {
      "base64_image": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQ..."
    }
  })
});
```

***

## 6. 🔐 АУТЕНТИФИКАЦИЯ И АВТОРИЗАЦИЯ

### **6.1. 🔓 Использование JWT в Swagger UI (/docs)**

Swagger UI поддерживает Bearer Authentication для удобного тестирования API:

**Шаги:**
1. Откройте `/docs` в браузере
2. Нажмите кнопку **"Authorize"** 🔓 (правый верхний угол)
3. В поле **"Value"** введите JWT токен **БЕЗ префикса "Bearer"**
   ```
   eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjNlNDU2Ny1lODliLTEyZDMtYTQ1Ni00MjY2MTQxNzQwMDAiLCJleHAiOjE3MDc2NTY0MDB9.xxx
   ```
4. Нажмите **"Authorize"**
5. Закройте диалог

✅ **Результат:** Все запросы к `/my/*` будут автоматически включать заголовок `Authorization: Bearer <token>`

---

### **6.2. 📝 Формат JWT токена**

**Требования к токену:**

| Параметр | Значение | Описание |
|----------|----------|----------|
| **Алгоритм** | `settings.jwt_algorithm` | По умолчанию HS256 |
| **Секретный ключ** | `settings.jwt_secret_key` | Из переменной окружения |
| **Claim "sub"** | UUID (обязательно) | Содержит `user_id` |
| **Claim "exp"** | Unix timestamp | Время истечения токена |
| **Claim "iat"** | Unix timestamp | Время создания токена |

**Пример payload:**
```json
{
  "sub": "123e4567-e89b-12d3-a456-426614174000",
  "exp": 1707656400,
  "iat": 1707652800
}
```

⚠️ **Важно:** Claim `"sub"` должен содержать валидный UUID, который используется как `user_id` для изоляции данных.

---

### **6.3. 🔧 Использование в API запросах**

**Пример curl команды:**
```bash
curl -X GET "/my/agents/" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -H "Content-Type: application/json"
```

**Пример JavaScript (fetch):**
```javascript
const response = await fetch('/my/agents/', {
  method: 'GET',
  headers: {
    'Authorization': `Bearer ${jwtToken}`,
    'Content-Type': 'application/json'
  }
});
```

**Пример Python (httpx):**
```python
import httpx

headers = {
    "Authorization": f"Bearer {jwt_token}",
    "Content-Type": "application/json"
}
response = httpx.get("/my/agents/", headers=headers)
```

---

### **6.4. ⚠️ Обработка ошибок аутентификации**

| Ошибка | HTTP Code | Error Code | Причина |
|--------|-----------|------------|---------|
| Отсутствует заголовок | **401** | `UNAUTHORIZED` | Нет `Authorization` header |
| Невалидный токен | **401** | `INVALID_TOKEN` | Токен истек или неверная подпись |
| Неверный user_id | **401** | `INVALID_USER_ID` | Claim `"sub"` не является UUID |

**Пример ответа при ошибке:**
```json
{
  "detail": "Invalid authentication credentials",
  "type": "INVALID_TOKEN",
  "error": "Token has expired"
}
```

---

### **6.5. 🛡️ User Isolation**

**Принципы изоляции:**
- Все эндпоинты `/my/*` автоматически проверяют JWT токен
- `user_id` извлекается из claim `"sub"` токена
- `agent_id` должен начинаться с `user{user_id}_`
- Все DB запросы автоматически фильтруются: `WHERE user_id = ?`
- Попытка доступа к чужим ресурсам → **403 Forbidden**

**Пример проверки:**
```python
# Токен: {"sub": "123e4567-e89b-12d3-a456-426614174000"}
# user_id = UUID("123e4567-e89b-12d3-a456-426614174000")

# ✅ Разрешено:
GET /my/agents/user123e4567-e89b-12d3-a456-426614174000_coder/

# ❌ Запрещено (403):
GET /my/agents/user999_hacker/
```

***

## 7. 📊 ERROR RESPONSES (стандарт)

```json
{
  "detail": "Agent user456_coder not found",
  "type": "agent_not_owned",
  "user_id": 123,
  "requested_agent": "user456_coder"
}
```

**HTTP Codes:**
```
200 OK     - Успех
201 Created - Создано
400 Bad Request - Неверные данные
403 Forbidden - Не свои агенты
404 Not Found - Ресурс не найден
429 Too Many Requests - Rate limit
500 Internal - Серверная ошибка
```

***

## 8. 🧪 SWAGGER /my/docs

```
Автогенерируемая документация:
├── Agents (5 endpoints)
├── Orchestrators (3)
├── Chat (6) ← CORE
├── Approvals (3)
└── Context (2)

Interactive SSE tester
Schema validation
Rate limit info
```

***

## 9. 📈 PERFORMANCE SLA

```
Direct call:     P95 < 2s
Orchestrator:    P95 < 8s
Qdrant search:   P95 < 50ms
SSE latency:     P99 < 100ms
Approval flow:   < 5s end-to-end
```

***

## 10. 🔗 SDK INTEGRATION EXAMPLE

```javascript
// npm i personal-ai-sdk
import { PersonalAI } from 'personal-ai-sdk';

const ai = new PersonalAI('user123_jwt');

await ai.createAgent({
  name: 'Мой аналитик',
  system_prompt: 'Data analyst'
});

const mathAgent = await ai.getAgent('user123_math_v1');
const result = await mathAgent.chat('Интеграл sin(x)');  // Direct call
```

***

**ЭТА API СПЕЦИФИКАЦИЯ ПОКРЫВАЕТ 100% ТЗ v1.0**

```
✅ Полная изоляция /my/*
✅ Direct calls + Orchestrator
✅ SSE real-time
✅ Approval workflow
✅ Agent context management
✅ Type-safe schemas
✅ Production-ready errors
✅ Swagger docs ready
✅ SDK friendly
```

**Готово к разработке!** 📋🚀✨