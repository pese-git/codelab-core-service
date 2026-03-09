# LLM Providers Management API

Управление несколькими LLM провайдерами через единый REST API.

## Обзор

Платформа позволяет пользователям добавлять и управлять несколькими LLM провайдерами:
- **OpenAI** (GPT-4, GPT-3.5)
- **Anthropic** (Claude 3)
- **Google** (Gemini)
- **Cohere**
- **Azure OpenAI**
- И другие провайдеры через LiteLLM

## Ключевые особенности

✅ **Безопасное хранение** - API ключи НЕ логируются и НЕ хранятся в PostgreSQL
✅ **Изоляция пользователей** - Каждый пользователь видит только своих провайдеров
✅ **Тестирование подключения** - Проверка работоспособности провайдера перед использованием
✅ **Аудит логирование** - Все операции логируются с IP адресом и user agent
✅ **Использование провайдеров** - Отслеживание какой провайдер используется какими агентами
✅ **Запрет изменения ключа** - API ключ можно только удалить и создать заново
✅ **Resilience** - Автоматические retry с exponential backoff (макс 3 попытки, 1s начальная задержка)

## API Endpoints

### Добавить LLM провайдер

**POST** `/my/llm-providers`

Регистрирует новый LLM провайдер для пользователя в LiteLLM.

**Request:**
```json
{
  "provider_type": "openai",
  "display_name": "My OpenAI GPT-4",
  "api_key": "sk-your-api-key-here",
  "config": {
    "model": "gpt-4o",
    "max_tokens": 2048,
    "temperature": 0.7
  }
}
```

**Response: 201 Created**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": "123e4567-e89b-12d3-a456-426614174000",
  "provider_type": "openai",
  "display_name": "My OpenAI GPT-4",
  "litellm_model_name": "user550e8400_openai_abc12345",
  "config": {
    "model": "gpt-4o",
    "max_tokens": 2048,
    "temperature": 0.7
  },
  "use_count": 0,
  "created_at": "2026-03-09T08:00:00Z",
  "updated_at": "2026-03-09T08:00:00Z"
}
```

**Ошибки:**
- 400: Invalid provider_type
- 400: Invalid configuration
- 500: LiteLLM registration failed

---

### Получить список провайдеров

**GET** `/my/llm-providers`

Получить все LLM провайдеры пользователя с пагинацией.

**Query параметры:**
- `skip`: Количество записей для пропуска (default: 0)
- `limit`: Максимум записей на странице (default: 100, max: 100)

**Response: 200 OK**
```json
{
  "providers": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "user_id": "123e4567-e89b-12d3-a456-426614174000",
      "provider_type": "openai",
      "display_name": "My OpenAI GPT-4",
      "litellm_model_name": "user550e8400_openai_abc12345",
      "config": {
        "model": "gpt-4o",
        "max_tokens": 2048,
        "temperature": 0.7
      },
      "use_count": 5,
      "last_used_at": "2026-03-09T07:45:00Z",
      "created_at": "2026-03-09T08:00:00Z",
      "updated_at": "2026-03-09T08:00:00Z"
    },
    {
      "id": "550e8400-e29b-41d4-a716-446655440001",
      "user_id": "123e4567-e89b-12d3-a456-426614174000",
      "provider_type": "anthropic",
      "display_name": "Claude 3 Opus",
      "litellm_model_name": "user550e8400_anthropic_xyz789",
      "config": {
        "model": "claude-3-opus-20240229",
        "max_tokens": 4096
      },
      "use_count": 2,
      "last_used_at": "2026-03-09T07:30:00Z",
      "created_at": "2026-03-08T14:30:00Z",
      "updated_at": "2026-03-08T14:30:00Z"
    }
  ],
  "total": 2,
  "page": 1,
  "page_size": 100,
  "total_pages": 1
}
```

---

### Получить конкретный провайдер

**GET** `/my/llm-providers/{provider_id}`

Получить детали конкретного провайдера.

**Response: 200 OK**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": "123e4567-e89b-12d3-a456-426614174000",
  "provider_type": "openai",
  "display_name": "My OpenAI GPT-4",
  "litellm_model_name": "user550e8400_openai_abc12345",
  "config": {
    "model": "gpt-4o",
    "max_tokens": 2048,
    "temperature": 0.7
  },
  "use_count": 5,
  "last_used_at": "2026-03-09T07:45:00Z",
  "created_at": "2026-03-09T08:00:00Z",
  "updated_at": "2026-03-09T08:00:00Z"
}
```

**Ошибки:**
- 404: Provider not found

---

### Обновить конфигурацию провайдера

**PATCH** `/my/llm-providers/{provider_id}`

Обновить конфигурацию провайдера (display_name, config параметры).

⚠️ **ВАЖНО:** API ключ НЕ может быть обновлён. Чтобы изменить API ключ, удалите и пересоздайте провайдер.

