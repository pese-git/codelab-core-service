# Operational Runbook: User Sync и Token Blacklist (Core Service)

## Содержание

1. [Обзор системы](#обзор-системы)
2. [Переменные окружения](#переменные-окружения)
3. [Запуск и остановка сервиса](#запуск-и-остановка-сервиса)
4. [Мониторинг](#мониторинг)
5. [Troubleshooting](#troubleshooting)
6. [Emergency Procedures](#emergency-procedures)
7. [Maintenance Tasks](#maintenance-tasks)

---

## Обзор системы

### Event Consumer Flow

```
Redis Streams (user_events)
           │
           ▼
    Event Consumer
           │
       ┌───┴───┬───────┬──────────┐
       │       │       │          │
       ▼       ▼       ▼          ▼
    created  updated deleted  revoked
       │       │       │          │
       ▼       ▼       ▼          ▼
    Handle   Handle  Handle    Handle
    Created  Updated Deleted   Revoked
       │       │       │          │
       └───────┴───────┴──────────┘
               │
               ▼
        PostgreSQL (users, etc.)

    Ошибки после N повторов
               │
               ▼
        Redis Streams (user_events_dlq)
```

### Token Blacklist в Middleware

```
HTTP Request
     │
     ▼
UserIsolationMiddleware
     │
     ├─► Извлечение JTI из JWT
     │
     ├─► Проверка Redis blacklist
     │       │
     │       ├─ Токен в blacklist? ──► 401 Unauthorized
     │       │
     │       └─ Нет в blacklist ──────► Продолжить
     │
     └─► GRACEFUL FALLBACK на JWT exp
         (если Redis недоступен)
```

---

## Переменные окружения

### Core Service конфигурация

```env
# Event Consumer Configuration
USE_EVENT_CONSUMER=true
EVENTS_STREAM_KEY=user_events
EVENTS_CONSUMER_GROUP=core_service_consumer_group
EVENTS_CONSUMER_NAME=core_service_consumer_1

# Event Processing
EVENTS_BATCH_SIZE=10
EVENTS_CONSUMER_TIMEOUT=1000
EVENTS_MAX_RETRIES=3
EVENTS_RETRY_BACKOFF_BASE=1
EVENTS_DLQ_STREAM_KEY=user_events_dlq
EVENTS_VERSION=1.0

# Token Blacklist Configuration
USE_TOKEN_BLACKLIST=true
TOKEN_BLACKLIST_MIN_TTL=3600

# Redis Connection
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=redis-secure-password-change-in-production
REDIS_DB=0
```

---

## Запуск и остановка сервиса

### 1. Инициализация Event Consumer при старте

```python
# app/main.py
from contextlib import asynccontextmanager

consumer = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global consumer
    
    # Инициализация consumer
    consumer = RedisStreamsConsumer(redis_client)
    await consumer.initialize()
    
    # Регистрация обработчиков
    handlers = UserEventHandlers(db_session)
    consumer.register_handler("user.created", handlers.handle_user_created)
    consumer.register_handler("user.updated", handlers.handle_user_updated)
    consumer.register_handler("user.deleted", handlers.handle_user_deleted)
    consumer.register_handler("token.revoked", handlers.handle_token_revoked)
    
    # Запуск consumer в фоне
    asyncio.create_task(consumer.start())
    
    logger.info("Event consumer started")
    
    yield
    
    # Shutdown
    await consumer.stop()
    logger.info("Event consumer stopped")

app = FastAPI(lifespan=lifespan)
```

### 2. Проверка статуса

```bash
# Проверка запущен ли consumer
docker-compose logs codelab-core-service | grep -i "consumer\|event"

# Проверка подключения к Redis
curl http://localhost:8000/health

# Проверка в памяти потребителя обработчиков
# (выполняется при инициализации)
```

### 3. Остановка graceful

```bash
# Остановка с завершением текущих операций
docker-compose stop codelab-core-service

# Принудительная остановка (если зависла)
docker-compose kill codelab-core-service
```

---

## Мониторинг

### 1. Event Consumer Status

```bash
# Информация о группе потребителей
redis-cli -h localhost -p 6379 << EOF
XINFO GROUPS user_events
XINFO CONSUMERS user_events core_service_consumer_group
EOF

# Задержка потребителя (consumer lag)
redis-cli -h localhost -p 6379 << EOF
-- Последний ID обработанного сообщения
XINFO GROUPS user_events | grep "last-delivered-id"

-- Последний ID в потоке
XREVRANGE user_events + COUNT 1
EOF
```

### 2. Event Processing Metrics

```bash
# Проверка обработанных событий
curl -s http://localhost:8000/metrics | grep core_events_processed_total

# Задержка обработки
curl -s http://localhost:8000/metrics | grep core_event_processing_duration_seconds

# Размер DLQ
curl -s http://localhost:8000/metrics | grep core_events_dlq_total
```

### 3. Database Sync Status

```bash
# Количество синхронизированных пользователей
psql -h localhost -U postgres -d codelab -c "
SELECT COUNT(*) FROM users WHERE synced_from_auth_at IS NOT NULL;
"

# Последний синхронизированный пользователь
psql -h localhost -U postgres -d codelab -c "
SELECT id, username, synced_from_auth_at, synced_version
FROM users
ORDER BY synced_from_auth_at DESC LIMIT 1;
"

# Пользователи без синхронизации
psql -h localhost -U postgres -d codelab -c "
SELECT COUNT(*) FROM users WHERE synced_from_auth_at IS NULL;
"
```

### 4. Token Blacklist Status

```bash
# Проверка доступности Redis для blacklist
redis-cli -h localhost -p 6379 PING

# Количество активных отозванных токенов
redis-cli -h localhost -p 6379 DBSIZE

# Проверить конкретный токен
redis-cli -h localhost -p 6379 GET "blacklist:token:<jti>"
```

---

## Troubleshooting

### 1. Consumer не обрабатывает события

**Симптомы:**
- Новые события не попадают в БД
- Логи: "Pending messages: 0"
- Размер потока растет

**Диагностика:**

```bash
# 1. Проверить, запущен ли consumer
docker-compose logs codelab-core-service | grep "consumer"

# 2. Проверить наличие сообщений в потоке
redis-cli -h localhost -p 6379 XLEN user_events

# 3. Проверить информацию о группе
redis-cli -h localhost -p 6379 XINFO GROUPS user_events

# 4. Проверить логи ошибок
docker-compose logs codelab-core-service | grep -i "error\|exception"

# 5. Проверить Redis соединение
docker-compose exec codelab-core-service python -c "import redis; print(redis.Redis(host='redis').ping())"
```

**Решение:**

```bash
# Вариант 1: Перезагрузить service
docker-compose restart codelab-core-service

# Вариант 2: Пересоздать группу потребителей
redis-cli -h localhost -p 6379 XGROUP DESTROY user_events core_service_consumer_group
docker-compose restart codelab-core-service

# Вариант 3: Обработать pending сообщения
# Это происходит автоматически при следующем запуске consumer
```

### 2. Token Blacklist не блокирует запросы

**Симптомы:**
- Отозванные токены принимаются middleware
- Запросы удаленных пользователей не отклоняются
- Логи: "Token not in blacklist"

**Диагностика:**

```bash
# 1. Проверить Redis доступность
redis-cli -h localhost -p 6379 PING

# 2. Проверить наличие токена в blacklist
redis-cli -h localhost -p 6379 GET "blacklist:token:<jti>"

# 3. Проверить переменные окружения
docker-compose exec codelab-core-service env | grep TOKEN_BLACKLIST

# 4. Проверить логи middleware
docker-compose logs codelab-core-service | grep -i "middleware\|blacklist"
```

**Решение:**

```bash
# Вариант 1: Проверить JTI в токене
# JTI должен быть в payload JWT токена

# Вариант 2: Вручную добавить токен в blacklist
redis-cli -h localhost -p 6379 SETEX "blacklist:token:<jti>" 3600 "1"

# Вариант 3: Перезагрузить Redis
docker-compose restart redis

# Вариант 4: Проверить конфигурацию middleware
# USE_TOKEN_BLACKLIST=true в .env
```

### 3. DLQ переполнен (много ошибок)

**Симптомы:**
- Размер user_events_dlq растет
- События не обрабатываются
- Логи содержат exceptions

**Диагностика:**

```bash
# 1. Проверить размер DLQ
redis-cli -h localhost -p 6379 XLEN user_events_dlq

# 2. Прочитать первое сообщение из DLQ
redis-cli -h localhost -p 6379 XREAD COUNT 1 STREAMS user_events_dlq 0

# 3. Проверить последний лог ошибки
docker-compose logs codelab-core-service | tail -50 | grep -i error

# 4. Проверить состояние БД
psql -h localhost -U postgres -d codelab -c "SELECT COUNT(*) FROM users;"
```

**Решение:**

```bash
# Вариант 1: Найти и исправить ошибку обработчика
# Обычно: ошибка БД, неверная схема данных, ошибка сериализации

# Вариант 2: Перезагрузить service с исправлением
docker-compose restart codelab-core-service

# Вариант 3: Очистить DLQ (если данные не восстанавливаемы)
redis-cli -h localhost -p 6379 DEL user_events_dlq

# Вариант 4: Разработать скрипт восстановления из DLQ
# (требует разработки)
```

### 4. Database не синхронизирует пользователей

**Симптомы:**
- Пользователь есть в Auth Service, но не в Core Service
- Ошибка: "User not found"
- synced_from_auth_at = NULL

**Диагностика:**

```bash
# 1. Проверить события создания пользователя
redis-cli -h localhost -p 6379 XREAD COUNT 10 STREAMS user_events 0 | grep "user.created"

# 2. Проверить наличие обработчика
docker-compose logs codelab-core-service | grep "handle_user_created"

# 3. Проверить логи Consumer
docker-compose logs codelab-core-service | grep -i "event.*processed\|handler"

# 4. Проверить ошибки БД
docker-compose logs codelab-core-service | grep -i "database\|constraint\|unique"
```

**Решение:**

```bash
# Вариант 1: Пересинхронизировать пользователя
psql -h localhost -U postgres -d codelab << EOF
INSERT INTO users (id, username, email, synced_from_auth_at, synced_version)
SELECT id, username, email, NOW(), '1.0'
FROM codelab_auth.users
WHERE id NOT IN (SELECT id FROM codelab_core.users);
EOF

# Вариант 2: Пересоздать поток событий
redis-cli -h localhost -p 6379 XGROUP SETID user_events core_service_consumer_group 0
docker-compose restart codelab-core-service

# Вариант 3: Перезагрузить consumer
docker-compose restart codelab-core-service
```

---

## Emergency Procedures

### 1. Отключение Event Consumer

Если нужно быстро остановить обработку событий:

```bash
# 1. Отключить consumer в конфигурации
# .env:
USE_EVENT_CONSUMER=false

# 2. Перезагрузить service
docker-compose restart codelab-core-service

# ⚠️ Примечание: события будут накапливаться в потоке
```

### 2. Graceful Fallback в JWT exp claim

Если Redis недоступен, но нужны операции:

```bash
# Middleware автоматически упадет на JWT exp claim
# - Проверит, не истек ли токен
# - Не будет проверять blacklist

# Восстановить Redis
docker-compose restart redis

# Перезагрузить service
docker-compose restart codelab-core-service
```

### 3. Восстановление после сбоя

```bash
# 1. Проверить здоровье системы
docker-compose ps
redis-cli PING
psql -c "SELECT 1"

# 2. Очистить состояние consumer
redis-cli XGROUP DESTROY user_events core_service_consumer_group

# 3. Перезагрузить все service
docker-compose restart

# 4. Проверить синхронизацию
psql -c "SELECT COUNT(*) FROM users WHERE synced_from_auth_at IS NOT NULL;"
```

---

## Maintenance Tasks

### 1. Ежедневные проверки

```bash
#!/bin/bash

# Проверка consumer lag
CONSUMER_LAG=$(redis-cli XINFO GROUPS user_events | grep "lag" | awk '{print $NF}')
if [ $CONSUMER_LAG -gt 100 ]; then
  echo "WARNING: Consumer lag is $CONSUMER_LAG"
fi

# Проверка DLQ
DLQ_SIZE=$(redis-cli XLEN user_events_dlq)
if [ $DLQ_SIZE -gt 0 ]; then
  echo "WARNING: DLQ has $DLQ_SIZE messages"
fi

# Проверка Redis memory
USED_MEMORY=$(redis-cli INFO memory | grep used_memory_human)
echo "Redis memory: $USED_MEMORY"
```

### 2. Еженедельные задачи

```bash
# Резервная копия БД
pg_dump codelab | gzip > backup_$(date +%Y%m%d).sql.gz

# Анализ размера потока
STREAM_SIZE=$(redis-cli XLEN user_events)
echo "Stream size: $STREAM_SIZE"

# Проверка метрик производительности
curl -s http://localhost:8000/metrics | grep "core_event_processing_duration"
```

### 3. Ежемесячное обслуживание

```bash
# Архивирование старых сообщений (опционально)
# Требует разработки скрипта

# Оптимизация БД
psql -c "VACUUM ANALYZE;"

# Проверка индексов
psql -c "SELECT * FROM pg_stat_user_indexes;"

# Обновление конфигурации потребителя при необходимости
# EVENTS_BATCH_SIZE, EVENTS_MAX_RETRIES, etc.
```

---

## Полезные команды

```bash
# Диагностика
docker-compose logs -f codelab-core-service
redis-cli MONITOR
psql -c "SELECT * FROM users LIMIT 5;"

# Очистка (⚠️ осторожно!)
redis-cli FLUSHALL
docker-compose down -v

# Восстановление
docker-compose up -d
```
