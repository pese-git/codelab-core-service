# Phase 5: Advanced Tracing - Embedding & Vector Analytics - Design

## Context

**Текущее состояние:**
- Phase 4 завершена: Tool Execution Tracing отслеживает каждый вызов инструмента в Langfuse
- Phase 3: LLM Call Tracing отслеживает LLM запросы и результаты
- Существует структурированное логирование через structlog с контекстом (user_id, workspace_id, agent_id)
- Система использует Qdrant для семантической памяти (RAG контекст)
- Embedding сервис интегрирован с OpenAI API

**Проблема:**
- Операции с embeddings и векторными поисками не трейсируются
- Невозможно отследить: какие embeddings дорогие, какие поиски медленные, какой контекст извлекается
- Анализ качества RAG невозможен без данных о контексте

**Ограничения:**
- Langfuse API имеет rate limits (100 requests/sec)
- Qdrant query API синхронный, требует async обертки
- Overhead трейсирования не должен превышать 50ms за tool execution
- Graceful degradation если Langfuse недоступна (как в Phase 4)

**Stakeholders:**
- Platform Engineers: мониторинг и оптимизация производительности RAG
- Data Scientists: анализ качества контекста и embeddings
- Product: cost optimization и SLA tracking

## Goals / Non-Goals

**Goals:**
- ✅ Каждый вызов embedding (OpenAI, локальные модели) создает Langfuse span с latency, токенами, стоимостью
- ✅ Каждый Qdrant поиск трейсируется: параметры, результаты, время выполнения
- ✅ REST API для анализа: metrics embeddings, ranking по cost/latency, context quality feedback
- ✅ Graceful degradation: система работает если Langfuse offline
- ✅ Минимальный overhead: < 50ms за tool execution
- ✅ Автоматическое распространение контекста (user_id, workspace_id) в spans
- ✅ Интеграция с Phase 4: embedding spans часть полной иерархии (embedding → LLM → tool)

**Non-Goals:**
- ❌ Real-time рекомендации по оптимизации (batch analysis only)
- ❌ Автоматическое переиндексирование vectorstore (manual process)
- ❌ Client-side embedding caching (server-side only, Phase 6)
- ❌ Полнотекстовый поиск по spans (Langfuse native search)
- ❌ Кастомные embedding модели (использует существующие OpenAI)

## Decisions

### 1. Span Hierarchy: Embedding в составе Tool Execution Trace

**Решение:** Embeddings трейсируются как nested spans внутри tool execution span, не отдельно

```
Tool Execution Span
├─ Validation Span
├─ Risk Assessment Span
├─ Approval Span
└─ Execution Span
   ├─ Semantic Memory Retrieval
   │  ├─ Embedding Generation (query)
   │  └─ Vector Search (Qdrant)
   ├─ LLM Call
   │  └─ Embedding (for context - если нужна переградировка)
   └─ Tool Result Span
```

**Обоснование:**
- Embedding операции часть инструмента execution
- Полная видимость в контекст (что retrieval вернул)
- Коррелирует успех инструмента с качеством контекста
- Упрощает анализ cost (по tool, не по embedding)

**Альтернативы рассмотрены:**
- ❌ Отдельные traces для embeddings: теряется контекст какой инструмент их использовал
- ❌ Только custom attributes в tool span: недостаточно деталей для анализа

---

### 2. Architecture для Embedding Service

**Решение:** EmbeddingService оборачивает API вызовы с Langfuse span creation

```python
class EmbeddingService:
    async def embed(
        self, 
        texts: List[str],
        model: str = "text-embedding-3-small",
        span_name: str = "query_embedding"
    ) -> List[List[float]]:
        # 1. Create span в Langfuse (if enabled)
        span = await self.langfuse_integration.create_embedding_span(
            model=model,
            input_count=sum(len(t) for t in texts),
            span_name=span_name
        )
        
        # 2. Call API (OpenAI или локальный)
        start = time.time()
        result = await self._call_embedding_api(texts, model)
        duration = time.time() - start
        
        # 3. End span с результатом (async, fire-and-forget)
        await self.langfuse_integration.end_embedding_span(
            span_id=span.id,
            output_count=len(result),
            latency_ms=duration * 1000,
            status="success"
        )
        
        return result
```

