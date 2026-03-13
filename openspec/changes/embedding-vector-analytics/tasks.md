# Phase 5: Advanced Tracing - Embedding & Vector Analytics - Tasks

## 1. Подготовка и Infrastructure

- [x] 1.1 Добавить feature flags в .env.example (EMBEDDING_TRACING_ENABLED, VECTOR_SEARCH_TRACING_ENABLED, EMBEDDING_ANALYTICS_API_ENABLED)
- [x] 1.2 Обновить pyproject.toml зависимости (если нужны новые библиотеки для анализа)
- [ ] 1.3 Создать пакеты `app/services/embedding_service.py` и обновить `app/services/vector_store_service.py` для tracing hooks
- [ ] 1.4 Написать unit тесты для feature flag checks (3 теста)

## 2. Embedding Trace Collection - Основная реализация

- [ ] 2.1 Добавить методы в [`app/services/langfuse_integration.py`](../../app/services/langfuse_integration.py): `create_embedding_span()`, `end_embedding_span()`, `_calculate_embedding_cost()` (~100 строк)
- [ ] 2.2 Обновить `EmbeddingService.embed()` для создания embedding spans перед/после API вызова (~50 строк)
- [ ] 2.3 Добавить cost calculation logic для OpenAI embedding моделей (text-embedding-3-small, text-embedding-3-large)
- [ ] 2.4 Написать unit тесты для embedding spans (8 тестов: success, error, graceful degradation, cost calc, async, batch, etc.)
- [ ] 2.5 Написать integration тесты с реальным/mock Langfuse (3 теста)

## 3. Vector Search Tracing - Основная реализация

- [ ] 3.1 Добавить методы в [`app/services/langfuse_integration.py`](../../app/services/langfuse_integration.py): `create_vector_search_span()`, `end_vector_search_span()`, `_extract_search_metadata()` (~80 строк)
- [ ] 3.2 Обновить `VectorStoreService.search_similar()` для создания vector search spans перед/после Qdrant вызова (~50 строк)
- [ ] 3.3 Добавить capture результатов: results_count, min_score, max_score, avg_score
- [ ] 3.4 Написать unit тесты для vector search spans (8 тестов: success, zero results, error, graceful degradation, async, etc.)
- [ ] 3.5 Написать integration тесты с Qdrant (3 теста)

## 4. Cost Attribution - Pricing и Cost Tracking

- [ ] 4.1 Создать `app/services/pricing_service.py` для управления embedding pricing (~100 строк)
- [ ] 4.2 Реализовать daily pricing sync из OpenAI API (с fallback на cached pricing)
- [ ] 4.3 Добавить cost calculation в embedding и vector search spans (использовать pricing service)
- [ ] 4.4 Написать unit тесты для pricing service (6 тестов: calculation, sync, fallback, different models)
- [ ] 4.5 Написать integration тесты с mock OpenAI API (2 теста)

## 5. Context Retrieval Analytics API - GET endpoints

- [ ] 5.1 Создать `app/routes/analytics_embeddings.py` с endpoint `GET /api/traces/embeddings/metrics` (~80 строк)
- [ ] 5.2 Реализовать фильтрацию по workspace_id, agent_id, time_range
- [ ] 5.3 Добавить Redis caching с TTL=3600s для metrics endpoint
- [ ] 5.4 Создать endpoint `GET /api/traces/embeddings/cost-breakdown` с фильтрацией по agent/model/user (~60 строк)
- [ ] 5.5 Создать endpoint `GET /api/traces/vector-searches/analytics` (~60 строк)
- [ ] 5.6 Написать unit тесты для endpoints (9 тестов: success, filtering, caching, authorization, rate limiting)
- [ ] 5.7 Написать integration тесты с Langfuse (3 теста)

## 6. Context Retrieval Analytics API - Feedback endpoint

- [ ] 6.1 Создать endpoint `POST /api/traces/context/feedback` для quality feedback (~40 строк)
- [ ] 6.2 Добавить валидацию relevance_score (0.0-1.0)
- [ ] 6.3 Реализовать сохранение feedback как custom event в Langfuse
- [ ] 6.4 Написать unit тесты (6 тестов: success, validation, authorization, opțional comments)

