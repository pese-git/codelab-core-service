# Спецификация: User Sync Event Handlers

**Версия:** 1.0.0  
**Дата:** 31 марта 2026  
**Сервис:** codelab-core-service

---

## 📋 Назначение компонента

**User Sync Event Handlers** — набор обработчиков для синхронизации информации пользователя между auth-service и core-service. Гарантирует идемпотентность, консистентность данных и каскадное удаление при удалении пользователя.

### Ключевые функции

- ✅ **Idempotent processing** — безопасно вызывать несколько раз
- 🔄 **Profile synchronization** — синхронизировать email, имя, данные
- 🗑️ **Cascade delete** — удалить все связанные данные (projects, agents, sessions)
- 📝 **Logging** — полное логирование всех операций
- 💾 **Transactional** — все операции ACID

---

## 🔌 API

### Handler: handle_user_created()

```python
async def handle_user_created(event: dict) -> None:
    """
    Обработать user.created событие
    
    Синхронизировать profile пользователя в core-service.
    Idempotent: если пользователь уже существует, просто return.
    
    Args:
        event (dict): Event with structure:
        {
            "event_type": "user.created",
            "aggregate_id": "user_uuid",
            "data": {
                "user_id": "UUID",
                "email": "user@example.com",
                "first_name": "John",
                "last_name": "Doe",
                "created_at": "ISO8601"
            }
        }
    
    Side Effects:
        - Create User record in DB if not exists
        - Set synced_from_auth_at timestamp
        
    Raises:
        Exception: Any exception triggers retry
    
    Example:
        >>> event = {
        ...     "event_type": "user.created",
        ...     "data": {
        ...         "user_id": "123e4567-e89b-12d3-a456-426614174000",
        ...         "email": "john@example.com",
        ...         "first_name": "John",
        ...         "last_name": "Doe"
        ...     }
        ... }
        >>> await handle_user_created(event)
    """
```

### Handler: handle_user_updated()

```python
async def handle_user_updated(event: dict) -> None:
    """
    Обработать user.updated событие
    
    Обновить profile пользователя в core-service.
    Idempotent: если пользователь не существует, skip (может быть race condition).
    
    Args:
        event (dict): Event with structure:
        {
            "event_type": "user.updated",
            "aggregate_id": "user_uuid",
            "data": {
                "user_id": "UUID",
                "email": "newemail@example.com",
                "first_name": "Jane",
                "last_name": "Smith",
                "updated_at": "ISO8601",
                "changes": ["email", "first_name"]  # Changed fields
            }
        }
    
    Side Effects:
        - Update User record
        - Update synced_from_auth_at timestamp
        - Notify active sessions if email changed
        
    Raises:
        Exception: Any exception triggers retry
    """
```

### Handler: handle_user_deleted()

```python
async def handle_user_deleted(event: dict) -> None:
    """
    Обработать user.deleted событие
    
    CASCADE delete всех данных пользователя.
    Критическое удаление! Должно быть идемпотентным.
    
    Args:
        event (dict): Event with structure:
        {
            "event_type": "user.deleted",
            "aggregate_id": "user_uuid",
            "data": {
                "user_id": "UUID",
                "email": "user@example.com",
                "deleted_at": "ISO8601",
                "reason": "admin_deletion|user_requested"
            }
        }
    
    Cascade Delete Order (respecting FK):
    1. DELETE UserProject (projects)
    2. DELETE UserAgent (agents)
    3. DELETE ChatSession (sessions)
    4. DELETE Message (messages)
    5. DELETE User (user profile)
    
    Side Effects:
        - Delete all user projects
        - Delete all user agents
        - Delete all user chat sessions
        - Delete all user messages
        - Delete user profile
        - Clear from caches
        - Log cascade deletion
    
    Idempotency:
        - If user already deleted, just log and return
        - If partially deleted, continue deletion
    
    Raises:
        Exception: Any exception triggers retry
        IntegrityError: FK constraint failure (rollback)
    """
```

---

## 📊 Примеры использования

### Пример 1: User Creation

```python
event = {
    "event_type": "user.created",
    "event_id": "550e8400-e29b-41d4-a716-446655440000",
    "aggregate_id": "123e4567-e89b-12d3-a456-426614174000",
    "data": {
        "user_id": "123e4567-e89b-12d3-a456-426614174000",
        "email": "john@example.com",
        "first_name": "John",
        "last_name": "Doe",
        "created_at": "2026-03-31T11:16:30Z"
    }
}

# Handler will:
# 1. Check if User already exists
# 2. If not: CREATE User
# 3. Set synced_from_auth_at
# 4. Commit transaction
# 5. Log "user_synced"
```

### Пример 2: User Update

```python
event = {
    "event_type": "user.updated",
    "aggregate_id": "123e4567-e89b-12d3-a456-426614174000",
    "data": {
        "user_id": "123e4567-e89b-12d3-a456-426614174000",
        "email": "jane@example.com",
        "first_name": "Jane",
        "last_name": "Smith",
        "updated_at": "2026-03-31T12:00:00Z",
        "changes": ["email", "first_name"]
    }
}

# Handler will:
# 1. Get User by ID
# 2. Update email, first_name, last_name
# 3. Update synced_from_auth_at
# 4. Commit transaction
# 5. If email changed: notify active sessions
# 6. Log "user_updated"
```

