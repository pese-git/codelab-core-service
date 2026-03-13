# Embedding Cost Attribution - Спецификация

## ADDED Requirements

### Requirement: Трейсирование стоимости embeddings по агентам и моделям

Система ДОЛЖНА отслеживать и атрибутировать стоимость embedding операций по агентам, моделям embedding и workspace для billing и cost optimization.

#### Scenario: Cost calculation для embedding вызова

- **WHEN** embedding вызов выполняется с моделью "text-embedding-3-small" и 1000 input tokens
- **THEN** система вычисляет стоимость:
  - Pricing за 1000 tokens: $0.02 (текущая OpenAI pricing)
  - Cost = (1000 / 1000) * 0.02 = $0.02
- **AND** span содержит атрибуты:
  - `input_cost` = 0.02
  - `output_cost` = 0.0 (embeddings not charged per-output)
  - `total_cost` = 0.02

#### Scenario: Cost calculation для text-embedding-3-large

- **WHEN** embedding вызов с моделью "text-embedding-3-large" и 1000 input tokens
- **THEN** система использует правильную pricing:
  - Pricing за 1000 tokens: $0.13
  - Cost = (1000 / 1000) * 0.13 = $0.13
- **AND** span содержит `input_cost` = 0.13

#### Scenario: Cost attribution по agent

- **WHEN** клиент запрашивает `GET /api/traces/embeddings/cost-breakdown?workspace_id=ws-123&by=agent&time_range=30d`
- **THEN** система возвращает cost breakdown:
  ```json
  {
    "breakdown_by": "agent",
    "data": [
      {
        "agent_id": "agent-123",
        "total_cost": 50.0,
        "embedding_count": 2500,
        "avg_cost_per_embedding": 0.020,
        "by_model": {
          "text-embedding-3-small": {
            "cost": 40.0,
            "count": 2000
          },
          "text-embedding-3-large": {
            "cost": 10.0,
            "count": 500
          }
        }
      }
    ]
  }
  ```

#### Scenario: Cost attribution по embedding модели

- **WHEN** клиент запрашивает `GET /api/traces/embeddings/cost-breakdown?workspace_id=ws-123&by=model`
- **THEN** система возвращает:
  ```json
  {
    "breakdown_by": "model",
    "data": [
      {
        "model": "text-embedding-3-small",
        "total_cost": 100.0,
        "embedding_count": 5000,
        "avg_latency_ms": 75
      },
      {
        "model": "text-embedding-3-large",
        "total_cost": 50.0,
        "embedding_count": 1000,
        "avg_latency_ms": 120
      }
    ]
  }
  ```

#### Scenario: Cost attribution по пользователю (для billing)

- **WHEN** клиент запрашивает `GET /api/traces/embeddings/cost-breakdown?workspace_id=ws-123&by=user`
- **THEN** система возвращает cost per user:
  ```json
  {
    "breakdown_by": "user",
    "data": [
      {
        "user_id": "user-111",
        "total_cost": 75.0,
        "embedding_count": 3500,
        "agents_used": ["agent-123", "agent-456"]
      }
    ]
  }
  ```

### Requirement: Pricing sync с OpenAI API

Система ДОЛЖНА периодически обновлять embedding pricing с OpenAI API для точной cost calculation.

#### Scenario: Daily pricing sync

- **WHEN** система стартует или один раз в день в scheduled time
- **THEN** она запрашивает текущее pricing для всех embedding моделей
- **AND** кэширует pricing в памяти (и/или Redis)
- **AND** использует это pricing для всех вычислений cost

#### Scenario: Fallback pricing если sync fails

- **WHEN** OpenAI pricing API недоступна
- **THEN** система использует cached/default pricing
- **AND** логирует warning что pricing может быть stale
- **AND** можно manually trigger sync через admin API если нужно

#### Scenario: Pricing history tracking

- **WHEN** OpenAI меняет pricing
- **THEN** новое pricing применяется для future embeddings
- **AND** старое pricing остается для уже recorded spans (для accurate calculations)
- **AND** система ДОЛЖНА уметь reconstruct historical cost с правильным pricing

### Requirement: Cost monitoring и alerts

Система ДОЛЖНА мониторить embedding costs и выявлять потенциальные cost optimization opportunities.

#### Scenario: Cost anomaly detection

- **WHEN** embedding cost за час > 2x от daily average за последние 7 дней
- **THEN** система выявляет это как anomaly
- **AND** может создать alert с severity="warning"
- **AND** recommend investigation

