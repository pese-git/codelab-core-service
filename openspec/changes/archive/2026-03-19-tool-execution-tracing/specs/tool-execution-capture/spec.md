# Specification: Tool Execution Capture

## Обзор

Система автоматического захватывания tool execution events в Langfuse с полным контекстом параметров, результатов, ошибок и временных метрик для построения полной trace цепочки: LLM Call → Tool Execution → Tool Result.

---

## ADDED Requirements

### Requirement: Создание span для tool execution через Langfuse SDK

Langfuse SDK (через `@observe` декоратор) ДОЛЖЕН автоматически создавать spans для tool execution с полным контекстом.

#### Scenario: Создание root tool execution span
- **WHEN** ToolExecutor вызывает `execute_tool(tool_name="search_docs", tool_params={...})`
- **THEN** декоратор `@observe(as_type="tool", name="ExecuteTool")` автоматически создает span
- **AND** span содержит атрибуты: `tool_name`, параметры через `_safe_tool_input()`, user_id, project_id
- **AND** span содержит input/output через вызовы `_update_langfuse_span()`

#### Scenario: Вложенные spans в tool execution workflow
- **WHEN** ToolExecutor выполняет валидацию, assessment, approval, выполнение
- **THEN** вложенные операции также покрываются `@observe` декораторами
- **AND** декоратор `@observe` на `_validate_tool_params()` создает child span
- **AND** в Langfuse SDK context автоматически отслеживается иерархия span'ов

#### Scenario: Graceful degradation при отсутствии Langfuse
- **WHEN** Langfuse отключен (`LANGFUSE_ENABLED=false` в LangfuseClient)
- **THEN** `@observe` декоратор пропускает создание spans (no-op)
- **AND** ToolExecutor продолжает работу без изменений
- **AND** ошибок tracing не логируются

#### Scenario: Graceful degradation при ошибке tracing
- **WHEN** Langfuse недоступен или возвращает ошибку
- **THEN** функция `_update_langfuse_span()` ловит исключение и логирует на уровне DEBUG
- **AND** tool execution продолжается как если бы tracing не было
- **AND** исключение не propagate в ToolExecutor

### Requirement: Обновление span payload в tool execution

Langfuse SDK span ДОЛЖЕН обновляться с полной информацией о tool execution: параметры, результаты, ошибки.

#### Scenario: Добавление input в tool execution span
- **WHEN** ToolExecutor начинает выполнение
- **THEN** вызывается `_update_langfuse_span(input_data=_safe_tool_input(...))`
- **AND** input содержит: tool_name, session_id, param_keys, path (если есть), command (если есть)
- **AND** sensitive данные исключаются (content длина вместо самого content)

#### Scenario: Добавление output в tool execution span
- **WHEN** tool execution завершается (success/rejection/approval/failed)
- **THEN** вызывается `_update_langfuse_span(output_data={...})`
- **AND** output содержит: status, tool_id, risk_level, approval_id, error_type (если есть)
- **AND** при ошибке добавляется поле error_type

#### Scenario: Безопасность при обновлении span
- **WHEN** `_update_langfuse_span()` вызывается с некорректными данными
- **THEN** функция ловит исключение и логирует DEBUG сообщение
- **AND** tool execution продолжается без влияния

### Requirement: Интеграция tracing в ToolExecutor.execute_tool()

ToolExecutor ДОЛЖЕН использовать `@observe` декораторы для создания spans для ключевых этапов tool execution.

#### Scenario: Root tool execution span
- **WHEN** ToolExecutor вызывает `execute_tool(tool_name="read_file", tool_params={...})`
- **THEN** декоратор `@observe(as_type="tool", name="ExecuteTool")` создает root span
- **AND** span содержит input с параметрами через `_update_langfuse_span(input_data=...)`
- **AND** span содержит output с результатом/статусом через `_update_langfuse_span(output_data=...)`

#### Scenario: Validation span через @observe
- **WHEN** ToolExecutor вызывает `_validate_tool_params(tool_name, params)`
- **THEN** декоратор `@observe(as_type="tool", name="ValidateTool")` создает child span
- **AND** при успехе span завершается нормально
- **AND** при ошибке валидации span отмечается как error но tool execution продолжается

#### Scenario: Risk assessment отслеживается в root span
- **WHEN** ToolExecutor вызывает `risk_assessor.assess_tool_risk()`
- **THEN** результат (risk_level) добавляется в output_data root span'а
- **AND** это видно в root `ExecuteTool` span как атрибут output

#### Scenario: Approval workflow отслеживается в root span
- **WHEN** risk_level = HIGH или MEDIUM и требуется одобрение
- **THEN** approval_id и статус добавляются в output_data root span'а
- **AND** если одобрение отклонено, span завершается с rejection status в output

#### Scenario: Tool выполнение отслеживается в root span
- **WHEN** ToolExecutor отправляет запрос на выполнение tool на клиент
- **THEN** финальный результат (success/rejection/error) добавляется в output_data
- **AND** tool_id включается в output для tracking

#### Scenario: Workflow в одном span дереве
- **WHEN** выполняется tool с валидацией, risk assessment и выполнением
- **THEN** структура в Langfuse:
  ```
  ExecuteTool (root span)
  ├── ValidateTool (child span через @observe)
  ├── [Риск-assessment данные в output parent]
  ├── [Approval данные в output parent]
  └── [Финальный результат в output parent]
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