### Пример 3: User Deletion (Cascade)

```python
event = {
    "event_type": "user.deleted",
    "aggregate_id": "123e4567-e89b-12d3-a456-426614174000",
    "data": {
        "user_id": "123e4567-e89b-12d3-a456-426614174000",
        "email": "john@example.com",
        "deleted_at": "2026-03-31T12:05:00Z",
        "reason": "admin_deletion"
    }
}

# Handler will:
# 1. BEGIN TRANSACTION
# 2. DELETE FROM user_project WHERE user_id = ?
# 3. DELETE FROM user_agent WHERE user_id = ?
# 4. DELETE FROM chat_session WHERE user_id = ?
# 5. DELETE FROM message WHERE user_id = ?
# 6. DELETE FROM user WHERE id = ?
# 7. COMMIT (or ROLLBACK if error)
# 8. Log "user_deleted_cascade"
```

---

## 🧪 Тесты

### Unit Test 1: User creation (idempotent)

```python
@pytest.mark.asyncio
async def test_user_created_handler_idempotent(db_session):
    """Test that handle_user_created is idempotent"""
    
    event = {
        "event_type": "user.created",
        "data": {
            "user_id": "user-123",
            "email": "user@example.com"
        }
    }
    
    # First call: creates user
    await handlers.handle_user_created(event)
    user = await db_session.get(User, UUID("user-123"))
    assert user is not None
    assert user.email == "user@example.com"
    
    # Second call: should be idempotent (no error)
    await handlers.handle_user_created(event)
    user = await db_session.get(User, UUID("user-123"))
    assert user is not None  # Still exists
```

### Unit Test 2: User deletion (cascade)

```python
@pytest.mark.asyncio
async def test_user_deleted_handler_cascade():
    """Test cascade delete on user.deleted event"""
    
    # Setup: create user with projects, agents, sessions
    user_id = "user-123"
    await create_test_user(user_id)
    await create_test_projects(user_id, count=3)
    await create_test_agents(user_id, count=2)
    await create_test_sessions(user_id, count=5)
    
    event = {
        "event_type": "user.deleted",
        "data": {"user_id": user_id}
    }
    
    # Act: handle deletion
    await handlers.handle_user_deleted(event)
    
    # Assert: all deleted
    assert await db_session.get(User, user_id) is None
    projects = await db_session.execute(
        select(UserProject).where(UserProject.user_id == user_id)
    )
    assert len(projects.scalars().all()) == 0
    # ... verify all other tables
```

### Unit Test 3: Deletion is idempotent

```python
@pytest.mark.asyncio
async def test_user_deleted_handler_idempotent():
    """Test that handle_user_deleted is idempotent"""
    
    event = {
        "event_type": "user.deleted",
        "data": {"user_id": "user-123"}
    }
    
    # First call: user already deleted
    # Second call: should not error
    await handlers.handle_user_deleted(event)  # Already deleted
    await handlers.handle_user_deleted(event)  # Should be OK
    # No exception raised
```

### Integration Test 1: Full user lifecycle

```python
@pytest.mark.asyncio
async def test_full_user_lifecycle():
    """Test complete user lifecycle: create -> update -> delete"""
    
    user_id = "user-123"
    
    # 1. Create user
    event_created = {
        "event_type": "user.created",
        "data": {
            "user_id": user_id,
            "email": "john@example.com",
            "first_name": "John"
        }
    }
    await handlers.handle_user_created(event_created)
    user = await db_session.get(User, user_id)
    assert user.email == "john@example.com"
    
    # 2. Update user
    event_updated = {
        "event_type": "user.updated",
        "data": {
            "user_id": user_id,
            "email": "jane@example.com",
            "changes": ["email"]
        }
    }
    await handlers.handle_user_updated(event_updated)
    user = await db_session.get(User, user_id)
    assert user.email == "jane@example.com"
    
    # 3. Delete user
    event_deleted = {
        "event_type": "user.deleted",
        "data": {"user_id": user_id}
    }
    await handlers.handle_user_deleted(event_deleted)
    user = await db_session.get(User, user_id)
    assert user is None
```

---

## 📋 Acceptance Criteria

- ✅ `handle_user_created()` синхронизирует profile
- ✅ `handle_user_updated()` обновляет данные
- ✅ `handle_user_deleted()` удаляет all related data (cascade)
- ✅ Все handlers идемпотентны
- ✅ Cascade delete respects FK constraints
- ✅ Transactional (ACID)
- ✅ Logging полное
- ✅ Error handling (retry on exception)
- ✅ Unit тесты: 100% coverage
- ✅ Integration тесты: full lifecycle

---

## 🔗 Связанные компоненты

- [`EventConsumer`](../event-consumer/spec.md) — вызывает эти handlers
- [`UserEventHandlers`](../../services/user_event_handlers.py) — реальная имплементация
