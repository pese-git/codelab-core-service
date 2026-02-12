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

```bash
# Установить токен в переменную
export TOKEN="your-jwt-token-here"

# Получить список агентов
curl -X GET "http://localhost:8000/my/agents/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" | jq .

# Создать нового агента
curl -X POST "http://localhost:8000/my/agents/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "MyAgent",
    "system_prompt": "You are a helpful assistant",
    "model": "gpt-4-turbo-preview",
    "tools": [],
    "concurrency_limit": 3,
    "temperature": 0.7,
    "max_tokens": 4096,
    "metadata": {}
  }' | jq .
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

# Проверить подключение к PostgreSQL
docker exec codelab-postgres psql -U postgres -d codelab -c "SELECT version();"

# Проверить подключение к Redis
docker exec codelab-redis redis-cli ping

# Проверить подключение к Qdrant
curl http://localhost:6333/collections
```

## Типичные проблемы и решения

### ❌ Ошибка: "500 Internal Server Error" при создании агента

**Причина:** Пользователь с указанным `user_id` не существует в базе данных.

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
```

### ❌ Ошибка: "ForeignKeyViolationError" при создании агента

**Причина:** Пользователь не существует в таблице `users`.

**Решение:** См. первую проблему выше.

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
OPENAI_MODEL=gpt-4-turbo-preview        # Модель, поддерживаемая вашим LiteLLM
OPENAI_EMBEDDING_MODEL=text-embedding-3-small

# JWT секрет (измените в продакшене!)
JWT_SECRET_KEY=your-secret-key-change-in-production

# База данных
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/codelab

# Redis
REDIS_URL=redis://localhost:6379/0

# Qdrant
QDRANT_URL=http://localhost:6333
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

## Дополнительные ресурсы

- [REST API документация](./rest-api.md)
- [SSE Event Streaming](./sse-event-streaming.md)
- [Gradio Client документация](../scripts/GRADIO_CLIENT.md)
- [Технические требования](./techincal-requrements.md)
