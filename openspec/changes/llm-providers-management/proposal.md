# Proposal: Система управления LLM провайдерами

## Почему

В настоящий момент пользователи не могут управлять своими LLM API провайдерами в CodeLab Core Service. Все AI агенты используют единую централизованную конфигурацию LLM, что создает проблемы безопасности при управлении API ключами и ограничивает гибкость. Это изменение позволяет пользователям безопасно регистрировать и управлять несколькими LLM провайдерами с автоматической обработкой API ключей через интеграцию с LiteLLM, обеспечивая как безопасность, так и автономию пользователей.

## Что изменится

- **Новые таблицы базы данных**: `user_llm_providers` для хранения метаданных провайдеров пользователя и `llm_provider_audit_log` для полного аудита операций
- **Новые REST API endpoints**: Полные операции CRUD для провайдеров под путем `/my/llm-providers` с изоляцией пользователей
- **Интеграция с LiteLLM**: Сервис LiteLLMClient для безопасного управления API ключами и операций с моделями через REST API LiteLLM
- **Система аудита**: LLMProviderAuditService для отслеживания всех операций с провайдерами (create, update, delete, test, use) с метриками успеха/ошибки
- **Интеграция с агентами**: Обновленные AgentManager и ContextualAgent для поддержки выбора провайдера и отслеживания использования
- **Конфигурация**: Новые параметры для подключения к LiteLLM (URL, master key) в app/config.py
- **Тестирование провайдеров**: Встроенный endpoint для проверки подключения к провайдеру перед использованием в агентах
- **Метрики использования**: Автоматическое отслеживание количества использований и времени последнего использования провайдера

## Возможности

### Новые возможности

- `llm-provider-management`: Возможность пользователей создавать, читать, обновлять и удалять свои LLM провайдеры с хранением метаданных в Core Service (display_name, provider_type, config), при этом API ключи остаются защищены в LiteLLM
- `litellm-integration`: Интеграция с API LiteLLM для безопасной регистрации моделей, удаления и тестирования с использованием master key аутентификации
- `llm-provider-audit`: Полное логирование аудита всех операций с провайдерами, включая тип действия, старые/новые значения, статус успеха и контекст (IP, user agent)
- `agent-llm-provider-binding`: Поддержка агентами выбора и использования конкретных управляемых пользователем LLM провайдеров вместо конфигурации по умолчанию

### Измененные возможности

- `personal-agents-management`: Обновлена для поддержки опционального поля `llm_provider_id` на агентах, позволяя связывать провайдер с агентом

## Влияние

**Затрагиваемый код:**
- `app/models/` - Новые модели: `UserLLMProvider`, `LLMProviderAuditLog`; Обновлены: `UserAgent` (новый FK llm_provider_id)
- `app/routes/` - Новый роутер: `project_llm_providers.py` для REST endpoints
- `app/services/` - Новые сервисы: `LiteLLMClient`, `LLMProviderService`, `LLMProviderAuditService`
- `app/schemas/` - Новые схемы: `UserLLMProviderCreate`, `UserLLMProviderUpdate`, `UserLLMProviderResponse`
- `app/agents/manager.py` - Обновлена для валидации и связывания провайдеров с агентами
- `app/agents/contextual_agent.py` - Обновлена для записи использования провайдера при выполнении

**База данных:**
- Требуется новая миграция для создания таблиц `user_llm_providers` и `llm_provider_audit_log`
- Новый индекс на `user_agents.llm_provider_id`

**API изменения:**
- Новые endpoints: POST, GET, PATCH, DELETE `/my/llm-providers`
- Новый endpoint: POST `/my/llm-providers/{id}/test`
- Новый endpoint: GET `/my/llm-providers/available`
- Новый endpoint: GET `/llm-providers/types`

**Конфигурация:**
- Новые переменные окружения: `LITELLM_URL`, `LITELLM_MASTER_KEY`

**Тестирование:**
- Unit тесты для `LiteLLMClient`, `LLMProviderService`, `LLMProviderAuditService`
- Интеграционные тесты для API endpoints
- Интеграционные тесты агентов

**Вне scope:**
- Управление провайдерами на уровне администратора (отложено на Фазу 2)
- Rate limiting и enforcement квот (отложено на Фазу 2)
- Аналитический dashboard для провайдеров (отложено на Фазу 2)
- Marketplace предконфигурированных провайдеров (отложено на Фазу 2)
