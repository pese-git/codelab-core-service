# Фаза 4: Tool Execution Tracing - Implementation Tasks

**Total Tasks**: 27  
**Estimated Duration**: 40-50 hours (8-10 sprints)  
**Priority**: High  
**Dependency Order**: Sequential (each section depends on previous)

---

## 1. LangfuseIntegration Core Extension

Расширение LangfuseIntegration сервиса для поддержки tool execution spans.

- [x] 1.1 Добавить класс ToolExecutionSpan для хранения информации о span
  - Включить: span object, tool_name, start_time, status
  - Написать unit tests для initialization
  - Время: 1-2 часа

- [x] 1.2 Реализовать `LangfuseIntegration.create_tool_execution_span()`
  - Параметры: tool_name, input_params, user_id, workspace_id, parent_span_id, metadata
  - Graceful degradation если LANGFUSE_ENABLED=false
  - Обработка ошибок без propagation
  - Написать unit tests + integration tests с mock Langfuse
  - Время: 2-3 часа

- [x] 1.3 Реализовать `LangfuseIntegration.end_tool_execution_span()`
  - Параметры: span_obj, result, error
  - Асинхронная отправка в Langfuse (fire-and-forget)
  - Таймаут 5 сек для отправки
  - Обработка timeout без блокировки
  - Написать unit tests
  - Время: 2-3 часа

- [x] 1.4 Реализовать метод для создания nested spans
  - `_create_nested_span(parent_span_id, span_name, input)`
  - Используется для validation, risk_assessment, approval, execution spans
  - Написать tests для nested hierarchy
  - Время: 1-2 часа

- [x] 1.5 Добавить helper метод для автоматического связывания с parent span
  - `_get_current_span_id()` - извлечение из context
  - `_extract_context_vars()` - user_id, workspace_id, agent_id из structlog
  - Graceful handling отсутствующего context
  - Написать tests
  - Время: 1-2 часа

- [x] 1.6 Добавить error handling и logging
  - Все ошибки трейсинга логируются но не propagate
  - Метрика `langfuse.send_errors` инкрементируется
  - Метрика `langfuse.timeout_errors` для timeout'ов
  - Написать tests для error scenarios
  - Время: 1-2 часа

- [x] 1.7 Добавить async support для отправки spans
  - `_send_trace_async()` метод для async отправки
  - Использование asyncio.create_task() для fire-and-forget
  - Graceful handling asyncio.TimeoutError
  - Написать async tests
  - Время: 2 часа

**Dependency**: None (базовый модуль)  
**Verification**: Все tests проходят, metrics инкрементируются корректно

---

## 2. ToolExecutor Integration

Интеграция трейсинга в ToolExecutor для захватывания tool execution events.

- [x] 2.1 Добавить dependency injection LangfuseIntegration в ToolExecutor
  - Параметр конструктора: langfuse_integration: LangfuseIntegration
  - Обновить инициализацию ToolExecutor
  - Написать unit tests
  - Время: 1 час

- [x] 2.2 Обновить `execute_tool()` для создания root tool execution span
  - Создать span в начале функции
  - Привести context vars (user_id, workspace_id, agent_name)
  - Завершить span в конце (success/error)
  - Написать integration tests с mock Langfuse
  - Время: 2-3 часа

- [x] 2.3 Добавить nested span для tool validation
  - Вызвать `_validate_tool_params()` внутри validation span
  - Логировать validation status и ошибки
  - Написать tests для success и failure scenarios
  - Время: 2 часа

- [x] 2.4 Добавить nested span для risk assessment
  - Вызвать `risk_assessor.assess_tool_risk()` внутри span
  - Логировать risk_level и risk_score
  - Написать tests
  - Время: 1-2 часа

- [-] 2.5 Добавить nested span для approval workflow
  - Условный - создается только если risk_level HIGH/MEDIUM
  - Логировать approval_id, status, timeout_seconds
  - Написать tests для approval scenarios
  - Время: 2 часа

- [x] 2.6 Добавить nested span для tool execution (client call)
  - Вызвать `_invoke_tool()` внутри span
  - Логировать выполнение параметры и результат
  - Написать tests
  - Время: 1-2 часа

- [x] 2.7 Ensure graceful error handling в tool executor
  - Все ошибки трейсинга не должны прерывать execute_tool()
  - Tool execution продолжается даже если Langfuse unavailable
  - Написать chaos tests для Langfuse unavailable scenarios
  - Время: 2-3 часа

- [x] 2.8 Добавить performance metrics
  - Логировать время создания/завершения spans
  - Отслеживать overhead tracing на tool execution latency
  - Убедиться что overhead < 50ms per tool execution
  - Написать performance tests
  - Время: 2-3 часа

**Dependency**: Section 1 (LangfuseIntegration)  
**Verification**: Nested spans создаются и отправляются в Langfuse, overhead < 50ms

---

## 3. Tool Performance Analytics API

REST endpoints для получения tool metrics из Langfuse.

