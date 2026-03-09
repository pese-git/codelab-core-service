# Changelog: LLM Providers Management System

## v0.3.0 - 2026-03-09

### ✨ Новые функции

#### Управление LLM провайдерами
- **Добавление провайдеров** - Поддержка OpenAI, Anthropic, Google, Cohere, Azure OpenAI и других через LiteLLM
- **REST API endpoints** для управления провайдерами:
  - `POST /my/llm-providers` - Добавить провайдер
  - `GET /my/llm-providers` - Получить список провайдеров (с пагинацией)
  - `GET /my/llm-providers/{id}` - Получить конкретный провайдер
  - `PATCH /my/llm-providers/{id}` - Обновить конфигурацию провайдера
  - `DELETE /my/llm-providers/{id}` - Удалить провайдер
  - `POST /my/llm-providers/{id}/test` - Тестировать подключение к провайдеру
  - `GET /my/llm-providers/available` - Получить доступные провайдеры
  - `GET /llm-providers/types` - Получить типы провайдеров (PUBLIC endpoint)
  - `GET /my/llm-providers/audit` - Получить audit log операций

#### Интеграция с агентами
- Агенты могут использовать выбранный LLM провайдер
- Поддержка переключения между провайдерами без пересоздания агента
- Отслеживание использования провайдера (use_count, last_used_at)
- Валидация что провайдер не может быть удалён если его используют агенты

#### Безопасность
- ✅ **API ключи не логируются** - Не появляются в logs, responses, или audit
- ✅ **API ключи не хранятся в БД** - Хранятся только в LiteLLM (secure vault)
- ✅ **Полная изоляция пользователей** - Каждый пользователь видит только своих провайдеров
- ✅ **Audit логирование** - Все операции логируются с IP адресом и user agent
- ✅ **Запрет обновления ключа** - API ключ можно только удалить и создать новый

#### Resilience и обработка ошибок
- **Retry logic с exponential backoff**:
  - Max 3 попытки
  - Начальная задержка 1 секунда
  - Backoff factor 2 (1s, 2s, 4s)
  - Только для timeout и network errors
  - Не делает retry на HTTP status errors (401, 400, etc.)
- **Timeout обработка** - 60 секунд timeout для всех LiteLLM API calls
- **Валидация** - Запрет обновления api_key в update_user_provider()

### 📊 База данных

#### Новые таблицы
- `user_llm_providers` - Хранит информацию о LLM провайдерах пользователя
- `llm_provider_audit_log` - Аудит лог всех операций с провайдерами

#### Обновления таблиц
- `user_agents` - Добавлено поле `llm_provider_id` с FK на `user_llm_providers`
- `user_llm_providers` - Добавлены индексы для оптимизации queries

### 🏗️ Архитектура

#### Новые компоненты
- **LiteLLMClient** (`app/services/litellm_client.py`) - HTTP клиент для интеграции с LiteLLM
  - `add_model()` - Регистрация модели в LiteLLM
  - `delete_model()` - Удаление модели из LiteLLM
  - `test_model()` - Тестирование подключения к модели
  - `_http_request()` - HTTP запросы с retry logic и exponential backoff

- **LLMProviderService** (`app/services/llm_provider_service.py`) - Основной сервис управления провайдерами
  - `create_user_provider()` - Создание нового провайдера
  - `get_user_provider()` - Получение провайдера
  - `get_user_providers()` - Получение списка провайдеров с пагинацией
  - `update_user_provider()` - Обновление конфигурации провайдера
  - `delete_user_provider()` - Удаление провайдера
  - `test_provider()` - Тестирование подключения
  - `record_provider_usage()` - Запись использования провайдера

- **LLMProviderAuditService** (`app/services/llm_provider_audit_service.py`) - Сервис аудит логирования
  - `log_action()` - Логирование операции с провайдером
  - `get_audit_log()` - Получение истории операций

- **LLMProviders REST Router** (`app/routes/llm_providers.py`) - REST endpoints для управления провайдерами

#### Обновления компонентов
- **AgentManager** - Обновлены методы создания агентов для поддержки провайдеров
  - `_validate_provider()` - Валидация провайдера
  - `create_agent()` - Добавлен параметр `llm_provider_id`
  - `create_agent_with_project()` - Добавлен параметр `llm_provider_id`
  - `update_agent_provider()` - Новый метод для изменения провайдера агента

- **ContextualAgent** - Интеграция с провайдерами
  - Использование `provider.litellm_model_name` при выполнении запроса
  - `_get_agent_provider_id()` - Получение ID провайдера агента
  - `_record_provider_usage()` - Запись использования провайдера

