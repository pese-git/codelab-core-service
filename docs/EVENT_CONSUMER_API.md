# API Документация: Event Consumer

## Обзор

`RedisStreamsConsumer` — это сервис, который потребляет события из Redis Streams, опубликованные Auth Service. Он предоставляет надежную доставку сообщений с подтверждением, обработкой ошибок, повторными попытками и маршрутизацией неудачных сообщений в Dead Letter Queue (DLQ).

## Класс: RedisStreamsConsumer

### Инициализация

```python
from app.services.event_consumer import RedisStreamsConsumer
from redis import AsyncRedis

# Инициализация с клиентом Redis
redis_client = AsyncRedis(host="redis", port=6379, decode_responses=True)
consumer = RedisStreamsConsumer(redis_client)

# Инициализация группы потребителей
await consumer.initialize()
```

#### Параметры конфигурации

- `stream_key` (str): Ключ Redis Stream для прослушивания (по умолчанию: "user_events")
- `consumer_group` (str): Имя группы потребителей (по умолчанию: "core_service_consumer_group")
- `consumer_name` (str): Имя потребителя (по умолчанию: "core_service_consumer_1")
- `batch_size` (int): Количество сообщений для обработки за один раз (по умолчанию: 10)
- `timeout_ms` (int): Таймаут XREADGROUP в миллисекундах (по умолчанию: 1000)
- `max_retries` (int): Максимальное количество повторов для неудачного сообщения (по умолчанию: 3)
- `dlq_stream_key` (str): Ключ потока Dead Letter Queue (по умолчанию: "user_events_dlq")

### Методы

#### `async initialize()`

Инициализирует потребителя и создает группу потребителей в Redis.

```python
await consumer.initialize()
```

**Возвращает:** `None`

**Исключения:**
- `RedisError`: Если ошибка подключения к Redis
- `RuntimeError`: Если потребитель уже инициализирован

#### `def register_handler()`

Регистрирует обработчик для определенного типа события.

```python
from app.services.user_event_handlers import UserEventHandlers

handlers = UserEventHandlers(db_session)

consumer.register_handler("user.created", handlers.handle_user_created)
consumer.register_handler("user.updated", handlers.handle_user_updated)
consumer.register_handler("user.deleted", handlers.handle_user_deleted)
consumer.register_handler("token.revoked", handlers.handle_token_revoked)
```

**Параметры:**

| Параметр | Тип | Обязательно | Описание |
|----------|-----|-------------|---------|
| `event_type` | str | Да | Тип события (например, "user.created") |
| `handler` | Callable | Да | Асинхронная функция-обработчик |

**Возвращает:** `None`

**Исключения:**
- `ValueError`: Если обработчик не является асинхронной функцией

#### `async start()`

Запускает цикл потребления событий. Этот метод блокирует выполнение до вызова `stop()`.

```python
# Запуск в фоне
asyncio.create_task(consumer.start())

# Или в отдельной корутине
await consumer.start()
```

**Возвращает:** `None`

**Исключения:**
- `RedisError`: Если ошибка подключения к Redis
- `RuntimeError`: Если нет зарегистрированных обработчиков

#### `async stop()`

Останавливает цикл потребления событий.

```python
await consumer.stop()
```

**Возвращает:** `None`

#### `async process_pending_messages()`

Обрабатывает сообщения, которые были отправлены потребителю, но не подтверждены (из-за отказа или перезагрузки).

```python
await consumer.process_pending_messages()
```

**Возвращает:** `int` - Количество обработанных сообщений

---

## Структура события

### Формат входящего события

События получаются из Redis Stream в следующем формате:

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "type": "user.created",
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "version": "1.0",
  "timestamp": "2026-03-31T20:33:12.564Z",
  "correlation_id": "corr-abc-123",
  "causation_id": "cause-xyz-789",
  "data": "{\"username\": \"john_doe\", \"email\": \"john@example.com\"}"
}
```

### Сигнатура обработчика

Все обработчики должны иметь эту сигнатуру:

```python
async def handle_event(event: dict) -> None:
    """
    Обработать событие из Redis Streams.
    
    Args:
        event: Словарь с данными события
        
    Raises:
        Exception: Для обработки повторных попыток и DLQ
    """
    event_type = event.get("type")
    user_id = event.get("user_id")
    data = event.get("data")
    
    # Обработка события
    ...
```

---

## Примеры интеграции

### Пример 1: Инициализация и запуск потребителя

```python
from app.services.event_consumer import RedisStreamsConsumer
from app.services.user_event_handlers import UserEventHandlers