## 7. Rate Limiting для Analytics API

- [ ] 7.1 Реализовать rate limiting middleware для analytics endpoints (100 req/min per workspace, 500 req/min для feedback)
- [ ] 7.2 Добавить X-RateLimit-* headers в responses
- [ ] 7.3 Написать unit тесты для rate limiting (3 теста)

## 8. Semantic Memory Performance Metrics - Aggregation

- [ ] 8.1 Создать `app/services/semantic_memory_analytics.py` для агрегирования всех метрик (~150 строк)
- [ ] 8.2 Реализовать `get_performance_metrics()` для consolidation view (embedding + search + quality)
- [ ] 8.3 Реализовать bottleneck detection (latency > p95, quality < 0.5, zero-result rate > 30%)
- [ ] 8.4 Реализовать per-agent performance aggregation
- [ ] 8.5 Написать unit тесты (7 тестов: aggregation, bottleneck detection, per-agent, etc.)

## 9. Semantic Memory Performance Metrics - API endpoints

- [ ] 9.1 Создать endpoint `GET /api/traces/semantic-memory/performance` (~80 строк)
- [ ] 9.2 Добавить time-series support (granularity=hourly/daily) с aggregation logic
- [ ] 9.3 Создать endpoint `GET /api/traces/semantic-memory/performance/compare` для period comparison (~60 строк)
- [ ] 9.4 Написать unit тесты (8 тестов: basic metrics, filtering, time-series, comparison)
- [ ] 9.5 Написать integration тесты (2 теста)

## 10. RAG Context Quality Scoring

- [ ] 10.1 Реализовать `create_context_feedback()` и `aggregate_quality_metrics()` в semantic_memory_analytics.py (~60 строк)
- [ ] 10.2 Добавить auto-scoring на основе tool execution success (trigger из tool execution completion)
- [ ] 10.3 Реализовать feedback aggregation и trend detection (ascending/descending/stable)
- [ ] 10.4 Реализовать correlation analysis между context quality и tool success rate
- [ ] 10.5 Написать unit тесты (7 тестов: feedback, auto-scoring, aggregation, correlation, trends)

## 11. Performance Monitoring и Alerts

- [ ] 11.1 Создать `app/services/performance_alerts.py` для аномалии detection (~80 строк)
- [ ] 11.2 Реализовать detection для: embedding latency regression, quality decline, zero-result rate spike
- [ ] 11.3 Интегрировать с Prometheus metrics для alerting
- [ ] 11.4 Добавить feature flag для отключения alerts
- [ ] 11.5 Написать unit тесты (5 тестов: detection, severity, disable flag)

## 12. Integration с Tool Execution Hierarchy

- [ ] 12.1 Обновить [`app/core/tools/executor.py`](../../app/core/tools/executor.py) для автоматического связывания embedding spans с tool execution span
- [ ] 12.2 Добавить context retrieval cost aggregation в tool execution span (cost_breakdown: embedding + search)
- [ ] 12.3 Написать unit тесты для span hierarchy (4 теста)
- [ ] 12.4 Написать integration тесты (2 теста)

## 13. Документация в исходном коде

- [ ] 13.1 Добавить docstrings для всех публичных методов в русском языке (embedding_service, vector_store_service, langfuse_integration embedding методы)
- [ ] 13.2 Добавить inline comments для сложной логики (async fire-and-forget, cost calculation, aggregation algorithms)
- [ ] 13.3 Добавить type hints для всех функций

## 14. User Documentation

- [ ] 14.1 Написать doc/embedding-tracing.md (100 строк): как работает embedding tracing, какие metrics собираются
- [ ] 14.2 Написать doc/vector-search-tracing.md (80 строк): vector search tracing guide
- [ ] 14.3 Написать doc/analytics-api-guide.md (150 строк): примеры curl, description endpoints
- [ ] 14.4 Написать doc/semantic-memory-analytics.md (100 строк): как использовать analytics, bottleneck remediation
- [ ] 14.5 Написать doc/context-quality-scoring.md (80 строк): feedback mechanism, auto-scoring
- [ ] 14.6 Обновить README.md с Tool Execution Tracing и Analytics API секциями

