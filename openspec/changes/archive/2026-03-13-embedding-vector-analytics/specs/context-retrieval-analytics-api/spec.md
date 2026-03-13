# Context Retrieval Analytics API - Спецификация

## ADDED Requirements

### Requirement: REST API для получения метрик embeddings

Система ДОЛЖНА предоставлять REST endpoint `GET /api/traces/embeddings/metrics` для запроса метрик производительности embeddings с фильтрацией и кэшированием.

#### Scenario: Успешное получение embedding метрик

- **WHEN** клиент отправляет `GET /api/traces/embeddings/metrics?workspace_id=ws-123&time_range=24h`
- **THEN** система возвращает 200 OK с JSON:
  ```json
  {
    "workspace_id": "ws-123",
    "time_range": "24h",
    "metrics": {
      "total_embeddings": 1250,
      "total_tokens": 125000,
      "total_cost": 2.50,
      "avg_latency_ms": 85.5,
      "p50_latency_ms": 80,
      "p95_latency_ms": 150,
      "p99_latency_ms": 200,
      "by_model": {
        "text-embedding-3-small": {
          "count": 1000,
          "avg_latency_ms": 75,
          "cost": 2.0
        },
        "text-embedding-3-large": {
          "count": 250,
          "avg_latency_ms": 120,
          "cost": 0.50
        }
      }
    }
  }
  ```
- **AND** response содержит `X-Cache: HIT` header если данные из Redis cache

#### Scenario: Фильтрация по agent_id

- **WHEN** клиент отправляет `GET /api/traces/embeddings/metrics?workspace_id=ws-123&agent_id=agent-456&time_range=7d`
- **THEN** система возвращает метрики только для этого агента
- **AND** response содержит только embeddings вызванные агентом agent-456

#### Scenario: Дефолтные параметры

- **WHEN** клиент отправляет `GET /api/traces/embeddings/metrics?workspace_id=ws-123` без time_range и agent_id
- **THEN** система использует дефолты:
  - `time_range` = "24h" (последние 24 часа)
  - `agent_id` = null (все агенты)
- **AND** возвращает метрики с этими параметрами

#### Scenario: Авторизация и isolation

- **WHEN** клиент без JWT токена пытается получить metrics
- **THEN** система возвращает 401 Unauthorized
- **WHEN** клиент с токеном workspace A пытается получить metrics workspace B
- **THEN** система возвращает 403 Forbidden

#### Scenario: Кэширование с Redis TTL

- **WHEN** клиент делает первый запрос к `/api/traces/embeddings/metrics`
- **THEN** система запрашивает данные из Langfuse, кэширует в Redis
- **AND** response содержит `X-Cache: MISS`
- **WHEN** второй клиент делает идентичный запрос в течение 3600 секунд
- **THEN** система возвращает данные из Redis cache
- **AND** response содержит `X-Cache: HIT`

### Requirement: REST API для cost breakdown анализа

Система ДОЛЖНА предоставлять endpoint `GET /api/traces/embeddings/cost-breakdown` для анализа стоимости embeddings по группам.

#### Scenario: Cost breakdown по агентам

- **WHEN** клиент отправляет `GET /api/traces/embeddings/cost-breakdown?workspace_id=ws-123&by=agent&time_range=30d`
- **THEN** система возвращает 200 OK с JSON:
  ```json
  {
    "workspace_id": "ws-123",
    "breakdown_by": "agent",
    "time_range": "30d",
    "data": [
      {
        "agent_id": "agent-123",
        "count": 5000,
        "total_cost": 10.0,
        "avg_cost_per_call": 0.002,
        "top_models": ["text-embedding-3-small"]
      },
      {
        "agent_id": "agent-456",
        "count": 3000,
        "total_cost": 8.0,
        "avg_cost_per_call": 0.0027,
        "top_models": ["text-embedding-3-large"]
      }
    ],
    "total_cost": 18.0,
    "total_count": 8000
  }
  ```
- **AND** результаты отсортированы по total_cost DESC

#### Scenario: Cost breakdown по embedding моделям

- **WHEN** клиент отправляет `GET /api/traces/embeddings/cost-breakdown?workspace_id=ws-123&by=model`
- **THEN** система возвращает breakdown с агрегированием по embedding моделям
- **AND** каждая модель показывает: count, total_cost, avg_latency

#### Scenario: Cost breakdown по пользователям

- **WHEN** клиент отправляет `GET /api/traces/embeddings/cost-breakdown?workspace_id=ws-123&by=user`
- **THEN** система возвращает breakdown с агрегированием по user_id
- **AND** показывает cost per user для billing/chargeback

### Requirement: REST API для аналитики vector searches

Система ДОЛЖНА предоставлять endpoint `GET /api/traces/vector-searches/analytics` для анализа производительности поисков.

#### Scenario: Успешное получение vector search аналитики

- **WHEN** клиент отправляет `GET /api/traces/vector-searches/analytics?workspace_id=ws-123&time_range=24h`
- **THEN** система возвращает 200 OK с JSON:
  ```json
  {
    "workspace_id": "ws-123",
    "time_range": "24h",
    "metrics": {
      "total_searches": 5000,
      "avg_latency_ms": 45.2,
      "p50_latency_ms": 40,
      "p95_latency_ms": 100,
      "p99_latency_ms": 200,
      "avg_results_per_search": 8.5,
      "search_result_distribution": {
        "0_results": 120,
        "1_5_results": 1200,
        "5_10_results": 2500,
        "10_plus_results": 1180
      },
      "by_agent": {
        "agent-123": {
          "count": 2500,
          "avg_latency_ms": 42
        }
      }
    }
  }
  ```