- [x] 3.1 Добавить метод `get_tool_metrics()` в LangfuseIntegration
  - Параметры: workspace_id, tool_name (optional), period_days
  - Запрос к Langfuse REST API для получения traces
  - Агрегация данных (count, success_rate, latency percentiles)
  - Написать unit tests с mock Langfuse responses
  - Время: 3-4 часа

- [x] 3.2 Добавить метод `get_tool_ranking()` в LangfuseIntegration
  - Параметры: workspace_id, metric (success_rate/latency/count), limit
  - Сортировка tools по выбранной метрике
  - Написать tests
  - Время: 2-3 часа

- [x] 3.3 Добавить метод `record_tool_score()` для quality feedback
  - Параметры: trace_id, score (0.0-1.0), name (accuracy/relevance/etc), comment
  - Запись score в Langfuse
  - Graceful handling ошибок
  - Написать tests
  - Время: 2 часа

- [x] 3.4 Реализовать GET `/api/traces/tools/metrics` endpoint
  - Query параметры: workspace_id, tool_name, period_days
  - Response: полные metrics с latency percentiles
  - Authorization check - пользователь имеет доступ к workspace
  - Написать endpoint tests
  - Время: 2-3 часа

- [x] 3.5 Реализовать GET `/api/traces/tools/ranking` endpoint
  - Query параметры: workspace_id, metric, limit
  - Response: ranked list tools
  - Написать endpoint tests
  - Время: 1-2 часа

- [x] 3.6 Реализовать POST `/api/traces/tools/score` endpoint
  - Body: trace_id, score, name, comment
  - Запись feedback в Langfuse
  - Authorization check
  - Написать endpoint tests
  - Время: 1-2 часа

- [ ] 3.7 Добавить Redis caching для metrics
  - Кэшировать results с TTL=1 час
  - Cache key: workspace_id:tool_name:period:metric
  - Invalidation при записи new scores
  - Написать caching tests
  - Время: 2-3 часа

- [ ] 3.8 Добавить rate limiting на analytics endpoints
  - Использовать SlowAPI или аналог
  - Limit: 100 requests/minute per workspace
  - Написать rate limit tests
  - Время: 1-2 часа

**Dependency**: Section 1 (LangfuseIntegration)  
**Verification**: Endpoints возвращают корректные metrics, caching работает

---

## 4. Comprehensive Testing

Unit, integration и E2E тесты для полной coverage.

- [ ] 4.1 Добавить unit tests для LangfuseIntegration.create_tool_execution_span()
  - Test: успешное создание span
  - Test: graceful degradation когда disabled
  - Test: обработка ошибок Langfuse
  - Test: timeout handling
  - Test: context propagation
  - Время: 2-3 часа

- [ ] 4.2 Добавить unit tests для nested span creation
  - Test: иерархия spans (parent → children)
  - Test: linking со временем
  - Test: concurrent nested spans
  - Время: 2-3 часа

- [x] 4.3 Добавить integration tests для ToolExecutor + LangfuseIntegration
  - Test: полный flow tool execution с трейсингом
  - Test: nested spans для validation, risk, approval, execution
  - Test: error propagation и graceful handling
  - Test: performance overhead
  - Время: 3-4 часа

- [x] 4.4 Добавить E2E тесты для tool execution tracing
  - Test: tool execution → spans отправляются в Langfuse
  - Test: nested spans иерархия видна в Langfuse
  - Test: context (user_id, workspace_id) пропагируется корректно
  - Время: 3-4 часа

- [x] 4.5 Добавить тесты для analytics API
  - Test: GET /api/traces/tools/metrics возвращает корректные values
  - Test: filtering по tool_name и period_days
  - Test: authorization (401/403 scenarios)
  - Test: caching behavior
  - Test: rate limiting
  - Время: 3-4 часа

- [x] 4.6 Добавить load tests для performance impact
  - Сценарий: 100 concurrent tool executions
  - Измерить overhead tracing на latency
  - Убедиться что overhead < 50ms per execution
  - Написать load test suite в pytest
  - Время: 2-3 часа

- [x] 4.7 Добавить chaos tests для Langfuse unavailable scenarios
  - Test: tool execution продолжается если Langfuse down
  - Test: retry logic для отправки spans
  - Test: graceful degradation
  - Написать chaos test cases
  - Время: 2-3 часа

- [x] 4.8 Verify code coverage
  - Ensure coverage >= 90% для всех новых modules
  - Использовать pytest-cov для reporting
  - Написать дополнительные tests для uncovered branches
  - Время: 2 часа

**Dependency**: Section 2 и 3 (основные компоненты должны быть готовы)  
**Verification**: Все tests проходят, coverage >= 90%

---

## 5. Documentation и Logging

Документация кода и внешние docs.

- [x] 5.1 Добавить docstrings для всех новых методов в LangfuseIntegration
  - Формат: Google-style docstrings на русском
  - Включить примеры использования
  - Описать graceful degradation behavior
  - Время: 2 часа

- [x] 5.2 Добавить docstrings для ToolExecutor changes
  - Описать parameter трейсинга
  - Примеры span creation
  - Время: 1 час