### 🧪 Тестирование

#### Новые тесты
- **test_llm_provider_api.py** - 34 API end-to-end теста:
  - CRUD операции (create, read, update, delete)
  - Авторизация (401 для неавторизованного доступа)
  - Пользовательская изоляция и multi-user сценарии
  - Пагинация и фильтрация
  - Audit log функциональность
  - Public endpoints (provider types)
  - Ошибки (404, 409, 422)
  - Edge cases (duplicate names, invalid formats)

- **test_agent_llm_provider_integration.py** - 11 интеграционных тестов:
  - Создание агентов с провайдерами
  - Валидация провайдеров
  - Обновление провайдера агента
  - Audit log записи при смене провайдера
  - Обработка ошибок и edge cases

- **test_llm_provider_service.py** - Дополнительные тесты resilience:
  - Timeout сценарии (60s timeout)
  - Запрет обновления api_key
  - Разрешение обновления других параметров config

- **test_litellm_client.py** - Тесты для retry logic:
  - Успешные retry после timeout
  - Отсутствие retry для HTTP status errors
  - Exponential backoff проверка

### 📚 Документация

#### Новые документы
- **doc/llm-providers-api.md** - Полная API документация управления провайдерами
  - Все endpoints с примерами запросов/ответов
  - Обработка ошибок и коды ошибок
  - Примеры использования
  - Информация о безопасности и retry logic

#### Обновленные документы
- **README.md** - Добавлена секция о LLM провайдерах с примерами
- **doc/rest-api.md** - Добавлена ссылка на LLM Providers API
- Все новые классы и методы имеют подробные docstrings на русском

### 🔐 Безопасность

- API ключи хранятся в LiteLLM (secure vault), не в PostgreSQL
- API ключи не логируются в logs или audit
- Полная изоляция между пользователями на middleware уровне
- Валидация на запрет обновления api_key (должно быть удаление + создание)
- Все операции логируются с IP адресом для аудита

### ⚡ Производительность

- **Retry logic с exponential backoff** - Улучшенная надежность при сетевых ошибках
- **Индексы на БД** - Оптимизированы queries для получения провайдеров
- **Кэширование** - Провайдеры кэшируются в памяти при использовании агентами
- **Пагинация** - Поддержка списков провайдеров с большим количеством записей

### 🐛 Исправления

- Обработка timeout при тестировании провайдеров
- Валидация конфигурации при добавлении провайдера
- Корректная обработка ошибок при удалении провайдера

### 📝 Notes

- Все операции с провайдерами требуют JWT авторизации
- Public endpoint для получения типов провайдеров не требует авторизации
- Провайдер не может быть удалён если его используют агенты
- API ключ не может быть обновлён (нужно удалить и создать новый)
- Все timeout операции имеют лимит 60 секунд

### 🔗 Связанные изменения

- Поддержка multi-provider архитектуры в AgentManager
- Обновление миграции для добавления llm_provider_id в user_agents
- Интеграция с LiteLLM для управления моделями провайдеров

---

## Migration Guide

### Для пользователей

1. **Добавить провайдер:**
   ```bash
   POST /my/llm-providers
   ```

2. **Создать агента с провайдером:**
   ```bash
   POST /my/projects/{project_id}/agents/
   # Добавить llm_provider_id в request
   ```

3. **Переключить провайдера агента:**
   ```bash
   PATCH /my/projects/{project_id}/agents/{agent_id}/llm-provider/
   ```

### Для разработчиков

1. **Обновить create_agent() calls:**
   ```python
   # Before
   agent = await manager.create_agent(name, config)
   
   # After
   agent = await manager.create_agent(name, config, llm_provider_id=provider_id)
   ```

2. **Использовать ContextualAgent с провайдером:**
   ```python
   # Before
   contextual_agent = ContextualAgent(agent_id, user_id, name, config, qdrant_client)
   
   # After
   contextual_agent = ContextualAgent(
       agent_id, user_id, name, config, qdrant_client, 
       llm_provider=provider  # Новый параметр
   )
   ```

---

## Breaking Changes

❌ **Нет breaking changes**

Все изменения backward compatible. Провайдер является опциональным параметром.

---

## Future Enhancements

- [ ] Поддержка custom model names для каждого провайдера
- [ ] Rate limiting и quotas по провайдерам
- [ ] Cost tracking для каждого провайдера
- [ ] Automatic fallback на другой провайдер при ошибке
- [ ] Load balancing между провайдерами
- [ ] A/B testing для сравнения провайдеров

---

## Contributors

- Team: OpenIdeaLab
- Date: 2026-03-09
