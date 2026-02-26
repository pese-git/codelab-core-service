# Specification: Event Logger Service

## ADDED Requirements

### Requirement: OutboxPublisher как асинхронный сервис
Система ДОЛЖНА предоставлять сервис `OutboxPublisher`, который асинхронно публикует pending события из `event_outbox` в streaming канал.

#### Scenario: Фоновая публикация
- **WHEN** сервис запущен
- **THEN** он периодически выбирает pending события батчами и пытается опубликовать их

#### Scenario: Неблокирующий request-path
- **WHEN** API обрабатывает запрос сообщения
- **THEN** запрос не ждет публикации в streaming; публикация выполняется в фоне через publisher

### Requirement: Конкурентно-безопасный батч процессинг
Publisher ДОЛЖЕН использовать блокировки, безопасные для нескольких воркеров.

#### Scenario: SKIP LOCKED
- **WHEN** несколько экземпляров publisher работают параллельно
- **THEN** выборка pending событий использует `FOR UPDATE SKIP LOCKED` и не обрабатывает одну запись дважды одновременно

### Requirement: Retry/backoff и отказоустойчивость
Publisher ДОЛЖЕН ретраить неуспешные публикации и не терять события.

#### Scenario: Ошибка публикации
- **WHEN** отправка события в StreamManager завершилась ошибкой
- **THEN** `retry_count` увеличивается, `next_retry_at` выставляется с backoff, `last_error` сохраняется

#### Scenario: Превышение лимита ретраев
- **WHEN** число попыток превышает configured max retries
- **THEN** запись переводится в `failed` статус и доступна для ручного reprocess

### Requirement: Lifecycle в app/main.py
Publisher ДОЛЖЕН управляться через lifecycle приложения.

#### Scenario: Startup
- **WHEN** приложение стартует
- **THEN** `OutboxPublisher.start()` вызывается и worker loop запускается

#### Scenario: Shutdown
- **WHEN** приложение останавливается
- **THEN** `OutboxPublisher.stop()` завершает worker корректно без повреждения состояния outbox

### Requirement: Идемпотентный контракт публикации
Публикуемое событие ДОЛЖНО содержать `event_id`, равный `event_outbox.id`.

#### Scenario: Event ID в payload
- **WHEN** publisher отправляет событие
- **THEN** payload содержит `event_id`, пригодный для дедупликации на клиенте/consumer

### Requirement: Метрики и наблюдаемость
Publisher ДОЛЖЕН публиковать операционные метрики.

#### Scenario: Метрики очереди
- **WHEN** мониторинг запрашивает состояние publisher
- **THEN** доступны метрики pending count, oldest pending age, success/failure counters, publish latency
