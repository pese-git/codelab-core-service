# Specification: Event Instrumentation

## ADDED Requirements

### Requirement: Инструментация через транзакционную запись в outbox
Доменные компоненты ДОЛЖНЫ записывать события в `event_outbox` в рамках текущей транзакции, а не публиковать их напрямую в streaming из request-path.

#### Scenario: Сообщение пользователя
- **WHEN** `send_project_message` создает `Message(role='user')`
- **THEN** система создает outbox событие `message_created` в той же транзакции

#### Scenario: Переключение агента
- **WHEN** orchestrated execution выбирает агента
- **THEN** система создает outbox событие `agent_switched` в той же транзакции запроса

#### Scenario: Ответ ассистента
- **WHEN** `Message(role='assistant')` сохраняется
- **THEN** outbox событие `message_created` для ответа ассистента сохраняется в той же транзакции

### Requirement: Отделение domain write от transport delivery
`StreamManager.broadcast_event()` НЕ ДОЛЖЕН быть обязательной частью request-path для доменных chat-событий.

#### Scenario: Ошибка streaming канала
- **WHEN** StreamManager недоступен во время запроса
- **THEN** транзакционная запись `messages + outbox` остается возможной
- **AND** публикация выполняется позже publisher'ом

### Requirement: Контекст и трассируемость события
Каждое outbox-событие ДОЛЖНО содержать минимальный контекст для анализа и доставки.

#### Scenario: Mandatory metadata
- **WHEN** создается outbox запись
- **THEN** payload содержит как минимум: `event_id`, `session_id`, `project_id`, `user_id`, `timestamp`

#### Scenario: Agent metadata
- **WHEN** событие связано с агентом
- **THEN** payload содержит `agent_id` и `agent_name` (если доступно)

### Requirement: Инструментация tool/approval/orchestrator
События инструментов, approval и orchestration ДОЛЖНЫ публиковаться через outbox-поток.

#### Scenario: Tool execution events
- **WHEN** выполняется tool workflow
- **THEN** события `tool_request`, `tool_result`/`error` фиксируются в outbox и публикуются publisher'ом

#### Scenario: Approval events
- **WHEN** approval запрошен/подтвержден/истек
- **THEN** соответствующие события фиксируются в outbox и публикуются publisher'ом

### Requirement: Производительность request-path
Инструментация НЕ ДОЛЖНА существенно увеличивать latency запроса.

#### Scenario: P99 latency guardrail
- **WHEN** включена outbox-инструментация
- **THEN** P99 request latency не деградирует из-за сетевой доставки событий, так как transport выполняется асинхронно
