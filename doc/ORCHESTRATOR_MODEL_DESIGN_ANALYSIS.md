# Анализ дизайна: UserOrchestrator vs UserAgent подход

**Дата**: 2026-02-22  
**Контекст**: Выбор между двумя архитектурными подходами для моделирования Orchestrator в системе

---

## 📊 Сравнительная таблица

| Критерий | UserOrchestrator (отдельная модель) | UserAgent (unified модель) |
|----------|--------------------------------------|-------------------------|
| **Таблиц в БД** | 2 (user_agents + user_orchestrators) | 1 (user_agents) |
| **Текущее использование** | ❌ Не используется | ✅ Активно используется |
| **Гибкость** | 🟡 Ограниченная (специфична для оркестратора) | ✅ Максимальная (подходит для любых агентов) |
| **Кол-во код а** | 🟡 Больше (2 модели, 2 сета операций) | ✅ Меньше (1 модель, 1 сет операций) |
| **Сложность запросов** | 🟡 Выше (JOIN двух таблиц) | ✅ Ниже (одна таблица) |
| **Масштабируемость** | 🟡 Проблемы при добавлении новых типов агентов | ✅ Легко добавлять новые типы |
| **Производительность** | 🟡 Возможны N+1 queries | ✅ Оптимальные query patterns |
| **Куб возможности** | 🟡 Только оркестратор | ✅ Architect, Code, Ask, Debug, Orchestrator и кастомные |

---

## 🏗️ Архитектурный анализ

### Подход 1: Отдельная модель UserOrchestrator

#### Структура
```
user_orchestrators (отдельная таблица)
├── id
├── user_id (FK → users)
├── project_id (FK → user_projects)
├── config (JSON)
└── created_at

user_agents (для остальных агентов)
├── id
├── user_id (FK → users)
├── project_id (FK → user_projects)
├── name
├── config (JSON)
├── status
└── created_at
```

#### ✅ Преимущества

**1. Явная семантика**
```
UserOrchestrator = "Это конфигурация системы оркестрации для проекта"
UserAgent = "Это агент (Architect, Code, Ask, etc.)"
```
Клиенты кода сразу видят: "оркестратор — это специальный объект"

**2. Специализированная конфигурация**
```
UserOrchestrator.config может содержать:
{
  "routing_strategy": "capability_matching",
  "max_parallel_agents": 3,
  "approval_threshold_cost": 0.10,
  "approval_threshold_tasks": 3,
  "concurrency_strategy": "greedy|optimal",
  "error_handling": "fail_fast|continue_on_error"
}
```
Не смешивается с конфигурацией агентов.

**3. Защита от случайных ошибок**
```python
# ✅ ПРАВИЛЬНО: ясно, что работаем с оркестратором
orchestrator = db.query(UserOrchestrator).filter(...).first()

# ❌ ЛЕГКО ОШИБИТЬСЯ: найти не того агента
agent = db.query(UserAgent).filter(name="orchestrator").first()
# Что если agent не найден? Что если найден неправильный?
```

**4. Per-project customization**
Каждый проект может иметь свой уникальный оркестратор с разной стратегией.

#### ❌ Недостатки

**1. Дублирование кода и логики**
```python
# Для UserOrchestrator нужен свой:
class UserOrchestratorManager:
    async def create_orchestrator(self, user_id, project_id, config):
        ...
    async def update_orchestrator(self, ...):
        ...
    async def delete_orchestrator(self, ...):
        ...

# А для UserAgent свой:
class AgentManager:
    async def create_agent(self, ...):
        ...
    async def update_agent(self, ...):
        ...
    async def delete_agent(self, ...):
        ...
```

**2. N+1 queries при получении всех агентов проекта**
```python
# Если нужны ВСЕ "агенты" (включая оркестратор):
orchestrators = await db.execute(
    select(UserOrchestrator).filter(project_id=project_id)
)
agents = await db.execute(
    select(UserAgent).filter(project_id=project_id)
)
# ВМЕСТО одного запроса - два отдельных
# Нужно мержить результаты в коде
all_items = list(orchestrators) + list(agents)
```

**3. Миграция сложнее**
```sql
-- Добавляем новую таблицу
CREATE TABLE user_orchestrators (...)

-- Переносим конфиги из... откуда?
-- Если оркестратор конфиг хранится в user_agents:
INSERT INTO user_orchestrators (...)
SELECT * FROM user_agents WHERE role = 'orchestrator'

-- Или если нигде не хранится - нужна миграция данных
```

