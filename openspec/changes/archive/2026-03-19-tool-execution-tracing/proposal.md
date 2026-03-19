# Фаза 4: Tool Execution Tracing

## Why

Текущая интеграция Langfuse покрывает LLM вызовы и embedding запросы, но не отслеживает выполнение инструментов (tools) - критической части workflow агентов. Трейсинг tool execution необходим для:
- Полного понимания цепочки выполнения агента (LLM → Tool → Result)
- Диагностики ошибок в инструментах без прерывания агента
- Анализа performance характеристик инструментов
- Сбора feedback для улучшения selection logic (какие tools вызываются, как часто)

## What Changes

- **Tool execution capture**: Langfuse будет получать события о вызове и результате каждого tool с параметрами, результатом и временем выполнения
- **Error handling in tools**: Ошибки инструментов логируются в Langfuse без propagation в агента (graceful degradation)
- **Tool metadata enrichment**: Каждое tool execution содержит контекст агента, пользователя, workspace для корректной аналитики
- **Tool performance analytics**: REST API для получения статистики по tool usage, latency, success rate по workspace/агенту/tool
- **Nested traces support**: Tool execution traces связаны с parent LLM call для визуализации полной цепочки в UI Langfuse

## Capabilities

### New Capabilities
- `tool-execution-capture`: Автоматический capture tool execution events с параметрами, результатом и ошибками в Langfuse через tracer

### Modified Capabilities
- `tool-execution-trace`: Обновление requirement для поддержки Langfuse integration и nested spans в контексте LLM call (вместо standalone spans)

## Impact

**Affected code**:
- `app/tools/` - добавление трейсинга в tool runner
- `app/services/` - интеграция с Langfuse REST client для tool events
- `app/services/langfuse_rest_client.py` - расширение для tool execution spans
- `app/routes/` - добавление analytics endpoints для tool metrics

**Affected systems**:
- Langfuse backend - будет получать tool execution events
- Agent execution pipeline - graceful degradation при недоступности Langfuse

**Dependencies**:
- Зависит от успешного завершения Фазы 3 (Langfuse infrastructure)

**No breaking changes** - tool execution трейсинг добавляется как новая функциональность, не изменяя существующие APIs.

