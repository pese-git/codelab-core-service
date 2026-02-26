# Specification: Interaction Analytics API

## ADDED Requirements

### Requirement: Endpoint истории событий проекта
Система ДОЛЖНА предоставлять endpoint `GET /my/projects/{project_id}/events` для получения истории событий с фильтрацией и пагинацией.

#### Scenario: Базовый список
- **WHEN** клиент вызывает `GET /my/projects/{project_id}/events`
- **THEN** система возвращает события проекта, сортированные по `created_at DESC`, с `limit/offset`

#### Scenario: Фильтры
- **WHEN** переданы `event_type`, `agent_id`, `start_time`, `end_time`
- **THEN** применяется AND-фильтрация по всем заданным критериям

### Requirement: Endpoint событий сессии для аналитики
Система ДОЛЖНА предоставлять endpoint `GET /my/projects/{project_id}/analytics/sessions/{session_id}/events`.

#### Scenario: Полная история сессии
- **WHEN** клиент вызывает endpoint сессии
- **THEN** возвращаются все связанные события сессии в порядке `created_at ASC`

### Requirement: Endpoint агрегированной аналитики
Система ДОЛЖНА предоставлять endpoint `GET /my/projects/{project_id}/analytics`.

#### Scenario: Сводная аналитика
- **WHEN** клиент запрашивает аналитику
- **THEN** response содержит как минимум `event_type_counts`, `agent_interactions`, `error_stats`

### Requirement: User/project isolation
Все analytics endpoint'ы ДОЛЖНЫ учитывать изоляцию пользователя и проекта.

#### Scenario: Нет доступа к чужому проекту
- **WHEN** пользователь запрашивает чужой проект
- **THEN** система возвращает `404 NOT FOUND`

#### Scenario: Только свои события
- **WHEN** пользователь получает события проекта
- **THEN** в выборке присутствуют только события с `user_id == current_user_id`

### Requirement: Источник данных аналитики согласован с outbox архитектурой
Analytics API ДОЛЖЕН читать из консистентного read-model (`event_logs` либо materialized view из outbox).

#### Scenario: Consistent read contract
- **WHEN** доменное изменение закоммичено
- **THEN** связанное событие доступно в analytics source после обработки publisher/materialization

#### Scenario: Eventual visibility SLA
- **WHEN** событие только что создано в outbox
- **THEN** API может вернуть его с задержкой в пределах документированного SLA materialization (например, до N секунд)

### Requirement: Response schema
События в API ДОЛЖНЫ возвращаться в унифицированном формате.

#### Scenario: Поля события
- **WHEN** клиент получает элемент события
- **THEN** он содержит поля: `id`, `event_type`, `payload`, `session_id`, `agent_id` (nullable), `project_id`, `created_at`

#### Scenario: Pagination metadata
- **WHEN** используется пагинация
- **THEN** response содержит `events`, `total`, `limit`, `offset`

### Requirement: Разделение chat history и analytics events
Endpoint чата (`/chat/{session_id}/messages/`) и analytics endpoints возвращают разные модели данных.

#### Scenario: Chat history
- **WHEN** клиент вызывает `GET /my/projects/{project_id}/chat/sessions/{session_id}/messages/`
- **THEN** возвращаются только user-facing `Message` записи

#### Scenario: Analytics history
- **WHEN** клиент вызывает `/events` или `/analytics/sessions/{session_id}/events`
- **THEN** возвращаются системные и технические события из event read-model
