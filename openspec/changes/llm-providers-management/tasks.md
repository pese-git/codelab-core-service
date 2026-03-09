# Задачи: Система управления LLM провайдерами

## 1. Подготовка БД и миграции

- [x] 1.1 Создать миграцию для таблицы `user_llm_providers`
- [x] 1.2 Создать миграцию для таблицы `llm_provider_audit_log`
- [x] 1.3 Создать миграцию для добавления колонки `llm_provider_id` в `user_agents`
- [x] 1.4 Создать индексы для оптимизации queries
- [x] 1.5 Запустить миграцию на dev окружении и проверить

## 2. SQLAlchemy модели

- [x] 2.1 Создать модель `UserLLMProvider` в `app/models/user_llm_provider.py`
- [x] 2.2 Создать модель `LLMProviderAuditLog` в `app/models/llm_provider_audit_log.py`
- [x] 2.3 Обновить модель `UserAgent` - добавить поле `llm_provider_id` с FK и relationship
- [x] 2.4 Обновить модель `User` - добавить relationship к llm_providers
- [x] 2.5 Написать unit тесты для моделей (fixture, ORM операции)

## 3. Pydantic схемы

- [x] 3.1 Создать схемы в `app/schemas/llm_provider.py`: `UserLLMProviderCreate`, `UserLLMProviderUpdate`, `UserLLMProviderResponse`
- [x] 3.2 Создать схему `LLMProviderListResponse` с пагинацией
- [x] 3.3 Создать схему `LLMProviderTestRequest` и `LLMProviderTestResponse`
- [x] 3.4 Создать схему `LLMProviderTypeInfo` и список типов
- [x] 3.5 Создать схему `LLMProviderAuditLogEntry`

## 4. LiteLLMClient сервис

- [x] 4.1 Создать `app/services/litellm_client.py` с классом `LiteLLMClient`
- [x] 4.2 Реализовать метод `add_model()` для регистрации модели в LiteLLM
- [x] 4.3 Реализовать метод `delete_model()` для удаления модели из LiteLLM
- [x] 4.4 Реализовать метод `test_model()` для тестирования подключения
- [x] 4.5 Реализовать метод `_generate_litellm_model_name()` для генерации уникальных имен
- [x] 4.6 Реализовать метод `_build_model_id()` для построения полного model ID
- [x] 4.7 Написать unit тесты для LiteLLMClient (mock httpx, различные сценарии)

## 5. LLMProviderAuditService

- [x] 5.1 Создать `app/services/llm_provider_audit_service.py` с классом `LLMProviderAuditService`
- [x] 5.2 Реализовать метод `log_action()` для логирования операций с валидацией action values
- [x] 5.3 Реализовать метод `get_audit_log()` для получения истории пользователя
- [x] 5.4 Документировать все возможные action values: create, update, delete, test, use (для провайдеров)
- [x] 5.5 Написать unit тесты для LLMProviderAuditService

## 6. LLMProviderService

- [x] 6.1 Создать `app/services/llm_provider_service.py` с классом `LLMProviderService`
- [x] 6.2 Реализовать метод `create_user_provider()` (создание + LiteLLM + аудит)
- [x] 6.3 Реализовать метод `get_user_providers()` (список с фильтрацией)
- [x] 6.4 Реализовать метод `get_user_provider()` (получение конкретного)
- [x] 6.5 Реализовать метод `update_user_provider()` (обновление конфига)
- [x] 6.6 Реализовать метод `delete_user_provider()` (удаление + проверка agents)
- [x] 6.7 Реализовать метод `test_provider()` (тестирование)
- [x] 6.8 Реализовать метод `record_provider_usage()` (отслеживание использования)
- [x] 6.9 Реализовать метод `_count_agents_using_provider()` (проверка использования)
- [x] 6.10 Написать unit тесты для LLMProviderService (TDD - сначала тесты)
- [x] 6.11 Написать интеграционные тесты с БД (transactional fixtures)

## 7. REST API endpoints

