# Delta Specification: Tool Execution Trace System (Phase 4 Update)

## Overview

Обновление требований для tool-execution-trace system с добавлением поддержки Langfuse integration. Фаза 4 расширяет существующие OpenTelemetry spans с Langfuse-specific трейсингом для tool execution events.

---

## MODIFIED Requirements

### Requirement: tool_execution span через Langfuse SDK
Обновленное требование для создания tool execution spans с поддержкой Langfuse integration через `@observe` декоратор.

**What changed**: 
- Использование Langfuse SDK `@observe` декоратора вместо кастомного LangfuseIntegration класса
- Tool execution трейсится и в Langfuse (через SDK) и в OpenTelemetry (параллельно)
- Nested spans через вложенные `@observe` декораторы

**Updated Requirement**:
Tool execution spans ДОЛЖНЫ создаваться через Langfuse SDK (`@observe` декоратор) с поддержкой обновления payload через `_update_langfuse_span()` для ключевых метрик.

#### Scenario: tool_execution span в Langfuse
- **WHEN** вызывается `ToolExecutor.execute_tool(tool_name="api_call", params={...})`
- **THEN** декоратор `@observe(as_type="tool", name="ExecuteTool")` автоматически создает span в Langfuse
- **AND** span содержит input: `_safe_tool_input()` с tool_name, session_id, param_keys
- **AND** span содержит output: status, tool_id, risk_level, approval_id (если есть)
- **AND** span отправляется в Langfuse асинхронно через SDK

#### Scenario: Nested tool_validation span
- **WHEN** ToolExecutor вызывает `_validate_tool_params()`
- **THEN** декоратор `@observe` на методе автоматически создает child span
- **AND** parent span = root ExecuteTool span
- **AND** span завершается с success или error в зависимости от валидации

#### Scenario: Risk assessment данные в root span
- **WHEN** ToolExecutor вызывает `risk_assessor.assess_tool_risk()`
- **THEN** результат (risk_level) добавляется в output_data root span'а через `_update_langfuse_span()`
- **AND** risk_level видна в output root ExecuteTool span'а

#### Scenario: Approval workflow данные в root span
- **WHEN** требуется одобрение (HIGH/MEDIUM risk)
- **THEN** approval_id и статус (approved/rejected) добавляются в output root span'а
- **AND** эти данные видны в root ExecuteTool span'а

#### Scenario: Финальный результат в root span
- **WHEN** инструмент выполняется или отклоняется
- **THEN** финальный статус (approved/rejected/failed) добавляется в output через `_update_langfuse_span()`
- **AND** tool_id всегда включается в output для tracking

#### Scenario: Linked trace hierarchy
- **WHEN** tool execution происходит в контексте LLM call
- **THEN** Langfuse SDK автоматически отслеживает иерархию через context
- **AND** в Langfuse UI видна иерархия: llm_call → ExecuteTool → ValidateTool (если был вызван)

#### Scenario: Graceful degradation при Langfuse unavailable
- **WHEN** Langfuse отключен (LANGFUSE_ENABLED=false) или недоступен
- **THEN** `@observe` декоратор пропускает создание spans (no-op)
- **AND** OpenTelemetry spans продолжают создаваться нормально (независимая система)
- **AND** `_update_langfuse_span()` ловит исключения и логирует на DEBUG
- **AND** tool execution продолжается без влияния

#### Scenario: Error handling в tool execution spans
- **WHEN** tool execution завершается с ошибкой (validation, timeout, rejection)
- **THEN** error_type добавляется в output через `_update_langfuse_span(output_data={..., "error_type": "validation_error"})`
- **AND** span завершается нормально (Langfuse SDK логирует выход из @observe)
- **AND** exception не propagate в ToolExecutor

### Requirement: Context propagation в OpenTelemetry spans (No Change)
Requirement остается без изменений. OpenTelemetry spans продолжают работать как ранее с context propagation через structlog.

#### Scenario: Контекст в OpenTelemetry spans
- **WHEN** OpenTelemetry span создается
- **THEN** span содержит атрибуты из structlog context: `user.id`, `workspace.id`, `agent.id`
- **AND** это работает параллельно с Langfuse spans (дублирования нет, разные системы)

---

## ADDED Requirements

### Requirement: Tool execution metrics и analytics через Langfuse REST API

LangfuseIntegration ДОЛЖЕН предоставлять методы для запроса tool execution metrics из Langfuse и expose их через REST API.