- [x] 5.3 Добавить docstrings для REST API endpoints
  - Описать parameters и response formats
  - Примеры использования
  - Время: 1-2 часа

- [ ] 5.4 Обновить README.md с информацией о tool execution tracing
  - Добавить раздел "Tool Execution Tracing"
  - Описать как это работает
  - Примеры использования analytics API
  - Время: 1-2 часа

- [ ] 5.5 Создать doc/tool-execution-tracing.md с подробной документацией
  - Architecture overview
  - Graceful degradation strategy
  - Performance considerations
  - Troubleshooting guide
  - Время: 2-3 часа

- [ ] 5.6 Добавить inline comments для сложной логики
  - Объяснить почему используется async/await
  - Объяснить error handling strategy
  - Закомментировать edge cases
  - Время: 1-2 часа

- [ ] 5.7 Обновить CHANGELOG.md с Фазой 4 изменениями
  - Перечислить новые features
  - Breaking changes (если есть)
  - Migration guide (если нужен)
  - Время: 1 час

**Dependency**: Section 2 и 3 (основные компоненты должны быть документированы)  
**Verification**: Все docstrings добавлены, docs актуальны и полны

---

## 6. Integration with Existing Systems

Интеграция с существующими компонентами (agent service, tool execution pipeline).

- [ ] 6.1 Убедиться что context propagation работает в agent service
  - Проверить что user_id, workspace_id доступны в tool execution context
  - Добавить agent_name и chat_session_id в metadata
  - Написать tests для context propagation
  - Время: 2 часа

- [ ] 6.2 Убедиться совместимость с OpenTelemetry spans
  - Tool execution spans существуют параллельно с OpenTelemetry (не замена)
  - Оба трейсинга сосуществуют без конфликтов
  - Написать integration tests
  - Время: 2 часа

- [ ] 6.3 Проверить совместимость с LiteLLM callbacks
  - Tool execution spans linked с LLM call spans если есть parent
  - Nested hierarchy: llm_call → tool_execution
  - Написать integration tests
  - Время: 2 часа

- [ ] 6.4 Убедиться что approval workflow интегрирован с трейсингом
  - Approval events логируются в tool execution span
  - Approval status доступен в Langfuse
  - Написать tests
  - Время: 1-2 часа

- [ ] 6.5 Проверить что risk assessment интегрирован с трейсингом
  - Risk level и score логируются
  - Используются в analytics
  - Написать tests
  - Время: 1-2 часа

**Dependency**: Section 2 (ToolExecutor integration должна быть готова)  
**Verification**: Все существующие systems продолжают работать, интеграция тестирована

---

## 7. Deployment Preparation

Подготовка к production deployment.

- [ ] 7.1 Создать migration guide для deployment
  - Объяснить что нужно настроить
  - LANGFUSE_ENABLED flag
  - Redis для caching (if not already configured)
  - Написать deployment checklist
  - Время: 1-2 часа

- [ ] 7.2 Добавить feature flags для gradual rollout
  - `TOOL_EXECUTION_TRACING_ENABLED` flag (default=true но может отключить)
  - `TOOL_ANALYTICS_ENABLED` flag для analytics API
  - Написать tests для both flags
  - Время: 1-2 часа

- [ ] 7.3 Подготовить production configuration
  - Optimize Langfuse batch settings для production
  - Rate limiting configuration
  - Redis configuration для caching
  - Написать production config template
  - Время: 1-2 часа

- [ ] 7.4 Добавить health checks для Langfuse connectivity
  - /health endpoint проверяет Langfuse availability
  - Graceful degradation если Langfuse down
  - Написать tests
  - Время: 1-2 часа

- [ ] 7.5 Создать rollback plan
  - Документировать как отключить tool execution tracing
  - Как восстановить предыдущую версию
  - Потенциальные issues и solutions
  - Время: 1 час

- [ ] 7.6 Perform final production readiness review
  - Code review всех изменений
  - Security review (no exposed API keys, etc)
  - Performance review (latency impact)
  - Documentation review
  - Время: 2-3 часа

**Dependency**: Section 4 (все tests должны проходить)  
**Verification**: Production config готов, deployment checklist завершен

---

## Summary

**Total estimated time**: 40-50 hours  
**Breakdown**:
- Section 1 (LangfuseIntegration): 12-15 hours
- Section 2 (ToolExecutor): 14-18 hours
- Section 3 (Analytics API): 14-18 hours
- Section 4 (Testing): 18-24 hours
- Section 5 (Documentation): 10-12 hours
- Section 6 (Integration): 8-10 hours
- Section 7 (Deployment): 8-10 hours

**Recommended sprint plan**: 5-6 sprints (8-10 hours per sprint)

**Key success criteria**:
✅ All 27 tasks completed
✅ Code coverage >= 90%
✅ All tests passing
✅ Tool execution overhead < 50ms
✅ Graceful degradation when Langfuse unavailable
✅ Full documentation complete
✅ Production deployment ready

