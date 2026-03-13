# RAG Context Quality Scoring - Спецификация

## ADDED Requirements

### Requirement: Механизм feedback на качество контекста

Система ДОЛЖНА позволять пользователям и системе записывать relevance scores для контекста, возвращенного RAG retrieval операциями.

#### Scenario: Успешное сохранение relevance score

- **WHEN** система/пользователь отправляет `POST /api/traces/context/feedback`
  ```json
  {
    "span_id": "span-789",
    "relevance_score": 0.85,
    "comments": "Context was highly relevant to the tool execution"
  }
  ```
- **THEN** система возвращает 201 Created с response:
  ```json
  {
    "feedback_id": "feedback-456",
    "span_id": "span-789",
    "relevance_score": 0.85,
    "timestamp": "2026-03-12T18:30:00Z"
  }
  ```
- **AND** feedback записывается в Langfuse как custom event на vector_search span
- **AND** event name = "context_feedback"
- **AND** event metadata содержит relevance_score и comments

#### Scenario: Auto-scoring based на tool execution success

- **WHEN** tool execution заканчивается успешно (result status = "success")
- **AND** был vector search для context retrieval в составе execution
- **THEN** система автоматически создает feedback с relevance_score = 1.0
- **AND** feedback comments = "Auto-scored: Tool execution successful"
- **AND** это не требует пользовательского input

#### Scenario: Auto-scoring based на tool execution failure

- **WHEN** tool execution заканчивается с ошибкой (status = "error" или "timeout")
- **AND** был vector search в составе execution
- **THEN** система может автоматически создать feedback с низким score (0.3)
- **AND** это опционально - может быть disabled через feature flag

#### Scenario: Валидация score диапазона

- **WHEN** клиент отправляет relevance_score = 1.5
- **THEN** система возвращает 400 Bad Request
- **AND** error message: "relevance_score must be between 0.0 and 1.0"
- **WHEN** клиент отправляет relevance_score = -0.1
- **THEN** система также возвращает 400 Bad Request

#### Scenario: Опциональные comments

- **WHEN** клиент отправляет feedback без comments поля
- **THEN** система принимает request
- **AND** feedback сохраняется с null/empty comments

### Requirement: Tracking контекста к документам

Система ДОЛЖНА сохранять информацию о том, какие документы/chunks были возвращены как контекст, для анализа контекста quality.

#### Scenario: Document metadata в context retrieval span

- **WHEN** vector search возвращает результаты
- **THEN** каждый результат содержит metadata:
  - `document_id` (от Qdrant payload)
  - `chunk_index` (порядок в документе)
  - `text_preview` (первые 100 chars для preview)
  - `chunk_size` (количество токенов)
- **AND** top-1 результат (most relevant) metadata сохраняется в span

#### Scenario: Linking relevance feedback к документам

- **WHEN** пользователь дает feedback relevance_score = 0.2 (низкий)
- **THEN** система может идентифицировать какой документ был low-quality
- **AND** analytics может aggregated по document_id
- **AND** это выявляет documents которые нужно переиндексировать

### Requirement: Корреляция quality feedback с tool success

Система ДОЛЖНА анализировать корреляцию между context quality и tool execution success для выявления improvement opportunities.

#### Scenario: Correlation analysis per agent

- **WHEN** система выполняет анализ за период (e.g. 7 дней)
- **THEN** она корреллирует:
  - avg context quality score (из feedback) 
  - tool execution success rate (из tool execution spans)
- **AND** вычисляет Pearson correlation coefficient
- **AND** высокая положительная корелляция (> 0.7) указывает что улучшение контекста поможет success rate
- **AND** низкая корелляция указывает что проблемы в другой части (validation, tool logic, etc)

#### Scenario: Quality metrics по agent

- **WHEN** клиент запрашивает `/api/traces/semantic-memory/performance?workspace_id=ws-123`
- **THEN** response содержит per-agent quality metrics:
  ```json
  {
    "context_quality": {
      "by_agent": {
        "agent-123": {
          "avg_relevance_score": 0.82,
          "feedback_count": 500,
          "correlation_with_success_rate": 0.75,
          "quality_trend": "improving"
        }
      }
    }
  }
  ```

### Requirement: Feedback aggregation и trending

Система ДОЛЖНА агрегировать quality feedback и выявлять trends.

#### Scenario: Aggregated quality metrics

- **WHEN** система агрегирует quality feedback за 24 часа
- **THEN** она вычисляет:
  - `total_feedback_count` - сколько feedback записано
  - `avg_relevance_score` - среднее из всех scores
  - `median_relevance_score` - медиана
  - `distribution` - сколько feedback было за каждый score диапазон (0.0-0.2, 0.2-0.4, etc)
  - `trend` - улучшается ли quality (ascending/descending/stable)

#### Scenario: Trend detection

- **WHEN** avg_relevance_score падает с 0.80 на 0.60 за 3 дня
- **THEN** система выявляет trend = "declining"
- **AND** это может быть алерт для investigation

#### Scenario: Per-document quality

- **WHEN** система анализирует какие документы возвращают низкий quality контекст
- **THEN** она groupирует feedback по document_id
- **AND** выявляет documents с avg quality < 0.5
- **AND** эти documents candidates для переиндексирования или удаления

## Testing Requirements

### Unit Tests
- [ ] `test_feedback_submission_success` - успешное сохранение
- [ ] `test_feedback_score_validation` - валидация диапазона
- [ ] `test_auto_scoring_on_success` - auto-scoring при успехе
- [ ] `test_auto_scoring_on_failure` - auto-scoring при ошибке
- [ ] `test_document_metadata_tracking` - tracking документов
- [ ] `test_correlation_analysis` - correlation calculation
- [ ] `test_feedback_aggregation` - aggregation metrics
- [ ] `test_trend_detection` - trend detection

### Integration Tests
- [ ] `test_feedback_integration_with_langfuse` - сохранение в Langfuse
- [ ] `test_feedback_in_analytics_queries` - использование в analytics
- [ ] `test_auto_scoring_with_tool_execution` - в составе tool execution flow

### Performance Tests
- [ ] `test_feedback_submission_latency` - response < 100ms
- [ ] `test_correlation_calculation_performance` - < 5 seconds для 30 дней
- [ ] `test_bulk_feedback_aggregation` - 100k+ feedback records

### Code Coverage
- [ ] Context quality scoring module: >= 95% coverage

## Documentation Requirements

### Code Documentation
- [ ] Docstrings для feedback handlers
- [ ] Comments для correlation algorithm
- [ ] Type hints

### User Documentation
- [ ] doc/context-quality-scoring.md: как использовать feedback
- [ ] Correlation analysis explanation
- [ ] Best practices для quality assessment

### Configuration Documentation
- [ ] .env.example: AUTO_SCORING_ENABLED, QUALITY_ALERT_THRESHOLD_*
- [ ] README.md update

## Edge Cases and Error Handling

1. **Feedback на deleted span**
   - Если span был удален из Langfuse (data retention policy)
   - Система ДОЛЖНА вернуть 404 Not Found

2. **Duplicate feedback**
   - Если два identical feedbacks отправляются на один span
   - Система ДОЛЖНА принять оба (может быть разные пользователи)
   - OR можно реализовать deduplication logic

3. **Массовая смена качества**
   - Если все feedback скачек от 0.9 к 0.1
   - Система ДОЛЖНА выявить это как potential data corruption
   - Может требовать human review перед aggregation

4. **Correlation с малым sample size**
   - Если feedback count < 10
   - Correlation может быть случайной
   - Система ДОЛЖНА не показывать correlation (или с asterisk warning)
