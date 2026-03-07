# 🔌 Интеграция внутреннего LiteLLM с Docker Compose

## Обзор

Сервис `codelab-core-service` интегрирован с локальным LiteLLM прокси, запущенным в docker-compose. Это позволяет:

- ✅ Управлять несколькими LLM провайдерами через единый API
- ✅ Кэшировать запросы через Redis
- ✅ Логировать все обращения к LLM
- ✅ Добавлять новые провайдеры без перезагрузки сервиса
- ✅ Использовать альтернативные модели (OpenAI, Anthropic, Azure, OpenRouter, и др.)

---

## 🏗️ Архитектура

```
┌─────────────────────────────────────┐
│   codelab-core-service (app)        │
│  - OpenAI AsyncClient               │
│  - Contextual Agents                │
│  - Agent Context Store              │
└──────────────────┬──────────────────┘
                   │ HTTP requests
                   │ OPENAI_BASE_URL=http://litellm:4000
                   ↓
┌─────────────────────────────────────┐
│   LiteLLM Proxy (litellm)           │
│  - REST API для управления          │
│  - Динамическое добавление моделей │
│  - Redis кэширование               │
│  - PostgreSQL управление ключами    │
└──────────────────┬──────────────────┘
                   │
        ┌──────────┼──────────┐
        ↓          ↓          ↓
     OpenAI    Anthropic   Azure
     API        API        OpenAI
```

---

## 📋 Конфигурация

### 1. Переменные окружения (`.env`)

```env
# OpenAI / LiteLLM - указываем на внутренний сервис
OPENAI_API_KEY=sk-your-api-key  # Ключ для доступа к LLM
OPENAI_BASE_URL=http://litellm:4000  # ✅ Внутренний LiteLLM в docker-compose
OPENAI_MODEL=openrouter/openai/gpt-4.1
OPENAI_EMBEDDING_MODEL=openai/text-embedding-3-small
OPENAI_MAX_RETRIES=3
OPENAI_TIMEOUT=60

# LiteLLM Proxy Configuration
LITELLM_MASTER_KEY=super-secret-key-change-in-production
LITELLM_REDIS_HOST=redis
LITELLM_REDIS_PORT=6379
LITELLM_REDIS_DB=1
LITELLM_CACHE=true
LITELLM_TELEMETRY=false
```

### 2. Docker Compose (`docker-compose.yml`)

#### LiteLLM сервис (строки 100-141)

```yaml
litellm:
  image: ghcr.io/berriai/litellm:main-latest
  container_name: codelab-litellm
  ports:
    - "4000:4000"
  environment:
    LITELLM_MASTER_KEY: ${LITELLM_MASTER_KEY:-super-secret-key-change-in-production}
    DATABASE_URL: postgresql://postgres:postgres@postgres:5432/litellm
    STORE_MODEL_IN_DB: "True"
    REDIS_HOST: redis
    REDIS_PORT: 6379
    REDIS_DB: 1
    REDIS_URL: redis://redis:6379/1
    LITELLM_LOG: INFO
    CACHE: "true"
  depends_on:
    postgres:
      condition: service_healthy
    redis:
      condition: service_healthy
  healthcheck:
    test: ["CMD", "sh", "-c", "curl -s http://localhost:4000/health/readiness | grep -q healthy"]
    interval: 30s
    timeout: 10s
    retries: 10
    start_period: 45s
  restart: unless-stopped
  command: >
    --port 4000
    --telemetry false
```

#### App сервис зависит от LiteLLM (строки 143-186)

```yaml
app:
  build:
    context: .
    dockerfile: Dockerfile
  container_name: codelab-core-service
  ports:
    - "8000:8000"
  volumes:
    - .:/app
  environment:
    # ... другие переменные ...
    LITELLM_URL: http://litellm:4000  # ← Подсказка для дополнительных операций
    PYTHONUNBUFFERED: 1
  env_file:
    - .env
  depends_on:
    postgres:
      condition: service_healthy
    redis:
      condition: service_healthy
    litellm:
      condition: service_started  # ← Ждем старта LiteLLM перед запуском app
```

### 3. Код интеграции

#### Contextual Agent (`app/agents/contextual_agent.py:57-61`)

