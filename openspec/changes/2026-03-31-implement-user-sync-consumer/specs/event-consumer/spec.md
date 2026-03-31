# Спецификация: Event Consumer (Redis Streams)

**Версия:** 1.0.0  
**Дата:** 31 марта 2026  
**Сервис:** codelab-core-service

---

## 📋 Назначение компонента

**Event Consumer** — асинхронный потребитель событий из Redis Streams. Обеспечивает прослушивание и обработку событий от auth-service (user.created, user.updated, user.deleted) с гарантией доставки через Consumer Groups.

### Ключевые функции

- 📡 **Event Consumption** из Redis Stream (XREADGROUP, XAUTOCLAIM)
- ♻️ **Consumer Groups** для надежной доставки
- 🔄 **Retry logic** с exponential backoff
- 💀 **Dead Letter Queue** для failed событий
- 🧬 **Idempotent processing** (safe to replay)
- 🛑 **Graceful shutdown** при SIGTERM

---

## 🔌 API (Интерфейсы)

### Класс: RedisStreamsConsumer

```python
class RedisStreamsConsumer:
    def __init__(self, redis: Redis):
        """
        Инициализировать consumer
        
        Args:
            redis: Redis async client
        """
```

### Метод: initialize()

```python
async def initialize(self) -> None:
    """
    Инициализировать consumer group и регистрацию
    
    Creates:
    - Consumer group if not exists
    - DLQ stream if not exists
    
    Raises:
        RedisConnectionError: если Redis недоступен
    
    Example:
        >>> consumer = RedisStreamsConsumer(redis)
        >>> await consumer.initialize()
    """
```

### Метод: register_handler()

```python
def register_handler(
    self,
    event_type: str,
    handler: Callable
) -> None:
    """
    Зарегистрировать обработчик для event_type
    
    Args:
        event_type (str): e.g., "user.created", "user.deleted"
        handler (Callable): async def handler(event: dict)
    
    Example:
        >>> from app.services.user_event_handlers import handlers
        >>> consumer.register_handler("user.deleted", handlers.handle_user_deleted)
        >>> consumer.register_handler("user.created", handlers.handle_user_created)
    """
```

### Метод: start()

```python
async def start(self) -> None:
    """
    Запустить consumer loop (блокирующая операция)
    
    Loops:
    1. XAUTOCLAIM pending messages
    2. XREADGROUP new messages
    3. For each message: call handler, XACK on success
    4. On error: retry or send to DLQ
    
    Raises:
        asyncio.CancelledError: при SIGTERM/shutdown
    
    Example:
        >>> consumer_task = asyncio.create_task(consumer.start())
        >>> # Later during shutdown:
        >>> await consumer.stop()
        >>> await consumer_task
    """
```

### Метод: stop()

```python
async def stop(self) -> None:
    """
    Остановить consumer loop (graceful shutdown)
    
    Stops accepting new messages but processes pending
    
    Example:
        >>> await consumer.stop()
    """
```

---

## 📊 Схемы данных

### Stream Configuration

```
Stream: user_events
Consumer Group: core_service_group
Consumer Name: core_service_1

Configuration:
  min_idle_time: 60000  # 60 seconds before XAUTOCLAIM
  count: 10             # Batch size
  block: 100            # 100ms blocking read
  max_retries: 5        # Max retry attempts
```

### Event Structure

```
Stream Message:
{
  "event_id": "UUID",
  "event_type": "string",  # user.created, user.deleted, etc.
  "event_version": "1.0",
  "timestamp": "ISO8601",
  "aggregate_type": "user",
  "aggregate_id": "UUID",
  "correlation_id": "UUID",
  "source": "auth-service",
  "data": "JSON string"  # Actual payload
}
```

### Handler Signature

```python
async def handle_event(event: dict) -> None:
    """
    Event handler must:
    - Be async
    - Accept dict with event data
    - Be idempotent (safe to call multiple times)
    - Raise exception on failure (for retry)
    - Commit DB changes (handler owns transaction)
    
    Args:
        event (dict): Full event with all fields
    
    Returns:
        None
    
    Raises:
        Exception: Any exception triggers retry
    """
```

---

## 🔄 Workflow Diagram

```mermaid
sequenceDiagram
    participant Stream as Redis Stream
    participant Consumer as Event Consumer
    participant Handler as Event Handler
    participant DB as Database
    participant DLQ as DLQ Stream
    
    loop Every batch (10ms - 100ms)
        Consumer->>Stream: XAUTOCLAIM (pending, 60s idle)
        activate Consumer
        
        alt Pending messages
            Stream-->>Consumer: pending_messages
            
            loop For each message
                Consumer->>Handler: Call handler(event)
                activate Handler
                
                alt Handler success
                    Handler->>DB: Update data
                    deactivate Handler
                    
                    Consumer->>Stream: XACK message
                    Note over Consumer: Message removed from pending
                
                else Handler error
                    Handler-->>Consumer: Exception
                    deactivate Handler
                    
                    Consumer->>Consumer: Check retry_count
                    
                    alt Retry < max
                        Note over Consumer: Message stays pending
                        Note over Consumer: Will be retried later
                    else Max retries exceeded
                        Consumer->>DLQ: XADD to DLQ
                        Consumer->>Stream: XACK (acknowledge)
                        Note over DLQ: Manual investigation needed
                    end
                end
            end
        
        else No pending messages
            Consumer->>Stream: XREADGROUP (new messages, block 100ms)
            Stream-->>Consumer: messages or timeout
        end
        
        deactivate Consumer
    end
```

