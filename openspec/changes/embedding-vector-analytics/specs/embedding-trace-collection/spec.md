# Embedding Trace Collection - Спецификация

## ADDED Requirements

### Requirement: Автоматическое создание span для embedding API вызовов

Система ДОЛЖНА автоматически создавать Langfuse span для каждого вызова embedding API (OpenAI, локальные модели) с захватом latency, количества токенов и стоимости.

#### Scenario: Успешный embedding вызов OpenAI

- **WHEN** приложение вызывает `EmbeddingService.embed()` с текстом
- **THEN** система создает Langfuse span с именем "embedding_generation"
- **AND** span содержит метрику `input_tokens` (подсчитано через tiktoken)
- **AND** span содержит метрику `latency_ms` (время выполнения API вызова)
- **AND** span содержит атрибут `embedding_model` с названием модели (e.g. "text-embedding-3-small")
- **AND** span содержит атрибут `status` = "success"
- **AND** span содержит estimated cost: `input_tokens * cost_per_1k_tokens`

#### Scenario: Отключение tracing через feature flag

- **WHEN** `EMBEDDING_TRACING_ENABLED=false` установлен в окружении
- **THEN** EmbeddingService не создает Langfuse spans
- **AND** embedding API вызов выполняется без overhead

#### Scenario: Обработка ошибок API

- **WHEN** OpenAI API возвращает ошибку (rate limit, 500 error, timeout)
- **THEN** система создает span с статусом "error"
- **AND** span содержит атрибут `error_code` (e.g. "rate_limit_exceeded")
- **AND** span содержит атрибут `error_message` с описанием ошибки
- **AND** exception пробрасывается дальше (не логируется только в span)

#### Scenario: Graceful degradation если Langfuse unavailable

- **WHEN** Langfuse API недоступна (connection refused, timeout)
- **THEN** EmbeddingService логирует warning в structlog
- **AND** embedding вызов продолжает выполняться (не зависит от Langfuse)
- **AND** метрика `embedding_trace_failures` инкрементируется
- **AND** operatorи может disable tracing через feature flag если проблемы

#### Scenario: Пакетные embeddings

- **WHEN** `EmbeddingService.embed()` вызывается с списком из 10 текстов
- **THEN** система создает один parent span "batch_embedding"
- **AND** parent span содержит `total_input_tokens` (сумма всех текстов)
- **AND** parent span содержит `batch_size` = 10
- **AND** latency_ms измеряет полное время пакета

### Requirement: Структурированная логирование контекста в embeddings spans

Система ДОЛЖНА автоматически извлекать и добавлять контекст (user_id, workspace_id, agent_id) в embedding spans из structlog context.

#### Scenario: Context propagation в embedding span

- **WHEN** embedding вызов происходит внутри tool execution с контекстом
- **THEN** embedding span содержит custom attributes:
  - `workspace_id` (из structlog.context)
  - `agent_id` (из structlog.context)
  - `user_id` (из structlog.context)
  - `chat_session_id` (если доступен)
- **AND** span может быть отфильтрован по workspace и агентам

#### Scenario: Отсутствие контекста

- **WHEN** embedding вызов происходит без structlog context (e.g. background task)
- **THEN** embedding span создается без workspace_id/agent_id
- **AND** система логирует debug message: "Embedding span created without context"

### Requirement: Inline cost tracking для embeddings

Система ДОЛЖНА хранить cost информацию в embedding spans для анализа cost per agent/model.

#### Scenario: Cost calculation для text-embedding-3-small

- **WHEN** embedding вызов с моделью "text-embedding-3-small"
- **AND** input_tokens = 1000
- **THEN** system вычисляет cost: 1000 * 0.02 / 1000 = $0.02
- **AND** span содержит `input_cost` = 0.02
- **AND** span содержит `output_cost` = 0.0 (embeddings не имеют output cost)
- **AND** span содержит `total_cost` = 0.02

#### Scenario: Cost calculation для text-embedding-3-large

- **WHEN** embedding вызов с моделью "text-embedding-3-large"
- **AND** input_tokens = 1000
- **THEN** system вычисляет cost: 1000 * 0.13 / 1000 = $0.13
- **AND** span содержит `input_cost` = 0.13

### Requirement: Async fire-and-forget отправка spans

