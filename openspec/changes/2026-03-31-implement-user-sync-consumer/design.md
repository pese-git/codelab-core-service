# Design: Event-Driven синхронизация и Token Blacklist (Core Service)

**Версия:** 1.0.0  
**Дата:** 31 марта 2026

---

## 🏗️ Архитектура системы

### 1. Event Consumer (Redis Streams)

#### Architecture

```
┌──────────────────────────────────────────────┐
│         Event Consumer Loop                   │
│                                              │
│  while running:                             │
│    1. XAUTOCLAIM (handle pending messages) │
│    2. XREADGROUP (read new messages)       │
│    3. For each message:                    │
│       - Call handler                       │
│       - XACK on success                    │
│       - On error: retry or send to DLQ    │
└──────────────────────────────────────────────┘
```

#### Consumer Group Configuration

```yaml
Stream: user_events
Consumer Group: core_service_group
Consumer Name: core_service_1

Settings:
  min_idle_time: 60000  # 60 seconds before autoclaim
  count: 10             # Batch size per read
  block: 100            # 100ms blocking read
  max_retries: 5        # Retry failed messages 5 times
```

### 2. Token Blacklist Integration

#### Middleware Flow

```
Request
  ├─ Extract JWT token from Authorization header
  │
  ├─ Validate JWT signature (JWKS)
  │
  ├─ ✨ NEW: Check if token in blacklist (Redis)
  │   └─ if revoked: return 401 Unauthorized
  │
  ├─ Inject user_id to request.state
  │
  └─ Process request
```

#### Blacklist Check Implementation

```python
# Before calling next handler:
blacklist_service = await get_token_blacklist_service()
is_revoked = await blacklist_service.is_token_revoked(jti)

if is_revoked:
    return JSONResponse(
        status_code=401,
        content={"error": "Token revoked"}
    )
```

### 3. User Event Handlers

#### Event Routing

```
user_events stream
  ├─ user.created
  │   └─ handle_user_created()
  │       ├─ Check if user exists
  │       ├─ Create user profile if not
  │       └─ Log sync
  │
  ├─ user.updated
  │   └─ handle_user_updated()
  │       ├─ Get user from DB
  │       ├─ Update email, name fields
  │       ├─ Notify active sessions
  │       └─ Log sync
  │
  ├─ user.deleted
  │   └─ handle_user_deleted()
  │       ├─ BEGIN TRANSACTION
  │       ├─ Delete UserProject (CASCADE)
  │       ├─ Delete UserAgent (CASCADE)
  │       ├─ Delete ChatSession (CASCADE)
  │       ├─ Delete Message (CASCADE)
  │       ├─ Delete User
  │       ├─ COMMIT
  │       └─ Log cascade
  │
  └─ token.revoked (optional logging)
      └─ handle_token_revoked()
          └─ Log revocation
```

#### Idempotency Strategy

```python
# All handlers must be idempotent (safe to call multiple times)

async def handle_user_created(event):
    user_id = UUID(event["data"]["user_id"])
    
    user = await session.get(User, user_id)
    if user:
        # Already created, idempotent — just return
        logger.info("user_already_exists", user_id=user_id)
        return
    
    # Create new user
    user = User(id=user_id, ...)
    session.add(user)
    await session.commit()
```

### 4. Database Schema Changes

#### New Columns in User Table

```sql
ALTER TABLE users ADD COLUMN (
    synced_from_auth_at TIMESTAMP WITH TIME ZONE,
    synced_version INTEGER DEFAULT 1
);

CREATE INDEX idx_users_synced
  ON users(synced_from_auth_at, synced_version);
```

#### Schema Version Table (Optional)

```sql
CREATE TABLE IF NOT EXISTS user_sync_state (
    user_id UUID PRIMARY KEY,
    last_event_id VARCHAR(50),  # Redis stream message ID
    last_sync_at TIMESTAMP WITH TIME ZONE,
    created_event BOOLEAN,
    created_from_auth BOOLEAN DEFAULT FALSE,
    
    CONSTRAINT fk_user FOREIGN KEY (user_id)
      REFERENCES users(id) ON DELETE CASCADE
);
```

### 5. Configuration

```yaml
# .env settings for Core Service

# Redis Streams
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_STREAM_KEY=user_events
REDIS_DLQ_STREAM_KEY=user_events_dlq

# Consumer Configuration
REDIS_CONSUMER_GROUP=core_service_group
REDIS_CONSUMER_NAME=core_service_1
REDIS_CONSUMER_MIN_IDLE_TIME=60000  # 60 seconds

# Event Processing
EVENT_MAX_RETRIES=5
EVENT_INITIAL_RETRY_DELAY=5
EVENT_MAX_RETRY_DELAY=300

# Token Blacklist
USE_TOKEN_BLACKLIST=true
BLACKLIST_PREFIX=token_blacklist

# JWT
JWT_ISSUER=https://auth.codelab.dev
JWT_AUDIENCE=codelab-services
```

### 6. Sequence Diagrams

#### Диаграмма 1: Event Consumer Processing

