# Changelog: LLM Error Handling Improvements

**Дата**: 2026-02-16  
**Версия**: 0.1.1  
**Автор**: Development Team

## Обзор изменений

Реализована детальная обработка ошибок при взаимодействии с LLM провайдерами для информирования пользователей о проблемах с доступностью моделей.

## Проблема

Из анализа логов обнаружена проблема:

```
2026-02-16 17:40:34.875 | Retrying request to /chat/completions in 0.468605 seconds
2026-02-16 17:40:39.482 | Retrying request to /chat/completions in 0.878860 seconds
2026-02-16 17:40:45.364 | [error] agent_execution_failed error='Request timed out.'
2026-02-16 17:40:45.367 | INFO: "POST /my/chat/.../message/ HTTP/1.1" 500 Internal Server Error
```

**Проблемы**:
- Пользователь получал общую ошибку 500 без деталей
- Не было информации о том, какой провайдер/модель недоступны
- Отсутствовала классификация типов ошибок
- Нет детальных SSE событий для ошибок

## Решение

### 1. Расширена схема ошибок

**Файл**: [`app/schemas/error.py`](app/schemas/error.py)

Добавлены:
- Поле `metadata` в `ErrorResponse` для дополнительной информации
- Новый класс `LLMProviderError` для специфичных ошибок LLM

```python
class LLMProviderError(ErrorResponse):
    """LLM Provider specific error."""
    error_code: str = Field(default="LLM_PROVIDER_ERROR")
```

### 2. Детальная обработка ошибок в агенте

**Файл**: [`app/agents/contextual_agent.py`](app/agents/contextual_agent.py)

Реализована обработка специфичных ошибок OpenAI:

- ✅ **APITimeoutError** - таймаут запроса к LLM
- ✅ **APIConnectionError** - ошибка подключения к провайдеру
- ✅ **RateLimitError** - превышен лимит запросов
- ✅ **AuthenticationError** - ошибка аутентификации (неверный API ключ)
- ✅ **BadRequestError** - неверные параметры запроса (например, несуществующая модель)

Каждая ошибка возвращает структурированный ответ:

```python
{
    "success": False,
    "error": "Детальное описание ошибки",
    "error_type": "timeout|connection|rate_limit|authentication|bad_request",
    "provider": "https://openrouter.ai/api/v1",
    "model": "openrouter/openai/gpt-4.1"
}
```

### 3. Улучшена обработка в REST API

**Файл**: [`app/routes/chat.py`](app/routes/chat.py)

Изменения:
- Импорт `LLMProviderError` для детальных ответов
- HTTP статус `503 Service Unavailable` для ошибок LLM провайдера
- Детальные SSE события типа `ERROR` с информацией о провайдере и модели
- Структурированные ответы с metadata

Пример ответа при ошибке:

```json
{
  "detail": "LLM request timeout: model 'openrouter/openai/gpt-4.1' did not respond in time",
  "error_code": "LLM_PROVIDER_ERROR",
  "timestamp": "2026-02-16T15:00:00Z",
  "metadata": {
    "provider": "https://openrouter.ai/api/v1",
    "model": "openrouter/openai/gpt-4.1",
    "error_type": "timeout",
    "agent_id": "78975b4b-697d-4e85-9521-fd73ef297d9e",
    "agent_name": "CodeAssistant"
  }
}
```

### 4. SSE события для ошибок

Клиенты получают детальные события через SSE:

```json
{
  "event_type": "error",
  "payload": {
    "agent_id": "78975b4b-697d-4e85-9521-fd73ef297d9e",
    "agent_name": "CodeAssistant",
    "error_type": "timeout",
    "error": "LLM request timeout: model 'openrouter/openai/gpt-4.1' did not respond in time",
    "provider": "https://openrouter.ai/api/v1",
    "model": "openrouter/openai/gpt-4.1"
  },
  "timestamp": "2026-02-16T15:00:00Z",
  "session_id": "3a3f6084-0b70-4d50-a56b-b78519d43bf2"
}
```

### 5. Улучшенное логирование

Все ошибки логируются с детальной информацией:

```python
logger.error(
    "agent_execution_failed",
    agent_id=str(self.agent_id),
    agent_name=self.config.name,
    error=error_msg,
    error_type="timeout",
    model=self.config.model,
    provider=settings.openai_base_url or "openai",
)
```

### 6. Документация

**Файл**: [`doc/llm-error-handling.md`](../guides/llm-error-handling.md)

Создана полная документация:
- Описание всех типов ошибок
- Примеры ответов API
- Примеры SSE событий
- Примеры обработки на клиенте (JavaScript, Python)
- Рекомендации по мониторингу

## Измененные файлы

1. ✅ [`app/schemas/error.py`](app/schemas/error.py) - расширена схема ошибок
2. ✅ [`app/agents/contextual_agent.py`](app/agents/contextual_agent.py) - детальная обработка ошибок
3. ✅ [`app/routes/chat.py`](app/routes/chat.py) - улучшенные ответы API
4. ✅ [`doc/llm-error-handling.md`](../guides/llm-error-handling.md) - новая документация
5. ✅ [`doc/INDEX.md`](doc/INDEX.md) - обновлен индекс документации

## Преимущества

### Для пользователей
- 🎯 Понятные сообщения об ошибках
- 📊 Информация о недоступном провайдере/модели
- ⚡ Real-time уведомления через SSE
- 🔄 Возможность retry с пониманием причины

### Для разработчиков
- 🐛 Упрощенная отладка
- 📈 Детальное логирование
- 🔍 Классификация ошибок
- 📚 Полная документация

### Для DevOps
- 📊 Метрики по типам ошибок
- 🚨 Возможность настройки алертов
- 🔧 Быстрая диагностика проблем
- 📉 Мониторинг доступности провайдеров

## Примеры использования

### JavaScript клиент

```javascript
try {
  const response = await fetch('/my/chat/session-id/message/', {
    method: 'POST',
    body: JSON.stringify({ content: 'Hello', target_agent: 'CodeAssistant' })
  });
  
  if (response.status === 503) {
    const error = await response.json();
    const { error_type, provider, model } = error.metadata;
    
    switch (error_type) {
      case 'timeout':
        showError(`Model ${model} is not responding. Please try again.`);
        break;
      case 'connection':
        showError(`Cannot connect to ${provider}. Check your network.`);
        break;
      // ... другие типы
    }
  }
} catch (error) {
  console.error('Request failed:', error);
}
```

### SSE обработка

```javascript
const eventSource = new EventSource('/my/chat/session-id/events/');

eventSource.addEventListener('message', (event) => {
  const data = JSON.parse(event.data);
  
  if (data.event_type === 'error') {
    const { error_type, model, provider } = data.payload;
    console.error(`LLM Error: ${error_type} for ${model} at ${provider}`);
  }
});
```

## Тестирование

Рекомендуется протестировать:

1. ✅ Timeout ошибки - установить короткий таймаут
2. ✅ Connection ошибки - неверный URL провайдера
3. ✅ Authentication ошибки - неверный API ключ
4. ✅ Bad Request ошибки - несуществующая модель
5. ✅ SSE события - проверить получение событий ошибок

## Мониторинг

Рекомендуется настроить алерты на:
- Количество timeout ошибок > 10/мин
- Количество connection ошибок > 5/мин
- Любые authentication ошибки
- Rate limit ошибки

## Следующие шаги

1. 🔄 Добавить retry логику с exponential backoff
2. 📊 Интеграция с Prometheus для метрик ошибок
3. 🔔 Webhook уведомления при критических ошибках
4. 📈 Dashboard для мониторинга доступности провайдеров
5. 🧪 Автоматические тесты для всех типов ошибок

## Обратная совместимость

✅ Изменения обратно совместимы:
- Существующие клиенты продолжат работать
- Добавлены новые поля в ответах (опциональные)
- HTTP статусы изменены только для ошибок LLM (500 → 503)

## Ссылки

- [LLM Error Handling Documentation](../guides/llm-error-handling.md)
- [API Specification](../api/api-specification.md)
- [SSE Event Streaming](../api/sse-event-streaming.md)

---

**Статус**: ✅ Реализовано  
**Версия**: 0.1.1  
**Дата**: 2026-02-16