## 15. Configuration Documentation

- [ ] 15.1 Обновить .env.example с новыми переменными (feature flags, cache TTL, rate limits)
- [ ] 15.2 Обновить CHANGELOG.md с Phase 5 изменениями
- [ ] 15.3 Написать migration guide для существующих systems

## 16. Comprehensive Testing

- [ ] 16.1 Написать end-to-end тесты для полного flow: embedding → vector search → analytics → feedback (3 E2E теста)
- [ ] 16.2 Написать performance тесты: 100+ concurrent embeddings < 50ms overhead (2 теста)
- [ ] 16.3 Написать chaos тесты: Langfuse unavailable, rate limiting, timeout scenarios (3 теста)
- [ ] 16.4 Проверить code coverage >= 90% для всех новых modules (использовать pytest --cov)
- [ ] 16.5 Написать load тесты: 1000 concurrent analytics requests (1 тест)

## 17. Code Quality и CI/CD

- [ ] 17.1 Запустить ruff linting на всех новых файлах (без errors)
- [ ] 17.2 Запустить mypy type checking (--strict mode)
- [ ] 17.3 Запустить все тесты: `pytest tests/test_langfuse_integration.py -v` (50+ тестов должны pass)
- [ ] 17.4 Проверить что код следует project standards (русские docstrings, type hints, TDD)

## 18. Integration Testing с Staging

- [ ] 18.1 Развернуть в staging окружении с EMBEDDING_TRACING_ENABLED=false
- [ ] 18.2 Запустить 24-часовой мониторинг для проверки performance overhead
- [ ] 18.3 Собрать метрики: span creation success rate, API latency, error rates
- [ ] 18.4 Включить EMBEDDING_TRACING_ENABLED=true и повторить мониторинг
- [ ] 18.5 Сравнить metrics: overhead должно быть < 50ms за tool execution

## 19. Feature Flag Rollout

- [ ] 19.1 Создать deployment plan с gradual rollout (10% → 50% → 100%)
- [ ] 19.2 Подготовить rollback scripts (disable всех flags если нужно)
- [ ] 19.3 Настроить alerting для trace failures и performance regression
- [ ] 19.4 Подготовить runbook для on-call engineers

## Зависимости и приоритизация

**Критические (Phase 1 - должны быть первыми):**
- Задачи 1-4 (infrastructure + embedding + cost)

**Высокий приоритет (Phase 2 - после embedding):**
- Задачи 5-7 (analytics API endpoints)
- Задача 8 (performance metrics aggregation)

**Средний приоритет (Phase 3 - параллельно/после):**
- Задача 10 (quality scoring)
- Задача 11 (alerts)
- Задача 12 (integration с tool execution)

**Низкий приоритет (Phase 4 - после функционала):**
- Задачи 13-15 (documentation)
- Задачи 16-19 (testing и rollout)

**Блокирующие зависимости:**
- 2.x должна быть готова перед 5.1 (нужны embedding spans для analytics)
- 3.x должна быть готова перед 5.5 (нужны vector search spans)
- 4.x должна быть параллельна 2.x и 3.x (cost calculation в spans)
- 8.x зависит от 5.1-5.5 (нужны metrics)
- 9.x зависит от 8.x (нужна aggregation)

**Примерный timeline:**
- Неделя 1: Задачи 1-4 (infrastructure + embedding + tracing = 20 часов)
- Неделя 1-2: Задачи 5-9 (analytics API = 24 часа)
- Неделя 2: Задачи 10-12 (quality scoring + integration = 16 часов)
- Неделя 2-3: Задачи 13-19 (documentation + testing + rollout = 20 часов)

**Итого:** ~80 часов = ~2 недели для полной реализации + 1 неделя staging + rollout
