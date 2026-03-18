# LLM Provider Error Handling

## Обзор

Система обработки ошибок LLM провайдеров обеспечивает детальную информацию пользователю о проблемах при взаимодействии с языковыми моделями.

## Типы ошибок

### 1. Timeout Error (Таймаут)
**Код ошибки:** `LLM_PROVIDER_ERROR`  
**HTTP статус:** `503 Service Unavailable`  
**Причина:** LLM модель не ответила в течение установленного времени

**Пример ответа:**
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

### 2. Connection Error (Ошибка подключения)
**Код ошибки:** `LLM_PROVIDER_ERROR`  
**HTTP статус:** `503 Service Unavailable`  
**Причина:** Не удалось установить соединение с LLM провайдером

**Пример ответа:**
```json
{
  "detail": "Failed to connect to LLM provider: Connection refused",
  "error_code": "LLM_PROVIDER_ERROR",
  "timestamp": "2026-02-16T15:00:00Z",
  "metadata": {
    "provider": "https://openrouter.ai/api/v1",
    "model": "openrouter/openai/gpt-4.1",
    "error_type": "connection",
    "agent_id": "78975b4b-697d-4e85-9521-fd73ef297d9e",
    "agent_name": "CodeAssistant"
  }
}
```

### 3. Rate Limit Error (Превышен лимит запросов)
**Код ошибки:** `LLM_PROVIDER_ERROR`  
**HTTP статус:** `503 Service Unavailable`  
**Причина:** Превышен лимит запросов к LLM провайдеру

**Пример ответа:**
```json
{
  "detail": "LLM provider rate limit exceeded for model 'openrouter/openai/gpt-4.1'",
  "error_code": "LLM_PROVIDER_ERROR",
  "timestamp": "2026-02-16T15:00:00Z",
  "metadata": {
    "provider": "https://openrouter.ai/api/v1",
    "model": "openrouter/openai/gpt-4.1",
    "error_type": "rate_limit",
    "agent_id": "78975b4b-697d-4e85-9521-fd73ef297d9e",
    "agent_name": "CodeAssistant"
  }
}
```

### 4. Authentication Error (Ошибка аутентификации)
**Код ошибки:** `LLM_PROVIDER_ERROR`  
**HTTP статус:** `503 Service Unavailable`  
**Причина:** Неверный API ключ или проблемы с аутентификацией

**Пример ответа:**
```json
{
  "detail": "LLM provider authentication failed: invalid API key",
  "error_code": "LLM_PROVIDER_ERROR",
  "timestamp": "2026-02-16T15:00:00Z",
  "metadata": {
    "provider": "https://openrouter.ai/api/v1",
    "model": "openrouter/openai/gpt-4.1",
    "error_type": "authentication",
    "agent_id": "78975b4b-697d-4e85-9521-fd73ef297d9e",
    "agent_name": "CodeAssistant"
  }
}
```

### 5. Bad Request Error (Неверный запрос)
**Код ошибки:** `LLM_PROVIDER_ERROR`  
**HTTP статус:** `503 Service Unavailable`  
**Причина:** Неверные параметры запроса к LLM

**Пример ответа:**
```json
{
  "detail": "Invalid request to LLM provider: model not found",
  "error_code": "LLM_PROVIDER_ERROR",
  "timestamp": "2026-02-16T15:00:00Z",
  "metadata": {
    "provider": "https://openrouter.ai/api/v1",
    "model": "invalid-model-name",
    "error_type": "bad_request",
    "agent_id": "78975b4b-697d-4e85-9521-fd73ef297d9e",
    "agent_name": "CodeAssistant"
  }
}
```

## SSE Events для ошибок

При возникновении ошибки клиент получает SSE событие типа `ERROR`:

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

## Логирование

Все ошибки LLM провайдера логируются с детальной информацией:

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

## Конфигурация

Настройки таймаутов и повторных попыток в [`app/config.py`](../app/config.py):

```python
# OpenAI / LiteLLM
openai_api_key: str = Field(default="")
openai_base_url: str | None = Field(default=None)
openai_model: str = Field(default="openrouter/openai/gpt-4.1")
openai_max_retries: int = Field(default=2)
openai_timeout: int = Field(default=120)  # Increased timeout for LLM requests
```

## Рекомендации для клиентов

1. **Обрабатывайте HTTP 503** - это означает временную недоступность LLM провайдера
2. **Проверяйте `error_type`** в metadata для определения типа ошибки
3. **Показывайте пользователю** информацию о провайдере и модели
4. **Реализуйте retry логику** для timeout и connection ошибок
5. **Подписывайтесь на SSE события** для получения ошибок в реальном времени

## Примеры обработки на клиенте

### JavaScript/TypeScript
```typescript
try {
  const response = await fetch('/my/chat/session-id/message/', {
    method: 'POST',
    body: JSON.stringify({ content: 'Hello', target_agent: 'CodeAssistant' })
  });
  
  if (response.status === 503) {
    const error = await response.json();
    const metadata = error.metadata;
    
    switch (metadata.error_type) {
      case 'timeout':
        showError(`Model ${metadata.model} is not responding. Please try again.`);
        break;
      case 'connection':
        showError(`Cannot connect to ${metadata.provider}. Check your network.`);
        break;
      case 'rate_limit':
        showError(`Rate limit exceeded for ${metadata.model}. Please wait.`);
        break;
      case 'authentication':
        showError(`Authentication failed. Check API key configuration.`);
        break;
      case 'bad_request':
        showError(`Invalid model: ${metadata.model}`);
        break;
    }
  }
} catch (error) {
  console.error('Request failed:', error);
}
```

### Python
```python
import httpx

try:
    response = httpx.post(
        'http://localhost:8000/my/chat/session-id/message/',
        json={'content': 'Hello', 'target_agent': 'CodeAssistant'}
    )
    response.raise_for_status()
except httpx.HTTPStatusError as e:
    if e.response.status_code == 503:
        error_data = e.response.json()
        metadata = error_data.get('metadata', {})
        error_type = metadata.get('error_type')
        
        if error_type == 'timeout':
            print(f"Model {metadata['model']} timeout")
        elif error_type == 'connection':
            print(f"Cannot connect to {metadata['provider']}")
        # ... handle other error types
```

## Мониторинг

Рекомендуется настроить алерты на следующие метрики:
- Количество timeout ошибок
- Количество connection ошибок
- Количество rate_limit ошибок
- Среднее время ответа LLM провайдера

## См. также

- [REST API Documentation](rest-api.md)
- [SSE Event Streaming](sse-event-streaming.md)
- [Configuration Guide](setup-guide.md)