**Request:**
```json
{
  "display_name": "Updated Name",
  "config": {
    "model": "gpt-4-turbo",
    "max_tokens": 4096,
    "temperature": 0.5
  }
}
```

**Response: 200 OK**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": "123e4567-e89b-12d3-a456-426614174000",
  "provider_type": "openai",
  "display_name": "Updated Name",
  "litellm_model_name": "user550e8400_openai_abc12345",
  "config": {
    "model": "gpt-4-turbo",
    "max_tokens": 4096,
    "temperature": 0.5
  },
  "use_count": 5,
  "last_used_at": "2026-03-09T07:45:00Z",
  "created_at": "2026-03-09T08:00:00Z",
  "updated_at": "2026-03-09T08:15:00Z"
}
```

**Ошибки:**
- 400: Attempt to update api_key
- 404: Provider not found

---

### Удалить провайдер

**DELETE** `/my/llm-providers/{provider_id}`

Удалить LLM провайдер и его регистрацию в LiteLLM.

⚠️ **Ограничение:** Провайдер не может быть удалён, если его используют агенты.

**Response: 204 No Content**

**Ошибки:**
- 404: Provider not found
- 409: Provider in use by agents (указывает количество агентов)

---

### Тестировать подключение к провайдеру

**POST** `/my/llm-providers/{provider_id}/test`

Проверить работоспособность подключения к провайдеру, выполнив простой запрос.

**Request:**
```json
{
  "test_prompt": "Hello, how are you?",
  "max_tokens": 100
}
```

**Response: 200 OK (success)**
```json
{
  "success": true,
  "response": "Hello! I'm doing well, thank you for asking.",
  "latency_ms": 1234.5,
  "error": null
}
```

**Response: 200 OK (timeout)**
```json
{
  "success": false,
  "response": null,
  "latency_ms": null,
  "error": "Request timeout after 60 seconds"
}
```

**Response: 200 OK (auth error)**
```json
{
  "success": false,
  "response": null,
  "latency_ms": null,
  "error": "Invalid API key"
}
```

**Ошибки:**
- 404: Provider not found

---

### Получить доступные провайдеры

**GET** `/my/llm-providers/available`

Получить список всех доступных провайдеров пользователя (активные и готовые к использованию).

**Response: 200 OK**
```json
{
  "providers": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "provider_type": "openai",
      "display_name": "My OpenAI GPT-4",
      "litellm_model_name": "user550e8400_openai_abc12345"
    },
    {
      "id": "550e8400-e29b-41d4-a716-446655440001",
      "provider_type": "anthropic",
      "display_name": "Claude 3 Opus",
      "litellm_model_name": "user550e8400_anthropic_xyz789"
    }
  ],
  "total": 2,
  "page": 1,
  "page_size": 2,
  "total_pages": 1
}
```

---

### Получить типы провайдеров (PUBLIC)

**GET** `/llm-providers/types`

Получить список доступных типов LLM провайдеров.

⚠️ **PUBLIC ENDPOINT** - не требует аутентификации.

**Response: 200 OK**
```json
[
  {
    "name": "openai",
    "display_name": "OpenAI",
    "description": "OpenAI API (GPT-4, GPT-3.5, etc.)",
    "icon": "🤖",
    "required_fields": ["api_key"],
    "config_template": {
      "model": "gpt-4o",
      "max_tokens": 2048,
      "temperature": 0.7
    }
  },
  {
    "name": "anthropic",
    "display_name": "Anthropic",
    "description": "Anthropic Claude API",
    "icon": "🧠",
    "required_fields": ["api_key"],
    "config_template": {
      "model": "claude-3-opus-20240229",
      "max_tokens": 4096
    }
  },
  {
    "name": "google",
    "display_name": "Google",
    "description": "Google Gemini API",
    "icon": "🔍",
    "required_fields": ["api_key"],
    "config_template": {
      "model": "gemini-pro",
      "max_tokens": 2048
    }
  }
]
```

---

### Получить audit log операций

**GET** `/my/llm-providers/audit`

Получить историю всех операций с провайдерами.

**Query параметры:**
- `provider_id`: Фильтр по ID провайдера (optional)
- `action`: Фильтр по типу действия: `create`, `update`, `delete`, `test`, `use`, `provider_reassigned` (optional)
- `skip`: Количество записей для пропуска (default: 0)
- `limit`: Максимум записей (default: 100, max: 100)

**Response: 200 OK**
```json
{
  "entries": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440100",
      "user_id": "123e4567-e89b-12d3-a456-426614174000",
      "provider_id": "550e8400-e29b-41d4-a716-446655440000",
      "action": "create",
      "new_values": {
        "display_name": "My OpenAI GPT-4",
        "provider_type": "openai",
        "litellm_model_name": "user550e8400_openai_abc12345"
      },
      "success": true,
      "error_message": null,
      "ip_address": "203.0.113.45",
      "user_agent": "Mozilla/5.0...",
      "created_at": "2026-03-09T08:00:00Z"
    },
    {
      "id": "550e8400-e29b-41d4-a716-446655440101",
      "user_id": "123e4567-e89b-12d3-a456-426614174000",
      "provider_id": "550e8400-e29b-41d4-a716-446655440000",
      "action": "test",
      "success": true,
      "error_message": null,
      "ip_address": "203.0.113.45",
      "user_agent": "Mozilla/5.0...",
      "created_at": "2026-03-09T08:05:00Z"
    },
    {
      "id": "550e8400-e29b-41d4-a716-446655440102",
      "user_id": "123e4567-e89b-12d3-a456-426614174000",
      "provider_id": "550e8400-e29b-41d4-a716-446655440000",
      "action": "use",
      "new_values": {
        "use_count": 1,
        "last_used_at": "2026-03-09T08:10:00Z"
      },
      "success": true,
      "error_message": null,
      "created_at": "2026-03-09T08:10:00Z"
    }
  ],
  "total": 3,
  "page": 1,
  "page_size": 100,
  "total_pages": 1
}
```

---

## Интеграция с агентами

После добавления LLM провайдера, его можно использовать при создании или обновлении агентов:

**Создание агента с провайдером:**
```bash
POST /my/projects/{project_id}/agents/
Content-Type: application/json
Authorization: Bearer YOUR_JWT_TOKEN