#### Scenario: Фильтрация по agent_id

- **WHEN** клиент отправляет `GET /api/traces/vector-searches/analytics?workspace_id=ws-123&agent_id=agent-456`
- **THEN** система возвращает метрики только для vector searches вызванных этим агентом

### Requirement: REST API для feedback на качество контекста

Система ДОЛЖНА предоставлять endpoint `POST /api/traces/context/feedback` для записи relevance scores контекста.

#### Scenario: Успешная отправка quality feedback

- **WHEN** клиент отправляет:
  ```json
  POST /api/traces/context/feedback
  {
    "span_id": "span-789",
    "relevance_score": 0.85,
    "comments": "Context was relevant and helped agent make good decision"
  }
  ```
- **THEN** система возвращает 201 Created
- **AND** feedback записывается в Langfuse как custom event на span
- **AND** response содержит `feedback_id` для reference

#### Scenario: Валидация score значения

- **WHEN** клиент отправляет relevance_score = 1.5 (не в диапазоне 0.0-1.0)
- **THEN** система возвращает 400 Bad Request
- **AND** сообщение: "relevance_score must be between 0.0 and 1.0"

#### Scenario: Авторизация на feedback

- **WHEN** клиент с JWT токеном workspace A пытается отправить feedback на span из workspace B
- **THEN** система возвращает 403 Forbidden

#### Scenario: Опциональные comments

- **WHEN** клиент отправляет feedback без comments поля
- **THEN** система принимает request (comments опциональны)
- **AND** feedback записывается с пустым comments

### Requirement: Rate limiting на analytics endpoints

Система ДОЛЖНА применять rate limiting для защиты от abuse analytics API.

#### Scenario: Rate limit per workspace

- **WHEN** клиент из workspace ws-123 делает 101-й request в течение 1 минуты
- **THEN** система возвращает 429 Too Many Requests
- **AND** response содержит headers:
  - `X-RateLimit-Limit: 100`
  - `X-RateLimit-Remaining: 0`
  - `X-RateLimit-Reset: <timestamp>`

#### Scenario: Разные лимиты для разных endpoints

- **WHEN** клиент отправляет запрос к `/api/traces/embeddings/metrics`
- **THEN** применяется rate limit 100 requests/min per workspace
- **WHEN** клиент отправляет `POST /api/traces/context/feedback`
- **THEN** применяется rate limit 500 requests/min per workspace (более свободный для writes)

## Testing Requirements

### Unit Tests
- [ ] `test_embeddings_metrics_success` - успешный запрос метрик
- [ ] `test_embeddings_metrics_filtering` - фильтрация по agent_id
- [ ] `test_embeddings_metrics_caching` - Redis caching
- [ ] `test_cost_breakdown_by_agent` - breakdown по агентам
- [ ] `test_cost_breakdown_by_model` - breakdown по моделям
- [ ] `test_vector_searches_analytics` - vector search аналитика
- [ ] `test_context_feedback_success` - успешное сохранение feedback
- [ ] `test_context_feedback_validation` - валидация relevance_score
- [ ] `test_rate_limiting` - rate limit enforcement
- [ ] `test_authorization_checks` - authorization checks

### Integration Tests
- [ ] `test_analytics_api_with_langfuse` - полная интеграция с Langfuse
- [ ] `test_analytics_api_with_redis_cache` - интеграция с Redis
- [ ] `test_analytics_workspace_isolation` - isolation по workspace

### Performance Tests
- [ ] `test_metrics_endpoint_latency` - endpoint response < 500ms
- [ ] `test_cache_hit_performance` - cached response < 50ms
- [ ] `test_bulk_feedback_submission` - 1000 feedback requests в параллели

### Code Coverage
- [ ] `app/routes/analytics.py` или `app/routes/traces.py` (analytics endpoints): >= 95% coverage

## Documentation Requirements

### Code Documentation
- [ ] Docstrings для всех endpoint handlers на русском
- [ ] OpenAPI/Swagger documentation для каждого endpoint
- [ ] Type hints для request/response models

### User Documentation
- [ ] doc/analytics-api-guide.md (100-150 строк): как использовать analytics endpoints
- [ ] Примеры curl команд для каждого endpoint
- [ ] Explanation Langfuse integration в анализе

### Configuration Documentation
- [ ] .env.example: добавить ANALYTICS_CACHE_TTL_SECONDS, ANALYTICS_RATE_LIMIT_*
- [ ] API documentation в README.md или отдельный файл

## Edge Cases and Error Handling

1. **Отсутствие данных в диапазоне времени**
   - Если time_range не содержит данных
   - Система ДОЛЖНА вернуть 200 OK с пустыми metrics, не 404

2. **Langfuse unavailable**
   - Если Langfuse API недоступна при запросе analytics
   - Система ДОЛЖНА вернуть cached данные если доступны
   - Если кэш также отсутствует, вернуть 503 Service Unavailable

3. **Большие диапазоны времени**
   - Если client запрашивает metrics для 1 года (очень много данных)
   - Система ДОЛЖНА применить разумный лимит (e.g. max 30 дней)
   - Вернуть 400 Bad Request с сообщением об ограничении

4. **Concurrent feedback submissions**
   - Если два feedback одновременно отправляются на один span
   - Оба должны быть приняты и записаны как отдельные events
