# Implementation Tasks: Event Log + Outbox

## 1. Database Schema

- [x] 1.1 Добавить модель `EventOutbox` в `app/models/event_outbox.py`
- [x] 1.2 Добавить экспорт модели в `app/models/__init__.py`
- [x] 1.3 Создать Alembic миграцию для `event_outbox` + индексы (`status,next_retry_at,created_at`, `aggregate_id,created_at`, `project_id,created_at`, `user_id,created_at`)
- [x] 1.4 (Опционально) добавить `event_logs` как read-model для аналитики (не требуется на текущем этапе)
- [x] 1.5 Написать unit тесты для моделей и ограничений

## 2. Outbox Write Path (Strict Consistency)

- [x] 2.1 Добавить repository/service для записи outbox-событий в текущую `AsyncSession`
- [x] 2.2 Интегрировать запись `message_created` в `app/routes/project_chat.py` в той же транзакции, что `Message`
- [ ] 2.3 Интегрировать запись `agent_switched` в `app/core/user_worker_space.py` в той же транзакции
- [ ] 2.4 Запретить отдельные DB-сессии для сохранения chat-domain событий в request-path
- [x] 2.5 Добавить тесты на atomic commit/rollback (`messages` + `event_outbox`)

## 3. Outbox Publisher Service

- [x] 3.1 Создать `app/core/outbox_publisher.py`
- [x] 3.2 Реализовать выборку pending батчей через `FOR UPDATE SKIP LOCKED`
- [x] 3.3 Реализовать publish в StreamManager и update статусов (`published|failed|pending+retry`)
- [x] 3.4 Реализовать retry/backoff и `max_retries`
- [x] 3.5 Добавить lifecycle управление в `app/main.py` (startup/shutdown)
- [x] 3.6 Написать unit/integration тесты publisher

## 4. Streaming Integration

- [ ] 4.1 Перевести доменные chat-события на публикацию только через `OutboxPublisher`
- [ ] 4.2 Удалить/отключить прямой publish доменных событий из request-path
- [ ] 4.3 Сохранить heartbeat/технические transport события в StreamManager без outbox (если требуется)
- [ ] 4.4 Добавить тесты, что streaming отражает только committed события

## 5. Analytics API and Read Model

- [ ] 5.1 Реализовать `GET /my/projects/{project_id}/events`
- [ ] 5.2 Реализовать `GET /my/projects/{project_id}/analytics/sessions/{session_id}/events`
- [ ] 5.3 Реализовать `GET /my/projects/{project_id}/analytics`
- [ ] 5.4 Обеспечить user/project isolation и валидные pagination limits
- [ ] 5.5 Зафиксировать источник данных analytics (`event_logs` или materialized outbox view)
- [ ] 5.6 Добавить тесты на фильтрацию, изоляцию и корректность агрегатов

## 6. Idempotency and Reliability

- [ ] 6.1 Использовать `event_outbox.id` как `event_id` в публикуемом payload
- [ ] 6.2 Добавить дедупликацию на клиентском контракте/consumer документации
- [ ] 6.3 Добавить reprocess path для `failed` событий
- [ ] 6.4 Добавить тесты на duplicate-safe retries

## 7. Observability

- [ ] 7.1 Добавить метрики: pending count, oldest pending age, publish success/failure, latency
- [ ] 7.2 Добавить структурированные логи outbox lifecycle
- [ ] 7.3 Настроить алерты на рост pending lag и ошибочные публикации

## 8. Documentation

- [ ] 8.1 Обновить архитектурную документацию и API docs по outbox контракту
- [ ] 8.2 Описать SLA eventual visibility для analytics
- [ ] 8.3 Обновить changelog и migration notes

## Dependencies

1. `1.*` -> `2.*` -> `3.*` -> `4.*`
2. `3.*` и `4.*` -> `5.*`
3. `3.*` -> `6.*` и `7.*`
4. Финализация: `8.*`

## Priorities

**Critical:** 1, 2, 3, 4
**High:** 5, 6
**Medium:** 7, 8