Система ДОЛЖНА отправлять embedding spans в Langfuse асинхронно без блокирования основного flow выполнения.

#### Scenario: Non-blocking span completion

- **WHEN** embedding вызов завершается
- **THEN** система создает coroutine для отправки span в Langfuse
- **AND** coroutine отправляется в background task queue
- **AND** основной embedding вызов возвращает результат сразу (не ждет span отправки)
- **AND** корутина имеет таймаут 5 секунд (если не отправилась за это время, пропускается)

#### Scenario: Performance overhead

- **WHEN** EmbeddingService.embed() вызывается 100 раз подряд
- **THEN** общее время выполнения с tracing < на 50ms больше чем без tracing
- **AND** средний overhead за один embedding < 5ms
- **AND** p99 overhead < 10ms

## MODIFIED Requirements

### Requirement: Context isolation по workspace

Существующее требование: spans должны быть изолированы по workspace для безопасности.

**Обновление**: Embedding spans ДОЛЖНЫ включать `workspace_id` для обеспечения изоляции.

#### Scenario: Embedding span workspace isolation

- **WHEN** два пользователя из разных workspace вызывают embeddings одновременно
- **THEN** их spans создаются с разными `workspace_id` атрибутами
- **AND** queries для analytics фильтруют по workspace (не могут видеть spans других workspace)
- **AND** cost attribution разделяется по workspace

## Testing Requirements

### Unit Tests
- [ ] `test_embedding_span_creation_success` - успешное создание span
- [ ] `test_embedding_span_error_handling` - обработка ошибок API
- [ ] `test_embedding_span_graceful_degradation` - Langfuse unavailable
- [ ] `test_embedding_context_propagation` - контекст из structlog
- [ ] `test_embedding_cost_calculation` - вычисление стоимости
- [ ] `test_embedding_async_fire_and_forget` - async отправка
- [ ] `test_batch_embedding_span` - пакетные embeddings
- [ ] `test_feature_flag_disabled` - отключение через flag

### Integration Tests
- [ ] `test_embedding_with_real_openai` - вызов реального OpenAI API (mock при необходимости)
- [ ] `test_embedding_with_langfuse_integration` - полная интеграция с Langfuse
- [ ] `test_embedding_span_in_tool_execution_hierarchy` - embedding span часть tool execution trace

### Performance Tests
- [ ] `test_embedding_overhead_single_call` - overhead < 5ms
- [ ] `test_embedding_overhead_batch_100` - overhead batch < 50ms
- [ ] `test_embedding_span_queue_performance` - background task queue не заполняется

### Code Coverage
- [ ] `app/services/embedding_service.py`: >= 95% coverage
- [ ] `app/services/langfuse_integration.py` (embedding методы): >= 90% coverage

## Documentation Requirements

### Code Documentation
- [ ] Docstrings для всех public методов EmbeddingService на русском
- [ ] Inline comments для logic span creation/error handling
- [ ] Type hints на всех функциях (Python 3.12+)

### User Documentation
- [ ] doc/embedding-tracing.md (50-100 строк): как работает embedding tracing, какие metrics собираются
- [ ] Примеры в docstrings: как использовать EmbeddingService с tracing

### Configuration Documentation
- [ ] .env.example: добавить EMBEDDING_TRACING_ENABLED
- [ ] README.md: обновить секцию Tracing с информацией об embeddings

## Edge Cases and Error Handling

1. **Очень большие тексты** (> 8000 tokens)
   - Система ДОЛЖНА split на chunks перед embedding
   - Каждый chunk получает отдельный span
   - Все chunks связаны через parent span

2. **Rate limiting от OpenAI**
   - Система ДОЛЖНА обработать 429 response
   - Retry logic с exponential backoff (TBD в separate spec)
   - Span должен содержать retry count

3. **Изменение pricing OpenAI**
   - Система ДОЛЖНА периодически обновлять pricing (daily sync)
   - Cost calculation использует cached pricing
   - Если pricing данные отсутствуют, estimated cost = 0

4. **Embedding для разных языков**
   - Система ДОЛЖНА обработать embedding для non-English текстов
   - Token count должен быть точен (tiktoken поддерживает multi-языковое)
   - Span атрибут `language` не требуется (TBD)
