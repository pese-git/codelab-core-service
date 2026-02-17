# Анализ: Как фиксировать проект в БД для per-project архитектуры

**Дата:** 17 февраля 2026  
**Версия:** 1.0  
**Контекст:** Необходимые изменения в БД для поддержки per-project User Worker Space

---

## 📊 Текущее состояние БД

### Текущая схема

```
User (user_id)
  ├── UserAgent (user_id, name, config, status)
  ├── ChatSession (user_id)
  │   └── Message (session_id, user_id)
  ├── UserOrchestrator (user_id)
  └── ApprovalRequest (user_id)
```

**Проблема:** 
- ❌ В моделях НЕТ `project_id`
- ❌ Все агенты и сессии привязаны только к пользователю, не к проекту
- ❌ Нельзя различить агенты разных проектов одного пользователя

### Пример проблемы

```
User user123 имеет:
- Проект "my-app" 
  - Агент: agent_coder
  - ChatSession: session1
  
- Проект "data-analysis"
  - Агент: agent_coder (с другой конфигурацией!)
  - ChatSession: session2

В БД оба агента имеют одинаковый (user_id, name="agent_coder")
→ КОНФЛИКТ! Невозможно различить!
```

---

## 🏗️ Требуемая архитектура БД

### Правильная схема (per-project)

```
User (user_id)
  └── UserProject (user_id, project_id, name, workspace_path)
      ├── UserAgent (user_id, project_id, name, config)
      │   ├── Task
      │   └── ApprovalRequest
      │
      ├── ChatSession (user_id, project_id)
      │   ├── Message
      │   └── Task
      │
      └── UserOrchestrator (user_id, project_id)
          └── ApprovalRequest
```

---

## 📝 Нужные изменения

### 1. Создать новую модель UserProject

**Файл:** `app/models/user_project.py` (СОЗДАТЬ)

```python
"""UserProject model."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UserProject(Base):
    """User project model."""

    __tablename__ = "user_projects"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), 
        primary_key=True, 
        default=uuid4, 
        index=True
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), 
        ForeignKey("users.id", ondelete="CASCADE"), 
        nullable=False, 
        index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    workspace_path: Mapped[str] = mapped_column(
        String(500), 
        nullable=True,  # Может быть NULL, если workspace управляется пользователем
        comment="Local path to user's workspace directory"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=datetime.utcnow, 
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        default=datetime.utcnow, 
        onupdate=datetime.utcnow,
        nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="projects")
    agents: Mapped[list["UserAgent"]] = relationship(
        "UserAgent", 
        back_populates="project",
        cascade="all, delete-orphan"
    )
    chat_sessions: Mapped[list["ChatSession"]] = relationship(
        "ChatSession",
        back_populates="project",
        cascade="all, delete-orphan"
    )
    orchestrators: Mapped[list["UserOrchestrator"]] = relationship(
        "UserOrchestrator",
        back_populates="project",
        cascade="all, delete-orphan"
    )

    # Indexes
    __table_args__ = (
        Index("ix_user_projects_user_id_name", "user_id", "name"),
        Index("ix_user_projects_user_id_created_at", "user_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<UserProject(id={self.id}, user_id={self.user_id}, name={self.name})>"
```

**Что добавляет:**
- ✅ Модель для хранения информации о проектах пользователя
- ✅ `user_id` - связь с пользователем
- ✅ `name` - имя проекта
- ✅ `workspace_path` - путь к workspace'у (опционально)
- ✅ Timestamps для аудита

---

### 2. Обновить модель UserAgent

**Файл:** `app/models/user_agent.py` (ИЗМЕНИТЬ)

```python
class UserAgent(Base):
    """User agent model."""

    __tablename__ = "user_agents"

    id: Mapped[UUID] = mapped_column(...)
    user_id: Mapped[UUID] = mapped_column(...)
    project_id: Mapped[UUID] = mapped_column(  # ← ДОБАВИТЬ
        PGUUID(as_uuid=True),
        ForeignKey("user_projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    name: Mapped[str] = mapped_column(...)
    config: Mapped[dict] = mapped_column(...)
    status: Mapped[str] = mapped_column(...)
    created_at: Mapped[datetime] = mapped_column(...)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="agents")
    project: Mapped["UserProject"] = relationship(  # ← ДОБАВИТЬ
        "UserProject", 
        back_populates="agents"
    )
    messages: Mapped[list["Message"]] = relationship(...)
    tasks: Mapped[list["Task"]] = relationship(...)

    # Indexes
    __table_args__ = (
        Index("ix_user_agents_user_id_project_id_name",   # ← ОБНОВИТЬ
              "user_id", "project_id", "name"),
        Index("ix_user_agents_project_id_status",         # ← ДОБАВИТЬ
              "project_id", "status"),
    )
```

**Что изменяет:**
- ✅ Добавлен `project_id`
- ✅ Foreign key на `user_projects.id`
- ✅ Relationship с UserProject
- ✅ Обновлены индексы для include project_id

---

### 3. Обновить модель ChatSession