**Обоснование:**
- Minimal overhead (< 5ms за span creation)
- Async fire-and-forget не блокирует execution
- Можем отключить через feature flag если нужно

**Альтернативы:**
- ❌ Middleware на уровне HTTP: слишком позднее перехватывание (теряем локальные модели)
- ✅ Wrapper на уровне API: полный контроль

---

### 3. Vector Search Tracing в Qdrant

**Решение:** VectorStoreService оборачивает Qdrant query с Langfuse spans

```python
class VectorStoreService:
    async def search_similar(
        self,
        query_embedding: List[float],
        top_k: int = 10,
        score_threshold: float = 0.5
    ) -> SearchResults:
        # 1. Create search span
        search_span = await self.langfuse_integration.create_vector_search_span(
            vector_size=len(query_embedding),
            top_k=top_k,
            threshold=score_threshold
        )
        
        # 2. Execute search
        start = time.time()
        try:
            results = await self.qdrant_client.search(
                collection_name=self.collection,
                query_vector=query_embedding,
                limit=top_k,
                score_threshold=score_threshold
            )
            duration = time.time() - start
            
            # 3. End span с результатами
            await self.langfuse_integration.end_vector_search_span(
                span_id=search_span.id,
                results_count=len(results),
                min_score=min(r.score for r in results) if results else 0,
                max_score=max(r.score for r in results) if results else 0,
                latency_ms=duration * 1000,
                status="success"
            )
        except Exception as e:
            await self.langfuse_integration.end_vector_search_span(
                span_id=search_span.id,
                error=str(e),
                status="error"
            )
            raise
```

**Обоснование:**
- Capture параметры для анализа (какой top_k, threshold использовались)
- Capture результаты (сколько найдено, scores range)
- Async для не блокирования main flow

---

### 4. Analytics API Design

**Решение:** REST endpoints для aggregating Langfuse span data

**Endpoints:**

1. **GET /api/traces/embeddings/metrics**
   - Query: workspace_id, model, agent_id, time_range
   - Response: count, avg_latency, p50/p95/p99, total_tokens, estimated_cost
   - Caching: Redis TTL=3600s

2. **GET /api/traces/embeddings/cost-breakdown**
   - Query: workspace_id, by=["agent", "model", "user"]
   - Response: breakdown по agent/model/user с cost и count

3. **GET /api/traces/vector-searches/analytics**
   - Query: workspace_id, agent_id, time_range
   - Response: count, avg_latency, distribution по top_k, results distribution

4. **POST /api/traces/context/feedback**
   - Body: {span_id, relevance_score (0.0-1.0), comments}
   - Сохраняет feedback в Langfuse как custom event
   - Используется для анализа context quality

5. **GET /api/traces/semantic-memory/performance**
   - Consolidated view: embedding latencies, search latencies, context quality
   - Identify bottlenecks и optimization opportunities

**Обоснование:**
- Simple HTTP API для frontend dashboards
- Caching Redis для scalability
- Rate limiting 100 req/min per workspace (как Phase 4)

---

### 5. Cost Attribution Strategy

**Решение:** Использовать Langfuse native cost tracking + custom attributes

```python
# Langfuse span с cost информацией:
span.input_cost = 0.002  # $0.002 для embedding 1000 tokens
span.output_cost = 0.000  # embeddings not charged per-output
span.cost = 0.002  # total

# Custom attributes для breakdown:
span.custom_attributes = {
    "embedding_model": "text-embedding-3-small",
    "token_count": 1000,
    "workspace_id": "ws-123",
    "agent_id": "agent-456",
    "context_type": "rag_retrieval"  # vs reranking, etc
}
```

**Aggregation query:**
```sql
SELECT 
    custom_attributes['agent_id'] as agent_id,
    custom_attributes['embedding_model'] as model,
    SUM(cost) as total_cost,
    COUNT(*) as count,
    AVG(duration) as avg_latency
FROM traces
WHERE span_type = 'embedding'
GROUP BY agent_id, model
```

**Обоснование:**
- Langfuse поддерживает cost tracking natively
- Custom attributes для flexible aggregation
- SQL queries для любых комбинаций breakdown

---

### 6. Error Handling и Degradation

**Решение:** Graceful fallback если Langfuse unavailable (как Phase 4)

