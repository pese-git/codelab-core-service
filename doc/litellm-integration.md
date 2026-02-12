# 🔌 Интеграция с LiteLLM

## Обзор

Сервис поддерживает использование собственного LiteLLM прокси вместо прямого обращения к OpenAI API. Это позволяет:

- Использовать альтернативные LLM провайдеры (Anthropic, Cohere, Azure, и др.)
- Контролировать расходы и лимиты
- Кэшировать запросы
- Логировать все обращения к LLM
- Работать в регионах с ограниченным доступом к OpenAI

## Быстрая настройка

### 1. Установка LiteLLM

```bash
pip install litellm[proxy]
```

### 2. Создание конфигурации

Создайте файл `litellm_config.yaml`:

```yaml
model_list:
  - model_name: gpt-4-turbo-preview
    litellm_params:
      model: openai/gpt-4-turbo-preview
      api_key: sk-your-openai-key
      
  - model_name: claude-3-opus
    litellm_params:
      model: anthropic/claude-3-opus-20240229
      api_key: sk-ant-your-anthropic-key
      
  - model_name: text-embedding-3-small
    litellm_params:
      model: openai/text-embedding-3-small
      api_key: sk-your-openai-key

litellm_settings:
  success_callback: ["langfuse"]  # Опционально: логирование
  cache: true
  cache_params:
    type: "redis"
    host: "localhost"
    port: 6379
```

### 3. Запуск LiteLLM

```bash
litellm --config litellm_config.yaml --port 4000
```

Или через Docker:

```bash
docker run -d \
  --name litellm \
  -p 4000:4000 \
  -v $(pwd)/litellm_config.yaml:/app/config.yaml \
  ghcr.io/berriai/litellm:main-latest \
  --config /app/config.yaml --port 4000
```

### 4. Настройка сервиса

Обновите `.env`:

```env
# LiteLLM настройки
OPENAI_API_KEY=sk-your-litellm-master-key  # Или любой ключ из config
OPENAI_BASE_URL=http://localhost:4000
OPENAI_MODEL=gpt-4-turbo-preview
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
```

### 5. Перезапуск сервиса

```bash
docker-compose restart codelab-core-service
```

## Проверка работы

```bash
# Проверить доступность LiteLLM
curl http://localhost:4000/health

# Создать агента и отправить сообщение
curl -X POST "http://localhost:8000/my/agents/" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "name": "TestAgent",
    "system_prompt": "You are a helpful assistant",
    "model": "gpt-4-turbo-preview",
    ...
  }'

# Отправить сообщение
curl -X POST "http://localhost:8000/my/chat/$SESSION_ID/message/" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "content": "Hello!",
    "target_agent": "TestAgent"
  }'
```

## Использование альтернативных моделей

### Anthropic Claude

```yaml
model_list:
  - model_name: claude-3-opus
    litellm_params:
      model: anthropic/claude-3-opus-20240229
      api_key: sk-ant-your-key
```

В `.env`:
```env
OPENAI_MODEL=claude-3-opus
```

### Azure OpenAI

```yaml
model_list:
  - model_name: gpt-4-azure
    litellm_params:
      model: azure/gpt-4
      api_key: your-azure-key
      api_base: https://your-resource.openai.azure.com
      api_version: "2024-02-15-preview"
```

### Ollama (локальные модели)

```yaml
model_list:
  - model_name: llama2
    litellm_params:
      model: ollama/llama2
      api_base: http://localhost:11434
```

## Мониторинг и логирование

### Langfuse интеграция

```yaml
litellm_settings:
  success_callback: ["langfuse"]
  
environment_variables:
  LANGFUSE_PUBLIC_KEY: "pk-..."
  LANGFUSE_SECRET_KEY: "sk-..."
  LANGFUSE_HOST: "https://cloud.langfuse.com"
```

### Prometheus метрики

LiteLLM автоматически экспортирует метрики на `/metrics`:

```bash
curl http://localhost:4000/metrics
```

## Кэширование

### Redis кэш

```yaml
litellm_settings:
  cache: true
  cache_params:
    type: "redis"
    host: "localhost"
    port: 6379
    ttl: 3600  # 1 час
```

### In-memory кэш

```yaml
litellm_settings:
  cache: true
  cache_params:
    type: "local"
    ttl: 600  # 10 минут
```

## Ограничение расходов

```yaml
litellm_settings:
  max_budget: 100  # $100 в месяц
  budget_duration: "30d"
  
model_list:
  - model_name: gpt-4-turbo-preview
    litellm_params:
      model: openai/gpt-4-turbo-preview
      api_key: sk-your-key
      max_tokens: 4096
      rpm: 60  # requests per minute
      tpm: 100000  # tokens per minute
```

## Troubleshooting

### Ошибка подключения

```bash
# Проверить, что LiteLLM запущен
curl http://localhost:4000/health

# Проверить логи
docker logs litellm
```

### Неверная модель

Убедитесь, что модель указана в `litellm_config.yaml` и соответствует `OPENAI_MODEL` в `.env`.

### Ошибки аутентификации

Проверьте API ключи в `litellm_config.yaml` и `OPENAI_API_KEY` в `.env`.

## Дополнительные ресурсы

- [LiteLLM документация](https://docs.litellm.ai/)
- [Поддерживаемые провайдеры](https://docs.litellm.ai/docs/providers)
- [Proxy сервер](https://docs.litellm.ai/docs/proxy/quick_start)
