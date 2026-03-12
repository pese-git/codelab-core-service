# Specification: Tool Execution Capture

## Обзор

Система автоматического захватывания tool execution events в Langfuse с полным контекстом параметров, результатов, ошибок и временных метрик для построения полной trace цепочки: LLM Call → Tool Execution → Tool Result.

---

## ADDED Requirements

### Requirement: Создание span для tool execution через LangfuseIntegration

LangfuseIntegration ДОЛЖЕН предоставлять методы для создания и завершения spans для tool execution с поддержкой nested spans.

#### Scenario: Создание root tool execution span
- **WHEN** ToolExecutor вызывает `create_tool_execution_span(tool_name="search_docs", input_params={...})`
- **THEN** LangfuseIntegration создает span с именем `tool_search_docs`
- **AND** span содержит атрибуты: `tool_name`, `input_params`, `user_id`, `workspace_id`
- **AND** возвращается объект ToolExecutionSpan для последующего завершения

#### Scenario: Создание nested tool execution span
- **WHEN** LLM call span существует в context и вызывается `create_tool_execution_span(..., parent_span_id=llm_span_id)`
- **THEN** создаемый span имеет parent = llm_span_id
- **AND** в Langfuse UI видна иерархия: llm_call → tool_execution

#### Scenario: Graceful degradation при отсутствии Langfuse
- **WHEN** Langfuse отключен (`LANGFUSE_ENABLED=false`)
- **THEN** `create_tool_execution_span()` возвращает None
- **AND** ToolExecutor продолжает работу без изменений
- **AND** ошибок tracing не логируются

#### Scenario: Graceful degradation при ошибке создания span
- **WHEN** Langfuse недоступен или возвращает ошибку
- **THEN** `create_tool_execution_span()` логирует ошибку на уровне ERROR
- **AND** возвращает None (не выбрасывает exception)
- **AND** ToolExecutor продолжает работу

### Requirement: Завершение tool execution span с результатом или ошибкой

LangfuseIntegration ДОЛЖЕН предоставлять метод для завершения tool execution span с передачей результата или информации об ошибке.

#### Scenario: Успешное завершение span
- **WHEN** `end_tool_execution_span(span_obj, result={"success": True, "data": {...}})`
- **THEN** span завершается с output содержащим результат
- **AND** span.status = "success"
- **AND** span отправляется в Langfuse асинхронно

#### Scenario: Завершение span с ошибкой
- **WHEN** `end_tool_execution_span(span_obj, error=ValidationError("Invalid params"))`
- **THEN** span завершается с output содержащим:
  ```json
  {
    "error": {
      "type": "ValidationError",
      "message": "Invalid params"
    },
    "success": false
  }
  ```
- **AND** span.status = "error"

#### Scenario: Асинхронная отправка span
- **WHEN** span завершается
- **THEN** отправка в Langfuse происходит асинхронно (fire-and-forget)
- **AND** таймаут отправки = 5 секунд (не блокирует tool execution)
- **AND** если таймаут - span не отправляется, но логируется warning

#### Scenario: Обработка ошибок при завершении span
- **WHEN** происходит исключение при отправке span в Langfuse
- **THEN** ошибка логируется но не propagate
- **AND** метрика `langfuse.send_errors` инкрементируется
- **AND** tool execution результат НЕ изменяется

### Requirement: Интеграция tracing в ToolExecutor.execute_tool()

ToolExecutor ДОЛЖЕН создавать и завершать spans для каждого этапа tool execution: валидация, risk assessment, одобрение, выполнение.

#### Scenario: Трейсинг валидации tool параметров
- **WHEN** ToolExecutor вызывает `execute_tool(tool_name="api_call", params={...})`
- **THEN** создается nested span с именем `tool_api_call_validation`
- **AND** span содержит input: параметры для валидации
- **AND** при успехе span завершается с `result={"valid": True}`
- **AND** при ошибке валидации span завершается с ошибкой но tool execution продолжается

#### Scenario: Трейсинг risk assessment
- **WHEN** ToolExecutor вызывает `risk_assessor.assess_tool_risk()`
- **THEN** создается nested span с именем `tool_api_call_risk_assessment`
- **AND** span содержит output: `{"risk_level": "HIGH", "risk_score": 0.85}`
- **AND** span завершается асинхронно