---

## ⚠️ Обработка ошибок

### Сценарий 1: Handler throws exception

```python
try:
    await handler(event)
except Exception as e:
    delivery_count = get_delivery_count(message_id)
    
    if delivery_count < MAX_RETRIES:
        logger.warning(f"Handler error (attempt {delivery_count}), will retry")
        # Don't ACK, message stays in pending
        # Will be retried by XAUTOCLAIM
    else:
        logger.error(f"Max retries exceeded for event {event_id}")
        # Send to DLQ and ACK
        await send_to_dlq(message_id, event, str(e))
        await redis.xack(stream_key, group, message_id)
```

### Сценарий 2: Redis connection lost

```python
while running:
    try:
        messages = await redis.xreadgroup(...)
    except RedisConnectionError:
        logger.error("redis_connection_lost, retrying in 30s")
        await asyncio.sleep(30)
        # Reconnect next iteration
```

### Сценарий 3: Event JSON parsing error

```python
try:
    event = json.loads(message_data["data"])
except json.JSONDecodeError as e:
    logger.error(f"Invalid JSON in event {message_id}")
    # Send to DLQ immediately (no retry)
    await send_to_dlq(message_id, event_bytes, str(e))
    await redis.xack(stream_key, group, message_id)
```

---

## 🧪 Тесты

### Unit Test 1: Consumer initialization

```python
@pytest.mark.asyncio
async def test_consumer_initialization(redis):
    """Test consumer group creation"""
    
    consumer = RedisStreamsConsumer(redis)
    await consumer.initialize()
    
    # Verify consumer group exists
    groups = await redis.xinfo_groups("user_events")
    assert any(g["name"] == "core_service_group" for g in groups)
```

### Unit Test 2: Handler registration

```python
@pytest.mark.asyncio
async def test_handler_registration(consumer):
    """Test handler registration"""
    
    async def my_handler(event):
        pass
    
    consumer.register_handler("user.deleted", my_handler)
    
    # Verify handler is registered
    assert "user.deleted" in consumer.event_handlers
```

### Unit Test 3: Event processing success

```python
@pytest.mark.asyncio
async def test_event_processing_success(consumer, redis):
    """Test successful event processing"""
    
    processed = False
    
    async def handler(event):
        nonlocal processed
        processed = True
    
    consumer.register_handler("user.created", handler)
    
    # Publish event
    await redis.xadd("user_events", {
        "event_type": "user.created",
        "data": json.dumps({"user_id": "123"})
    })
    
    # Process one batch
    await consumer._consume_batch()
    
    assert processed == True
```

### Integration Test 1: Full event flow

```python
@pytest.mark.asyncio
async def test_full_event_flow():
    """Test complete event processing pipeline"""
    
    # 1. Start consumer in background
    consumer = RedisStreamsConsumer(redis)
    await consumer.initialize()
    
    events_processed = []
    
    async def handler(event):
        events_processed.append(event)
    
    consumer.register_handler("user.created", handler)
    consumer_task = asyncio.create_task(consumer.start())
    
    # 2. Publish event
    await publisher.publish_event(
        event_type="user.created",
        aggregate_type="user",
        aggregate_id="user-123",
        data={"user_id": "user-123"}
    )
    
    # 3. Wait for processing
    await asyncio.sleep(1)
    
    # 4. Verify processed
    assert len(events_processed) == 1
    assert events_processed[0]["event_type"] == "user.created"
    
    # 5. Cleanup
    await consumer.stop()
    await consumer_task
```

---

## 📋 Acceptance Criteria

- ✅ Consumer группа создается при initialize()
- ✅ Handlers регистрируются и вызываются
- ✅ XREADGROUP читает новые события
- ✅ XAUTOCLAIM обрабатывает pending
- ✅ XACK успешных сообщений
- ✅ Retry logic с exponential backoff
- ✅ DLQ для failed событий
- ✅ Graceful shutdown (SIGTERM)
- ✅ Error handling: no crashes
- ✅ Logging: полное
- ✅ Unit тесты: 95%+ coverage
- ✅ Integration тесты: full flow

---

## 🔗 Связанные компоненты

- [`UserEventHandlers`](../user-sync-handlers/spec.md) — обработчики событий
- [`EventPublisher`](../../../codelab-auth-service/openspec/changes/2026-03-31-implement-user-sync-events/specs/event-publisher/spec.md) — издатель в auth-service
