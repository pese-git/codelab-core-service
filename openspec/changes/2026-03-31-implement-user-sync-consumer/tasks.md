# Tasks: Event-Driven синхронизация и Token Blacklist (Core Service)

**Версия:** 1.0.0  
**Дата:** 31 марта 2026  
**Приоритет:** High

---

## 📋 Список задач по приоритетам

### 🔴 Phase 1: Foundation (Must Have)

#### Task 1.1: Создать EventConsumer для Redis Streams
- **Описание:** Реализовать consumer для прослушивания и обработки событий
- **Файлы:**
  - `app/services/event_consumer.py` — основной класс
  - `tests/test_event_consumer.py` — unit тесты
- **Зависимости:** Redis client (уже есть)
- **Критерии приёмки:**
  - ✅ `initialize()` создает consumer group
  - ✅ `start()` запускает consumer loop
  - ✅ `register_handler()` регистрирует обработчики
  - ✅ Events читаются из stream (XREADGROUP)
  - ✅ Успешные события ACKnowledged (XACK)
  - ✅ Failed события в DLQ после max retries
  - ✅ Pending messages обрабатываются (XAUTOCLAIM)
  - ✅ Unit тесты: 100% coverage
- **Ответственный:** Backend Dev

#### Task 1.2: Реализовать User Event Handlers
- **Описание:** Обработчики для всех типов user-событий
- **Файлы:**
  - `app/services/user_event_handlers.py`
  - `tests/test_user_event_handlers.py`
- **Зависимости:** Task 1.1, Database session
- **Обработчики:**
  - `handle_user_created()` — создать profile
  - `handle_user_updated()` — обновить profile
  - `handle_user_deleted()` — CASCADE delete
  - `handle_token_revoked()` — logging only
- **Критерии приёмки:**
  - ✅ Все обработчики idempotent
  - ✅ handle_user_deleted() удаляет все связанные данные
  - ✅ Транзакции (ACID) для каждого handler
  - ✅ Логирование каждого события
  - ✅ Unit тесты: 100% coverage
  - ✅ Integration тесты: E2E обработка
- **Ответственный:** Backend Dev

#### Task 1.3: Обновить UserIsolationMiddleware (Token Blacklist)
- **Описание:** Добавить проверку blacklist перед обработкой запроса
- **Файлы:**
  - `app/middleware/user_isolation.py` — обновить dispatch()
  - `tests/test_middleware_blacklist.py` — новые тесты
- **Зависимости:** Task 1.1, TokenBlacklistService (из auth)
- **Критерии приёмки:**
  - ✅ Извлечь JTI из JWT payload
  - ✅ Проверить if token in blacklist (Redis)
  - ✅ Return 401 если revoked
  - ✅ Continue if not revoked
  - ✅ Graceful fallback if Redis down (use exp only)
  - ✅ Logging: revoked token attempts
  - ✅ Unit тесты: all scenarios
- **Ответственный:** Backend Dev

#### Task 1.4: Database Schema Migration
- **Описание:** Alembic миграция для новых полей и индексов
- **Файлы:**
  - `migrations/versions/2026_03_31_add_user_sync_fields.py`
- **Зависимости:** Task 1.2
- **Критерии приёмки:**
  - ✅ Добавить synced_from_auth_at, synced_version колонки
  - ✅ Создать индекс на этих колонках
  - ✅ Downgrade работает корректно
  - ✅ Тестирование на clean DB
- **Ответственный:** Backend Dev / DevOps

---

### 🟡 Phase 2: Integration & Testing

#### Task 2.1: Написать Unit Tests для EventConsumer
- **Описание:** Полное покрытие consumer логики
- **Тесты должны покрывать:**
  - ✅ XREADGROUP читает новые события
  - ✅ XAUTOCLAIM обрабатывает pending
  - ✅ XACK успешных сообщений
  - ✅ Retry logic при ошибке
  - ✅ DLQ при max retries
  - ✅ Consumer group initialization
  - ✅ Stop gracefully
- **Критерии приёмки:**
  - ✅ Coverage >= 95%
  - ✅ Все тесты проходят
- **Ответственный:** QA / Backend Dev

#### Task 2.2: Написать Unit Tests для Event Handlers
- **Описание:** Тесты для каждого обработчика
- **Тесты должны покрывать:**
  - ✅ handle_user_created() создает profile
  - ✅ handle_user_updated() обновляет данные
  - ✅ handle_user_deleted() каскадно удаляет
  - ✅ Idempotency (повторные вызовы OK)
  - ✅ Error scenarios (DB error, constraints)
- **Критерии приёмки:**
  - ✅ Coverage >= 95%
- **Ответственный:** QA

#### Task 2.3: E2E Test Full Event Flow
- **Описание:** Полный сценарий от auth-service до core-service
- **Сценарий:**
  1. Auth: создать пользователя → event опубликован
  2. Auth: обновить пользователя → event опубликован
  3. Auth: удалить пользователя → event опубликован
  4. Core: Consumer получает события
  5. Core: Handlers обрабатывают события
  6. Core: БД синхронизирована
  7. Core: Token blacklist работает
