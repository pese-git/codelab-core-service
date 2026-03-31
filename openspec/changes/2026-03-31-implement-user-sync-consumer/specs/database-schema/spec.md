# Спецификация: Database Schema Changes

**Версия:** 1.0.0  
**Дата:** 31 марта 2026  
**Сервис:** codelab-core-service

---

## 📋 Назначение компонента

**Database Schema Changes** — обновления PostgreSQL схемы для поддержки синхронизации пользователей и отслеживания статуса синхронизации.

---

## 🔄 Schema Updates

### 1. Users Table - Новые колонки

```sql
-- Migration: 2026_03_31_add_user_sync_fields.py

ALTER TABLE users ADD COLUMN (
    synced_from_auth_at TIMESTAMP WITH TIME ZONE DEFAULT NULL,
    synced_version INTEGER DEFAULT 1
);

-- Индекс для отслеживания синхронизации
CREATE INDEX IF NOT EXISTS idx_users_synced
  ON users(synced_from_auth_at DESC, synced_version);
```

### 2. Новая таблица: user_sync_state (опционально)

```sql
-- For advanced tracking of sync state per user

CREATE TABLE IF NOT EXISTS user_sync_state (
    user_id UUID PRIMARY KEY,
    last_event_id VARCHAR(50),
    last_event_type VARCHAR(50),
    last_sync_at TIMESTAMP WITH TIME ZONE,
    created_from_auth BOOLEAN DEFAULT FALSE,
    total_events_processed INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT fk_user_sync_state_user
      FOREIGN KEY (user_id)
      REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_user_sync_state_last_sync
  ON user_sync_state(last_sync_at DESC);
```

### 3. Existing Tables - Validation

```sql
-- Verify FK constraints for cascade delete

-- users (primary)
-- ├── user_projects (foreign key: user_id)
-- ├── user_agents (foreign key: user_id)
-- ├── chat_sessions (foreign key: user_id)
-- └── messages (foreign key: user_id via session)

-- All should have ON DELETE CASCADE for proper cascade delete
```

---

## 📊 Data Model

### Updated User Table

```python
class User(Base):
    __tablename__ = "users"
    
    id: Mapped[UUID] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    
    # ✨ NEW: Sync tracking
    synced_from_auth_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp of last sync from auth-service"
    )
    synced_version: Mapped[int] = mapped_column(
        Integer,
        default=1,
        comment="Version counter for sync tracking"
    )
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), onupdate=now)
```

### New User Sync State Table

```python
class UserSyncState(Base):
    __tablename__ = "user_sync_state"
    
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True
    )
    
    last_event_id: Mapped[Optional[str]] = mapped_column(String(50))
    last_event_type: Mapped[Optional[str]] = mapped_column(String(50))
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_from_auth: Mapped[bool] = mapped_column(Boolean, default=False)
    total_events_processed: Mapped[int] = mapped_column(Integer, default=0)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), onupdate=now)
```

---

## 🔄 Migration Script

```python
# migrations/versions/2026_03_31_add_user_sync_fields.py

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic
revision = 'abc123def456'
down_revision = 'previous_revision'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add user sync tracking fields"""
    
    # 1. Add columns to users table
    op.add_column(
        'users',
        sa.Column(
            'synced_from_auth_at',
            sa.DateTime(timezone=True),
            nullable=True,
            comment='Last sync from auth-service'
        )
    )
    op.add_column(
        'users',
        sa.Column(
            'synced_version',
            sa.Integer(),
            nullable=False,
            server_default='1',
            comment='Sync version counter'
        )
    )
    
    # 2. Create index
    op.create_index(
        'idx_users_synced',
        'users',
        ['synced_from_auth_at', 'synced_version']
    )
    
    # 3. Create user_sync_state table
    op.create_table(
        'user_sync_state',
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('last_event_id', sa.String(50), nullable=True),
        sa.Column('last_event_type', sa.String(50), nullable=True),
        sa.Column('last_sync_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_from_auth', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('total_events_processed', sa.Integer(), server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('user_id')
    )
    
    # 4. Create index on user_sync_state
    op.create_index(
        'idx_user_sync_state_last_sync',
        'user_sync_state',
        ['last_sync_at'],
        postgresql_using='btree'
    )


def downgrade() -> None:
    """Revert changes"""
    
    # 1. Drop user_sync_state table
    op.drop_table('user_sync_state')
    
    # 2. Drop index
    op.drop_index('idx_users_synced', table_name='users')
    
    # 3. Remove columns
    op.drop_column('users', 'synced_version')
    op.drop_column('users', 'synced_from_auth_at')
```