```python
# Инициализация OpenAI клиента с поддержкой LiteLLM
client_kwargs = {"api_key": settings.openai_api_key}
if settings.openai_base_url:
    client_kwargs["base_url"] = settings.openai_base_url
self.openai_client = openai.AsyncOpenAI(**client_kwargs)
```

#### Agent Context Store (`app/vectorstore/agent_context_store.py:35-39`)

```python
# То же самое для embeddings
client_kwargs = {"api_key": settings.openai_api_key}
if settings.openai_base_url:
    client_kwargs["base_url"] = settings.openai_base_url
self.openai_client = openai.AsyncOpenAI(**client_kwargs)
```

#### Конфигурация (`app/config.py:61-67`)

```python
# OpenAI / LiteLLM
openai_api_key: str = Field(default="")
openai_base_url: str | None = Field(default=None)  # ← Автоматически используется если установлено
openai_model: str = Field(default="openrouter/openai/gpt-4.1")
openai_embedding_model: str = Field(default="text-embedding-3-small")
openai_max_retries: int = Field(default=3)
openai_timeout: int = Field(default=60)
```

---

## 🚀 Запуск

### Вариант 1: Полная стэк (Development)

```bash
# Запустить все сервисы
docker-compose up -d

# Проверить статус
docker-compose ps

# Просмотреть логи
docker-compose logs -f app
docker-compose logs -f litellm
```

### Вариант 2: Минимальный стэк (для тестирования)

```bash
# Запустить только необходимые сервисы
docker-compose up -d postgres redis litellm app

# Проверить LiteLLM здоровье
docker-compose logs litellm | grep -i health
```

### Вариант 3: Разработка без Docker

```bash
# Если вам нужно запустить только внешние сервисы
docker-compose up -d postgres redis litellm

# Установить зависимости и запустить локально
pip install -r requirements.txt
export $(cat .env | xargs)
uvicorn app.main:app --reload
```

---

## ✅ Проверка интеграции

### 1. Проверить доступность LiteLLM

```bash
# Проверить health endpoint
curl -s http://localhost:4000/health | jq .

# Ожидаемый ответ:
# {
#   "status": "healthy"
# }
```

### 2. Проверить доступность сервиса

```bash
# Проверить health сервиса
curl -s http://localhost:8000/health | jq .

# Ожидаемый ответ:
# {
#   "status": "ok"
# }
```

### 3. Проверить логи

```bash
# Посмотреть логи LiteLLM
docker-compose logs litellm | tail -50

# Посмотреть логи app
docker-compose logs app | tail -50
```

### 4. Проверить соединение (через REST API)

```bash
# Попробовать создать chat completion через LiteLLM API
curl -X POST http://localhost:4000/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4-turbo-preview",
    "messages": [
      {"role": "user", "content": "Hello!"}
    ]
  }'
```

---

## 🔧 Управление провайдерами

### Добавить новый провайдер (OpenAI)

```bash
curl -X POST http://localhost:4000/model/new \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer super-secret-key-change-in-production" \
  -d '{
    "model_name": "gpt-4-turbo",
    "litellm_params": {
      "model": "openai/gpt-4-turbo-preview",
      "api_key": "sk-your-openai-api-key"
    }
  }'
```

### Добавить Anthropic Claude

```bash
curl -X POST http://localhost:4000/model/new \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer super-secret-key-change-in-production" \
  -d '{
    "model_name": "claude-3-opus",
    "litellm_params": {
      "model": "anthropic/claude-3-opus-20240229",
      "api_key": "sk-ant-your-anthropic-api-key"
    }
  }'
```

### Добавить OpenRouter

```bash
curl -X POST http://localhost:4000/model/new \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer super-secret-key-change-in-production" \
  -d '{
    "model_name": "openrouter/openai/gpt-4.1",
    "litellm_params": {
      "model": "openrouter/openai/gpt-4-turbo-2024-04-09",
      "api_key": "sk-or-v1-your-openrouter-key"
    }
  }'
```

### Получить список всех моделей

```bash
curl -X GET http://localhost:4000/models \
  -H "Authorization: Bearer super-secret-key-change-in-production"
```

### Удалить провайдер

```bash
curl -X DELETE http://localhost:4000/model/delete \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer super-secret-key-change-in-production" \
  -d '{
    "model_name": "gpt-4-turbo"
  }'
```

---

## 🧪 Тестирование

### Создать агента и отправить сообщение