**Файл:** `app/models/chat_session.py` (ИЗМЕНИТЬ)

```python
class ChatSession(Base):
    """Chat session model."""

    __tablename__ = "chat_sessions"

    id: Mapped[UUID] = mapped_column(...)
    user_id: Mapped[UUID] = mapped_column(...)
    project_id: Mapped[UUID] = mapped_column(  # ← ДОБАВИТЬ
        PGUUID(as_uuid=True),
        ForeignKey("user_projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    created_at: Mapped[datetime] = mapped_column(...)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="chat_sessions")
    project: Mapped["UserProject"] = relationship(  # ← ДОБАВИТЬ
        "UserProject",
        back_populates="chat_sessions"
    )
    messages: Mapped[list["Message"]] = relationship(...)
    tasks: Mapped[list["Task"]] = relationship(...)

    # Indexes
    __table_args__ = (
        Index("ix_chat_sessions_user_id_project_id_created_at",  # ← ОБНОВИТЬ
              "user_id", "project_id", "created_at"),
        Index("ix_chat_sessions_project_id_created_at",          # ← ДОБАВИТЬ
              "project_id", "created_at"),
    )
```

**Что изменяет:**
- ✅ Добавлен `project_id`
- ✅ Foreign key на `user_projects.id`
- ✅ Relationship с UserProject
- ✅ Обновлены индексы

---

### 4. Обновить модель User

**Файл:** `app/models/user.py` (ИЗМЕНИТЬ)

```python
class User(Base):
    """User model."""

    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(...)
    email: Mapped[str] = mapped_column(...)
    created_at: Mapped[datetime] = mapped_column(...)

    # Relationships
    projects: Mapped[list["UserProject"]] = relationship(  # ← ДОБАВИТЬ
        "UserProject",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    agents: Mapped[list["UserAgent"]] = relationship(...)
    orchestrators: Mapped[list["UserOrchestrator"]] = relationship(...)
    chat_sessions: Mapped[list["ChatSession"]] = relationship(...)
    approval_requests: Mapped[list["ApprovalRequest"]] = relationship(...)

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email})>"
```

**Что изменяет:**
- ✅ Добавлен relationship к projects

---

### 5. Обновить модель UserOrchestrator

**Файл:** `app/models/user_orchestrator.py` (ИЗМЕНИТЬ)

```python
class UserOrchestrator(Base):
    """User orchestrator model."""

    __tablename__ = "user_orchestrators"

    id: Mapped[UUID] = mapped_column(...)
    user_id: Mapped[UUID] = mapped_column(...)
    project_id: Mapped[UUID] = mapped_column(  # ← ДОБАВИТЬ
        PGUUID(as_uuid=True),
        ForeignKey("user_projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    config: Mapped[dict] = mapped_column(...)
    created_at: Mapped[datetime] = mapped_column(...)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="orchestrators")
    project: Mapped["UserProject"] = relationship(  # ← ДОБАВИТЬ
        "UserProject",
        back_populates="orchestrators"
    )
    approval_requests: Mapped[list["ApprovalRequest"]] = relationship(...)

    # Indexes
    __table_args__ = (
        Index("ix_user_orchestrators_user_id_project_id",  # ← ОБНОВИТЬ
              "user_id", "project_id"),
    )
```

**Что изменяет:**
- ✅ Добавлен `project_id`
- ✅ Foreign key на `user_projects.id`
- ✅ Relationship с UserProject

---

### 6. Обновить модель Message (если нужно)

**Файл:** `app/models/message.py`

Может потребоваться добавить `project_id` для быстрого поиска по проекту:

```python
class Message(Base):
    """Message model."""

    __tablename__ = "messages"

    id: Mapped[UUID] = mapped_column(...)
    session_id: Mapped[UUID] = mapped_column(...)
    user_id: Mapped[UUID] = mapped_column(...)
    project_id: Mapped[UUID] = mapped_column(  # ← ОПЦИОНАЛЬНО
        PGUUID(as_uuid=True),
        ForeignKey("user_projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    agent_id: Mapped[UUID] = mapped_column(...)
    role: Mapped[str] = mapped_column(...)
    content: Mapped[str] = mapped_column(...)
    created_at: Mapped[datetime] = mapped_column(...)

    # Indexes
    __table_args__ = (
        Index("ix_messages_session_id_created_at",
              "session_id", "created_at"),
        Index("ix_messages_project_id_created_at",  # ← ОПЦИОНАЛЬНО
              "project_id", "created_at"),
    )
```

---

## 🔄 Миграция Alembic

Нужно создать миграцию для добавления нового столбца `project_id` и новой таблицы `user_projects`.

**Команда:**
```bash
alembic revision --autogenerate -m "add project_id support for per-project architecture"
```

**Файл:** `migrations/versions/2026_02_17_xxxx-add_project_id_support.py`

