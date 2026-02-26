# Specification: Event Logging Persistence

## ADDED Requirements

### Requirement: Транзакционное хранение событий через outbox
Система ДОЛЖНА сохранять intent событий в таблицу `event_outbox` в той же транзакции, что и доменные изменения чата (`messages`).

#### Scenario: Атомарный commit
- **WHEN** endpoint обработки сообщения успешно завершает транзакцию
- **THEN** в БД зафиксированы и `messages`, и соответствующие `event_outbox` записи

#### Scenario: Атомарный rollback
- **WHEN** endpoint обработки сообщения завершился ошибкой до commit
- **THEN** ни `messages`, ни `event_outbox` записи не сохраняются

### Requirement: Схема таблицы event_outbox
Система ДОЛЖНА иметь таблицу `event_outbox` с полями статуса публикации и retry-метаданными.

#### Scenario: Структура outbox записи
- **WHEN** создается outbox событие
- **THEN** запись содержит: `id`, `aggregate_type`, `aggregate_id`, `user_id`, `project_id`, `event_type`, `payload`, `status`, `retry_count`, `next_retry_at`, `created_at`, `published_at`, `last_error`

#### Scenario: Статусы публикации
- **WHEN** событие создано request-path
- **THEN** `status='pending'`
- **AND WHEN** событие успешно опубликовано
- **THEN** `status='published'` и `published_at` заполнен

### Requirement: Индексы для outbox processing и аналитики
Система ДОЛЖНА иметь индексы, оптимизированные для выборки pending событий и пользовательской фильтрации.

#### Scenario: Быстрая выборка pending событий
- **WHEN** publisher запрашивает pending записи
- **THEN** используется индекс по `(status, next_retry_at, created_at)`

#### Scenario: Быстрая фильтрация по aggregate/project/user
- **WHEN** выполняются запросы истории
- **THEN** используются индексы `(aggregate_id, created_at)`, `(project_id, created_at)`, `(user_id, created_at)`

### Requirement: EventLog как опциональный read-model
Система МОЖЕТ хранить опубликованные события в таблице `event_logs` для аналитики и аудита.

#### Scenario: Наполнение event_logs после publish
- **WHEN** publisher успешно отправил событие
- **THEN** событие может быть сохранено в `event_logs` как аналитическая проекция

#### Scenario: Источник истины
- **WHEN** возникает конфликт между `messages` и analytics read-model
- **THEN** source of truth для чата остается `messages`, а `event_logs` трактуется как проекция

### Requirement: Миграции схемы
Система ДОЛЖНА иметь Alembic миграции для создания `event_outbox` (и опционально `event_logs`) с обратимым downgrade.

#### Scenario: Upgrade
- **WHEN** выполняется `alembic upgrade head`
- **THEN** таблицы и индексы создаются корректно

#### Scenario: Downgrade
- **WHEN** выполняется `alembic downgrade -1`
- **THEN** новые таблицы и индексы удаляются без нарушения целостности существующих данных
