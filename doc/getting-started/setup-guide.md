# 🚀 Руководство по настройке и запуску

## Быстрый старт

### 1. Запуск инфраструктуры

```bash
# Запустить все сервисы (PostgreSQL, Redis, Qdrant, приложение)
docker-compose up -d

# Проверить статус
docker ps
```

### 2. Инициализация базы данных

```bash
# Применить миграции
docker exec codelab-core-service alembic upgrade head

# Создать тестовых пользователей и агентов
docker exec codelab-core-service python scripts/init_db.py seed
```

### 3. Получение JWT токена

После создания пользователя, получите JWT токен:

```bash
# Получить список пользователей
docker exec codelab-postgres psql -U postgres -d codelab -c "SELECT id, email FROM users;"

# Сгенерировать JWT токен для пользователя (замените USER_ID)
docker exec codelab-core-service python scripts/generate_test_jwt.py --user-id USER_ID --expire 3600
```

Пример вывода:
```
Token:
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI1YWM3YjFkNC01MjFlLTRmYmUtYWUxNy0wMWVjYzk5ZGZjYjkiLCJpYXQiOjE3NzA5MjQwMDUsImV4cCI6MTc3MTE0MDAwNX0.WyGh0b8WYlb5dAvUXSC04asPanoXFiZ4fApHym0fYVo
```

### 4. Тестирование API

#### 4.1 Создание проекта

```bash
# Установить токен в переменную
export TOKEN="your-jwt-token-here"

# Создать новый проект
curl -X POST "http://localhost:8000/my/projects/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My First Project",
    "workspace_path": "/Users/john/projects/first"
  }' | jq .

# Сохранить ID проекта (из ответа, поле "id")
export PROJECT_ID="550e8400-e29b-41d4-a716-446655440000"
```

Ожидаемый ответ:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": "123e4567-e89b-12d3-a456-426614174000",
  "name": "My First Project",
  "workspace_path": "/Users/john/projects/first",
  "created_at": "2026-02-18T05:30:00Z",
  "updated_at": "2026-02-18T05:30:00Z"
}
```

#### 4.2 Просмотр агентов проекта

```bash
# Получить список агентов (автоматически созданы Starter Pack)
curl -X GET "http://localhost:8000/my/projects/$PROJECT_ID/agents/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" | jq .

# Ожидается: CodeAssistant, DataAnalyst, DocumentWriter
```

#### 4.3 Создание нового агента

```bash
# Создать нового пользовательского агента в проекте
curl -X POST "http://localhost:8000/my/projects/$PROJECT_ID/agents/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "MyCustomAgent",
    "system_prompt": "You are a helpful AI assistant specialized in Python development",
    "model": "openrouter/openai/gpt-4.1",
    "tools": ["code_executor", "file_reader"],
    "concurrency_limit": 3,
    "temperature": 0.7,
    "max_tokens": 4096,
    "metadata": {"specialty": "python"}
  }' | jq .
```

#### 4.4 Создание чат-сессии

```bash
# Создать новую сессию чата в проекте
curl -X POST "http://localhost:8000/my/projects/$PROJECT_ID/chat/sessions/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{}' | jq .

# Сохранить ID сессии (из ответа, поле "id")
export SESSION_ID="550e8400-e29b-41d4-a716-446655440001"
```

#### 4.5 Отправка сообщения агенту

```bash
# Режим 1: Прямой вызов конкретного агента ⚡ (быстрый, 1-2 сек)
curl -X POST "http://localhost:8000/my/projects/$PROJECT_ID/chat/$SESSION_ID/message/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Write me a Python function to validate email",
    "target_agent": "MyCustomAgent"
  }' | jq .

# Режим 2: Автоматический 🧠 (медленнее, 5-10 сек, оркестратор анализирует)
curl -X POST "http://localhost:8000/my/projects/$PROJECT_ID/chat/$SESSION_ID/message/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Plan and implement a complete REST API with authentication"
  }' | jq .
