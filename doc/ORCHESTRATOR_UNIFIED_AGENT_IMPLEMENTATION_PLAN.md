# План внедрения Unified UserAgent подхода для Orchestrator

**Дата**: 2026-02-22  
**Статус**: Одобрено использовать Unified UserAgent подход  
**Приоритет**: КРИТИЧЕСКИЙ (PHASE 1 для Intelligent Agent Routing)

---

## 📋 Содержание

1. [Общее описание](#общее-описание)
2. [Архитектурные изменения](#архитектурные-изменения)
3. [Этапы внедрения](#этапы-внедрения)
4. [Миграция БД](#миграция-бд)
5. [Код изменения](#код-изменения)
6. [Testing стратегия](#testing-стратегия)
7. [Timeline и ответственность](#timeline-и-ответственность)

---

## Общее описание

### Текущее состояние

```
user_agents таблица (используется активно)
├── Architect Agent ✅
├── Code Agent ✅
├── Ask Agent ✅
├── Debug Agent ✅
└── Orchestrator Agent ✅ (хранится как UserAgent с role="orchestrator")

user_orchestrators таблица (НЕ используется)
└── ❌ Мертвый код
```

### Целевое состояние

```
user_agents таблица (ЕДИНСТВЕННАЯ)
├── Architect Agent (role: "architect")
├── Code Agent (role: "code")
├── Ask Agent (role: "ask")
├── Debug Agent (role: "debug")
├── Orchestrator Agent (role: "orchestrator")
├── Custom Agent 1 (role: "custom")
└── Custom Agent N (role: "custom")

user_orchestrators таблица 🗑️ УДАЛЕНО
```

### Преимущества

- ✅ DRY: одна таблица, одна модель, одна логика CRUD
- ✅ Оптимально: нет JOIN'ов, оптимальные query'и
- ✅ Масштабируемо: легко добавлять новые типы агентов
- ✅ Гибко: несколько оркестраторов с разными стратегиями
- ✅ Соответствует текущей реализации: DEFAULT_AGENTS_CONFIG уже использует это

---

## Архитектурные изменения

### 1. Удаление UserOrchestrator модели

#### Текущая структура

```python
# app/models/user_orchestrator.py
class UserOrchestrator(Base):
    id: Mapped[UUID]
    user_id: Mapped[UUID]
    project_id: Mapped[UUID]
    config: Mapped[dict]
    created_at: Mapped[datetime]
    
    user: Mapped["User"]
    project: Mapped["UserProject"]
```

#### Что удалить

- ❌ `app/models/user_orchestrator.py` — весь файл
- ❌ `app/models/__init__.py` — remove UserOrchestrator import
- ❌ `app/models/user.py` — remove `orchestrators: Mapped[list["UserOrchestrator"]]` relationship
- ❌ `app/models/user_project.py` — remove `orchestrators: Mapped[list["UserOrchestrator"]]` relationship

### 2. Добавление helper'ов и enum'ов в UserAgent логику

#### Новая структура

```python
# app/schemas/agent.py или новый app/core/agent_helpers.py

from enum import Enum

class AgentRole(str, Enum):
    """Agent role enumeration."""
    ARCHITECT = "architect"
    ORCHESTRATOR = "orchestrator"
    CODE = "code"
    ASK = "ask"
    DEBUG = "debug"
    CUSTOM = "custom"


# Helper функции
async def get_orchestrator(
    db: AsyncSession, 
    user_id: UUID, 
    project_id: UUID
) -> Optional[UserAgent]:
    """Get the orchestrator agent for a project.
    
    Returns:
        UserAgent with role='orchestrator' or None if not found.
    """
    result = await db.execute(
        select(UserAgent)
        .where(UserAgent.user_id == user_id)
        .where(UserAgent.project_id == project_id)
        .where(
            cast(
                UserAgent.config['metadata']['role'],
                String
            ) == AgentRole.ORCHESTRATOR.value
        )
    )
    return result.scalar_one_or_none()


async def get_agents_by_role(
    db: AsyncSession,
    project_id: UUID,
    role: AgentRole,
    status: str = "ready"
) -> list[UserAgent]:
    """Get all agents with a specific role.
    
    Args:
        db: Database session
        project_id: Project ID
        role: Agent role to filter by
        status: Agent status to filter by (default: "ready")
    
    Returns:
        List of agents matching the criteria.
    """
    result = await db.execute(
        select(UserAgent)
        .where(UserAgent.project_id == project_id)
        .where(UserAgent.status == status)
        .where(
            cast(
                UserAgent.config['metadata']['role'],
                String
            ) == role.value
        )
    )
    return result.scalars().all()


async def find_agent_by_name(
    db: AsyncSession,
    project_id: UUID,
    name: str,
    status: str = "ready"
) -> Optional[UserAgent]:
    """Find agent by name in a project.
    
    Args:
        db: Database session
        project_id: Project ID
        name: Agent name (e.g., "Architect", "Orchestrator")
        status: Agent status to filter by (default: "ready")
    
    Returns:
        UserAgent or None if not found.
    """
    result = await db.execute(
        select(UserAgent)
        .where(UserAgent.project_id == project_id)
        .where(UserAgent.name == name)
        .where(UserAgent.status == status)
    )
    return result.scalar_one_or_none()
```

### 3. Добавление валидаторов конфига

```python
# app/core/agent_config_validator.py

class AgentRoleValidator:
    """Validators for agent configs based on role."""
    
    @staticmethod
    def validate_orchestrator_config(config: dict) -> bool:
        """Validate orchestrator agent config.
        
        Required fields:
        - metadata.role = "orchestrator"
        - metadata.capabilities (list of strings)
        - metadata.cost_per_call (float)
        - model (string)
        - temperature (float)
        
        Optional fields:
        - metadata.max_parallel_agents (int)
        - metadata.approval_threshold_cost (float)
        - metadata.approval_threshold_tasks (int)
        """
        if "metadata" not in config:
            raise ValueError("Missing 'metadata' in config")
        
        metadata = config["metadata"]
        
        if metadata.get("role") != "orchestrator":
            raise ValueError("Config role must be 'orchestrator'")
        
        if not isinstance(metadata.get("capabilities"), list):
            raise ValueError("Missing or invalid 'capabilities' in metadata")
        
        if "model" not in config:
            raise ValueError("Missing 'model' in config")
        
        if "temperature" not in config:
            raise ValueError("Missing 'temperature' in config")
        
        return True
    
    @staticmethod
    def validate_code_agent_config(config: dict) -> bool:
        """Validate code agent config."""
        # Similar validation for code agent
        pass
    
    @staticmethod
    def validate_architect_agent_config(config: dict) -> bool:
        """Validate architect agent config."""
        # Similar validation for architect agent
        pass
    
    @staticmethod
    def validate_agent_config_by_role(config: dict) -> bool:
        """Validate agent config based on its role."""
        role = config.get("metadata", {}).get("role")
        
        if role == "orchestrator":
            return AgentRoleValidator.validate_orchestrator_config(config)
        elif role == "code":
            return AgentRoleValidator.validate_code_agent_config(config)
        elif role == "architect":
            return AgentRoleValidator.validate_architect_agent_config(config)
        # ... others
        
        return True  # Custom roles pass by default
```

### 4. Обновление документации конфига

```python
# docs/AGENT_CONFIG_SCHEMA.md (новый файл)

## Orchestrator Agent Config Schema

```json
{
  "model": "openrouter/openai/gpt-4.1",
  "temperature": 0.4,
  "system_prompt": "You are an Orchestrator Agent...",
  "tools": [],
  "concurrency_limit": 3,
  "max_tokens": 4096,
  "metadata": {
    "role": "orchestrator",
    "capabilities": [
      "workflow_management",
      "task_routing",
      "dependency_tracking",
      "result_aggregation"
    ],
    "risk_level": "LOW",
    "cost_per_call": 0.01,
    "estimated_duration": 5.0,
    "max_parallel_agents": 3,
    "approval_threshold_cost": 0.10,
    "approval_threshold_tasks": 3
  }
}
```

## Code Agent Config Schema

```json
{
  "model": "openrouter/openai/gpt-4.1",
  "temperature": 0.7,
  "system_prompt": "You are a Code Agent...",
  "tools": ["tool_read_file", "tool_write_file", "tool_execute_command"],
  "metadata": {
    "role": "code",
    "capabilities": [
      "implement_feature",
      "fix_bug",
      "debug",
      "code_review"
    ],
    "risk_level": "HIGH",
    "cost_per_call": 0.03,
    "estimated_duration": 15.0
  }
}
```
```

---

## Этапы внедрения

### ✅ ЭТА П 0: Подготовка (1 день)

**Tasks**:
- [ ] Verify что `UserOrchestrator` не используется нигде
- [ ] Backup текущей БД схемы
- [ ] Подготовить migration файл
- [ ] Создать feature branch
- [ ] Обновить README с описанием подхода

### ✅ ЭТАП 1: Миграция БД и удаление кода (2 дня)

**Миграция БД**:
- [ ] Создать migration файл: `YYYY_MM_DD_HHMM_###_remove_user_orchestrator.py`
  ```python
  def upgrade():
      op.drop_table('user_orchestrators')
  
  def downgrade():
      op.create_table(
          'user_orchestrators',
          sa.Column('id', PGUUID(as_uuid=True), primary_key=True),
          sa.Column('user_id', PGUUID(as_uuid=True), ...),
          ...
      )
  ```

**Код изменения**:
- [ ] Удалить `app/models/user_orchestrator.py`
- [ ] Удалить import из `app/models/__init__.py`
- [ ] Удалить relationship из `app/models/user.py`
- [ ] Удалить relationship из `app/models/user_project.py`

**Tests**:
- [ ] Verify что удаление не сломало imports
- [ ] Syntax check всех файлов

### ✅ ЭТАП 2: Добавление helpers и enum'ов (2 дня)

**Создать новые файлы**:
- [ ] `app/core/agent_helpers.py` с функциями:
  - `get_orchestrator()`
  - `get_agents_by_role()`
  - `find_agent_by_name()`
  
- [ ] `app/core/agent_config_validator.py` с классом `AgentRoleValidator`

- [ ] `app/schemas/agent_role.py` с Enum:
  ```python
  class AgentRole(str, Enum):
      ARCHITECT = "architect"
      ORCHESTRATOR = "orchestrator"
      CODE = "code"
      ASK = "ask"
      DEBUG = "debug"
      CUSTOM = "custom"
  ```

**Tests**:
- [ ] Unit tests для helpers
- [ ] Unit tests для валидаторов

### ✅ ЭТАП 3: Обновление существующих вызовов (2-3 дня)

**Обновить функции поиска**:

До:
```python
orchestrator_id = await find_agent_by_role(db, user_id, project_id, "orchestrator")
# Как работает find_agent_by_role? Где она определена?
```

После:
```python
from app.core.agent_helpers import get_orchestrator

orchestrator = await get_orchestrator(db, user_id, project_id)
if not orchestrator:
    raise ValueError("Orchestrator agent not found")

# Явное имя функции показывает намерение
```

**Files to update**:
- [ ] `app/routes/project_plans.py` — использование get_orchestrator()
- [ ] `app/routes/project_chat.py` — если использует оркестратор
- [ ] Любые другие места которые ищут агентов по роли

**Tests**:
- [ ] Integration tests для endpoints используя новые helpers

### ✅ ЭТАП 4: Документирование (1 день)

**Документы**:
- [ ] `docs/AGENT_CONFIG_SCHEMA.md` — schema для каждой роли агента
- [ ] Update `docs/AGENT_ROLES.md` — описание ролей и их ответственности
- [ ] Update `README.md` — mention что используется Unified UserAgent подход
- [ ] Developer guide — как создавать новых агентов

**Comments в коде**:
- [ ] Добавить docstrings со примерами использования
- [ ] Добавить comments объясняющие структуру config

### ✅ ЭТАП 5: Testing и QA (2-3 дня)

**Smoke tests**:
- [ ] Приложение запускается без ошибок
- [ ] Миграция БД проходит успешно
- [ ] Все imports работают

**Unit tests**:
- [ ] `test_agent_helpers.py` — get_orchestrator, get_agents_by_role, etc.
- [ ] `test_agent_config_validator.py` — validation logic

**Integration tests**:
- [ ] `/my/projects/{id}/chat` работает (маршрутизация)
- [ ] `/my/projects/{id}/plans` работает (Architect Agent)
- [ ] `/my/projects/{id}/plans/{id}/execute` работает (Orchestrator Agent)

**Regression tests**:
- [ ] Все существующие tests проходят
- [ ] Нет разломанного функционала

### ✅ ЭТАП 6: Deploy (1 день)

**Staging**:
- [ ] Merge feature branch в staging
- [ ] Run migration на staging БД
- [ ] Smoke tests на staging
- [ ] Performance tests на staging

**Production**:
- [ ] Merge в main
- [ ] Run migration на production БД
- [ ] Monitor logs для ошибок
- [ ] Rollback plan если нужно

---

## Миграция БД

### Migration файл

```python
# migrations/versions/2026_02_22_HHMM_###_remove_user_orchestrator.py

"""Remove UserOrchestrator model and table.

This migration removes the user_orchestrators table as we're moving to
unified UserAgent approach where Orchestrator is just a UserAgent with
role='orchestrator'.

Revision ID: <new_id>
Revises: <previous_id>
Create Date: 2026-02-22 HH:MM:SS

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '<new_id>'
down_revision = '<previous_id>'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop the user_orchestrators table
    op.drop_index('ix_user_orchestrators_user_id_project_id', 
                  table_name='user_orchestrators')
    op.drop_table('user_orchestrators')


def downgrade() -> None:
    # Recreate the user_orchestrators table
    op.create_table(
        'user_orchestrators',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('config', postgresql.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), 
                  server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['project_id'], ['user_projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_user_orchestrators_user_id_project_id', 
                    'user_orchestrators', 
                    ['user_id', 'project_id'])
```

### Downtime considerations

- Migration не требует downtime (drop таблица которая не используется)
- Можно safely run в production
- Rollback возможен если нужен

---

## Код изменения

### 1. Новые файлы

#### `app/core/agent_helpers.py`

```python
"""Helper functions for agent operations."""

from typing import Optional
from uuid import UUID

from sqlalchemy import cast, String, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_agent import UserAgent
from app.schemas.agent_role import AgentRole


async def get_orchestrator(
    db: AsyncSession,
    user_id: UUID,
    project_id: UUID,
    status: str = "ready"
) -> Optional[UserAgent]:
    """Get the orchestrator agent for a project.
    
    The orchestrator is a special UserAgent with role='orchestrator'
    that coordinates execution of other agents.
    
    Args:
        db: Database session
        user_id: User ID
        project_id: Project ID
        status: Agent status to filter by (default: "ready")
    
    Returns:
        UserAgent with role='orchestrator' or None if not found.
    
    Raises:
        ValueError: If multiple orchestrators found (shouldn't happen)
    
    Example:
        orchestrator = await get_orchestrator(db, user_id, project_id)
        if orchestrator:
            result = await workspace.direct_execution(
                agent_id=orchestrator.id,
                user_message="..."
            )
    """
    result = await db.execute(
        select(UserAgent)
        .where(UserAgent.user_id == user_id)
        .where(UserAgent.project_id == project_id)
        .where(UserAgent.status == status)
        .where(
            cast(
                UserAgent.config['metadata']['role'],
                String
            ) == AgentRole.ORCHESTRATOR.value
        )
    )
    return result.scalar_one_or_none()


async def get_agents_by_role(
    db: AsyncSession,
    project_id: UUID,
    role: AgentRole,
    status: str = "ready",
    user_id: Optional[UUID] = None
) -> list[UserAgent]:
    """Get all agents with a specific role.
    
    Args:
        db: Database session
        project_id: Project ID
        role: Agent role to filter by
        status: Agent status to filter by (default: "ready")
        user_id: Optional user ID for additional filtering
    
    Returns:
        List of agents matching the criteria.
    
    Example:
        code_agents = await get_agents_by_role(
            db, project_id, AgentRole.CODE
        )
        for agent in code_agents:
            print(agent.name)
    """
    query = select(UserAgent).where(
        UserAgent.project_id == project_id,
        UserAgent.status == status,
        cast(
            UserAgent.config['metadata']['role'],
            String
        ) == role.value
    )
    
    if user_id:
        query = query.where(UserAgent.user_id == user_id)
    
    result = await db.execute(query)
    return result.scalars().all()


async def find_agent_by_name(
    db: AsyncSession,
    project_id: UUID,
    name: str,
    status: str = "ready"
) -> Optional[UserAgent]:
    """Find agent by name in a project.
    
    Args:
        db: Database session
        project_id: Project ID
        name: Agent name (e.g., "Architect", "Orchestrator", "Custom LLM")
        status: Agent status to filter by (default: "ready")
    
    Returns:
        UserAgent or None if not found.
    
    Example:
        architect = await find_agent_by_name(db, project_id, "Architect")
    """
    result = await db.execute(
        select(UserAgent)
        .where(UserAgent.project_id == project_id)
        .where(UserAgent.name == name)
        .where(UserAgent.status == status)
    )
    return result.scalar_one_or_none()
```

#### `app/schemas/agent_role.py`

```python
"""Agent role enumeration."""

from enum import Enum


class AgentRole(str, Enum):
    """Agent role in the system.
    
    Each agent in the system has a specific role that determines:
    - What it can do (capabilities)
    - How it's selected for tasks (routing)
    - How it's configured (config schema)
    
    Attributes:
        ARCHITECT: Creates plans and analyzes requirements
        ORCHESTRATOR: Routes messages and coordinates task execution
        CODE: Writes and modifies code
        ASK: Answers questions and explains concepts
        DEBUG: Investigates errors and adds logging
        CUSTOM: Custom agent with user-defined role
    """
    
    ARCHITECT = "architect"
    ORCHESTRATOR = "orchestrator"
    CODE = "code"
    ASK = "ask"
    DEBUG = "debug"
    CUSTOM = "custom"
```

### 2. Обновляемые файлы

#### `app/models/__init__.py`

```python
# Удалить эту строку:
# from app.models.user_orchestrator import UserOrchestrator

# И из __all__:
# "UserOrchestrator",
```

#### `app/models/user.py`

```python
# Удалить это отношение:
# orchestrators: Mapped[list["UserOrchestrator"]] = relationship(
#     "UserOrchestrator", back_populates="user", cascade="all, delete-orphan"
# )
```

#### `app/models/user_project.py`

```python
# Удалить это отношение:
# orchestrators: Mapped[list["UserOrchestrator"]] = relationship(
#     "UserOrchestrator",
#     back_populates="project",
# )
```

#### `app/routes/project_plans.py`

```python
# ДО:
from app.core.starter_pack import find_agent_by_role

orchestrator_id = await find_agent_by_role(db, user_id, project_id, "orchestrator")

# ПОСЛЕ:
from app.core.agent_helpers import get_orchestrator

orchestrator = await get_orchestrator(db, user_id, project_id)
if not orchestrator:
    raise ValueError("Orchestrator agent not found for this project")

orchestrator_id = orchestrator.id
```

---

## Testing стратегия

### Unit Tests

```python
# tests/test_agent_helpers.py

import pytest
from uuid import uuid4
from app.core.agent_helpers import (
    get_orchestrator,
    get_agents_by_role,
    find_agent_by_name
)
from app.schemas.agent_role import AgentRole


@pytest.mark.asyncio
async def test_get_orchestrator_found(db_session, user, project):
    """Test getting orchestrator agent."""
    # Setup
    orchestrator = UserAgent(
        user_id=user.id,
        project_id=project.id,
        name="Orchestrator",
        status="ready",
        config={
            "metadata": {"role": "orchestrator"}
        }
    )
    db_session.add(orchestrator)
    await db_session.commit()
    
    # Execute
    result = await get_orchestrator(db_session, user.id, project.id)
    
    # Assert
    assert result is not None
    assert result.id == orchestrator.id


@pytest.mark.asyncio
async def test_get_orchestrator_not_found(db_session, user, project):
    """Test getting orchestrator when none exists."""
    result = await get_orchestrator(db_session, user.id, project.id)
    assert result is None


@pytest.mark.asyncio
async def test_get_agents_by_role(db_session, user, project):
    """Test getting agents by role."""
    # Setup: Create code agent
    code_agent = UserAgent(
        user_id=user.id,
        project_id=project.id,
        name="CodeAssistant",
        status="ready",
        config={
            "metadata": {"role": "code", "capabilities": ["code_impl"]}
        }
    )
    db_session.add(code_agent)
    await db_session.commit()
    
    # Execute
    result = await get_agents_by_role(
        db_session, project.id, AgentRole.CODE
    )
    
    # Assert
    assert len(result) == 1
    assert result[0].id == code_agent.id
```

### Integration Tests

```python
# tests/test_orchestrator_routing.py

@pytest.mark.asyncio
async def test_orchestrated_execution_with_helper(
    db_session, user, project, workspace
):
    """Test orchestrated execution using new helper."""
    # Setup
    orchestrator = await get_orchestrator(db_session, user.id, project.id)
    assert orchestrator is not None
    
    # Execute
    result = await workspace.orchestrated_execution(
        user_message="Find bugs in the code"
    )
    
    # Assert
    assert result["success"]
    assert result["selected_agent_id"]
```

---

## Timeline и ответственность

### Timeline

| Этап | Длительность | Дата начала | Дата завершения |
|------|-------------|-----------|-----------------|
| Подготовка | 1 день | 2026-02-23 | 2026-02-23 |
| Миграция БД | 2 дня | 2026-02-24 | 2026-02-25 |
| Helpers/Enum | 2 дня | 2026-02-25 | 2026-02-26 |
| Обновление вызовов | 2-3 дня | 2026-02-27 | 2026-02-28 |
| Документирование | 1 день | 2026-03-01 | 2026-03-01 |
| Testing | 2-3 дня | 2026-03-02 | 2026-03-03 |
| Deploy | 1 день | 2026-03-04 | 2026-03-04 |
| **ИТОГО** | **11-12 дней** | **2026-02-23** | **2026-03-04** |

### Ответственность

- **Architecture & Design**: Senior Backend Engineer
- **Миграция БД**: Database Engineer / Senior Backend
- **Код изменения**: Backend Developer Team (2-3 человека параллельно)
- **Testing**: QA Engineer + Developer Team
- **Documentation**: Technical Writer + Developer who implemented

---

## Контрольный список

### Pre-Implementation
- [ ] Architecture review одобрена
- [ ] Timeline agreed с командой
- [ ] Resources allocated

### Implementation
- [ ] Feature branch создана
- [ ] Migration файл создан и протестирован на staging
- [ ] Helper функции реализованы и протестированы
- [ ] Enum и валидаторы реализованы
- [ ] Все вызовы обновлены
- [ ] Documentaiton обновлена
- [ ] Code review passed
- [ ] All tests passing

### Deployment
- [ ] Staging deployment successful
- [ ] Smoke tests passed
- [ ] Production deployment scheduled
- [ ] Monitoring и alerts настроены
- [ ] Rollback plan ready

### Post-Deployment
- [ ] Production monitoring 24h
- [ ] Performance metrics checked
- [ ] User feedback gathered
- [ ] Issues logged and triaged

---

## Резюме

Unified UserAgent подход упростит архитектуру, улучшит производительность и сделает систему более гибкой.

Основные преимущества:
- ✅ Одна таблица, одна модель, одна логика
- ✅ Оптимальные query'и без JOIN'ов
- ✅ Легко добавлять новые типы агентов
- ✅ Соответствует текущей реализации
- ✅ Поддерживает несколько оркестраторов с разными стратегиями

Примерный timeline: **11-12 дней** включая все тестирование и документирование.

