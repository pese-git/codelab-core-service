# Управление LLM провайдерами через LiteLLM REST API

## Обзор

LiteLLM сервис в `docker-compose.yml` предоставляет REST API для динамического добавления, обновления и удаления LLM провайдеров без перезагрузки сервиса.

## Быстрый старт

### 1. Запуск контейнеров

```bash
docker-compose up -d litellm redis postgres
```

LiteLLM будет доступен на `http://localhost:4000`

### 2. Проверка здоровья

```bash
curl http://localhost:4000/health
```

## REST API для управления провайдерами

### Добавление нового провайдера

**Endpoint:** `POST /model/new`

**Пример: Добавление OpenAI провайдера**

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

**Пример: Добавление Anthropic Claude провайдера**

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

**Пример: Добавление Azure OpenAI**

```bash
curl -X POST http://localhost:4000/model/new \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer super-secret-key-change-in-production" \
  -d '{
    "model_name": "azure-gpt-4",
    "litellm_params": {
      "model": "azure/gpt-4",
      "api_key": "your-azure-api-key",
      "api_base": "https://your-resource.openai.azure.com/",
      "api_version": "2024-02-15-preview"
    }
  }'
```

**Пример: Добавление OpenRouter**

```bash
curl -X POST http://localhost:4000/model/new \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer super-secret-key-change-in-production" \
  -d '{
    "model_name": "openrouter-gpt4",
    "litellm_params": {
      "model": "openrouter/openai/gpt-4-turbo",
      "api_key": "sk-or-v1-your-openrouter-api-key"
    }
  }'
```

**Пример: Добавление Cohere**

```bash
curl -X POST http://localhost:4000/model/new \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer super-secret-key-change-in-production" \
  -d '{
    "model_name": "cohere-command",
    "litellm_params": {
      "model": "cohere/command-r-plus",
      "api_key": "your-cohere-api-key"
    }
  }'
```

### Список всех добавленных моделей

**Endpoint:** `GET /models`

```bash
curl http://localhost:4000/models \
  -H "Authorization: Bearer super-secret-key-change-in-production"
```

**Ответ:**

```json
{
  "data": [
    {
      "model_name": "gpt-4-turbo",
      "litellm_params": {
        "model": "openai/gpt-4-turbo-preview",
        "api_key": "sk-***"
      }
    },
    {
      "model_name": "claude-3-opus",
      "litellm_params": {
        "model": "anthropic/claude-3-opus-20240229",
        "api_key": "sk-***"
      }
    }
  ]
}
```

### Тестирование модели

**Endpoint:** `POST /chat/completions`

```bash
curl -X POST http://localhost:4000/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer super-secret-key-change-in-production" \
  -d '{
    "model": "gpt-4-turbo",
    "messages": [
      {
        "role": "user",
        "content": "Hello, how are you?"
      }
    ],
    "max_tokens": 100
  }'
```

### Использование в core-service

Приложение должно обращаться к LiteLLM вместо прямого обращения к OpenAI:

```python
from openai import AsyncOpenAI

# Конфигурация из docker-compose
client = AsyncOpenAI(
    api_key="your-api-key",  # Может быть любой, LiteLLM не проверяет
    base_url="http://litellm:4000"  # URL LiteLLM в Docker сети
)

# Использование как обычно
response = await client.chat.completions.create(
    model="gpt-4-turbo",  # Имя модели, добавленное через REST API
    messages=[
        {"role": "user", "content": "Hello"}
    ]
)
```

## Переменные окружения

### Для app сервиса

```env
# URL LiteLLM прокси (автоматически установлена в docker-compose)
LITELLM_URL=http://litellm:4000

# Ключ для OpenAI клиента (может быть любой)
OPENAI_API_KEY=sk-local-test-key
```

### Для LiteLLM сервиса

```env
# Мастер ключ для управления провайдерами через API
# ВАЖНО: Измените на production!
LITELLM_MASTER_KEY=super-secret-key-change-in-production

# Redis для кэширования
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=1

# Уровень логирования
LITELLM_LOG=DEBUG
```

## Поддерживаемые провайдеры

### OpenAI
- `gpt-4-turbo-preview`
- `gpt-4`
- `gpt-3.5-turbo`
- Embeddings: `text-embedding-3-small`, `text-embedding-3-large`