```

#### 4.6 Получение истории чата

```bash
# Получить все сообщения из сессии
curl -X GET "http://localhost:8000/my/projects/$PROJECT_ID/chat/sessions/$SESSION_ID/messages/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" | jq .
```

## Использование Gradio UI

### Установка зависимостей

```bash
pip install -r scripts/requirements-gradio.txt
```

### Запуск UI

```bash
python scripts/gradio_ui.py
```

Откройте браузер: http://localhost:7860

**Важно:** Используйте JWT токен, полученный на шаге 3, для аутентификации в UI.

## Проверка здоровья сервисов

```bash
# Проверить статус контейнеров
docker ps

# Проверить логи приложения
docker logs codelab-core-service --tail 50

# Проверить health endpoint
curl http://localhost:8000/health

# Проверить readiness endpoint (проверяет все зависимости)
curl http://localhost:8000/ready

# Проверить подключение к PostgreSQL
docker exec codelab-postgres psql -U postgres -d codelab -c "SELECT version();"

# Проверить подключение к Redis
docker exec codelab-redis redis-cli ping

# Проверить подключение к Qdrant
curl http://localhost:6333/collections
```

## Типичные проблемы и решения

### ❌ Ошибка: "404 Project not found"

**Причина:** Проект не существует или ID неверный.

**Решение:**
```bash
# 1. Проверить список проектов
curl -X GET "http://localhost:8000/my/projects/" \
  -H "Authorization: Bearer $TOKEN" | jq .

# 2. Убедиться, что используется правильный PROJECT_ID
export PROJECT_ID="<копировать из списка выше>"
```

### ❌ Ошибка: "500 Internal Server Error" при создании проекта

**Причина:** Пользователь не существует в базе данных или ошибка конфигурации.

**Решение:**
```bash
# 1. Создать пользователя через seed скрипт
docker exec codelab-core-service python scripts/init_db.py seed

# 2. Или создать пользователя вручную
docker exec codelab-postgres psql -U postgres -d codelab -c \
  "INSERT INTO users (id, email) VALUES ('YOUR-UUID-HERE', 'user@example.com');"

# 3. Сгенерировать JWT токен для этого пользователя
docker exec codelab-core-service python scripts/generate_test_jwt.py --user-id YOUR-UUID-HERE
```

### ❌ Ошибка: "Invalid or expired token"

**Причина:** JWT токен истек или неверный.

**Решение:**
```bash
# Сгенерировать новый токен с большим временем жизни (3600 секунд = 1 час)
docker exec codelab-core-service python scripts/generate_test_jwt.py \
  --user-id YOUR-UUID-HERE --expire 3600
```

### ❌ Ошибка: "Connection refused" к Qdrant/Redis

**Причина:** Сервисы не запущены.

**Решение:**
```bash
# Запустить все сервисы
docker-compose up -d

# Проверить статус
docker ps --filter "name=codelab"

# Если конкретный сервис не запущен, перезапустить все
docker-compose restart
```

### ❌ Ошибка: "ForeignKeyViolationError" при создании проекта

**Причина:** Пользователь не существует в таблице `users`.

**Решение:** См. проблему "500 Internal Server Error" выше.

### ❌ Ошибка: "Agent not found" при отправке сообщения

**Причина:** Агент с таким именем не существует в проекте или имя неверно.

**Решение:**
```bash
# Проверить список агентов в проекте
curl -X GET "http://localhost:8000/my/projects/$PROJECT_ID/agents/" \
  -H "Authorization: Bearer $TOKEN" | jq '.agents[].name'

# Использовать точное имя агента в target_agent
```

## Переменные окружения

Скопируйте `.env.example` в `.env` и настройте:

```bash
cp .env.example .env
```

Основные переменные:

```env
# OpenAI API (обязательно для работы агентов)
OPENAI_API_KEY=sk-your-api-key-here

