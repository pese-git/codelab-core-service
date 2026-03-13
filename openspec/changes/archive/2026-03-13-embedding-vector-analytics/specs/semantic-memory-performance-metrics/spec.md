# Semantic Memory Performance Metrics - Спецификация

## ADDED Requirements

### Requirement: Консолидированный view производительности RAG

Система ДОЛЖНА предоставлять endpoint `GET /api/traces/semantic-memory/performance` для получения консолидированного view всех метрик RAG производительности (embeddings, vector searches, context quality).

#### Scenario: Успешное получение performance metrics

- **WHEN** клиент отправляет `GET /api/traces/semantic-memory/performance?workspace_id=ws-123&time_range=24h`
- **THEN** система возвращает 200 OK с JSON:
  ```json
  {
    "workspace_id": "ws-123",
    "time_range": "24h",
    "summary": {
      "total_embedding_calls": 1250,
      "total_searches": 5000,
      "avg_embedding_latency_ms": 85.5,
      "avg_search_latency_ms": 45.2,
      "context_quality_score": 0.78,
      "total_semantic_memory_cost": 12.50
    },
    "embedding_metrics": {
      "count": 1250,
      "avg_latency_ms": 85.5,
      "p95_latency_ms": 150,
      "by_model": {
        "text-embedding-3-small": 1000,
        "text-embedding-3-large": 250
      }
    },
    "search_metrics": {
      "count": 5000,
      "avg_latency_ms": 45.2,
      "p95_latency_ms": 100,
      "avg_results_per_search": 8.5,
      "zero_result_searches": 120
    },
    "context_quality": {
      "avg_relevance_score": 0.78,
      "feedback_count": 340,
      "quality_by_agent": {
        "agent-123": 0.82,
        "agent-456": 0.75
      }
    },
    "bottlenecks": [
      {
        "type": "high_latency_search",
        "agent_id": "agent-456",
        "avg_latency_ms": 250,
        "recommendation": "Consider optimizing Qdrant index"
      },
      {
        "type": "low_quality_context",
        "agent_id": "agent-789",
        "avg_quality_score": 0.45,
        "recommendation": "Review embedding model or document indexing"
      }
    ]
  }
  ```
- **AND** response содержит `X-Cache: HIT/MISS` header

#### Scenario: Фильтрация по agent_id

- **WHEN** клиент отправляет `GET /api/traces/semantic-memory/performance?workspace_id=ws-123&agent_id=agent-456`
- **THEN** система возвращает metrics только для этого агента
- **AND** bottlenecks отфильтрованы по agent

#### Scenario: Автоматическое выявление bottlenecks

- **WHEN** система вычисляет performance metrics
- **THEN** она автоматически выявляет проблемы:
  - Embeddings с latency > p95 (потенциально дорогие модели)
  - Searches с latency > p95 (потенциальные Qdrant проблемы)
  - Contexts с avg relevance_score < 0.5 (качество проблемы)
  - Searches с > 30% zero-result rate (индексирование проблемы)
- **AND** каждый bottleneck содержит `recommendation` для fix

### Requirement: Metrics для по-агентной производительности

Система ДОЛЖНА отслеживать семантическую память performance per agent и предоставлять детальный breakdown.

#### Scenario: Per-agent performance metrics

- **WHEN** клиент отправляет `GET /api/traces/semantic-memory/performance?workspace_id=ws-123&by=agent`
- **THEN** система возвращает массив per-agent metrics:
  ```json
  {
    "agents": [
      {
        "agent_id": "agent-123",
        "embedding_count": 500,
        "search_count": 2000,
        "avg_embedding_latency_ms": 80,
        "avg_search_latency_ms": 42,
        "context_quality_score": 0.82,
        "cost": 5.0,
        "tool_execution_success_rate": 0.92
      }
    ]
  }
  ```
- **AND** результаты отсортированы по agent_id

#### Scenario: Корреляция с tool execution

- **WHEN** система вычисляет per-agent metrics
- **THEN** она корреллирует:
  - avg_search_latency_ms ↔ tool_execution_success_rate
  - context_quality_score ↔ tool_execution_success_rate
- **AND** высокая корелляция может быть выявлена и предложена как optimization opportunity

### Requirement: Time-series данные для trend analysis

Система ДОЛЖНА сохранять и предоставлять time-series данные для анализа трендов семантической памяти.

#### Scenario: Time-series metrics по часам

- **WHEN** клиент отправляет `GET /api/traces/semantic-memory/performance?workspace_id=ws-123&granularity=hourly&time_range=7d`
- **THEN** система возвращает metrics aggregated hourly:
  ```json
  {
    "time_series": [
      {
        "hour": "2026-03-12T12:00Z",
        "embedding_count": 125,
        "avg_embedding_latency_ms": 85,
        "search_count": 500,
        "avg_search_latency_ms": 45,
        "avg_quality_score": 0.78
      },
      {
        "hour": "2026-03-12T13:00Z",
        "embedding_count": 150,
        "avg_embedding_latency_ms": 92,
        ...
      }
    ]
  }
  ```
