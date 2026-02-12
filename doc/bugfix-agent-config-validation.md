# Исправление: Ошибка валидации AgentConfig

## Проблема

При выполнении `GET /my/agents/` возникала ошибка валидации Pydantic:

```
Field required [type=missing, input_value={'model': 'gpt-4-turbo-pr...}, input_type=dict]
```

## Причина

В базе данных поле `config` (JSON) хранилось двумя способами:

1. **Seed данные** (scripts/init_db.py): `config` НЕ содержал поле `name`
2. **API создание** (app/agents/manager.py): `config` СОДЕРЖАЛ поле `name` (дублирование с `UserAgent.name`)

При десериализации `AgentConfig(**agent.config)` требовалось обязательное поле `name`, которого не было в seed данных.

## Решение

Исключить поле `name` из `config` при сохранении, так как оно уже хранится в отдельном поле `UserAgent.name`.

### Изменения в `app/agents/manager.py`

#### 1. Метод `create_agent()` (строка 35-43)

**Было:**
```python
agent = UserAgent(
    user_id=self.user_id,
    name=config.name,
    config=config.model_dump(),
    status=AgentStatus.READY.value,
)
```

**Стало:**
```python
# Exclude 'name' from config as it's stored separately in UserAgent.name
config_dict = config.model_dump(exclude={'name'})
agent = UserAgent(
    user_id=self.user_id,
    name=config.name,
    config=config_dict,
    status=AgentStatus.READY.value,
)
```

#### 2. Метод `update_agent()` (строка 114-129)

**Было:**
```python
# Update config
agent.config = config.model_dump()
await self.db.flush()
```

**Стало:**
```python
# Update config (exclude 'name' as it's stored separately)
agent.name = config.name
agent.config = config.model_dump(exclude={'name'})
await self.db.flush()
```

#### 3. Методы чтения: `get_agent()`, `list_agents()`, `get_agent_by_name()`

**Было:**
```python
config=AgentConfig(**agent.config)
```

**Стало:**
```python
config=AgentConfig(name=agent.name, **agent.config)
```

## Результат

✅ Все операции CRUD для агентов работают корректно:
- `POST /my/agents/` - создание агента
- `GET /my/agents/` - список агентов
- `GET /my/agents/{id}` - получение агента
- `PUT /my/agents/{id}` - обновление агента
- `DELETE /my/agents/{id}` - удаление агента

✅ Seed данные корректно десериализуются
✅ Нет дублирования поля `name` в JSON config
✅ Логирование работает корректно

## Тестирование

```bash
# Генерация JWT токена
docker-compose exec app python scripts/generate_test_jwt.py --user-id 3c07246a-6310-4e83-aa5c-73c6010d74f1

# Список агентов
curl -X GET "http://localhost:8000/my/agents/" \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json"

# Создание агента
curl -X POST "http://localhost:8000/my/agents/" \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "TestAgent",
    "system_prompt": "You are a test agent",
    "model": "gpt-4-turbo-preview",
    "tools": ["test_tool"],
    "concurrency_limit": 2,
    "temperature": 0.5,
    "max_tokens": 2048,
    "metadata": {"test": true}
  }'

# Обновление агента
curl -X PUT "http://localhost:8000/my/agents/{agent_id}" \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "config": {
      "name": "UpdatedAgent",
      "system_prompt": "Updated prompt",
      "model": "gpt-4-turbo-preview",
      "tools": ["updated_tool"],
      "concurrency_limit": 5,
      "temperature": 0.9,
      "max_tokens": 8192,
      "metadata": {"updated": true}
    }
  }'

# Удаление агента
curl -X DELETE "http://localhost:8000/my/agents/{agent_id}" \
  -H "Authorization: Bearer <TOKEN>"
```

## Дата исправления

2026-02-12