async def setup_event_consumer(redis_client, db_session):
    # Создание потребителя
    consumer = RedisStreamsConsumer(redis_client)
    
    # Инициализация группы потребителей
    await consumer.initialize()
    
    # Регистрация обработчиков
    handlers = UserEventHandlers(db_session)
    consumer.register_handler("user.created", handlers.handle_user_created)
    consumer.register_handler("user.updated", handlers.handle_user_updated)
    consumer.register_handler("user.deleted", handlers.handle_user_deleted)
    
    # Запуск в фоне
    asyncio.create_task(consumer.start())
    
    return consumer
```

### Пример 2: Запуск в lifespan FastAPI приложения

```python
from contextlib import asynccontextmanager

consumer = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global consumer
    consumer = RedisStreamsConsumer(redis_client)
    await consumer.initialize()
    
    handlers = UserEventHandlers(db_session)
    consumer.register_handler("user.created", handlers.handle_user_created)
    consumer.register_handler("user.updated", handlers.handle_user_updated)
    consumer.register_handler("user.deleted", handlers.handle_user_deleted)
    
    asyncio.create_task(consumer.start())
    
    yield
    
    # Shutdown
    await consumer.stop()

app = FastAPI(lifespan=lifespan)
```

### Пример 3: Обработчик события с логированием

```python
from app.services.user_event_handlers import UserEventHandlers

handlers = UserEventHandlers(db_session)

async def logged_handle_user_created(event: dict):
    """Обработчик с логированием."""
    correlation_id = event.get("correlation_id")
    user_id = event.get("user_id")
    
    logger.info(
        "Processing user.created event",
        extra={
            "correlation_id": correlation_id,
            "user_id": user_id,
            "event_id": event.get("id"),
        }
    )
    
    try:
        await handlers.handle_user_created(event)
        logger.info("User created successfully", extra={"user_id": user_id})
    except Exception as e:
        logger.error(
            "Failed to create user",
            exc_info=True,
            extra={"user_id": user_id, "error": str(e)}
        )
        raise

consumer.register_handler("user.created", logged_handle_user_created)
```

---

## Обработка ошибок

### Стратегия повторных попыток

При ошибке обработчика сообщение переводится в режим повторного попыток:

```
Попытка 1 → Ошибка → Ожидание 1 сек
Попытка 2 → Ошибка → Ожидание 2 сек
Попытка 3 → Ошибка → Ожидание 4 сек
Попытка 4 (последняя) → Ошибка → Маршрутизация в DLQ
```

### Маршрутизация в Dead Letter Queue

Если после максимального количества повторов обработка остается неудачной, сообщение перемещается в DLQ:

```python
# Структура сообщения в DLQ
{
    "original_stream": "user_events",
    "message_id": "1-0",
    "original_event": {...},
    "error": "Database connection failed",
    "retry_count": 3,
    "timestamp": "2026-03-31T20:33:12.564Z"
}
```

### Обработка ошибок Redis

```python
try:
    await consumer.initialize()
    await consumer.start()
except RedisError as e:
    logger.error("Redis connection failed", exc_info=True)
    # Fallback: использование прямых запросов в БД
    # или ожидание восстановления Redis
```

---

## Обработчики событий

### handle_user_created()

Обрабатывает событие создания пользователя. Создает запись пользователя в Core Service.

```python
from app.services.user_event_handlers import UserEventHandlers

handlers = UserEventHandlers(db_session)
consumer.register_handler("user.created", handlers.handle_user_created)
```

**Ожидаемые поля события:**

```json
{
  "type": "user.created",
  "user_id": "string",
  "data": {
    "user_id": "string",
    "username": "string",
    "email": "string"
  }
}
```

**Операции:**
1. Создает запись пользователя в таблице `users`
2. Устанавливает `synced_from_auth_at` на текущее время
3. Устанавливает `synced_version` из события

### handle_user_updated()

Обрабатывает событие обновления пользователя. Обновляет профиль пользователя.

```python
consumer.register_handler("user.updated", handlers.handle_user_updated)
```

**Ожидаемые поля события:**

```json
{
  "type": "user.updated",
  "user_id": "string",
  "data": {
    "user_id": "string",
    "email": "string (опционально)",
    "is_active": "boolean (опционально)",
    "updated_fields": ["string"]
  }
}
```

### handle_user_deleted()

Обрабатывает событие удаления пользователя. Выполняет каскадное удаление.

```python
consumer.register_handler("user.deleted", handlers.handle_user_deleted)
```

**Порядок каскадного удаления:**
1. Удаление `Messages` пользователя
2. Удаление `ChatSessions` пользователя
3. Удаление `UserAgents` пользователя
4. Удаление `UserProjects` пользователя
5. Удаление записи `User`

### handle_token_revoked()

Обрабатывает событие отзыва токена. В Core Service это в основном логирование.

```python
consumer.register_handler("token.revoked", handlers.handle_token_revoked)
```

---

## Идемпотентность

Все обработчики разработаны как идемпотентные. Это означает, что обработка одного и того же события несколько раз приводит к одинаковому результату:

```python
# Обработка одного события дважды
await handlers.handle_user_created(event)
await handlers.handle_user_created(event)