- **AND** это позволяет выявить daily patterns и anomalies

#### Scenario: Дефолтная granularity

- **WHEN** клиент не указывает granularity
- **THEN** система использует дефолт:
  - Для `time_range=24h`: granularity=15m (четверть часа)
  - Для `time_range=7d`: granularity=hourly
  - Для `time_range=30d`: granularity=daily

### Requirement: Comparison функционала для A/B testing

Система ДОЛЖНА позволять сравнивать metrics для двух периодов времени для выявления улучшений/регрессий.

#### Scenario: Comparison двух временных периодов

- **WHEN** клиент отправляет `GET /api/traces/semantic-memory/performance/compare?workspace_id=ws-123&period1=2026-03-05,2026-03-11&period2=2026-03-12,2026-03-18`
- **THEN** система возвращает comparison metrics:
  ```json
  {
    "period1": {
      "date_range": "2026-03-05 to 2026-03-11",
      "embedding_latency_ms": 85,
      "search_latency_ms": 45,
      "quality_score": 0.75
    },
    "period2": {
      "date_range": "2026-03-12 to 2026-03-18",
      "embedding_latency_ms": 82,
      "search_latency_ms": 44,
      "quality_score": 0.78
    },
    "changes": {
      "embedding_latency_improvement_pct": 3.5,
      "search_latency_improvement_pct": 2.2,
      "quality_improvement_pct": 4.0
    }
  }
  ```

### Requirement: Алерты для аномалий в RAG производительности

Система ДОЛЖНА выявлять аномалии в семантической памяти и создавать алерты.

#### Scenario: Обнаружение regress в производительности

- **WHEN** embedding latency p95 увеличивается на > 25% за последний час (по сравнению с 7-day average)
- **THEN** система создает internal alert с severity="warning"
- **AND** alert содержит:
  - Тип: "embedding_latency_regression"
  - Current value vs baseline
  - Recommendation: "Check OpenAI API status or consider using smaller model"

#### Scenario: Обнаружение качества regress

- **WHEN** avg context quality score падает ниже 0.5
- **THEN** система создает alert с severity="critical"
- **AND** alert содержит рекомендацию для investigation

#### Scenario: Отключение алертов через feature flag

- **WHEN** `PERFORMANCE_ALERTS_ENABLED=false`
- **THEN** система не создает алерты (но все еще собирает metrics)

## Testing Requirements

### Unit Tests
- [ ] `test_performance_metrics_aggregation` - агрегирование метрик
- [ ] `test_bottleneck_detection` - выявление bottlenecks
- [ ] `test_per_agent_metrics` - per-agent breakdown
- [ ] `test_time_series_aggregation` - hourly/daily aggregation
- [ ] `test_comparison_metrics` - сравнение периодов
- [ ] `test_anomaly_detection` - выявление аномалий
- [ ] `test_performance_alerts` - создание алертов

### Integration Tests
- [ ] `test_performance_metrics_with_langfuse` - полная интеграция
- [ ] `test_performance_metrics_with_cache` - Redis caching
- [ ] `test_performance_workspace_isolation` - isolation

### Performance Tests
- [ ] `test_performance_endpoint_latency` - response < 1000ms
- [ ] `test_time_series_query_performance` - aggregation < 5000ms
- [ ] `test_bulk_alert_generation` - 1000+ agents

### Code Coverage
- [ ] Analytics module for semantic memory: >= 95% coverage

## Documentation Requirements

### Code Documentation
- [ ] Docstrings для aggregation logic
- [ ] Comments для bottleneck detection алгоритмов
- [ ] Type hints для all functions

### User Documentation
- [ ] doc/semantic-memory-analytics.md: полный guide
- [ ] Examples для comparison queries
- [ ] Bottleneck remediation guide

### Configuration Documentation
- [ ] .env.example: PERFORMANCE_ALERTS_ENABLED, ALERT_THRESHOLDS_*
- [ ] Prometheus metrics для performance alerts

## Edge Cases and Error Handling

1. **Недостаточно данных**
   - Если query period содержит < 10 data points
   - Система ДОЛЖНА вернуть 200 OK с warning в response

2. **Очень большие queries**
   - Если time_range = 1 год и много agents
   - Система ДОЛЖНА применить limits и вернуть sampling

3. **Стремительное изменение patterns**
   - Если latency резко скачет (e.g. 10ms → 500ms за 1 minute)
   - Система ДОЛЖНА выявить как critical anomaly
