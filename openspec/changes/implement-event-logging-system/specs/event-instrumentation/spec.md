# Specification: Event Instrumentation

## ADDED Requirements

### Requirement: Логирование в StreamManager при отправке событий
StreamManager.broadcast_event() ДОЛЖНА автоматически логировать каждое событие в EventLogger.

#### Scenario: Event логируется при broadcast
- **WHEN** код вызывает `await stream_manager.broadcast_event(session_id, event, user_id, project_id)`
- **THEN** событие отправляется клиентам AND вызывается `await event_logger.log_event(event, user_id, project_id)`

#### Scenario: Логирование не блокирует отправку
- **WHEN** EventLogger.log_event() добавляет событие в асинхронную очередь
- **THEN** broadcast_event() не ждет завершения логирования, отправка клиентам выполняется параллельно

#### Scenario: User isolation в StreamManager
- **WHEN** broadcast_event() вызывается с user_id и project_id
- **THEN** EventLogger проверяет, что user_id принадлежит проекту (через get_project_with_validation())

### Requirement: Логирование операций в UserWorkerSpace
UserWorkerSpace.handle_message() ДОЛЖНА логировать события взаимодействия с агентами при обработке сообщений.

#### Scenario: AGENT_SWITCHED событие при выборе агента в orchestrated mode
- **WHEN** orchestrator выбирает агента для обработки сообщения
- **THEN** система генерирует EVENT_LOGGED event с agent_id и отправляет его через stream_manager

#### Scenario: DIRECT_AGENT_CALL событие при direct execution
- **WHEN** пользователь отправляет сообщение с target_agent_id
- **THEN** система генерирует DIRECT_AGENT_CALL event с информацией о агенте

#### Scenario: Логирование параметров вызова агента
- **WHEN** агент вызывается с определенными параметрами
- **THEN** event payload содержит: agent_id, agent_name, mode (direct/orchestrated), input parameters

### Requirement: Логирование инструментов при выполнении
ToolExecutor ДОЛЖНА логировать все запросы и результаты выполнения инструментов.

#### Scenario: TOOL_REQUEST событие перед выполнением
- **WHEN** инструмент готовится к выполнению
- **THEN** система генерирует TOOL_REQUEST event с полями: tool_name, tool_type, input_params

#### Scenario: TOOL_EXECUTED событие после успешного выполнения
- **WHEN** инструмент успешно выполнилась
- **THEN** система генерирует event (типа TOOL_RESULT или внутри payload TOOL_REQUEST) с результатом выполнения

#### Scenario: ERROR событие при ошибке инструмента
- **WHEN** инструмент выбрасывает исключение при выполнении
- **THEN** система генерирует ERROR event с error_code, error_message, и stack trace в payload

#### Scenario: Risk assessment логирование
- **WHEN** RiskAssessor оценивает риск инструмента
- **THEN** event payload содержит: risk_level (high/medium/low), risk_factors, mitigation measures

### Requirement: Логирование одобрений в ApprovalManager
ApprovalManager ДОЛЖНА логировать все события, связанные с системой одобрений.

#### Scenario: APPROVAL_REQUIRED событие
- **WHEN** инструмент или действие требует одобрения
- **THEN** система генерирует APPROVAL_REQUIRED event с action_description, risk_assessment, и timeout info

#### Scenario: APPROVAL_RESOLVED событие при принятии
- **WHEN** пользователь одобряет действие
- **THEN** система генерирует APPROVAL_RESOLVED event с approved=true, reviewer_id, timestamp

#### Scenario: APPROVAL_TIMEOUT_WARNING событие перед истечением
- **WHEN** остается 30 секунд до истечения timeout одобрения
- **THEN** система генерирует APPROVAL_TIMEOUT_WARNING event

#### Scenario: APPROVAL_TIMEOUT событие при истечении
- **WHEN** одобрение истекает по времени без ответа
- **THEN** система генерирует APPROVAL_TIMEOUT event, действие отменяется

### Requirement: Логирование в OrchestratorRouter
OrchestratorRouter ДОЛЖНА логировать решения маршрутизации и переходы между агентами.

#### Scenario: AGENT_SWITCHED событие при смене агента
- **WHEN** orchestrator переключается на другого агента
- **THEN** система генерирует AGENT_SWITCHED event с from_agent_id, to_agent_id, и reason

#### Scenario: TASK_PLAN_CREATED событие при создании плана
- **WHEN** orchestrator создает план для сложной задачи
- **THEN** система генерирует TASK_PLAN_CREATED event с task_description, plan_steps

#### Scenario: TASK_STARTED событие
- **WHEN** orchestrator начинает выполнение задачи
- **THEN** система генерирует TASK_STARTED event с task_id, assigned_agent_id

#### Scenario: TASK_COMPLETED событие
- **WHEN** задача успешно завершена
- **THEN** система генерирует TASK_COMPLETED event с task_id, result, duration_ms

#### Scenario: CONTEXT_RETRIEVED событие
- **WHEN** AgentContextStore извлекает контекст для агента
- **THEN** система генерирует CONTEXT_RETRIEVED event с context_type, document_count, relevance_score

### Requirement: Логирование в AgentBus
AgentBus ДОЛЖНА логировать все операции очереди задач.

#### Scenario: Task submission логирование
- **WHEN** задача отправляется в очередь агента через submit_task()
- **THEN** система генерирует event с task_id, agent_id, queue_position

#### Scenario: Task execution логирование
- **WHEN** worker обрабатывает задачу из очереди
- **THEN** система генерирует event (может быть TOOL_REQUEST или custom TASK_EXECUTION)

### Requirement: Context для всех логируемых событий
Все генерируемые события ДОЛЖНЫ содержать достаточный контекст для анализа.

#### Scenario: Metadata fields в каждом event
- **WHEN** событие логируется
- **THEN** payload содержит: timestamp (ISO 8601), session_id, user_id, agent_id (если применимо), request_id (для трейсинга)

#### Scenario: Full context для error events
- **WHEN** событие типа ERROR генерируется
- **THEN** payload содержит: error_code, error_message, exception_type, stack_trace, context (что делалось когда произошла ошибка)

### Requirement: Performance impact контролируется
Логирование НЕ ДОЛЖНО значительно влиять на performance основной системы.

#### Scenario: Асинхронное логирование не блокирует requests
- **WHEN** EventLogger буферизирует события
- **THEN** каждый request обрабатывается без ожидания логирования (P99 latency не превышает 50ms)

#### Scenario: Batch insert не создает bottleneck
- **WHEN** высокий volume событий (1000+/sec)
- **THEN** batch insert достаточно оптимален, CPU и memory не деградируют

### Requirement: Тестирование инструментации
Все инструментированные компоненты ДОЛЖНЫ иметь тесты логирования.

#### Scenario: Unit тесты для StreamManager логирования
- **WHEN** StreamManager.broadcast_event() вызывается
- **THEN** тест с mocked EventLogger проверяет, что log_event() был вызван с правильными параметрами

#### Scenario: Integration тесты для полного flow
- **WHEN** пользователь отправляет сообщение и вызывает инструмент
- **THEN** тест проверяет, что в БД сохранились события MESSAGE_CREATED, TOOL_REQUEST, TOOL_RESULT (или ERROR)

#### Scenario: Load тесты для performance
- **WHEN** система получает 1000+ событий/sec
- **THEN** тест проверяет, что все события сохранились без потерь, no memory leaks