---

## 🔍 Validation

### FK Constraints Check

```sql
-- Verify all FK constraints for cascade delete

-- Users -> UserProject
SELECT constraint_name FROM information_schema.referential_constraints
WHERE table_name='user_projects' AND referenced_table_name='users';
-- Should have: ON DELETE CASCADE

-- Users -> UserAgent
SELECT constraint_name FROM information_schema.referential_constraints
WHERE table_name='user_agents' AND referenced_table_name='users';
-- Should have: ON DELETE CASCADE

-- Users -> ChatSession
SELECT constraint_name FROM information_schema.referential_constraints
WHERE table_name='chat_sessions' AND referenced_table_name='users';
-- Should have: ON DELETE CASCADE

-- ChatSession -> Message
SELECT constraint_name FROM information_schema.referential_constraints
WHERE table_name='messages' AND referenced_table_name='chat_sessions';
-- Should have: ON DELETE CASCADE
```

---

## 🧪 Tests

### Unit Test 1: Migration up

```python
def test_migration_upgrade(alembic_runner):
    """Test migration creates new columns"""
    
    alembic_runner.migrate_up_to('abc123def456')
    
    # Check columns exist
    with sa.inspect(engine) as inspector:
        columns = {c['name'] for c in inspector.get_columns('users')}
        assert 'synced_from_auth_at' in columns
        assert 'synced_version' in columns
    
    # Check table exists
    assert 'user_sync_state' in inspector.get_table_names()
```

### Unit Test 2: Migration down

```python
def test_migration_downgrade(alembic_runner):
    """Test migration rollback"""
    
    alembic_runner.migrate_up_to('abc123def456')
    alembic_runner.migrate_down_to('previous_revision')
    
    # Check columns removed
    with sa.inspect(engine) as inspector:
        columns = {c['name'] for c in inspector.get_columns('users')}
        assert 'synced_from_auth_at' not in columns
        assert 'synced_version' not in columns
    
    # Check table dropped
    assert 'user_sync_state' not in inspector.get_table_names()
```

### Integration Test 1: Cascade delete works

```python
@pytest.mark.asyncio
async def test_cascade_delete_on_user_deletion():
    """Test that cascade delete works for all tables"""
    
    # Setup
    user_id = UUID("123e4567-e89b-12d3-a456-426614174000")
    await create_test_user(user_id)
    await create_test_projects(user_id)
    await create_test_agents(user_id)
    await create_test_sessions(user_id)
    
    # Act: Delete user
    await session.delete(User.get(user_id))
    await session.commit()
    
    # Assert: All related deleted
    assert await session.get(User, user_id) is None
    
    projects = await session.execute(
        select(UserProject).where(UserProject.user_id == user_id)
    )
    assert len(projects.scalars().all()) == 0
    
    agents = await session.execute(
        select(UserAgent).where(UserAgent.user_id == user_id)
    )
    assert len(agents.scalars().all()) == 0
    
    sessions = await session.execute(
        select(ChatSession).where(ChatSession.user_id == user_id)
    )
    assert len(sessions.scalars().all()) == 0
```

---

## 📋 Acceptance Criteria

- ✅ Migration создает новые колонки (synced_from_auth_at, synced_version)
- ✅ Migration создает индексы
- ✅ Migration создает user_sync_state таблицу
- ✅ Downgrade полностью откатывает изменения
- ✅ FK constraints на CASCADE DELETE
- ✅ Migration работает на clean DB
- ✅ Migration работает на existing DB
- ✅ Cascade delete работает правильно

---

## 🔗 Связанные документы

- Alembic documentation: https://alembic.sqlalchemy.org/
- SQLAlchemy documentation: https://docs.sqlalchemy.org/