```mermaid
sequenceDiagram
    participant Stream as Redis Stream
    participant Consumer as Event Consumer
    participant Handler as Event Handler
    participant DB as PostgreSQL
    participant DLQ as DLQ Stream
    
    loop Every 100ms
        Consumer->>Stream: XAUTOCLAIM (pending messages)
        activate Consumer
        
        alt Pending messages
            Stream-->>Consumer: messages
            Consumer->>Handler: Process message
            activate Handler
            
            alt Success
                Handler->>DB: Update data
                DB-->>Handler: OK
                deactivate Handler
                
                Consumer->>Stream: XACK
                Note over Consumer,Stream: Message acknowledged
            else Failure (retry < max)
                Handler-->>Consumer: Error
                deactivate Handler
                Consumer->>Consumer: Log error
                Note over Consumer: Will retry next iteration
            else Failure (max retries exceeded)
                Handler-->>Consumer: Fatal Error
                Consumer->>DLQ: XADD (send to DLQ)
                Consumer->>Stream: XACK
                Note over DLQ: Manual investigation needed
            end
        else No pending
            Consumer->>Stream: XREADGROUP (new messages)
            Stream-->>Consumer: messages or timeout
        end
        
        deactivate Consumer
    end
```

#### Диаграмма 2: Token Blacklist Check in Middleware

```mermaid
sequenceDiagram
    participant Client
    participant API as Core Service API
    participant MW as UserIsolationMiddleware
    participant JWT as JWT Validator
    participant BL as Token Blacklist
    participant Handler as Request Handler
    
    Client->>API: Request with token
    activate API
    
    API->>MW: dispatch()
    activate MW
    
    MW->>MW: Extract token from header
    
    MW->>JWT: Validate JWT
    activate JWT
    JWT-->>MW: payload {sub, jti, exp, ...}
    deactivate JWT
    
    MW->>BL: is_token_revoked(jti)
    activate BL
    
    alt Token in blacklist
        BL-->>MW: TRUE
        MW-->>Client: 401 Token Revoked
        deactivate BL
        deactivate API
    else Token NOT revoked
        BL-->>MW: FALSE
        deactivate BL
        
        MW->>MW: Inject user_id to request.state
        
        MW->>Handler: call_next(request)
        activate Handler
        Handler-->>MW: response
        deactivate Handler
        
        MW-->>Client: response
    end
    
    deactivate MW
    deactivate API
```

### 7. Error Handling

#### Scenario: Event Processing Error

```python
try:
    event = json.loads(message_data)
    handler = get_event_handler(event["event_type"])
    await handler(event)
    await redis.xack(stream_key, group, message_id)
    
except Exception as e:
    delivery_count = get_delivery_count(message_id)
    
    if delivery_count < MAX_RETRIES:
        logger.warning(f"Will retry (attempt {delivery_count})")
        # Message stays in pending, will be retried
    else:
        logger.error(f"Max retries exceeded, sending to DLQ")
        await send_to_dlq(message_id, event, str(e))
        await redis.xack(stream_key, group, message_id)
```

#### Scenario: Cascade Delete Error

```python
async def handle_user_deleted(event):
    user_id = UUID(event["data"]["user_id"])
    
    async with session.begin():  # Transaction
        try:
            # Delete in order (respecting FK constraints)
            await session.execute(delete(UserProject).where(...))
            await session.execute(delete(UserAgent).where(...))
            await session.execute(delete(ChatSession).where(...))
            await session.execute(delete(User).where(...))
            # COMMIT if all successful
        except IntegrityError as e:
            # ROLLBACK automatic
            logger.error("cascade_delete_failed", user_id=user_id)
            raise  # Will retry or go to DLQ
```

---

## 📊 Компоненты и взаимодействие

```
┌──────────────────────────────────────────────────┐
│           Codelab Core Service                   │
│                                                  │
│  ┌─────────────────────────────────────────┐   │
│  │ Event Consumer (Redis Streams)          │   │
│  │                                         │   │
│  │ - XREAD/XREADGROUP                     │   │
│  │ - Consumer Groups                       │   │
│  │ - Retry logic                           │   │
│  │ - DLQ handling                          │   │
│  └────────────────┬────────────────────────┘   │
│                   │                             │
│  ┌────────────────▼────────────────────────┐   │
│  │ Event Handlers                          │   │
│  │                                         │   │
│  │ - handle_user_created()                │   │
│  │ - handle_user_updated()                │   │
│  │ - handle_user_deleted() (CASCADE)      │   │
│  │ - handle_token_revoked()               │   │
│  └────────────────┬────────────────────────┘   │
│                   │                             │
│  ┌────────────────▼────────────────────────┐   │
│  │ UserIsolationMiddleware (UPDATED)       │   │
│  │                                         │   │
│  │ 1. Extract JWT                          │   │
│  │ 2. Validate signature                   │   │
│  │ 3. ✨ Check blacklist (NEW)             │   │
│  │ 4. Inject user_id                       │   │
│  └─────────────────────────────────────────┘   │
│                   │                             │
│  ┌────────────────▼────────────────────────┐   │
│  │ Request Handlers                        │   │
│  │ (existing endpoints)                    │   │
│  └─────────────────────────────────────────┘   │
│                                                  │
└──────────────────────────────────────────────────┘
         │                    │
         │                    │
    ┌────▼────┐         ┌─────▼──────┐
    │PostgreSQL│         │ Redis      │
    │  (Users, │         │ (Blacklist,│
    │ Projects,│         │  Streams)  │
    │ Agents)  │         └────────────┘
    └──────────┘
```

---

## ✅ Acceptance Criteria

- ✅ EventConsumer запускается при startup
- ✅ Events из stream обрабатываются правильно
- ✅ handle_user_deleted() выполняет CASCADE delete
- ✅ handle_user_created/updated() синхронизирует profile
- ✅ UserIsolationMiddleware проверяет blacklist
- ✅ Revoked токен возвращает 401
- ✅ Consumer Groups работают корректно
- ✅ DLQ обрабатывает failed события
- ✅ Graceful degradation если Redis down
- ✅ Логирование полное
- ✅ Transactional consistency (ACID)
