# Vector Similarity Tracing - Спецификация

## ADDED Requirements

### Requirement: Трейсирование операций поиска сходства в Qdrant

Система ДОЛЖНА автоматически создавать Langfuse span для каждого вызова Qdrant similarity search с захватом параметров запроса, результатов и latency.

#### Scenario: Успешный вектор поиск с параметрами

- **WHEN** VectorStoreService вызывает `search_similar(query_embedding=[...], top_k=10, score_threshold=0.5)`
- **THEN** система создает Langfuse span с именем "vector_search"
- **AND** span содержит custom attributes:
  - `vector_size` = длина query_embedding (e.g. 1536 для text-embedding-3-small)
  - `top_k` = 10
  - `score_threshold` = 0.5
  - `distance_metric` = "cosine" (или другая метрика)
  - `collection_name` = имя Qdrant collection (e.g. "agent_context_123")
- **AND** span содержит результаты поиска после выполнения:
  - `results_count` = количество найденных точек
  - `min_score` = минимальное значение сходства из результатов
  - `max_score` = максимальное значение сходства из результатов
  - `avg_score` = среднее значение сходства
- **AND** span содержит `latency_ms` = время выполнения Qdrant запроса
- **AND** span содержит `status` = "success"

#### Scenario: Поиск с нулевыми результатами

- **WHEN** вектор поиск не находит совпадений (нет points с score >= threshold)
- **THEN** span создается с `results_count` = 0
- **AND** `min_score` и `max_score` = null (или 0)
- **AND** span всё ещё содержит все остальные параметры
- **AND** статус = "success" (нулевые результаты - не ошибка)

#### Scenario: Отключение tracing через feature flag

- **WHEN** `VECTOR_SEARCH_TRACING_ENABLED=false` установлен в окружении
- **THEN** VectorStoreService не создает Langfuse spans
- **AND** Qdrant запрос выполняется без overhead от tracing

#### Scenario: Обработка Qdrant ошибок

- **WHEN** Qdrant API возвращает ошибку (connection refused, timeout, invalid collection)
- **THEN** система создает span с статусом "error"
- **AND** span содержит атрибут `error_code` (e.g. "collection_not_found")
- **AND** span содержит атрибут `error_message` с описанием
- **AND** exception пробрасывается дальше (not caught at span level)

#### Scenario: Graceful degradation если Langfuse unavailable

- **WHEN** Langfuse API недоступна при попытке создать vector search span
- **THEN** VectorStoreService логирует warning
- **AND** Qdrant запрос продолжает выполняться (не зависит от Langfuse)
- **AND** метрика `vector_search_trace_failures` инкрементируется

### Requirement: Контекст и изоляция по workspace для vector searches

Система ДОЛЖНА автоматически добавлять workspace/agent контекст в vector search spans.

#### Scenario: Context propagation в vector search span

- **WHEN** vector search происходит в контексте tool execution с workspace контекстом
- **THEN** vector search span содержит custom attributes:
  - `workspace_id` (из structlog.context)
  - `agent_id` (из structlog.context)
  - `user_id` (из structlog.context)
- **AND** span может быть отфильтрован по workspace и агентам для analytics

#### Scenario: Isolation по workspace в queries

- **WHEN** два пользователя из разных workspace выполняют одновременно vector searches
- **THEN** их spans создаются с разными `workspace_id` атрибутами
- **AND** queries для analytics автоматически фильтруют по текущему workspace

### Requirement: Async fire-and-forget отправка vector search spans

Система ДОЛЖНА отправлять spans асинхронно без блокирования основного flow.

#### Scenario: Non-blocking vector search completion

- **WHEN** Qdrant search операция завершается
- **THEN** система создает coroutine для отправки span в Langfuse
- **AND** основной search результат возвращается сразу
- **AND** span отправляется в background task queue с таймаутом 5 секунд

#### Scenario: Performance overhead для search

- **WHEN** 50 последовательных vector search операций выполняются
- **THEN** общее время с tracing < на 50ms больше чем без tracing
- **AND** средний overhead за один search < 10ms
- **AND** p99 overhead < 20ms

### Requirement: Tracking результатов поиска для анализа качества

