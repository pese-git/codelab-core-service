# agent-workflow-tracing Specification

## Назначение

Поддержка создания и управления traces для отслеживания multi-step агентных workflow'ов с автоматической группировкой в sessions.

## ADDED Requirements

### Requirement: Создание и управление traces для агентных workflow'ов

Система ДОЛЖНА поддерживать явное создание traces для отслеживания multi-step агентных операций.

#### Scenario: Создание root trace для агента
- **WHEN** агент начинает обработку сообщения пользователя
- **THEN** система создает trace с name=f"agent_{agent_name}", user_id, session_id=f"workspace_{workspace_id}", metadata={agent, model, ...}

#### Scenario: Создание spans для шагов агента
- **WHEN** агент выполняет шаги: prepare_context → generate_response → save_interaction
- **THEN** для каждого шага создается span с input, output, metadata и end_time

#### Scenario: Группировка traces в sessions
- **WHEN** пользователь проводит разговор с агентом
- **THEN** все traces для этого workspace группируются в session_id=f"workspace_{workspace_id}"

### Requirement: Интеграция с agent service

Agent service ДОЛЖЕН использовать LangfuseIntegration для трейсинга workflows.

#### Scenario: Трейсинг процесса обработки сообщения
- **WHEN** agent.process_message() вызывается
- **THEN** создается root trace с agent_name, user_id, workspace_id
- **AND** создается span для prepare_context
- **AND** создается span для generate_response (LiteLLM auto-captures через callback)
- **AND** создается span для save_interaction
- **AND** trace завершается с успехом

#### Scenario: Обработка ошибок в трейсе
- **WHEN** во время process_message() возникает исключение
- **THEN** trace обновляется с metadata={error: str(e)}, level="ERROR"
- **AND** исключение пробрасывается дальше

### Requirement: Span создание с метаданными

Spans ДОЛЖНЫ содержать полную информацию о шагах агента.

#### Scenario: Span с input/output данными
- **WHEN** создается span для шага агента
- **THEN** span содержит: input (исходные данные), output (результат шага), duration, status
- **AND** metadata включает: step_name, step_index, dependencies

#### Scenario: Вложенные spans
- **WHEN** агент вызывает другие агенты или сервисы
- **THEN** spans создаются вложенными с корректной parent_span_id и индексацией

### Requirement: Context propagation для traces

Контекст трейсинга ДОЛЖЕН пропагироваться через асинхронные операции.

#### Scenario: Propagation через async operations
- **WHEN** агент запускает асинхронные операции (например, parallel tool execution)
- **THEN** trace_id и span_id пропагируются через контекст (contextvars)
- **AND** все child spans содержат корректный parent_span_id