#### Scenario: Трейсинг approval workflow
- **WHEN** risk_level = HIGH или MEDIUM и требуется одобрение
- **THEN** создается nested span с именем `tool_api_call_approval`
- **AND** span содержит: `approval_id`, `status` (approved/rejected), `timeout_seconds`
- **AND** если одобрение отклонено - span завершается с error, tool execution прерывается

#### Scenario: Трейсинг выполнения инструмента
- **WHEN** ToolExecutor отправляет запрос на выполнение tool
- **THEN** создается nested span с именем `tool_api_call_execution`
- **AND** span содержит input: параметры отправленные на клиент
- **AND** span содержит output: результат выполнения tool
- **AND** span завершается с success или error в зависимости от результата

#### Scenario: Иерархия nested spans
- **WHEN** выполняется tool с валидацией, risk assessment и выполнением
- **THEN** в Langfuse видна иерархия:
  ```
  tool_execution (root)
  ├── tool_validation
  ├── tool_risk_assessment
  ├── tool_approval (опционально)
  └── tool_execution_run
  ```

### Requirement: Context propagation в tool execution spans

Tool execution spans ДОЛЖНЫ содержать полный контекст пользователя, workspace, агента для корректной аналитики и изоляции данных.

#### Scenario: Извлечение user_id и workspace_id из context
- **WHEN** ToolExecutor создает tool execution span
- **THEN** система извлекает user_id и workspace_id из structlog context
- **AND** эти значения добавляются в span metadata
- **AND** при отсутствии context span создается без них (graceful)

#### Scenario: Добавление agent metadata
- **WHEN** tool выполняется в контексте агента
- **THEN** span содержит metadata:
  ```json
  {
    "agent_id": "agent-123",
    "agent_name": "search_agent",
    "chat_session_id": "session-456"
  }
  ```

#### Scenario: Изоляция traces по workspace
- **WHEN** запрашиваются tool metrics для workspace_id=W1
- **THEN** возвращаются только spans где `workspace_id=W1`
- **AND** spans из других workspaces недоступны

### Requirement: Error handling в tool execution без propagation

Ошибки tool execution ДОЛЖНЫ быть залогированы в Langfuse но НЕ должны прерывать работу агента.

#### Scenario: Ошибка в tool выполнении
- **WHEN** tool возвращает ошибку (timeout, connection error, validation failure)
- **THEN** ошибка логируется в span с полной информацией: type, message, stack trace
- **AND** span завершается с error status
- **AND** ToolExecutor возвращает ToolResult с success=False и error details
- **AND** agent МОЖЕТ обработать ошибку и продолжить работу

#### Scenario: Ошибка в самом tracing коде
- **WHEN** возникает исключение при создании/завершении span (Langfuse unavailable, invalid params)
- **THEN** ошибка НЕ propagate в ToolExecutor
- **AND** tool выполнение продолжается как если бы tracing не существовал
- **AND** ошибка логируется с уровнем ERROR или WARNING

#### Scenario: Graceful timeout при отправке span
- **WHEN** Langfuse не отвечает > 5 сек при завершении span
- **THEN** отправка отменяется (не блокирует tool execution)
- **AND** логируется warning `"Langfuse span timeout"`
- **AND** tool execution результат остается валидным

### Requirement: Поддержка linked traces для tool execution

Tool execution spans ДОЛЖНЫ быть связаны с parent LLM call span для построения полной trace цепочки.

#### Scenario: Автоматическое связывание с parent span
- **WHEN** tool вызывается как результат LLM call decision
- **THEN** tool execution span автоматически связывается с parent LLM call span
- **AND** в Langfuse UI видна полная цепочка: LLM Call → Tool Execution → Tool Result
- **AND** это происходит через parameter parent_span_id в create_tool_execution_span()

#### Scenario: Standalone tool execution (без parent)
- **WHEN** tool выполняется не в контексте LLM call (например system background task)
- **THEN** tool execution span создается без parent
- **AND** этот span остается root span в его trace

#### Scenario: Trace linking в Langfuse UI
- **WHEN** пользователь смотрит LLM call span в Langfuse
- **THEN** видит все связанные tool execution spans как child nodes
- **AND** может кликнуть на tool execution span для детальной информации

