# llm-provider-management Specification

## Purpose
TBD - created by archiving change llm-providers-management. Update Purpose after archive.
## Requirements
### Requirement: Пользователь может создавать новые LLM провайдеры
Пользователь ДОЛЖЕН иметь возможность зарегистрировать новый LLM провайдер, предоставив display_name, provider_type, API ключ и конфигурацию. Система ДОЛЖНА сохранить метаданные в PostgreSQL и отправить API ключ в LiteLLM для безопасного хранения.

#### Scenario: Успешное создание провайдера OpenAI
- **WHEN** пользователь отправляет POST /my/llm-providers с {display_name: "My GPT-4", provider_type: "openai", api_key: "sk-...", config: {model: "gpt-4"}}
- **THEN** система создает запись в user_llm_providers, регистрирует модель в LiteLLM, возвращает 201 Created с id и litellm_model_name

#### Scenario: Создание провайдера с невалидным типом
- **WHEN** пользователь отправляет POST /my/llm-providers с provider_type: "invalid_type"
- **THEN** система возвращает 400 Bad Request с сообщением об ошибке

#### Scenario: Создание провайдера когда LiteLLM недоступен
- **WHEN** пользователь создает провайдер и LiteLLM API возвращает ошибку соединения
- **THEN** система откатывает транзакцию, возвращает 503 Service Unavailable, логирует ошибку в audit_log

### Requirement: Пользователь может получить список своих провайдеров
Пользователь ДОЛЖЕН иметь возможность получить отфильтрованный список своих LLM провайдеров с опциональной фильтрацией по статусу и пагинацией.

#### Scenario: Получение списка активных провайдеров
- **WHEN** пользователь отправляет GET /my/llm-providers?status=active&skip=0&limit=50
- **THEN** система возвращает 200 OK с массивом активных провайдеров пользователя, отсортированных по дате создания (новые первыми)

#### Scenario: Получение списка без фильтра по статусу
- **WHEN** пользователь отправляет GET /my/llm-providers?skip=0&limit=50
- **THEN** система возвращает 200 OK со всеми провайдерами пользователя (независимо от статуса)

#### Scenario: Попытка получить провайдеры другого пользователя
- **WHEN** пользователь A отправляет GET /my/llm-providers и авторизован как пользователь A
- **THEN** система возвращает только провайдеры пользователя A, никогда не провайдеры других пользователей

### Requirement: Пользователь может получить детали конкретного провайдера
Пользователь ДОЛЖЕН иметь возможность получить полную информацию о конкретном провайдере, включая метаданные и статистику использования (но НЕ API ключ).

#### Scenario: Успешное получение деталей провайдера
- **WHEN** пользователь отправляет GET /my/llm-providers/{id}
- **THEN** система возвращает 200 OK с деталями: id, display_name, provider_type, litellm_model_name, status, config, usage_count, created_at, но БЕЗ api_key

#### Scenario: Получение несуществующего провайдера
- **WHEN** пользователь отправляет GET /my/llm-providers/{nonexistent_id}
- **THEN** система возвращает 404 Not Found

#### Scenario: Попытка доступа к провайдеру другого пользователя
- **WHEN** пользователь A отправляет GET /my/llm-providers/{provider_id_of_user_b}
- **THEN** система возвращает 404 Not Found (скрывает существование провайдера)

### Requirement: Пользователь может обновить конфигурацию провайдера
Пользователь ДОЛЖЕН иметь возможность обновить display_name и config провайдера. API ключ НЕ МОЖЕТ быть обновлен через этот endpoint (требуется удаление и создание нового).

#### Scenario: Успешное обновление display_name
- **WHEN** пользователь отправляет PATCH /my/llm-providers/{id} с {display_name: "Updated Name"}
- **THEN** система обновляет запись, логирует в audit_log (action=update, old_values={display_name: "Old"}, new_values={display_name: "Updated"}), возвращает 200 OK

#### Scenario: Попытка обновить API ключ
- **WHEN** пользователь отправляет PATCH /my/llm-providers/{id} с {api_key: "sk-new"}
- **THEN** система игнорирует поле api_key или возвращает 400 Bad Request с указанием, что обновление ключа не поддерживается

#### Scenario: Обновление несуществующего провайдера
- **WHEN** пользователь отправляет PATCH /my/llm-providers/{nonexistent_id}
- **THEN** система возвращает 404 Not Found