- [x] 7.1 Создать роутер `app/routes/project_llm_providers.py`
- [x] 7.2 Реализовать POST `/my/llm-providers` (создание провайдера) - требует авторизации
- [x] 7.3 Реализовать GET `/my/llm-providers` (список провайдеров) - требует авторизации
- [x] 7.4 Реализовать GET `/my/llm-providers/{id}` (получение провайдера) - требует авторизации
- [x] 7.5 Реализовать PATCH `/my/llm-providers/{id}` (обновление) - требует авторизации
- [x] 7.6 Реализовать DELETE `/my/llm-providers/{id}` (удаление) - требует авторизации
- [x] 7.7 Реализовать POST `/my/llm-providers/{id}/test` (тестирование) - требует авторизации
- [x] 7.8 Реализовать GET `/my/llm-providers/available` (доступные провайдеры) - требует авторизации
- [x] 7.9 Реализовать GET `/llm-providers/types` (типы провайдеров) - ПУБЛИЧНЫЙ endpoint (без авторизации)
- [x] 7.10 Реализовать GET `/my/llm-providers/audit` (audit log пользователя) - требует авторизации
- [x] 7.11 Добавить роутер в main.py
- [x] 7.12 Документировать доступ к endpoints (приватные /my/* требуют авторизации, публичные /llm-providers/* без авторизации)
- [x] 7.13 Написать API тесты (end-to-end через HTTP) включая неавторизованный доступ к приватным endpoints

## 8. Интеграция с агентами

- [x] 8.1 Обновить `AgentManager` - добавить параметр `llm_provider_id` в `create_agent()`
- [x] 8.2 Реализовать `AgentManager._validate_provider()` для валидации провайдера
- [x] 8.3 Обновить `ContextualAgent` - использовать `provider.litellm_model_name`
- [x] 8.4 Реализовать `ContextualAgent._get_agent_provider_id()` для получения провайдера агента
- [x] 8.5 Реализовать `ContextualAgent._record_provider_usage()` для записи использования с action="use"
- [x] 8.6 Обновить логику создания агента - делать провайдер обязательным
- [x] 8.7 Обновить логику выполнения агента - использовать модель провайдера
- [x] 8.8 Реализовать PATCH для изменения llm_provider_id агента (валидация, логирование с action="provider_reassigned")
- [x] 8.9 Написать тесты интеграции с AgentManager (включая сценарии смены провайдера и логирование action values)

## 9. Обработка ошибок и resilience

- [x] 9.1 Реализовать retry logic с exponential backoff для LiteLLM API calls (макс 3 попытки, стартовая задержка 1s)
- [x] 9.2 Добавить валидацию на запрет обновления api_key в update_user_provider()
- [x] 9.3 Добавить тесты для timeout scenarios (60s timeout) в unit/integration тестах

## 10. Конфигурация

- [x] 10.1 Обновить `app/config.py` - добавить `litellm_url`, `litellm_master_key`
- [x] 10.2 Обновить `.env.example` с новыми переменными
- [x] 10.3 Обновить `docker-compose.yml` для LiteLLM service (если требуется)
- [x] 10.4 Обновить docs с новыми конфигурационными параметрами

## 11. Документация и обновления

- [ ] 11.1 Обновить README с информацией о LLM провайдерах
- [ ] 11.2 Обновить `doc/rest-api.md` с новыми endpoints
- [ ] 11.3 Обновить `doc/architecture/api-specification.md` если требуется
- [ ] 11.4 Добавить docstrings на русском ко всем новым классам и методам
- [ ] 11.5 Обновить CHANGELOG с описанием новой функциональности

## 12. Тестирование и валидация

- [ ] 12.1 Запустить все unit тесты - проверить 100% coverage новых модулей
- [ ] 12.2 Запустить все интеграционные тесты
- [ ] 12.3 Запустить API тесты через pytest
- [ ] 12.4 Проверить линтинг через ruff
- [ ] 12.5 Проверить type hints через mypy (если используется)
- [ ] 12.6 Написать и запустить smoke тесты на dev окружении
- [ ] 12.7 Проверить edge cases: обработка ошибок, таймауты, невалидные ключи

## 13. Финальные проверки

- [ ] 13.1 Убедиться, что миграции применяются корректно
- [ ] 13.2 Убедиться, что все endpoints работают и возвращают корректные коды статуса
- [ ] 13.3 Убедиться, что API ключи НЕ логируются и НЕ хранятся в PostgreSQL
- [ ] 13.4 Убедиться, что изоляция пользователей работает корректно
- [ ] 13.5 Убедиться, что все операции логируются в audit log
- [ ] 13.6 Провести код-ревью
- [ ] 13.7 Обновить документацию по завершении