```python
"""add project_id support for per-project architecture

Revision ID: xxxxx
Revises: yyyyy
Create Date: 2026-02-17 08:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'xxxxx'
down_revision = 'yyyyy'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Создать таблицу user_projects
    op.create_table(
        'user_projects',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('workspace_path', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_index('ix_user_projects_user_id_name', 'user_projects', ['user_id', 'name'])
    op.create_index('ix_user_projects_user_id_created_at', 'user_projects', ['user_id', 'created_at'])

    # 2. Добавить project_id в user_agents
    # Сначала создать столбец как nullable
    op.add_column('user_agents', 
                  sa.Column('project_id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=True))
    
    # Нужно заполнить существующие записи
    # Создать default project для каждого пользователя
    op.execute("""
        WITH user_projects_created AS (
            INSERT INTO user_projects (id, user_id, name, created_at, updated_at)
            SELECT gen_random_uuid(), user_id, 'Default Project', NOW(), NOW()
            FROM (SELECT DISTINCT user_id FROM users) u
            RETURNING id, user_id
        )
        UPDATE user_agents ua
        SET project_id = up.id
        FROM user_projects_created up
        WHERE ua.user_id = up.user_id
    """)
    
    # Теперь сделать project_id NOT NULL и добавить FK
    op.alter_column('user_agents', 'project_id', nullable=False)
    op.create_foreign_key('fk_user_agents_project_id', 'user_agents', 'user_projects', ['project_id'], ondelete='CASCADE')
    op.create_index('ix_user_agents_user_id_project_id_name', 'user_agents', ['user_id', 'project_id', 'name'])
    op.create_index('ix_user_agents_project_id_status', 'user_agents', ['project_id', 'status'])
    
    # 3. Аналогично для chat_sessions
    op.add_column('chat_sessions', 
                  sa.Column('project_id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=True))
    
    op.execute("""
        UPDATE chat_sessions cs
        SET project_id = ua.project_id
        FROM (SELECT DISTINCT user_id, project_id FROM user_agents) ua
        WHERE cs.user_id = ua.user_id
    """)
    
    op.alter_column('chat_sessions', 'project_id', nullable=False)
    op.create_foreign_key('fk_chat_sessions_project_id', 'chat_sessions', 'user_projects', ['project_id'], ondelete='CASCADE')
    op.create_index('ix_chat_sessions_user_id_project_id_created_at', 'chat_sessions', ['user_id', 'project_id', 'created_at'])
    op.create_index('ix_chat_sessions_project_id_created_at', 'chat_sessions', ['project_id', 'created_at'])


def downgrade() -> None:
    # Удалить в обратном порядке
    op.drop_table('user_projects')
    op.drop_column('user_agents', 'project_id')
    op.drop_column('chat_sessions', 'project_id')
```

---

## 📊 Итоговая схема БД

```sql
-- Таблица пользователей (существует)
users (id, email, created_at)

-- Таблица проектов пользователя (НОВАЯ)
user_projects (id, user_id, name, workspace_path, created_at, updated_at)
  ↑ FK user_id → users.id

-- Таблица агентов (ОБНОВЛЕНА)
user_agents (id, user_id, project_id, name, config, status, created_at)
  ↑ FK user_id → users.id
  ↑ FK project_id → user_projects.id

-- Таблица сессий чата (ОБНОВЛЕНА)
chat_sessions (id, user_id, project_id, created_at)
  ↑ FK user_id → users.id
  ↑ FK project_id → user_projects.id

-- Таблица сообщений (существует, но может быть обновлена)
messages (id, session_id, user_id, agent_id, role, content, created_at)
  ↑ FK session_id → chat_sessions.id

-- Таблица оркестраторов (ОБНОВЛЕНА)
user_orchestrators (id, user_id, project_id, config, created_at)
  ↑ FK user_id → users.id
  ↑ FK project_id → user_projects.id
```

---

## ✅ Рекомендации

1. **Сначала создать модель UserProject** и миграцию
2. **Обновить все модели** для добавления project_id
3. **Создать миграцию** для заполнения существующих данных
4. **Обновить endpoints** для работы с project_id
5. **Обновить User Worker Space** для использования project_id

---

## ⚠️ Важные моменты

### Backward compatibility
После добавления `project_id` все старые endpoints без `project_id` должны будут быть обновлены. Это breaking change.

### Обновление endpoints

**До:**
```
POST /my/agents/
POST /my/chat/{session_id}/message/
```

**После:**
```
POST /my/projects/{project_id}/agents/
POST /my/projects/{project_id}/chat/{session_id}/message/
```

### Migration strategy

1. Создать "Default Project" для каждого пользователя
2. Заполнить все existing агенты и сессии в default project
3. Обновить endpoints для требования project_id
4. Постепенно добавлять поддержку multiple projects в UI

---

## 🎯 Вывод

**Да, запись о проекте ДОЛЖНА фиксироваться в БД** через новую таблицу `user_projects` и добавлением `project_id` во все связанные модели.

Это необходимо для:
- ✅ Per-project архитектуры User Worker Space
- ✅ Изоляции данных между проектами
- ✅ Правильного управления ресурсами per-project
- ✅ Аудита и истории
