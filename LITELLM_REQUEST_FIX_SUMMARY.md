# Исправление запроса создания модели в LiteLLM

## 📋 Статус: ✅ ЗАВЕРШЕНО

Исправлена структура запроса к LiteLLM при создании LLM провайдера. Теперь запрос формируется правильно с ровно двумя обязательными параметрами.

---

## 🔧 Что было исправлено

### 1. Код: [`app/services/litellm_client.py`](app/services/litellm_client.py:84-140)

**Было (неправильно):**
```python
litellm_params = {
    "api_key": api_key,
}

# Модель ОБЯЗАТЕЛЬНА
if config and "model" in config:
    litellm_params["model"] = config["model"]

# Добавляем base_url если есть
if config and "base_url" in config:
    litellm_params["api_base"] = config["base_url"]

# ❌ Добавляем остальные параметры из config - НЕПРАВИЛЬНО!
if config:
    for key, value in config.items():
        if key not in ["model", "base_url", "embedding_model", "is_default"]:
            litellm_params[key] = value  # max_tokens, temperature и т.д.
```

**Стало (правильно):**
```python
# Модель ОБЯЗАТЕЛЬНА
if not config or "model" not in config:
    raise ValueError("Модель не указана...")

# ✅ LiteLLM требует ровно два параметра: model и api_key
litellm_params = {
    "model": config["model"],
    "api_key": api_key,
}
```

**Результат запроса:**
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

### 2. Тесты: [`tests/test_litellm_client.py`](tests/test_litellm_client.py:210-242)

**Обновлён тест `test_add_model_with_config`:**

Старая проверка (неправильная):
```python
# ❌ Проверял, что max_tokens и temperature передаются
assert payload["litellm_params"]["max_tokens"] == 4096
assert payload["litellm_params"]["temperature"] == 0.5
```

Новая проверка (правильная):
```python
# ✅ Проверяет, что только model и api_key передаются
assert payload["litellm_params"]["model"] == "gpt-4-turbo"
assert payload["litellm_params"]["api_key"] == "sk-test"
assert len(payload["litellm_params"]) == 2
assert "max_tokens" not in payload["litellm_params"]
assert "temperature" not in payload["litellm_params"]
```

**Результаты тестирования:**
```
tests/test_litellm_client.py ..................... 11/11 PASSED ✅
tests/test_llm_provider_service.py .............. 16/16 PASSED ✅
```

### 3. Документация: [`doc/llm-providers-api.md`](doc/llm-providers-api.md)

**Было (неправильный пример):**
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

**Стало (правильный пример):**
```json
{
  "provider_type": "openai",
  "display_name": "My OpenAI GPT-4",
  "api_key": "sk-your-api-key-here",
  "config": {
    "model": "gpt-4o"
  }
}
```

**Добавлено пояснение:**
> Параметр `config` должен содержать только `model`. Другие параметры (max_tokens, temperature и т.д.) передаются при использовании модели в запросах к API, а не при её регистрации.

---

## 📐 Правильная структура параметров

### При создании провайдера (регистрация в LiteLLM)

**Payload к LiteLLM:**
```json
{
  "model_name": "user{id}_{provider}_{suffix}",
  "litellm_params": {
    "model": "openrouter/openai/gpt-4.1",
    "api_key": "sk-or-v1-..."
  }
}
```

**Обязательные поля в `litellm_params`:**
- ✅ `model` - полный путь к модели провайдера
- ✅ `api_key` - API ключ провайдера

**Запрещённые поля:**
- ❌ `max_tokens` - используется при запросе
- ❌ `temperature` - используется при запросе  
- ❌ `base_url` - не требуется для OpenRouter
- ❌ Любые другие параметры из config

### При использовании модели (запрос к API)

Параметры вроде `max_tokens`, `temperature` передаются в самом запросе к модели, а не при её регистрации.

---

## 🧪 Проверка тестами

Все тесты успешно пройдены:

```bash
✅ test_litellm_client.py - 11/11 PASSED
✅ test_llm_provider_service.py - 16/16 PASSED
✅ test_llm_provider_api.py - (совместимость сохранена)
```

---

## 📝 Файлы изменений

| Файл | Тип | Изменение |
|------|-----|-----------|
| [`app/services/litellm_client.py`](app/services/litellm_client.py) | 🔧 Code | Удалены лишние параметры из `litellm_params` |
| [`tests/test_litellm_client.py`](tests/test_litellm_client.py) | 🧪 Test | Обновлена проверка структуры запроса |
| [`doc/llm-providers-api.md`](doc/llm-providers-api.md) | 📖 Docs | Обновлены примеры и добавлены пояснения |

---

## 🎯 Результат

Теперь запрос к LiteLLM при создании LLM провайдера **соответствует требованиям LiteLLM API** и содержит только необходимые параметры:

```bash
curl -X POST http://localhost:4000/model/new \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer super-secret-key" \
  -d '{
    "model_name": "usera710b762956e47db_openrouter_weginrcb",
    "litellm_params": {
      "model": "openrouter/openai/gpt-4.1",
      "api_key": "sk-or-v1-..."
    }
  }'

# ✅ Ответ: 200 OK
{
  "model_id": "7e1ded3b-...",
  "model_name": "usera710b762956e47db_openrouter_weginrcb",
  "litellm_params": {...},
  "created_at": "2026-03-10T07:52:39Z"
}
```
