# Design: Event Log + Outbox Architecture

## Context

Система уже использует PostgreSQL как source of truth для чата (`messages`) и streaming канал для realtime UI. Для строгой консистентности нельзя смешивать domain-write и network side effects в одном request-path.

## Goals / Non-Goals

**Goals:**
- Атомарная запись `messages` и событийного intent в рамках одной транзакции.
- Надежная публикация событий в streaming после commit.
- Retry/backoff без потери событий.
- User/project isolation для всех операций чтения и публикации.

**Non-Goals:**
- Exactly-once доставка на транспортном уровне.
- Замена streaming протокола.
- Event sourcing как полная замена доменных таблиц.

## Decisions

### 1. Транзакционная запись через `event_outbox`

Все доменные операции, влияющие на чат, записывают outbox-события в той же DB транзакции, что и `messages`.

**Контракт:**
1. Begin transaction.
2. Write `messages`.
3. Write `event_outbox` rows.
4. Commit.

Если commit не произошел, ни `messages`, ни события не считаются существующими.

### 2. Publisher как отдельный фоновый компонент

`OutboxPublisher` периодически выбирает события `pending`:

```sql
SELECT * FROM event_outbox
WHERE status = 'pending' AND (next_retry_at IS NULL OR next_retry_at <= now())
ORDER BY created_at ASC
FOR UPDATE SKIP LOCKED
LIMIT :batch_size;
```

После publish:
- success -> `status=published`, `published_at=now()`
- fail -> `retry_count += 1`, `next_retry_at` по backoff, `last_error` обновляется

### 3. Streaming не источник истины

`StreamManager` доставляет только уже зафиксированные события. Прямой publish из request-path не используется для доменных событий чата.

### 4. Идемпотентность и дедупликация

- `event_outbox.id` используется как `event_id`.
- `event_id` включается в payload при публикации.
- Клиент/consumer может дедуплицировать события по `event_id`.

### 5. Analytics read-model

`event_log` может использоваться как отдельная аналитическая таблица. Наполнение:
- либо в publisher после успешной публикации,
- либо materialization job из outbox.

Для API аналитики допустимы оба варианта, но контракт на консистентность должен быть документирован.

## Data Model

### `event_outbox`

- `id UUID PK`
- `aggregate_type VARCHAR(50)`
- `aggregate_id UUID`
- `user_id UUID NOT NULL`
- `project_id UUID NOT NULL`
- `event_type VARCHAR(100) NOT NULL`
- `payload JSONB NOT NULL`
- `status VARCHAR(20) NOT NULL` (`pending|published|failed`)
- `retry_count INT NOT NULL DEFAULT 0`
- `next_retry_at TIMESTAMPTZ NULL`
- `created_at TIMESTAMPTZ NOT NULL`
- `published_at TIMESTAMPTZ NULL`
- `last_error TEXT NULL`

Индексы:
- `(status, next_retry_at, created_at)`
- `(aggregate_id, created_at)`
- `(project_id, created_at)`
- `(user_id, created_at)`

### `event_log` (optional)

Содержит опубликованные события для аудита и аналитики.

## Failure Handling

1. Ошибка в request-path до commit -> rollback всего (messages + outbox).
2. Ошибка publisher -> запись остается в outbox и ретраится.
3. Превышение retry limit -> `failed`; операторский reprocess path.

## Observability

Метрики:
- `outbox_pending_count`
- `outbox_oldest_pending_age_seconds`
- `outbox_publish_success_total`
- `outbox_publish_failed_total`
- `outbox_publish_latency_ms`

Логи:
- `outbox_enqueued`
- `outbox_publish_succeeded`
- `outbox_publish_failed`
- `outbox_dead_lettered`

## Migration Plan

1. Ввести `event_outbox` и запись outbox в request-path.
2. Запустить publisher в shadow mode (без отключения старого publish).
3. Переключить streaming на publisher-only для доменных событий.
4. Удалить прямую публикацию доменных chat-event из request-path.
5. Включить/добавить `event_log` для аналитики при необходимости.