```bash
# 1. Получить JWT токен (замените на свой)
TOKEN="your-jwt-token"

# 2. Создать проект
curl -X POST http://localhost:8000/projects \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Project"
  }'

# 3. Создать агента
curl -X POST http://localhost:8000/projects/1/agents \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "TestAgent",
    "system_prompt": "You are a helpful assistant",
    "model": "gpt-4-turbo-preview",
    "temperature": 0.7
  }'

# 4. Отправить сообщение
curl -X POST http://localhost:8000/projects/1/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": 1,
    "content": "Hello, how can you help me?"
  }'
```

---

## 🔍 Логирование и мониторинг

### LiteLLM логи

```bash
# Следить за логами LiteLLM в реальном времени
docker-compose logs -f litellm
```

### App логи

```bash
# Следить за логами app в реальном времени
docker-compose logs -f app
```

### Prometheus метрики

```bash
# Доступны на http://localhost:9090
# Метрики LiteLLM можно добавить через Prometheus в docker-compose.yml
```

---

## ⚠️ Troubleshooting

### LiteLLM не запускается

```bash
# Проверить логи
docker-compose logs litellm

# Убедиться, что PostgreSQL и Redis готовы
docker-compose logs postgres redis
```

### Ошибка: "Cannot reach LiteLLM"

```bash
# Проверить, что контейнер работает
docker-compose ps litellm

# Проверить, что приложение видит LiteLLM
docker-compose exec app curl http://litellm:4000/health

# Проверить сетевые интерфейсы
docker network ls
docker network inspect codelab-core-service_default
```

### Ошибка аутентификации при добавлении провайдера

```bash
# Убедиться, что используется правильный мастер ключ
echo $LITELLM_MASTER_KEY

# Если не установлен, использовать значение по умолчанию
MASTER_KEY="super-secret-key-change-in-production"
```

### Redis кэш не работает

```bash
# Проверить Redis доступность
docker-compose exec redis redis-cli ping

# Проверить LiteLLM Redis конфигурацию
docker-compose logs litellm | grep -i redis
```

---

## 📊 Переменные окружения (Полный справочник)

| Переменная | Значение | Назначение |
|---|---|---|
| `OPENAI_API_KEY` | sk-... | API ключ для доступа к LLM провайдеру |
| `OPENAI_BASE_URL` | http://litellm:4000 | ⭐ Адрес внутреннего LiteLLM прокси |
| `OPENAI_MODEL` | openrouter/openai/gpt-4.1 | Основная модель для агентов |
| `OPENAI_EMBEDDING_MODEL` | openai/text-embedding-3-small | Модель для создания embeddings |
| `OPENAI_MAX_RETRIES` | 3 | Количество повторов при ошибке |
| `OPENAI_TIMEOUT` | 60 | Таймаут в секундах |
| `LITELLM_MASTER_KEY` | super-secret-key-... | Мастер ключ для управления моделями |
| `LITELLM_REDIS_HOST` | redis | Redis хост в docker-compose |
| `LITELLM_REDIS_PORT` | 6379 | Redis порт |
| `LITELLM_REDIS_DB` | 1 | Redis БД для кэша |
| `LITELLM_CACHE` | true | Включить кэширование |
| `LITELLM_TELEMETRY` | false | Отключить телеметрию |

---

## 🎯 Best Practices

1. **Всегда используйте `OPENAI_BASE_URL=http://litellm:4000`** для docker-compose окружения
2. **Установите `LITELLM_MASTER_KEY`** в production окружении
3. **Кэшируйте запросы** через Redis для снижения затрат
4. **Мониторьте логи** LiteLLM и app для отладки
5. **Тестируйте новые провайдеры** перед использованием в production
6. **Регулярно обновляйте** образ LiteLLM (`ghcr.io/berriai/litellm:main-latest`)

---

## 📚 Дополнительные ресурсы

- [LiteLLM документация](https://docs.litellm.ai/)
- [LiteLLM REST API](https://docs.litellm.ai/docs/routing)
- [Поддерживаемые провайдеры](https://docs.litellm.ai/docs/providers)
- [Кэширование в LiteLLM](https://docs.litellm.ai/docs/caching)
- [Docker Compose для LiteLLM](https://docs.litellm.ai/docs/deployment/proxy/deploy)