**Ключи:** https://platform.openai.com/api-keys

### Anthropic (Claude)
- `claude-3-opus-20240229`
- `claude-3-sonnet-20240229`
- `claude-3-haiku-20240307`

**Ключи:** https://console.anthropic.com

### Azure OpenAI
Требует `api_base` и `api_version`

**Документация:** https://learn.microsoft.com/en-us/azure/ai-services/openai/

### Google Vertex AI
- `gemini-pro`
- `gemini-1.5-pro`

**Документация:** https://cloud.google.com/vertex-ai

### Cohere
- `command-r-plus`
- `command-r`

**Ключи:** https://dashboard.cohere.com

### Ollama (локальный)
```json
{
  "model_name": "local-mistral",
  "litellm_params": {
    "model": "ollama/mistral",
    "api_base": "http://ollama:11434"
  }
}
```

## Кэширование

LiteLLM автоматически кэширует запросы в Redis. Параметры:

- **Host:** `redis` (в Docker сети)
- **Port:** `6379`
- **DB:** `1` (отдельно от основного Redis)

Кэширование полезно для:
- Снижения расходов на API
- Ускорения ответов на повторяющиеся запросы
- Работы в offline режиме для кэшированных запросов

## Примеры интеграции

### Python

```python
import os
from openai import AsyncOpenAI

litellm_url = os.getenv("LITELLM_URL", "http://litellm:4000")

client = AsyncOpenAI(
    api_key="local",
    base_url=litellm_url
)

async def chat(message: str, model: str = "gpt-4-turbo"):
    response = await client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": message}],
        temperature=0.7,
        max_tokens=500
    )
    return response.choices[0].message.content
```

### cURL скрипт для добавления провайдеров

```bash
#!/bin/bash

LITELLM_URL="http://localhost:4000"
MASTER_KEY="super-secret-key-change-in-production"

add_provider() {
  local model_name=$1
  local provider=$2
  local model_id=$3
  local api_key=$4
  
  curl -X POST "$LITELLM_URL/model/new" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $MASTER_KEY" \
    -d "{
      \"model_name\": \"$model_name\",
      \"litellm_params\": {
        \"model\": \"$provider/$model_id\",
        \"api_key\": \"$api_key\"
      }
    }"
}

# Добавление провайдеров
add_provider "gpt-4" "openai" "gpt-4-turbo-preview" "$OPENAI_API_KEY"
add_provider "claude-opus" "anthropic" "claude-3-opus-20240229" "$ANTHROPIC_API_KEY"
```

## Безопасность

### Production рекомендации

1. **Измените мастер ключ:**
   ```bash
   export LITELLM_MASTER_KEY=$(openssl rand -base64 32)
   ```

2. **Используйте HTTPS:**
   ```yaml
   litellm:
     # Добавьте nginx прокси или используйте traefik
   ```

3. **Ограничьте доступ:**
   - Не открывайте порт 4000 в интернет
   - Используйте firewall rules
   - Требуйте аутентификацию

4. **Ротация ключей:**
   - Регулярно обновляйте API ключи провайдеров
   - Используйте Vault или аналог для хранения

## Логирование и мониторинг

### Просмотр логов

```bash
docker-compose logs -f litellm
```

### Метрики

LiteLLM предоставляет Prometheus метрики на `/metrics`:

```bash
curl http://localhost:4000/metrics
```

## Troubleshooting

### Ошибка: "Invalid API key"

Проверьте, что API ключ корректен:
- OpenAI: должен начинаться с `sk-`
- Anthropic: должен начинаться с `sk-ant-`

### Ошибка: "Unauthorized"

Проверьте мастер ключ в заголовке `Authorization`:
```bash
curl -H "Authorization: Bearer YOUR_MASTER_KEY"
```

### LiteLLM не запускается

Проверьте логи:
```bash
docker-compose logs litellm
```

Убедитесь, что Redis доступен:
```bash
docker-compose logs redis
```

### Медленные запросы

Проверьте:
1. Кэширование включено
2. Redis работает нормально
3. Наличие сетевой задержки между сервисами

## Дополнительные ресурсы

- [LiteLLM Documentation](https://docs.litellm.ai/)
- [LiteLLM API Reference](https://docs.litellm.ai/docs/api)
- [Поддерживаемые провайдеры](https://docs.litellm.ai/docs/providers)