{
  "name": "gpt4_agent",
  "system_prompt": "You are a helpful assistant",
  "llm_provider_id": "550e8400-e29b-41d4-a716-446655440000",
  "config": {
    "temperature": 0.7,
    "max_tokens": 2048
  }
}
```

**Изменение провайдера агента:**
```bash
PATCH /my/projects/{project_id}/agents/{agent_id}/llm-provider/
Content-Type: application/json
Authorization: Bearer YOUR_JWT_TOKEN

{
  "llm_provider_id": "550e8400-e29b-41d4-a716-446655440001"
}
```

---

## Обработка ошибок

### Retry Logic

Клиент автоматически делает retry при:
- **Timeout** - запрос занял более 60 секунд
- **Network errors** - ошибки подключения

Retry параметры:
- **Max retries:** 3 попытки
- **Initial delay:** 1 секунда
- **Backoff factor:** 2 (1s, 2s, 4s)

**Примеры:**
```
Попытка 1: Timeout → ожидание 1s
Попытка 2: Timeout → ожидание 2s
Попытка 3: Timeout → ошибка
```

### Код ошибок

| Код | Описание |
|-----|----------|
| 400 | Invalid provider_type или configuration |
| 400 | Attempt to update api_key |
| 401 | Unauthorized (missing/invalid token) |
| 404 | Provider not found |
| 409 | Provider in use by agents |
| 500 | LiteLLM registration/connection failed |

---

## Примеры использования

### Пример 1: Добавить несколько провайдеров и переключаться между ними

```bash
# 1. Добавить OpenAI
curl -X POST http://localhost:8000/my/llm-providers \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "provider_type": "openai",
    "display_name": "GPT-4",
    "api_key": "sk-your-openai-key",
    "config": {"model": "gpt-4o"}
  }'

# Результат: {"id": "provider-uuid-1", ...}

# 2. Добавить Claude
curl -X POST http://localhost:8000/my/llm-providers \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "provider_type": "anthropic",
    "display_name": "Claude 3",
    "api_key": "sk-your-anthropic-key",
    "config": {"model": "claude-3-opus-20240229"}
  }'

# Результат: {"id": "provider-uuid-2", ...}

# 3. Создать агента с первым провайдером
curl -X POST http://localhost:8000/my/projects/{project_id}/agents/ \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "gpt_agent",
    "system_prompt": "You are helpful",
    "llm_provider_id": "provider-uuid-1"
  }'

# 4. Переключить агента на другой провайдер
curl -X PATCH http://localhost:8000/my/projects/{project_id}/agents/{agent_id}/llm-provider/ \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "llm_provider_id": "provider-uuid-2"
  }'
```

### Пример 2: Тестировать провайдер перед использованием

```bash
# Получить список провайдеров
curl -X GET http://localhost:8000/my/llm-providers \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"

# Тестировать провайдер
curl -X POST http://localhost:8000/my/llm-providers/provider-uuid-1/test \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "test_prompt": "Hello, what is 2+2?",
    "max_tokens": 50
  }'
```

---

## Безопасность

- 🔒 **API ключи не логируются** - Не появляются в logs, audit, или ответах
- 🔒 **API ключи не хранятся в БД** - Хранятся только в LiteLLM
- 🔒 **Полная изоляция** - Пользователь видит только своих провайдеров
- 🔒 **Audit логирование** - IP адрес и user agent записываются для каждой операции
- 🔒 **Запрет обновления ключа** - Можно только удалить и создать новый

---

## Документация

- [litellm-providers-management.md](./litellm-providers-management.md) - Детальное руководство по интеграции
- [rest-api.md](./rest-api.md) - Общая REST API документация