- **Критерии приёмки:**
  - ✅ Все события обработаны
  - ✅ Cascade delete работает
  - ✅ Token revocation блокирует access
- **Ответственный:** QA

#### Task 2.4: Обновить Configuration & ENV
- **Описание:** Добавить новые env vars для consumer
- **Файлы:**
  - `.env.example` — новые vars
  - `app/config.py` — конфигурация
  - `docker-compose.yml` — if needed
- **Критерии приёмки:**
  - ✅ Все vars определены
  - ✅ Defaults reasonable
  - ✅ Consumer может запуститься
- **Ответственный:** DevOps

---

### 🟢 Phase 3: Optimization & Documentation

#### Task 3.1: Добавить Monitoring & Logging
- **Описание:** Метрики для consumer и handlers
- **Метрики:**
  - `events_consumed_total` — счетчик обработанных событий
  - `event_processing_duration_seconds` — latency
  - `events_failed_total` — счетчик failures
  - `dlq_size` — размер DLQ
  - `blacklist_check_duration_seconds` — middleware latency
- **Файлы:**
  - `app/metrics/consumer_metrics.py`
  - `app/metrics/middleware_metrics.py`
- **Критерии приёмки:**
  - ✅ Metrics expose на /metrics
  - ✅ Alerts на DLQ growth
  - ✅ Consumer lag monitoring
- **Ответственный:** DevOps

#### Task 3.2: Написать API Documentation
- **Описание:** OpenAPI docs для middleware changes
- **Файлы:**
  - `docs/api/token-blacklist-check.md`
  - `docs/api/event-consumer.md`
  - `docs/api/user-sync-handlers.md`
- **Содержание:**
  - Flow diagrams
  - Error codes
  - Performance notes
- **Критерии приёмки:**
  - ✅ Документация полная
  - ✅ Примеры актуальны
- **Ответственный:** Tech Writer

#### Task 3.3: Написать Operational Runbook
- **Описание:** Гайд для операций
- **Файлы:**
  - `docs/operational/event-consumer-runbook.md`
  - `docs/operational/token-blacklist-runbook.md`
- **Содержание:**
  - Health checks
  - Troubleshooting
  - DLQ inspection
  - Metrics to monitor
- **Критерии приёмки:**
  - ✅ Полная документация
  - ✅ Команды протестированы
- **Ответственный:** DevOps

#### Task 3.4: Graceful Degradation & Resilience
- **Описание:** Fallback поведение при failure
- **Сценарии:**
  - Redis недоступен → middleware rely on exp
  - Event consumer crashed → alerts
  - DLQ растет → alerts + investigation
  - Cascade delete ошибка → rollback
- **Критерии приёмки:**
  - ✅ При Redis down: graceful fallback
  - ✅ При consumer crash: auto-restart
  - ✅ Alerts отправляются
- **Ответственный:** Backend Dev / DevOps

---

## 📊 Dependencies Graph

```
Task 1.1: EventConsumer
    ├─→ Task 1.2: Event Handlers
    │   └─→ Task 1.4: Database Migration
    │
    ├─→ Task 1.3: Middleware Update
    │   └─→ Task 2.1: Unit Tests
    │
    └─→ Task 2.3: E2E Tests
        ├─→ Task 2.4: Configuration
        │
        └─→ Phase 3: Monitoring, Docs, Runbooks
```

---

## ⏱️ Estimation

| Task | Complexity | Effort | Dependencies |
|------|-----------|--------|--------------|
| 1.1 | Medium | Medium | Redis |
| 1.2 | High | Large | Database, 1.1 |
| 1.3 | Medium | Medium | 1.1, Middleware |
| 1.4 | Low | Small | 1.2 |
| 2.1 | Low | Small | 1.1 |
| 2.2 | Medium | Medium | 1.2 |
| 2.3 | High | Large | 1.1, 1.2, 1.3 |
| 2.4 | Low | Small | 1.1, 1.2, 1.3 |
| 3.1 | Medium | Medium | 1.1, 1.2, 1.3 |
| 3.2 | Low | Small | All Phase 1,2 |
| 3.3 | Low | Small | All Phase 1,2 |
| 3.4 | Medium | Medium | 1.1, 1.2, 1.3 |

---

## 🎯 Success Criteria (все Phase)

- ✅ EventConsumer запущен и работает
- ✅ Все handlers реализованы и idempotent
- ✅ Token blacklist интегрирована в middleware
- ✅ Unit tests: 95%+ coverage
- ✅ Integration tests: all scenarios pass
- ✅ E2E tests: full flow работает
- ✅ Documentation: complete
- ✅ No production incidents
- ✅ Metrics monitoring: working
- ✅ Performance: event processing < 500ms p95
- ✅ Reliability: event delivery > 99.9%