#### Scenario: Per-agent cost limits (опционально)

- **WHEN** администратор устанавливает cost limit для agent:
  ```json
  {
    "agent_id": "agent-456",
    "monthly_cost_limit": 100.0
  }
  ```
- **THEN** система отслеживает cost и может:
  - Выявить когда лимит будет превышен (projection)
  - Выдать alert за 80% utilization
  - Заблокировать дальнейшие embeddings если лимит превышен (опционально)

#### Scenario: Cost efficiency metrics

- **WHEN** система анализирует per-agent cost
- **THEN** она вычисляет:
  - Cost per successful tool execution
  - Cost per context retrieval
  - Embedding cost as % of total API costs
- **AND** выявляет agents с high cost per execution

### Requirement: Integration с tool execution hierarchy

Система ДОЛЖНА атрибутировать embedding costs к parent tool execution spans для полного cost tracking.

#### Scenario: Embedding cost в tool execution span

- **WHEN** tool execution содержит embeddings для context retrieval
- **THEN** tool execution span содержит:
  - `total_cost` = LLM cost + embedding cost + other costs
  - `cost_breakdown`: { "llm": X, "embeddings": Y }
  - `context_retrieval_cost` = embedding + vector search cost
- **AND** это видно в tool execution tracing

#### Scenario: Cost aggregation по tool

- **WHEN** один tool часто вызывается
- **THEN** его total cost (LLM + embeddings + vector search) может быть aggregated
- **AND** выявлены "expensive tools" которые candidates для optimization

## Testing Requirements

### Unit Tests
- [ ] `test_cost_calculation_text_embedding_3_small` - correct pricing
- [ ] `test_cost_calculation_text_embedding_3_large` - correct pricing
- [ ] `test_cost_breakdown_by_agent` - aggregation
- [ ] `test_cost_breakdown_by_model` - aggregation
- [ ] `test_pricing_sync_success` - daily sync
- [ ] `test_pricing_sync_failure_fallback` - fallback logic
- [ ] `test_cost_anomaly_detection` - anomaly detection
- [ ] `test_cost_in_tool_span` - integration

### Integration Tests
- [ ] `test_cost_attribution_with_real_pricing` - OpenAI API (mock if needed)
- [ ] `test_cost_tracking_across_spans` - hierarchical cost tracking
- [ ] `test_cost_persistence_in_langfuse` - storage

### Performance Tests
- [ ] `test_cost_calculation_performance` - < 1ms per calculation
- [ ] `test_cost_aggregation_performance` - aggregation < 5 seconds
- [ ] `test_pricing_sync_performance` - sync < 30 seconds

### Code Coverage
- [ ] Pricing and cost attribution module: >= 95% coverage

## Documentation Requirements

### Code Documentation
- [ ] Docstrings для cost calculation functions на русском
- [ ] Comments для pricing sync logic
- [ ] Type hints

### User Documentation
- [ ] doc/embedding-cost-analysis.md: cost tracking and analysis
- [ ] Examples для cost breakdown queries
- [ ] Cost optimization recommendations

### Configuration Documentation
- [ ] .env.example:
  - PRICING_SYNC_INTERVAL_HOURS
  - COST_ALERT_THRESHOLD_PCT
  - COST_LIMIT_ENABLED
- [ ] README.md update with cost tracking

## Edge Cases and Error Handling

1. **Pricing для новых моделей**
   - Если OpenAI добавит новую embedding модель
   - Система ДОЛЖНА автоматически получить pricing при следующем sync
   - До sync можно использовать estimated pricing

2. **Pricing in different currencies**
   - Если workspace в non-USD валюте
   - Система ДОЛЖНА конвертировать USD pricing
   - Требует exchange rate sync (TBD)

3. **Batch embedding cost**
   - Если batch содержит 100 texts
   - Каждый text может иметь разное количество токенов
   - Total cost = sum(individual costs)
   - Batch должно быть атрибутировано как single parent cost

4. **Retroactive pricing changes**
   - Если OpenAI меняет pricing за прошлый период
   - Система ДОЛЖНА уметь recalculate historical costs (опционально)
   - Или просто использовать pricing которая была в момент execution

5. **Cost rounding**
   - Очень маленькие embeddings могут иметь cost < $0.0001
   - Система ДОЛЖНА правильно аккумулировать (не терять precision)
   - Использовать Decimal для финансовых вычислений