### Requirement: Пользователь может удалить провайдер
Пользователь ДОЛЖЕН иметь возможность удалить провайдер, если он НЕ используется никакими агентами. При удалении модель ДОЛЖНА быть удалена из LiteLLM, а запись - из PostgreSQL.

#### Scenario: Успешное удаление неиспользуемого провайдера
- **WHEN** пользователь отправляет DELETE /my/llm-providers/{id} и провайдер не используется агентами
- **THEN** система удаляет провайдер из LiteLLM и PostgreSQL, логирует в audit_log (action=delete, success=true), возвращает 204 No Content

#### Scenario: Попытка удалить провайдер, используемый агентами
- **WHEN** пользователь отправляет DELETE /my/llm-providers/{id} и провайдер используется одним или несколькими агентами
- **THEN** система возвращает 400 Bad Request с сообщением: "Cannot delete: N agent(s) are using this provider"

#### Scenario: Удаление несуществующего провайдера
- **WHEN** пользователь отправляет DELETE /my/llm-providers/{nonexistent_id}
- **THEN** система возвращает 404 Not Found

#### Scenario: Ошибка при удалении из LiteLLM
- **WHEN** пользователь удаляет провайдер и LiteLLM API возвращает ошибку
- **THEN** система откатывает удаление из PostgreSQL, логирует в audit_log (action=delete, success=false), возвращает 503 Service Unavailable

### Requirement: Пользователь может тестировать подключение к провайдеру
Пользователь ДОЛЖЕН иметь возможность отправить простой prompt к провайдеру и получить ответ, чтобы валидировать API ключ и конфигурацию перед использованием в агентах.

#### Scenario: Успешное тестирование провайдера
- **WHEN** пользователь отправляет POST /my/llm-providers/{id}/test с {test_message: "Hello", max_tokens: 100}
- **THEN** система отправляет message в LiteLLM через litellm_model_name, возвращает 200 OK с {status: "success", response: "...", latency_ms: N}, обновляет last_tested_at провайдера

#### Scenario: Тестирование провайдера с невалидным API ключом
- **WHEN** пользователь тестирует провайдер и LiteLLM возвращает ошибку аутентификации
- **THEN** система возвращает 422 Unprocessable Entity с {status: "error", error: "Invalid API key"}, обновляет test_error_message в провайдере

#### Scenario: Timeout при тестировании
- **WHEN** пользователь тестирует провайдер и запрос к LiteLLM превышает timeout (60s)
- **THEN** система возвращает 504 Gateway Timeout с {status: "error", error: "Request timeout"}

#### Scenario: Тестирование несуществующего провайдера
- **WHEN** пользователь отправляет POST /my/llm-providers/{nonexistent_id}/test
- **THEN** система возвращает 404 Not Found

### Requirement: Пользователь может получить список доступных типов провайдеров
Система ДОЛЖНА предоставить endpoint для получения информации о всех поддерживаемых типах провайдеров, включая требуемые поля и доступные модели.

#### Scenario: Получение списка типов провайдеров
- **WHEN** пользователь отправляет GET /llm-providers/types
- **THEN** система возвращает 200 OK с массивом {type: "openai", display_name: "OpenAI", description: "...", required_fields: ["api_key"], models: ["gpt-4", ...]}

### Requirement: Система логирует все операции с провайдерами для аудита
Каждая операция (create, update, delete, test, use) ДОЛЖНА быть залогирована в таблице llm_provider_audit_log с информацией о действии, пользователе, результате и контексте.

#### Scenario: Создание записи в audit log при успешной операции
- **WHEN** пользователь успешно создает провайдер
- **THEN** система вставляет запись в llm_provider_audit_log с {user_id, provider_id, action: "create", success: true, new_values: {...}, created_at: now}

#### Scenario: Логирование ошибки в audit log
- **WHEN** пользователь пытается создать провайдер и операция в LiteLLM фейлится
- **THEN** система вставляет запись в llm_provider_audit_log с {user_id, action: "create", success: false, error_message: "...", created_at: now}

### Requirement: Система отслеживает статистику использования провайдеров
Система ДОЛЖНА автоматически обновлять usage_count и last_used_at при использовании провайдера в агенте.

#### Scenario: Обновление usage_count при использовании
- **WHEN** агент с bind к провайдеру выполняет prompt
- **THEN** система увеличивает usage_count на 1 и устанавливает last_used_at в текущее время

