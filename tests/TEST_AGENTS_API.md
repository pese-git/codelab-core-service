# Тесты REST API для `/my/agents/`

## Обзор

Файл [`test_agents_api.py`](test_agents_api.py) содержит комплексные тесты для всех эндпоинтов управления агентами.

## Статистика

- **Всего тестов**: 24
- **Статус**: ✅ Все тесты проходят
- **Покрытие модуля** [`app/routes/agents.py`](../app/routes/agents.py): 77%

## Структура тестов

### 1. TestCreateAgent (POST `/my/agents/`)

Тесты создания новых агентов:

- ✅ `test_create_agent_success` - успешное создание агента с полной конфигурацией
- ✅ `test_create_agent_minimal_config` - создание с минимальной конфигурацией (проверка дефолтных значений)
- ✅ `test_create_agent_invalid_name` - валидация пустого имени
- ✅ `test_create_agent_invalid_temperature` - валидация температуры вне диапазона (0.0-2.0)
- ✅ `test_create_agent_invalid_concurrency` - валидация лимита конкурентности (1-10)
- ✅ `test_create_agent_unauthorized` - проверка требования аутентификации

**Проверяемые аспекты:**
- Корректное сохранение всех полей конфигурации
- Применение дефолтных значений
- Валидация входных данных (Pydantic)
- Генерация UUID и timestamp
- Статус агента по умолчанию (`ready`)
- Требование JWT токена

### 2. TestListAgents (GET `/my/agents/`)

Тесты получения списка агентов:

- ✅ `test_list_agents_empty` - пустой список для нового пользователя
- ✅ `test_list_agents_with_data` - список с несколькими агентами
- ✅ `test_list_agents_user_isolation` - изоляция данных между пользователями
- ✅ `test_list_agents_unauthorized` - проверка требования аутентификации

**Проверяемые аспекты:**
- Корректный формат ответа (`agents`, `total`)
- Возврат всех агентов пользователя
- Изоляция данных (пользователь видит только свои агенты)
- Различные статусы агентов (`ready`, `busy`)

### 3. TestGetAgent (GET `/my/agents/{agent_id}`)

Тесты получения конкретного агента:

- ✅ `test_get_agent_success` - успешное получение агента по ID
- ✅ `test_get_agent_not_found` - 404 для несуществующего ID
- ✅ `test_get_agent_wrong_user` - 404 при попытке доступа к чужому агенту
- ✅ `test_get_agent_invalid_uuid` - 422 для невалидного UUID
- ✅ `test_get_agent_unauthorized` - проверка требования аутентификации

**Проверяемые аспекты:**
- Полнота возвращаемых данных
- Изоляция данных между пользователями
- Валидация UUID формата
- Корректные HTTP статусы

### 4. TestUpdateAgent (PUT `/my/agents/{agent_id}`)

Тесты обновления конфигурации агента:

- ✅ `test_update_agent_success` - успешное обновление всех полей
- ✅ `test_update_agent_not_found` - 404 для несуществующего агента
- ✅ `test_update_agent_wrong_user` - 404 при попытке обновить чужого агента
- ✅ `test_update_agent_invalid_config` - валидация новой конфигурации
- ✅ `test_update_agent_unauthorized` - проверка требования аутентификации

**Проверяемые аспекты:**
- Обновление имени агента
- Обновление всех параметров конфигурации
- Валидация новых значений
- Изоляция данных между пользователями
- Сохранение изменений в БД

### 5. TestDeleteAgent (DELETE `/my/agents/{agent_id}`)

Тесты удаления агента:

- ✅ `test_delete_agent_success` - успешное удаление с проверкой в БД
- ✅ `test_delete_agent_not_found` - 404 для несуществующего агента
- ✅ `test_delete_agent_wrong_user` - 404 при попытке удалить чужого агента
- ✅ `test_delete_agent_unauthorized` - проверка требования аутентификации

**Проверяемые аспекты:**
- HTTP 204 при успешном удалении
- Физическое удаление из БД
- Изоляция данных между пользователями
- Сохранность чужих агентов

## Тестовая инфраструктура

### Фикстуры (из [`conftest.py`](conftest.py))

- `test_engine` - in-memory SQLite база для тестов
- `db_session` - сессия БД с автоматическим rollback
- `test_user` - тестовый пользователь с фиксированным UUID
- `test_jwt_token` - валидный JWT токен для аутентификации
- `auth_headers` - заголовки с Bearer токеном
- `mock_redis` - мок Redis клиента
- `mock_qdrant` - мок Qdrant клиента
- `client_with_mocks` - HTTP клиент с замоканными зависимостями

### Моки внешних сервисов

Тесты используют моки для:
- **Redis** - кеширование конфигураций агентов
- **Qdrant** - векторное хранилище контекста агентов

Это позволяет тестировать API без реальных внешних зависимостей.

## Покрытие безопасности

Все тесты проверяют:

1. **Аутентификация** - требование JWT токена для всех операций
2. **Авторизация** - изоляция данных между пользователями
3. **Валидация** - проверка входных данных через Pydantic схемы

## Запуск тестов

```bash
# Запуск всех тестов агентов
uv run pytest tests/test_agents_api.py -v

# Запуск конкретного класса тестов
uv run pytest tests/test_agents_api.py::TestCreateAgent -v

# Запуск конкретного теста
uv run pytest tests/test_agents_api.py::TestCreateAgent::test_create_agent_success -v

# С покрытием кода
uv run pytest tests/test_agents_api.py --cov=app/routes/agents --cov-report=html
```

## Примеры тестовых данных

### Минимальная конфигурация агента
```json
{
  "name": "minimal_agent",
  "system_prompt": "You are a helpful assistant"
}
```

### Полная конфигурация агента
```json
{
  "name": "test_coder",
  "system_prompt": "You are an expert Python developer",
  "model": "gpt-4-turbo-preview",
  "tools": ["code_executor", "file_reader"],
  "concurrency_limit": 3,
  "temperature": 0.7,
  "max_tokens": 4096,
  "metadata": {"specialty": "backend"}
}
```

## Известные ограничения

1. **Покрытие 77%** - не покрыты некоторые edge cases в обработке ошибок
2. **Моки** - реальное взаимодействие с Redis/Qdrant не тестируется
3. **Асинхронность** - тесты выполняются последовательно

## Связанные файлы

- [`app/routes/agents.py`](../app/routes/agents.py) - тестируемые эндпоинты
- [`app/agents/manager.py`](../app/agents/manager.py) - бизнес-логика управления агентами
- [`app/schemas/agent.py`](../app/schemas/agent.py) - Pydantic схемы
- [`app/models/user_agent.py`](../app/models/user_agent.py) - SQLAlchemy модель
- [`conftest.py`](conftest.py) - общие фикстуры

## Рекомендации по улучшению

1. Добавить интеграционные тесты с реальными Redis/Qdrant
2. Тестировать параллельное создание агентов
3. Добавить тесты производительности для больших списков
4. Тестировать граничные случаи (очень длинные промпты, большие metadata)
5. Добавить тесты для каскадного удаления связанных сущностей
