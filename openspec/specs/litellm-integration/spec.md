# litellm-integration Specification

## Purpose
TBD - created by archiving change llm-providers-management. Update Purpose after archive.
## Requirements
### Requirement: Система может регистрировать новые модели в LiteLLM
LiteLLMClient ДОЛЖЕН иметь возможность добавить новую модель в LiteLLM с API ключом и конфигурацией, используя master key для аутентификации.

#### Scenario: Успешная регистрация модели в LiteLLM
- **WHEN** LiteLLMClient вызывает add_model(model_name: "user550e84001eb241d4a716_openai_abc12345", provider_type: "openai", api_key: "sk-...", config: {model: "gpt-4"})
- **THEN** система отправляет POST /model/new в LiteLLM с litellm_params, получает 200 OK, возвращает результат

#### Scenario: LiteLLM отклоняет невалидный API ключ
- **WHEN** LiteLLMClient пытается добавить модель с невалидным API ключом
- **THEN** LiteLLM возвращает 401/422, LiteLLMClient пробрасывает исключение, которое обрабатывается на уровне LLMProviderService

#### Scenario: Невалидная конфигурация провайдера
- **WHEN** LiteLLMClient пытается добавить модель с неполной конфигурацией (например, отсутствует model для OpenAI)
- **THEN** система конструирует model_id с приоритетом, LiteLLM может отклонить или система заранее валидирует

### Requirement: Система может удалять модели из LiteLLM
LiteLLMClient ДОЛЖЕН иметь возможность удалить модель из LiteLLM по имени.

#### Scenario: Успешное удаление модели из LiteLLM
- **WHEN** LiteLLMClient вызывает delete_model(model_name: "user550e84001eb241d4a716_openai_abc12345")
- **THEN** система отправляет POST /model/delete в LiteLLM, получает 200 OK

#### Scenario: Удаление несуществующей модели
- **WHEN** LiteLLMClient пытается удалить модель, которой нет в LiteLLM
- **THEN** LiteLLM может вернуть 404 или 200, LiteLLMClient обрабатывает gracefully

### Requirement: Система может тестировать модели в LiteLLM
LiteLLMClient ДОЛЖЕН иметь возможность отправить test prompt к модели и получить ответ.

#### Scenario: Успешное тестирование модели
- **WHEN** LiteLLMClient вызывает test_model(model_name: "user550e84001eb241d4a716_openai_abc12345", message: "Hello, are you working?", max_tokens: 100)
- **THEN** система отправляет POST /chat/completions в LiteLLM, получает 200 OK с response, возвращает {status: "success", response: "...", model: "..."}

#### Scenario: Тестирование с невалидным API ключом
- **WHEN** LiteLLMClient тестирует модель с невалидным API ключом
- **THEN** LiteLLM возвращает 401, LiteLLMClient пробрасывает исключение

#### Scenario: Timeout при тестировании
- **WHEN** LiteLLMClient тестирует модель и запрос превышает timeout (60s)
- **THEN** система пробрасывает исключение TimeoutError

### Requirement: LiteLLMClient использует безопасную аутентификацию
LiteLLMClient ДОЛЖЕН использовать master key из конфигурации для всех запросов к LiteLLM API, все запросы ДОЛЖНЫ включать Authorization header.

#### Scenario: Запрос с корректным Authorization header
- **WHEN** LiteLLMClient отправляет запрос в LiteLLM
- **THEN** запрос содержит header "Authorization: Bearer {master_key}" и "Content-Type: application/json"

#### Scenario: Конфигурация LiteLLM при инициализации
- **WHEN** LiteLLMClient инициализируется
- **THEN** система читает LITELLM_URL и LITELLM_MASTER_KEY из config, использует defaults если не установлены: LITELLM_URL="http://litellm:4000", LITELLM_MASTER_KEY="super-secret-key-change-in-production"

### Requirement: Генерация уникального имени модели для изоляции пользователей
LiteLLMClient ДОЛЖЕН генерировать уникальное имя модели, которое встраивает user_id и provider_type для изоляции и идентификации.

#### Scenario: Генерация имени модели
- **WHEN** LiteLLMClient вызывает _generate_litellm_model_name(user_id: UUID, provider_type: "openai")
- **THEN** система возвращает строку вида "user{sanitized_user_id}_{provider_type}_{random_suffix}", например "user550e84001eb241d4a716_openai_abc12345"

#### Scenario: Санитизация user_id
- **WHEN** user_id содержит дефисы (например, "550e8400-e29b-41d4-a716-446655440000")
- **THEN** система удаляет дефисы и берет первые 16 символов для включения в имя модели