Система ДОЛЖНА сохранять информацию о результатах поиска для последующего анализа качества RAG.

#### Scenario: Результаты поиска в span

- **WHEN** vector search возвращает результаты
- **THEN** span содержит массив `search_results` с сохранением:
  - Количество результатов (results_count)
  - Score распределение (min/max/avg)
  - Список top-3 point IDs (для trace-back в Qdrant)
- **AND** эта информация используется в анализе context quality

#### Scenario: Сохранение metadata результатов

- **WHEN** Qdrant points содержат metadata (e.g. document_id, chunk_index)
- **THEN** top-1 результата metadata сохраняется в span как custom attribute
- **AND** это помогает identify какой документ был возвращен в контексте

## MODIFIED Requirements

### Requirement: Agent Context Store isolation

Существующее требование: Vector Store ДОЛЖНА быть изолирована по workspace.

**Обновление**: Vector search spans ДОЛЖНЫ быть также изолированы по workspace для аудита и анализа.

#### Scenario: Search isolation по workspace

- **WHEN** AgentContextStore выполняет vector search для context retrieval
- **THEN** поиск выполняется в workspace-specific collection
- **AND** span содержит workspace_id для аудита
- **AND** cost attribution может быть вычислена per workspace

## Testing Requirements

### Unit Tests
- [ ] `test_vector_search_span_creation_success` - успешное создание span
- [ ] `test_vector_search_span_zero_results` - span при нулевых результатах
- [ ] `test_vector_search_span_error_handling` - обработка Qdrant ошибок
- [ ] `test_vector_search_graceful_degradation` - Langfuse unavailable
- [ ] `test_vector_search_context_propagation` - контекст из structlog
- [ ] `test_vector_search_async_fire_and_forget` - async отправка spans
- [ ] `test_vector_search_feature_flag_disabled` - отключение через flag
- [ ] `test_vector_search_score_calculations` - min/max/avg score

### Integration Tests
- [ ] `test_vector_search_with_real_qdrant` - вызов реального Qdrant (или docker)
- [ ] `test_vector_search_with_langfuse_integration` - полная интеграция
- [ ] `test_vector_search_in_context_retrieval` - в составе context retrieval flow
- [ ] `test_vector_search_workspace_isolation` - isolation по workspace

### Performance Tests
- [ ] `test_vector_search_overhead_single` - overhead < 10ms за search
- [ ] `test_vector_search_overhead_batch_50` - batch overhead < 50ms
- [ ] `test_vector_search_concurrent_100` - 100 concurrent searches

### Code Coverage
- [ ] `app/services/vector_store_service.py`: >= 95% coverage
- [ ] `app/services/langfuse_integration.py` (vector search методы): >= 90% coverage

## Documentation Requirements

### Code Documentation
- [ ] Docstrings для всех public методов VectorStoreService на русском
- [ ] Inline comments для span creation и error handling logic
- [ ] Type hints на всех функциях

### User Documentation
- [ ] doc/vector-search-tracing.md (50-100 строк): как работает vector search tracing
- [ ] Примеры в docstrings: как использовать search с tracing

### Configuration Documentation
- [ ] .env.example: добавить VECTOR_SEARCH_TRACING_ENABLED
- [ ] README.md: обновить Tracing секцию

## Edge Cases and Error Handling

1. **Очень большие vectors** (> 2000 dimensions)
   - Система ДОЛЖНА обработать без ошибок
   - Span size может быть большой (но не должна вызывать Langfuse limit issues)

2. **Qdrant timeout**
   - Если поиск занимает > 10 секунд, Qdrant killает операцию
   - Span ДОЛЖЕН быть создан с `status="timeout"`

3. **Пустой query embedding**
   - Если query_embedding = null/empty list
   - Система ДОЛЖНА выбросить error перед созданием span
   - Error обработана на уровне выше (validation)

4. **Изменение collection структуры**
   - Если Qdrant collection schema меняется (размер векторов)
   - Searches могут начать failen
   - Span ДОЛЖЕН содержать error с информацией о mismatch

5. **Batch searches**
   - Если выполняется несколько searches для разных queries
   - Каждый search получает отдельный span
   - Система ДОЛЖНА связать их через parent span если нужно
