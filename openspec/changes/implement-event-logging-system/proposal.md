# Proposal: Implement Event Log + Outbox for Consistent Chat Events

## Why

Текущая модель realtime событий не гарантирует строгую консистентность чата. Если событие отправлено в streaming, но транзакция запроса откатилась (или наоборот), состояние UI и БД расходится.

Для режима с приоритетом на строгую консистентность требуется паттерн Outbox:

- изменения доменной модели (`messages`) и intent события фиксируются атомарно в одной транзакции;
- публикация в realtime выполняется асинхронно после commit;
- неуспешная публикация ретраится без потери данных.

## What Changes

- Добавляется таблица `event_outbox` как транзакционный буфер событий.
- В request-path (`project_chat`, `user_worker_space`) события записываются в outbox в той же транзакции, что и `messages`.
- Добавляется фоновый `OutboxPublisher`, публикующий pending события в streaming и помечающий их как `published`.
- Добавляется/уточняется `event_log` (опциональный read-model) для аналитики и аудита.
- Analytics API работает по консистентному источнику (`event_log` или `event_outbox` + materialization) и сохраняет user/project isolation.

## Capabilities

### New Capabilities

- `event-logging-persistence`: Транзакционное хранение event intent в `event_outbox` и долговременное хранение событий для аналитики.
- `event-logger-service`: Асинхронный publisher с retry/backoff и lifecycle management.
- `interaction-analytics-api`: API для чтения истории событий и агрегатов по проекту.
- `event-instrumentation`: Инструментация доменных операций через запись в outbox внутри той же транзакции.

### Modified Capabilities

- `sse-event-streaming`: Streaming становится downstream-каналом доставки подтвержденных (committed) событий, а не источником истины.

## Impact

**Затронутый код:**
- `app/models/` - новые модели `EventOutbox` (и `EventLog`/read-model)
- `app/core/` - `outbox_publisher.py`, repository слой, изменения stream_manager integration
- `app/routes/project_chat.py` и `app/core/user_worker_space.py` - запись событий через outbox в одной транзакции
- `migrations/` - схема outbox/event-log и индексы
- `tests/` - транзакционная консистентность, retry/idempotency, API

**API изменения:**
- Endpoints аналитики сохраняются и уточняются по источнику данных и SLA консистентности.

**Breaking changes:**
- Нет для пользовательских endpoint'ов.
- Внутренний контракт публикации событий меняется: прямой publish из request-path считается недопустимым.