#### Scenario: Получение tool metrics по workspace
- **WHEN** вызывается `GET /api/traces/tools/metrics?workspace_id=W1&tool_name=search_docs&period_days=7`
- **THEN** возвращается JSON с метриками:
  ```json
  {
    "tool_name": "search_docs",
    "workspace_id": "W1",
    "period_days": 7,
    "total_invocations": 1245,
    "success_count": 1198,
    "error_count": 47,
    "success_rate": 0.9623,
    "avg_latency_ms": 234.5,
    "p50_latency_ms": 180,
    "p95_latency_ms": 456,
    "p99_latency_ms": 678,
    "most_common_errors": [
      {"error_type": "timeout", "count": 34},
      {"error_type": "validation_error", "count": 13}
    ]
  }
  ```

#### Scenario: Получение ranking tools по метрике
- **WHEN** вызывается `GET /api/traces/tools/ranking?workspace_id=W1&metric=success_rate&limit=10`
- **THEN** возвращается list tools отсортированный по success_rate в descending порядке
- **AND** каждый tool содержит всех metrics для сравнения

#### Scenario: Caching analytics results
- **WHEN** вызывается analytics endpoint
- **THEN** результаты кэшируются в Redis с TTL=1 час
- **AND** повторный запрос за тот же период возвращает cached результат
- **AND** при недоступности Redis возвращается свежий результат из Langfuse

#### Scenario: Фильтрация по tool_name
- **WHEN** вызывается endpoint с параметром `tool_name=search_docs`
- **THEN** возвращаются metrics только для этого инструмента
- **AND** если tool_name не указан - возвращаются metrics для всех tools в workspace

#### Scenario: Фильтрация по периоду
- **WHEN** вызывается endpoint с параметром `period_days=30`
- **THEN** возвращаются metrics за последние 30 дней
- **AND** default period = 7 дней если не указан

#### Scenario: Authorization в analytics API
- **WHEN** вызывается analytics endpoint
- **THEN** система проверяет что пользователь имеет доступ к workspace_id
- **AND** если нет доступа - возвращается 403 Forbidden

### Requirement: Tool performance scoring для quality feedback

LangfuseIntegration ДОЛЖЕН предоставлять методы для записи quality scores для tool execution spans в Langfuse.

#### Scenario: Запись score для tool execution
- **WHEN** пользователь оставляет feedback для tool результата (например "результат был точным" = 1.0, "неточный" = 0.0)
- **THEN** вызывается `langfuse_integration.record_tool_score(trace_id, score=1.0, name="accuracy")`
- **AND** score записывается в Langfuse для соответствующего trace

#### Scenario: Multiple scores для одного trace
- **WHEN** записываются несколько scores для одного tool execution trace
- **THEN** каждый score имеет уникальное имя (accuracy, relevance, correctness)
- **AND** все scores доступны в analytics для расчета weighted metrics

#### Scenario: Score aggregation в analytics
- **WHEN** запрашиваются metrics для tool с scores
- **THEN** возвращаются:
  - `avg_score_accuracy`: average accuracy score
  - `avg_score_relevance`: average relevance score
  - `score_count`: количество записанных scores
  - `score_distribution`: распределение scores (0.0-0.2, 0.2-0.4, etc.)

---

## Implementation Notes for Phase 4

### Key Integration Points
1. **LangfuseIntegration.create_tool_execution_span()** - создание root span для tool execution
2. **LangfuseIntegration.create_nested_span()** - создание child spans для валидации, risk assessment, одобрения
3. **ToolExecutor.execute_tool()** - интеграция трейсинга в основной flow
4. **app/routes/traces.py** - новые REST endpoints для metrics и analytics
5. **app/services/langfuse_rest_client.py** - расширение для tool execution запросов

### Graceful Degradation Strategy
- Если `LANGFUSE_ENABLED=false` - все методы создания spans возвращают None
- Если Langfuse недоступен - ошибки трейсинга логируются но не propagate
- OpenTelemetry spans продолжают работать независимо от Langfuse
- Tool execution продолжает работу в любом случае

### Testing Requirements
- Unit tests для каждого метода создания/завершения spans
- Integration tests для nested span hierarchy
- E2E tests для полного flow: LLM call → Tool execution → Analytics API
- Load tests для performance impact (< 50ms overhead per tool execution)
- Chaos tests для Langfuse unavailable scenarios