# Результат: пользователь создан один раз
# (благодаря проверкам EXISTS и UNIQUE constraints)
```

---

## Конфигурация

### Переменные окружения

```env
# .env
USE_EVENT_CONSUMER=true
EVENTS_STREAM_KEY=user_events
EVENTS_CONSUMER_GROUP=core_service_consumer_group
EVENTS_CONSUMER_NAME=core_service_consumer_1
EVENTS_BATCH_SIZE=10
EVENTS_CONSUMER_TIMEOUT=1000
EVENTS_MAX_RETRIES=3
EVENTS_RETRY_BACKOFF_BASE=1
EVENTS_DLQ_STREAM_KEY=user_events_dlq
EVENTS_VERSION=1.0
```

### Класс Settings

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    use_event_consumer: bool = True
    events_stream_key: str = "user_events"
    events_consumer_group: str = "core_service_consumer_group"
    events_consumer_name: str = "core_service_consumer_1"
    events_batch_size: int = 10
    events_consumer_timeout: int = 1000
    events_max_retries: int = 3
    events_retry_backoff_base: int = 1
    events_dlq_stream_key: str = "user_events_dlq"
    events_version: str = "1.0"
```

---

## Мониторинг

### Основные метрики

- `core_events_processed_total`: Всего обработано событий (по типу события и статусу)
- `core_event_processing_duration_seconds`: Продолжительность обработки события
- `core_events_dlq_total`: Количество сообщений в DLQ
- `core_consumer_group_lag`: Задержка группы потребителей
- `core_pending_messages`: Количество необработанных сообщений

### Пример Prometheus запроса

```promql
# События обработаны в секунду
rate(core_events_processed_total[5m])

# Задержка обработки (P95)
histogram_quantile(0.95, core_event_processing_duration_seconds_bucket)

# Задержка группы потребителей
core_consumer_group_lag

# Необработанные сообщения
core_pending_messages > 100
```

---

## Интеграция с middleware Token Blacklist

The consumer works alongside the [`UserIsolationMiddleware`] which checks token blacklist for incoming requests. Когда пользователь удаляется:

1. Auth Service публикует событие `user.deleted`
2. Core Service consumer получает событие
3. Consumer вызывает `handle_user_deleted()`
4. Пользователь удаляется из Core Service БД
5. Middleware будет блокировать запросы удаленного пользователя благодаря token blacklist

---

## Troubleshooting

### Consumer не обрабатывает события

```python
# Проверка 1: Consumer инициализирован?
logger.info(f"Consumer initialized: {consumer._initialized}")

# Проверка 2: Есть ли зарегистрированные обработчики?
logger.info(f"Handlers registered: {len(consumer._handlers)}")

# Проверка 3: Consumer запущен?
logger.info(f"Consumer running: {consumer._running}")

# Проверка 4: Есть ли события в потоке?
stream_info = await redis_client.xinfo_stream("user_events")
logger.info(f"Stream length: {stream_info['length']}")
```

### Обработчик вызывает исключение

```python
# Включить debug логирование
LOG_LEVEL=DEBUG

# Проверить сообщения в DLQ
dlq_messages = await redis_client.xlen("user_events_dlq")
logger.warning(f"Messages in DLQ: {dlq_messages}")

# Прочитать сообщение из DLQ для анализа
messages = await redis_client.xread(
    {"user_events_dlq": "0"}, 
    count=1
)
```

---

## Связанная документация

- [API Event Publisher](../codelab-auth-service/docs/EVENT_PUBLISHER_API.md)
- [Спецификация Event Consumer](../../openspec/changes/2026-03-31-implement-user-sync-consumer/specs/event-consumer/spec.md)
- [Спецификация User Event Handlers](../../openspec/changes/2026-03-31-implement-user-sync-consumer/specs/user-sync-handlers/spec.md)
- [Руководство по Redis Streams](../../plans/redis-streams-implementation-guide.md)