**4. Синхронизация между таблицами**
```python
# Если пользователь удаляет оркестратор:
await db.delete(UserOrchestrator)
await db.commit()

# Нужно ли удалять что-то в user_agents? 
# Состояние разделено между двумя таблицами → сложнее гарантировать consistency
```

**5. Это "специальный" объект, но обрабатывается как "еще один объект"**
```python
# В коде нужно постоянно помнить о двух типах:
async def get_all_agents_in_project(project_id):
    agents = ...
    orchestrator = ...
    return agents, orchestrator  # Кортеж вместо списка

# Вместо:
async def get_all_agents_in_project(project_id):
    return [UserAgent]  # Простой список
```

---

### Подход 2: Unified UserAgent (использовать для оркестратора)

#### Структура
```
user_agents (одна таблица для ВСЕ агентов)
├── id
├── user_id (FK → users)
├── project_id (FK → user_projects)
├── name (например: "Architect", "Orchestrator", "Code", "Custom LLM")
├── config (JSON)
│   └── metadata:
│       ├── role (architect, orchestrator, code, ask, debug, custom)
│       ├── capabilities (список умений)
│       ├── cost_per_call
│       └── estimated_duration
├── status (ready, busy, error)
└── created_at
```

#### ✅ Преимущества

**1. DRY принцип — нет дублирования**
```python
# Один manager для всего:
class AgentManager:
    async def create_agent(self, name, config):
        # Работает для Architect, Code, Orchestrator, и кастомных агентов
        ...
    
    async def update_agent(self, agent_id, config):
        ...
    
    async def delete_agent(self, agent_id):
        ...
```

**2. Простые и оптимальные query'и**
```python
# Получить ВСЕ агенты (включая оркестратор):
agents = await db.execute(
    select(UserAgent)
    .where(UserAgent.project_id == project_id)
    .where(UserAgent.status == "ready")
)
# Один запрос, возвращает ВСЕ готовые агенты

# Получить только оркестратор:
orchestrator = await db.execute(
    select(UserAgent)
    .where(UserAgent.project_id == project_id)
    .where(UserAgent.config['metadata']['role'] == 'orchestrator')
).scalar_one()

# Получить агентов с capability "code_implementation":
code_agents = await db.execute(
    select(UserAgent)
    .where(UserAgent.project_id == project_id)
    .where(UserAgent.config['metadata']['capabilities'].contains("code_implementation"))
)
```

**3. Легко расширяется новыми типами агентов**
```python
# Добавить нового кастомного агента?
new_agent = UserAgent(
    name="CustomAnalyzer",
    project_id=project_id,
    config={
        "model": "custom-model",
        "metadata": {
            "role": "custom",
            "capabilities": ["analyze_data", "generate_report"],
        }
    }
)
# БЕЗ миграций БД, БЕЗ новых моделей

# Оркестратор может использовать его в маршрутизации
routing_score = calculate_match(user_query, new_agent.config)
```

**4. Миграция проста**
```sql
-- Не нужна новая таблица!
-- Просто добавляем агента со специальной ролью:
INSERT INTO user_agents (user_id, project_id, name, config, status)
VALUES (
    user_id,
    project_id,
    'Orchestrator',
    jsonb_build_object(
        'model', 'gpt-4',
        'metadata', jsonb_build_object(
            'role', 'orchestrator',
            'capabilities', ARRAY['workflow_management', 'task_routing']
        )
    ),
    'ready'
);
```

**5. Гибкость для будущего**
```python
# Если в будущем захотим:
# - несколько оркестраторов с разными стратегиями
# - динамически переключаться между оркестраторами
# - A/B тестировать стратегии оркестрации

# С UserAgent просто создаем нескольких:
orchestrator_v1 = UserAgent(name="OrchestratorGreedy", ...)
orchestrator_v2 = UserAgent(name="OrchestratorOptimal", ...)

# И выбираем какой использовать в runtime
```

**6. Per-project конфигурация сохраняется**
```python
# Каждый агент может иметь свой config по проекту:
orchestrator_config_project_a = {
    "model": "gpt-4",
    "metadata": {
        "role": "orchestrator",
        "max_parallel": 5,  # Project A разрешает много параллельных
        "approval_threshold": 0.20
    }
}

orchestrator_config_project_b = {
    "model": "gpt-3.5",
    "metadata": {
        "role": "orchestrator",
        "max_parallel": 2,  # Project B более консервативна
        "approval_threshold": 0.05
    }
}

# Это все еще в config, просто хранится в user_agents
```