# LiteLLM (опционально, для использования собственного LLM прокси)
OPENAI_BASE_URL=http://localhost:4000  # URL вашего LiteLLM сервера
OPENAI_MODEL=openrouter/openai/gpt-4.1  # Модель, поддерживаемая вашим LiteLLM

# JWT секрет (измените в продакшене!)
JWT_SECRET_KEY=your-secret-key-change-in-production

# База данных
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/codelab

# Redis
REDIS_URL=redis://localhost:6379/0

# Qdrant
QDRANT_URL=http://localhost:6333

# Debug режим (выключить в продакшене)
DEBUG=false
```

### Использование LiteLLM

Если у вас есть собственный LiteLLM сервер:

1. Запустите LiteLLM:
   ```bash
   litellm --port 4000
   ```

2. Настройте переменные окружения:
   ```env
   OPENAI_API_KEY=your-litellm-api-key
   OPENAI_BASE_URL=http://localhost:4000
   OPENAI_MODEL=gpt-4  # или любая модель, поддерживаемая вашим LiteLLM
   ```

3. Перезапустите сервис:
   ```bash
   docker-compose restart codelab-core-service
   ```

## Swagger UI

Откройте http://localhost:8000/docs для интерактивной документации API.

1. Нажмите кнопку **"Authorize"** 🔓
2. Вставьте JWT токен (БЕЗ префикса 'Bearer')
3. Нажмите **"Authorize"**
4. Теперь можете тестировать все endpoints

### Примеры в Swagger:

1. **POST /my/projects/** - Создать проект
   - Вставьте JSON с `name` и `workspace_path`
   - Получите ID проекта

2. **GET /my/projects/{project_id}/agents/** - Список агентов
   - Подставьте `project_id` из шага 1
   - Увидите Starter Pack агентов

3. **POST /my/projects/{project_id}/chat/sessions/** - Создать сессию
   - Подставьте `project_id`
   - Получите `session_id`

4. **POST /my/projects/{project_id}/chat/{session_id}/message/** - Отправить сообщение
   - Подставьте `project_id` и `session_id`
   - Вставьте message с `content` и опциональным `target_agent`

## Практический пример: Полный цикл

```bash
#!/bin/bash

# Установить переменные
export TOKEN="your-jwt-token-here"
export BASE_URL="http://localhost:8000"

# Шаг 1: Создать проект
PROJECT=$(curl -s -X POST "$BASE_URL/my/projects/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Demo Project",
    "workspace_path": "/workspace/demo"
  }')

PROJECT_ID=$(echo $PROJECT | jq -r '.id')
echo "Created project: $PROJECT_ID"

# Шаг 2: Создать сессию
SESSION=$(curl -s -X POST "$BASE_URL/my/projects/$PROJECT_ID/chat/sessions/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{}')

SESSION_ID=$(echo $SESSION | jq -r '.id')
echo "Created session: $SESSION_ID"

# Шаг 3: Отправить сообщение
MESSAGE=$(curl -s -X POST "$BASE_URL/my/projects/$PROJECT_ID/chat/$SESSION_ID/message/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Write a Python function to calculate factorial",
    "target_agent": "CodeAssistant"
  }')

echo "Message response:"
echo $MESSAGE | jq .

# Шаг 4: Получить историю
HISTORY=$(curl -s -X GET "$BASE_URL/my/projects/$PROJECT_ID/chat/sessions/$SESSION_ID/messages/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json")

echo "Chat history:"
echo $HISTORY | jq '.messages[] | "\(.role): \(.content)"'
```

## Дополнительные ресурсы

- [REST API документация](./rest-api.md)
- [SSE Event Streaming](./sse-event-streaming.md)
- [Gradio Client документация](../scripts/GRADIO_CLIENT.md)
- [Технические требования](../guides/technical-requirements.md)
- [Architecture Overview](./architecture/system-overview.md)
