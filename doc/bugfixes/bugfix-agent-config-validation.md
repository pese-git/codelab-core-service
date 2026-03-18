# Исправление ошибки валидации AgentConfig

**Дата:** 2026-02-20  
**Статус:** ✅ Исправлено

## Проблема

При инициализации Worker Space возникала ошибка валидации Pydantic:

```
1 validation error for AgentConfig
name
  Field required [type=missing, input_value={'model': 'openrouter/ope...imated_duration': 10.0}}, input_type=dict]
```

## Причина

Структура `DEFAULT_AGENTS_CONFIG` в [`app/core/starter_pack.py`](../app/core/starter_pack.py) была неправильной:

**Неправильная структура:**
```python
{
    "name": "Architect",  # ← name вне config
    "config": {
        "model": "...",
        # name отсутствует внутри config
    }
}
```

**Требуемая структура согласно [`AgentConfig`](../app/schemas/agent.py):**
```python
class AgentConfig(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)  # ← REQUIRED
    system_prompt: str
    model: str
    tools: list[str]
    ...
```

## Решение

### 1. Обновлена структура DEFAULT_AGENTS_CONFIG

Добавлено поле `name` внутрь `config` для всех 5 агентов:
- Architect
- Orchestrator  
- CodeAssistant
- DataAnalyst
- DocumentWriter

Также добавлены недостающие обязательные поля `concurrency_limit` и `max_tokens` для CodeAssistant, DataAnalyst и DocumentWriter.

### 2. Исправлена логика чтения в AgentManager

В [`app/agents/manager.py`](../app/agents/manager.py) обновлены методы чтения агентов:

**Было:**
```python
config=AgentConfig(name=agent.name, **agent.config)
```

**Стало:**
```python
config=AgentConfig(**agent.config) if isinstance(agent.config, dict) else agent.config
```

Это позволяет правильно обрабатывать новую структуру, где `name` уже внутри `config`.

### 3. Обновлены тесты

Тесты в [`tests/test_create_project_with_starter_pack.py`](../tests/test_create_project_with_starter_pack.py) обновлены для проверки всех 5 агентов вместо 3.

## Результат

✅ Ошибка валидации устранена  
✅ Все агенты имеют `name` внутри `config`  
✅ Тесты проходят успешно  
✅ Сервис запускается без ошибок

## Затронутые файлы

- [`app/core/starter_pack.py`](../app/core/starter_pack.py) - обновлена структура DEFAULT_AGENTS_CONFIG
- [`app/agents/manager.py`](../app/agents/manager.py) - исправлена логика чтения AgentConfig
- [`tests/test_create_project_with_starter_pack.py`](../tests/test_create_project_with_starter_pack.py) - обновлены тесты

## Проверка

```bash
# Валидация конфигурации агентов
uv run python -c "from app.core.starter_pack import DEFAULT_AGENTS_CONFIG; from app.schemas.agent import AgentConfig; [AgentConfig(**agent['config']) for agent in DEFAULT_AGENTS_CONFIG]; print('✅ Все агенты валидны!')"

# Запуск тестов
uv run pytest tests/test_create_project_with_starter_pack.py -v
```
