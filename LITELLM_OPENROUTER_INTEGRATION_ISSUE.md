# Проблема интеграции с OpenRouter в LiteLLM

## Обнаруженная ошибка

При попытке использовать зарегистрированную модель OpenRouter, LiteLLM выдаёт ошибку:

```
litellm.acompletion(model=openrouter/openai/gpt-4.1) Exception litellm.APIError: APIError: OpenrouterException - Method Not Allowed
```

### Логи ошибки

```
19:39:53 - LiteLLM Router:INFO: router.py:1622 - litellm.acompletion(model=openrouter/openai/gpt-4.1) 
Exception litellm.APIError: APIError: OpenrouterException - Method Not Allowed

Received Model Group=usera710b762956e47db_openrouter_weginrcb
LiteLLM Retried: 1 times, LiteLLM Max Retries: 2

httpx.HTTPStatusError: Client error '405 Method Not Allowed' for url 'https://openrouter.ai/api/v1/chat/completions'
```

## Анализ проблемы

### Шаг 1: Создание модели (✅ РАБОТАЕТ)

Запрос к LiteLLM:
```json
POST /model/new
{
  "model_name": "usera710b762956e47db_openrouter_weginrcb",
  "litellm_params": {
    "model": "openrouter/openai/gpt-4.1",
    "api_key": "sk-or-v1-..."
  }
}
```

**Результат:** ✅ 200 OK - модель успешно зарегистрирована

### Шаг 2: Использование модели (❌ ОШИБКА)

Запрос к LiteLLM:
```json
POST /completions
{
  "model": "usera710b762956e47db_openrouter_weginrcb",
  "messages": [...],
  "max_tokens": 100
}
```

**Результат:** ❌ 405 Method Not Allowed

## Корневая причина

Ошибка 405 "Method Not Allowed" при POST запросе к `https://openrouter.ai/api/v1/chat/completions` указывает на проблему в конфигурации модели.

### Возможные причины:

1. **Неправильный параметр `model`**
   - OpenRouter требует конкретный формат имени модели
   - `openrouter/openai/gpt-4.1` может быть неправильным идентификатором
   - Нужно уточнить правильное имя модели у OpenRouter

2. **Отсутствуют обязательные параметры**
   - OpenRouter может требовать дополнительные headers или параметры
   - Например: `site_url`, `app_id`, `title`, `schema_version`

3. **Конфликт с методом HTTP**
   - OpenRouter может требовать другой метод (GET вместо POST)
   - Или требовать определённую версию API

4. **Неправильная конфигурация base_url**
   - Может быть нужен другой base_url для OpenRouter
   - Например: `https://openrouter.ai/api/v1`

## Решение

### Вариант 1: Проверить правильное имя модели

Используйте OpenRouter API для получения списка доступных моделей:

```bash
curl https://openrouter.ai/api/v1/models \
  -H "Authorization: Bearer sk-or-v1-..."
```

Найдите правильный ID модели вместо `openai/gpt-4.1`.

### Вариант 2: Добавить требуемые параметры OpenRouter

В методе [`add_model`](app/services/litellm_client.py:84-150) добавить специальную обработку для OpenRouter:

```python
async def add_model(
    self,
    user_id: UUID,
    provider_type: str,
    api_key: str,
    config: dict[str, Any] | None = None,
) -> str:
    litellm_model_name = self._generate_litellm_model_name(user_id, provider_type)
    
    litellm_params = {
        "api_key": api_key,
    }
    
    if config and "model" in config:
        litellm_params["model"] = config["model"]
    else:
        raise ValueError("Модель не указана...")
    
    # Добавить параметры OpenRouter если это OpenRouter провайдер
    if provider_type == "openrouter":
        # OpenRouter требует дополнительные параметры
        litellm_params.setdefault("api_base", "https://openrouter.ai/api/v1")
        # Добавляем из config если есть
        if config:
            if "site_url" in config:
                litellm_params["site_url"] = config["site_url"]
            if "title" in config:
                litellm_params["title"] = config["title"]
    
    # ... остальной код ...
```

### Вариант 3: Обновить документацию для пользователя

В [`doc/llm-providers-api.md`](doc/llm-providers-api.md) добавить примеры для OpenRouter:

```json
{
  "provider_type": "openrouter",
  "display_name": "OpenRouter GPT-4",
  "api_key": "sk-or-v1-...",
  "config": {
    "model": "openai/gpt-4-turbo-preview",
    "site_url": "https://myapp.com",
    "title": "My Application"
  }
}
```

## Рекомендации

1. **Проверить документацию OpenRouter**
   - Какой формат требуется для параметра `model`
   - Какие дополнительные параметры требуются
   - Какой base_url использовать

2. **Добавить обработку для разных провайдеров**
   - Каждый провайдер может иметь специфичные требования
   - Нужна специализированная подготовка параметров

3. **Добавить логирование**
   - Логировать полный payload перед отправкой в LiteLLM
   - Помогает отладить проблемы в интеграции

4. **Добавить валидацию параметров**
   - Проверять наличие обязательных параметров для каждого провайдера
   - Давать понятные сообщения об ошибках пользователю

## Файлы для исправления

1. **[`app/services/litellm_client.py`](app/services/litellm_client.py:84-150)**
   - Добавить специальную обработку для OpenRouter
   - Добавить логирование формируемого payload

2. **[`doc/llm-providers-api.md`](doc/llm-providers-api.md)**
   - Добавить примеры для каждого типа провайдера
   - Включить обязательные параметры

3. **[`tests/test_litellm_client.py`](tests/test_litellm_client.py)**
   - Добавить тесты для OpenRouter конфигурации
   - Проверить формирование параметров для разных провайдеров