#### ❌ Недостатки

**1. Менее явная семантика**
```python
orchestrator = db.query(UserAgent)\
    .filter(UserAgent.project_id == project_id)\
    .filter(UserAgent.config['metadata']['role'] == 'orchestrator')\
    .first()

# Новый разработчик может не понять что это оркестратор
# Vs. UserOrchestrator был бы явнее
```

**2. Проверка role в runtime (не в compile time)**
```python
# ❌ НЕПРАВИЛЬНО:
orchestrator = find_agent_by_role(db, "orchestartor")  # Опечатка!
# Ошибка обнаружится только в runtime

# Vs. с UserOrchestrator был бы type-safe
orchestrator: UserOrchestrator = db.query(UserOrchestrator).first()
# Тип гарантирует что это оркестратор
```

**3. Смешивание конфигов в JSON**
```python
config = {
    "model": "gpt-4",
    "temperature": 0.4,
    "system_prompt": "...",
    "metadata": {
        "role": "orchestrator",  # ← role в metadata
        "capabilities": [...],
        "cost_per_call": 0.01,
        "max_parallel": 3
    },
    "tools": []
}
# Нужно знать структуру config для оркестратора
# Иначе используешь неправильно
```

**4. Возможна ошибка: обработать оркестратор как обычный агент**
```python
async def execute_agent(agent_id):
    agent = db.query(UserAgent).filter_by(id=agent_id).first()
    
    # ❌ ПРОБЛЕМА: если agent — это Orchestrator, мы попытаемся 
    # выполнить его как обычного агента!
    result = await agent.execute(user_message)
    
    # Это не сработает правильно, потому что Orchestrator
    # не должен выполняться как обычный агент
```

**5. Индексирование и поиск сложнее**
```sql
-- Нужен индекс на JSON field (дороговато):
CREATE INDEX ix_agents_role ON user_agents 
USING GIN (config -> 'metadata' -> 'role');

-- Vs. с отдельной таблицей был бы просто индекс на PK:
CREATE INDEX ix_orchestrators_project ON user_orchestrators(project_id);
```

---

## 💡 Практический анализ

### Текущее состояние кода

**В starter_pack.py**:
```python
DEFAULT_AGENTS_CONFIG = [
    {
        "name": "Architect",
        "config": {
            "metadata": {"role": "architect", ...}
        }
    },
    {
        "name": "Orchestrator",
        "config": {
            "metadata": {"role": "orchestrator", ...}
        }
    },
    # ... остальные агенты
]
```

→ **Все хранятся как UserAgent с разными ролями!**

**В поиске оркестратора**:
```python
orchestrator_id = await find_agent_by_role(db, user_id, project_id, "orchestrator")
```

→ **Уже ищется как UserAgent с role="orchestrator"!**

**Вывод**: Архитектура уже реализует Подход 2 (UserAgent для всех).
`UserOrchestrator` таблица — это наследие, которое никогда не использовалось.

---

## 🎯 Рекомендация

### ✅ Рекомендуемый подход: **Unified UserAgent**

**Причины**:

1. **Уже реализовано в коде** — DEFAULT_AGENTS_CONFIG использует один формат для всех агентов
2. **Соответствует текущему использованию** — find_agent_by_role уже ищет по role в UserAgent
3. **DRY принцип** — один manager, один table, одна логика CRUD
4. **Масштабируемо** — легко добавлять новые типы агентов (Custom Agent, Analyzer, Reporter, и т.д.)
5. **Гибко** — возможность иметь несколько оркестраторов с разными стратегиями
6. **Простая миграция** — просто удалить неиспользуемую таблицу

### ❌ Почему НЕ UserOrchestrator

1. **Дублирование** — вторая таблица, вторая модель, вторая логика CRUD
2. **Неиспользуемо** — таблица существует, но никогда не вызывается в коде
3. **Усложнение** — нужны JOIN'и, синхронизация между таблицами
4. **Противоречит текущему design** — остальные агенты хранятся в UserAgent

### 📋 Рекомендуемые улучшения при unified подходе