```python
async def create_embedding_span(...):
    if not self.langfuse_enabled:
        return DummySpan(id="dummy")  # No-op span
    
    try:
        span = self.langfuse_client.span(
            name=span_name,
            input=inputs
        )
        return span
    except Exception as e:
        self.logger.error(f"Failed to create span: {e}")
        self.metrics.increment("embedding_trace_failures")
        return DummySpan(id="dummy")  # Continue without tracing
```

**Обоснование:**
- Embedding операции не должны зависеть от Langfuse availability
- Soft failures предпочтительнее hard failures
- Monitoring/alerting на trace failures

---

## Risks / Trade-offs

### Risk 1: Langfuse API Rate Limits
**Описание:** 100 requests/sec limit, embedding spans могут превысить
**Mitigation:**
- Batch span creation (отправлять 50 spans за раз)
- Redis queue для retry logic
- Feature flag для отключения embedding tracing если нужно

### Risk 2: Vector Search Latency Regression
**Описание:** Async span creation может добавить latency к search операциям
**Mitigation:**
- Fire-and-forget async отправка (не await span completion)
- Max overhead target < 10ms - если превышается, отключаем
- Performance tests на каждый commit

### Risk 3: Redis Cache Invalidation
**Описание:** Metrics cache может быть stale
**Mitigation:**
- TTL = 3600s (1 hour) - acceptable для non-critical analytics
- Manual invalidation endpoint для admin если нужно свежие данные
- Background refresh перед TTL expiry

### Risk 4: Cost Attribution Accuracy
**Описание:** OpenAI embedding costs меняются, нужно актуально
**Mitigation:**
- Загружать pricing из OpenAI API регулярно (daily sync)
- Store в config, use при span creation
- Мониторить diff между estimated и actual costs

### Trade-off: Span Creation vs Performance
**Trade:** More detailed spans (каждый embedding отдельный span) vs higher overhead
**Решение:** Minimum viable spans (только уровень embedding retrieval + vector search)

### Trade-off: Real-time Analytics vs Batch Processing
**Trade:** Real-time dashboards требуют indexed data
**Решение:** Batch processing с hourly aggregation, real-time через Redis cache

## Migration Plan

### Step 1: Feature Flags (0 impact)
```bash
EMBEDDING_TRACING_ENABLED=false  # Default off
VECTOR_SEARCH_TRACING_ENABLED=false
EMBEDDING_ANALYTICS_API_ENABLED=false
```

### Step 2: EmbeddingService Integration (staging only)
- Deploy code with feature flags OFF
- Internal testing: verify no overhead
- Staging: enable flags, monitor metrics

### Step 3: Vector Search Integration (staging only)
- Same as Step 2: code first, flags OFF, test, enable

### Step 4: Analytics API (staging)
- Deploy endpoints with feature flags OFF
- Internal users test API contracts

### Step 5: Gradual Rollout to Production
1. Day 1: Enable embedding tracing for 10% workspaces
   - Monitor: span creation success rate, latency overhead
   - Alert threshold: > 5% failures or > 50ms overhead
2. Day 2: Rollout to 50% if metrics OK
3. Day 3-4: 100% rollout
4. Day 5+: Enable vector search tracing (same gradual rollout)
5. Week 2: Enable analytics endpoints (lower risk)

### Rollback Procedure
```bash
# If metrics degradation detected:
export EMBEDDING_TRACING_ENABLED=false
export VECTOR_SEARCH_TRACING_ENABLED=false
# Restart app, verify metrics return to normal
```

## Open Questions

1. **Embedding Model Pricing**: Как обновлять pricing если OpenAI меняет rates?
   - Proposal: Daily sync из OpenAI API, cache в config
   
2. **Context Relevance Scoring**: Как пользователи будут отправлять relevance feedback?
   - Proposal: Frontend UI для rating context relevance (0-5 stars)
   - Stored as custom event в Langfuse
   
3. **Qdrant Index Stats**: Нужны ли метрики по Qdrant collection stats (size, count)?
   - Proposal: Separate endpoint /api/traces/vector-stores/stats
   - Можно добавить в Phase 5.1
   
4. **Long-tail Embeddings**: Как обрабатывать embeddings для документов > 8000 tokens?
   - Proposal: Split на chunks, trace каждый, aggregate в parent span

5. **Vector Search Reranking**: Если добавим reranking шаг, как трейсировать?
   - Proposal: Дополнительный nested span внутри search span
