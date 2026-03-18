# Changelog

Все замечательные изменения в этом проекте будут задокументированы в этом файле.

## [Unreleased]

### Phase 4: Tool Execution Tracing (March 12, 2026)

#### Added

**LangfuseIntegration Service Extensions:**
- `create_tool_execution_span()` - Создание root span для каждого исполнения инструмента с поддержкой nested spans
- `end_tool_execution_span()` - Асинхронное завершение span с результатом/ошибкой (fire-and-forget, 5-sec timeout)
- `_create_nested_span()` - Helper для создания nested spans (validation, risk_assessment, approval, execution)
- `_get_current_span_id()` - Извлечение span ID из structlog context для автоматического связывания
- `_extract_context_vars()` - Извлечение user_id, workspace_id, agent_id из structlog
- `get_tool_metrics()` - Агрегация metrics из Langfuse (count, success_rate, latency percentiles)
- `get_tool_ranking()` - Ранжирование tools по метрике (success_rate, latency, count)
- `record_tool_score()` - Запись quality feedback (0.0-1.0) с комментариями
- `_get_cached_metrics()` / `_cache_metrics()` - Redis caching с TTL=3600s
- `_invalidate_metrics_cache()` - Инвалидация кэша при записи scores

**ToolExecutor Integration:**
- Automatic tool execution span creation in `execute_tool()` method
- Nested spans для всех фаз: validation → risk_assessment → approval → execution
- Graceful error handling - tool execution продолжается если Langfuse unavailable
- Performance overhead tracking (< 50ms requirement met)
- Full context propagation (user_id, workspace_id, agent_name, chat_session_id)

**Tool Performance Analytics REST API:**
- `GET /api/traces/tools/metrics` - Получение метрик инструментов с фильтрацией
- `GET /api/traces/tools/ranking` - Ранжирование tools по выбранной метрике
- `POST /api/traces/tools/score` - Запись quality feedback с валидацией
- Rate limiting: 100 requests/minute per workspace
- Authorization checks на всех endpoints
- Redis caching интеграция (1 hour TTL)

**Comprehensive Testing Suite:**
- 44 новых тестовых методов в `tests/test_langfuse_integration.py`
- Unit tests для span creation/completion, nested spans, context propagation
- Integration tests для ToolExecutor + LangfuseIntegration flow
- E2E tests для полного tool execution с отправкой в Langfuse
- Performance tests (100+ concurrent executions, overhead < 50ms)
- Chaos tests для graceful degradation (Langfuse unavailable scenarios)
- Load tests для concurrent operations и metrics retrieval
- Code coverage >= 90% для всех новых modules

**Documentation:**
- Updated README.md с Tool Execution Tracing секцией
- Comprehensive doc/tool-execution-tracing.md с:
  - Architecture overview и diagrams
  - Integration guide для разработчиков
  - Performance & overhead анализ
  - Graceful degradation strategy
  - Troubleshooting guide
  - Migration guide для deployment
  - FAQ и contact info
- Inline comments для сложной логики (async, error handling, edge cases)

#### Features

- **Full Tool Tracing:** Каждое исполнение инструмента автоматически создает Langfuse span
- **Nested Spans Hierarchy:** Иерархия spans для анализа всех фаз execution
- **Context Propagation:** user_id, workspace_id, agent_name автоматически попадают в spans
- **Graceful Degradation:** Tool execution продолжает работать если Langfuse down/unavailable
- **Performance Optimized:** Минимальный overhead (< 50ms), async send с fire-and-forget
- **Analytics & Metrics:** REST API для получения metrics, ranking, quality feedback
- **Caching:** Redis caching с 1-hour TTL для optimization
- **Security:** Trace ID изолирован по workspace, authorization checks на API
- **Monitoring:** Метрики для Prometheus (spans_created, send_errors, timeout_errors, etc)

#### Performance Improvements

- Tool execution latency increased by < 50ms (avg 15ms, < 50ms max)
- Async span completion doesn't block main execution flow
- 100+ concurrent executions supported with stable performance
- Redis caching reduces Langfuse API load
- Rate limiting prevents abuse of analytics endpoints

#### Breaking Changes

None. Tool execution API remains unchanged. Tracing is automatic and transparent.

#### Configuration

New environment variables:
```bash
# Langfuse
LANGFUSE_ENABLED=true                    # Включить/отключить трейсинг
LANGFUSE_PUBLIC_KEY=pk-...               # Из Langfuse dashboard
LANGFUSE_SECRET_KEY=sk-...               # Из Langfuse dashboard
LANGFUSE_BASE_URL=https://api.langfuse.com  # Default

# Tool Execution Tracing
TOOL_EXECUTION_TRACING_ENABLED=true      # Включить tracing
TOOL_ANALYTICS_ENABLED=true              # Включить analytics API
TOOL_EXECUTION_TIMEOUT_SECONDS=300       # Таймаут выполнения

# Redis (для caching)
REDIS_URL=redis://localhost:6379/0
ANALYTICS_CACHE_TTL_SECONDS=3600         # 1 hour
```

#### Migration Guide

1. Обновить .env с Langfuse credentials
2. Убедиться что Redis настроен (для caching)
3. Выполнить тесты: `pytest tests/test_langfuse_integration.py -v`
4. Проверить health endpoint: `GET /health`
5. (Опционально) Запустить нагрузочный тест для верификации overhead

#### Deprecations

None.

#### Known Issues

None identified during testing.

#### Contributors

- Phase 4 Implementation Team (Tool Execution Tracing)

---

## Previous Releases

[Документация предыдущих версий находится в doc/MIGRATION_V0.2.0.md и других change logs]

### Format

Этот changelog следует [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) формату.