**1. Укрепить семантику через helpers**
```python
async def get_orchestrator(db, user_id, project_id) -> Optional[UserAgent]:
    """Get the orchestrator agent for a project (or None if not found)."""
    return await db.execute(
        select(UserAgent)
        .where(UserAgent.user_id == user_id)
        .where(UserAgent.project_id == project_id)
        .where(UserAgent.config['metadata']['role'].astext == 'orchestrator')
    ).scalar_one_or_none()

async def get_agents_by_role(db, project_id, role: str) -> list[UserAgent]:
    """Get all agents with a specific role."""
    return (await db.execute(
        select(UserAgent)
        .where(UserAgent.project_id == project_id)
        .where(UserAgent.config['metadata']['role'].astext == role)
    )).scalars().all()
```

**2. Типизировать роли через Enum**
```python
from enum import Enum

class AgentRole(str, Enum):
    ARCHITECT = "architect"
    ORCHESTRATOR = "orchestrator"
    CODE = "code"
    ASK = "ask"
    DEBUG = "debug"
    CUSTOM = "custom"

# Использование:
async def get_orchestrator(db, project_id):
    return await get_agents_by_role(db, project_id, AgentRole.ORCHESTRATOR)
```

**3. Валидировать структуру config в приложении**
```python
class AgentConfigValidator:
    @staticmethod
    def validate_orchestrator_config(config: dict):
        """Ensure orchestrator config has required fields."""
        required_keys = ["model", "metadata"]
        if "metadata" not in config:
            raise ValueError("Missing metadata in config")
        
        metadata = config["metadata"]
        if metadata.get("role") != "orchestrator":
            raise ValueError("Config role must be 'orchestrator'")
        
        if "capabilities" not in metadata:
            raise ValueError("Missing capabilities in metadata")
        
        return True
```

**4. Документировать структуру config для разных ролей**
```python
# docs/AGENT_CONFIG_SCHEMA.md

## Orchestrator Agent Config

config = {
    "model": "openrouter/openai/gpt-4.1",
    "temperature": 0.4,
    "system_prompt": "...",
    "tools": [],
    "metadata": {
        "role": "orchestrator",
        "capabilities": ["workflow_management", "task_routing", "dependency_tracking"],
        "risk_level": "LOW",
        "cost_per_call": 0.01,
        "estimated_duration": 5.0,
        # ORCHESTRATOR-specific fields:
        "max_parallel_agents": 3,
        "approval_threshold_cost": 0.10,
        "approval_threshold_tasks": 3,
    }
}
```

---

## 🗑️ Миграция: Удаление UserOrchestrator

### Шаги

1. **Verify что ничего не использует UserOrchestrator**
```bash
grep -r "UserOrchestrator" app/ --include="*.py"
# Результат должен быть только импорты и отношения
```

2. **Создать migration для удаления таблицы**
```python
# migrations/versions/YYYY_MM_DD_HHMM_###_remove_user_orchestrator.py
def upgrade():
    op.drop_table('user_orchestrators')

def downgrade():
    op.create_table('user_orchestrators', ...)
```

3. **Удалить model и отношения**
```python
# app/models/user_orchestrator.py — delete file
# app/models/user.py — remove orchestrators relationship
# app/models/user_project.py — remove orchestrators relationship
# app/models/__init__.py — remove UserOrchestrator import
```

4. **Обновить tests** если есть

5. **Deploy** migration

---

## Итоговый вывод

| Аспект | Unified UserAgent | Отдельная UserOrchestrator |
|--------|-------------------|---------------------------|
| **Архитектурная целостность** | ✅ ВСЕ агенты одного типа | ❌ Специальный случай |
| **Код сложность** | ✅ DRY, одна модель | ❌ Дублирование |
| **Query эффективность** | ✅ Одна таблица | ❌ JOIN необходимы |
| **Масштабируемость** | ✅ Легко добавлять новые роли | ❌ Нужны новые таблицы |
| **Текущее использование** | ✅ ВСЕ существующие агенты используют это | ❌ Не используется в коде |
| **Гибкость** | ✅ Несколько оркестраторов, A/B тестирование | ❌ Одна таблица = один оркестратор |
| **Type safety** | ⚠️ Runtime role checking | ✅ Type-safe через таблицу |

**РЕКОМЕНДАЦИЯ**: ✅ **Unified UserAgent подход** с улучшениями (helpers, Enum для ролей, валидация конфига).

