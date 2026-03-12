# Улучшения интеграции Langfuse для LLM Observability

## Обзор внесенных улучшений

Документ описывает критические улучшения в интеграции Langfuse для полного observability мультиагентной LLM системы.

### Дата реализации
2026-03-12

### Версия
1.0

---

## 1. Новые компоненты

### 1.1 Декораторы для LLM вызовов (`app/services/langfuse_decorators.py`)

**Назначение:** Автоматический трейсинг LLM вызовов в Langfuse.

**Основные декораторы:**

#### `@trace_llm_call(name="llm_generation")`
Оборачивает вызовы OpenAI API и автоматически создает Langfuse spans.

```python
from app.services.langfuse_decorators import trace_llm_call

class ContextualAgent:
    @trace_llm_call(name="agent_llm_generation")
    async def _call_llm(self, messages, model, langfuse_trace=None):
        """LLM вызов с автоматическим трейсингом."""
        return await self.openai_client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        )
```

**Автоматически захватывает:**
- Input: model, temperature, max_tokens, top_p
- Output: content, finish_reason, tokens, latency
- Metadata: status, error type, latency_ms

#### `@trace_embedding_call(name="embedding_generation")`
Оборачивает embedding вызовы.

```python
@trace_embedding_call(name="agent_embedding")
async def get_embeddings(self, texts, langfuse_trace=None):
    return await self.embedding_client.create(input=texts)
```

---

### 1.2 Сервис метрик качества (`app/services/quality_metrics.py`)

**Назначение:** Централизованный сбор метрик качества и бизнес-событий.

**Методы:**

```python
from app.services.quality_metrics import QualityMetricsCollector

# Записать успех/ошибку задачи
await QualityMetricsCollector.record_task_completion(
    trace_id=trace.id,
    success=True,
    error_type=None,
    duration_ms=1500,
)

# Записать релевантность контекста
await QualityMetricsCollector.record_context_relevance(
    trace_id=trace.id,
    relevance_score=0.95,
    documents_count=5,
)

# Записать выполнение инструмента
await QualityMetricsCollector.record_tool_execution(
    trace_id=trace.id,
    tool_name="search_tool",
    success=True,
    execution_time_ms=250,
)

# Записать качество ответа
await QualityMetricsCollector.record_response_quality(
    trace_id=trace.id,
    quality_score=0.88,
    quality_reason="Relevant and well-structured response",
)

# Записать стоимость LLM вызова
await QualityMetricsCollector.record_llm_cost(
    trace_id=trace.id,
    model="gpt-4",
    prompt_tokens=150,
    completion_tokens=200,
    cost=0.015,
)

# Записать передачу управления между агентами
await QualityMetricsCollector.record_agent_handoff(
    trace_id=trace.id,
    from_agent="research_agent",
    to_agent="writing_agent",
    handoff_reason="Need to write summary",
)
```

---

### 1.3 API Endpoints для feedback (`app/routes/feedback.py`)

**Назначение:** Собирать feedback от пользователей.

**Endpoints:**

#### POST `/feedback/traces/{trace_id}/rating`
Оценить ответ агента (1-5 звезд).

```bash
curl -X POST "http://localhost:8000/feedback/traces/trace-123/rating?rating=5&comment=Excellent%20response" \
  -H "Authorization: Bearer $TOKEN"
```

**Response:**
```json
{
  "success": true,
  "trace_id": "trace-123",
  "rating": 5,
  "normalized_score": 1.0
}
```

#### POST `/feedback/traces/{trace_id}/thumbs`
Простой thumbs up/down feedback.

```bash
curl -X POST "http://localhost:8000/feedback/traces/trace-123/thumbs?thumbs_up=true" \
  -H "Authorization: Bearer $TOKEN"
```

#### POST `/feedback/traces/{trace_id}/scores/{score_name}`
Записать пользовательскую оценку.

```bash
curl -X POST "http://localhost:8000/feedback/traces/trace-123/scores/relevance?score_value=0.85" \
  -H "Authorization: Bearer $TOKEN"
```

---

### 1.4 Context Manager для spans (`app/services/langfuse_integration.py`)

**Новый метод:** `span_context()`

Удобный контекст-менеджер для создания spans с автоматическим управлением lifecycle.

```python
async def execute(self, user_message: str, langfuse_trace=None):
    # Context retrieval span
    async with langfuse.span_context(
        trace=langfuse_trace,
        name="context_retrieval",
        input_data={"query": user_message[:100]},
    ) as ctx_span:
        context = await self.context_store.search(user_message)
        
        await QualityMetricsCollector.record_context_relevance(
            trace_id=langfuse_trace.id,
            relevance_score=context[0].score if context else 0.0,
            documents_count=len(context),
        )
    
    # LLM generation span
    async with langfuse.span_context(
        trace=langfuse_trace,
        name="llm_generation",
        input_data={"context_size": len(context)},
    ) as llm_span:
        response = await self._call_llm(messages, langfuse_trace=langfuse_trace)
    
    # Tool execution span
    if response.tool_calls:
        async with langfuse.span_context(
            trace=langfuse_trace,
            name="tool_execution",
            input_data={"tools": [t.name for t in response.tool_calls]},
        ) as tool_span:
            results = await self._execute_tools(response.tool_calls)
    
    return response
```

**Особенности:**
- Автоматический подсчет latency
- Автоматическая запись ошибок
- Graceful degradation если Langfuse disabled

---

### 1.5 Интеграция LiteLLM callbacks

**Изменение:** `app/services/litellm_client.py`

Добавлен метод `_setup_langfuse_callbacks()` который:
- Включает Langfuse callbacks в LiteLLM
- Устанавливает credentials из конфигурации
- Автоматически захватывает все LLM вызовы

```python
class LiteLLMClient:
    def __init__(self):
        # ... existing code ...
        self._setup_langfuse_callbacks()  # Новая строка
```

**Преимущества:**
- ✅ Все LLM вызовы автоматически трейсятся
- ✅ Токены и стоимость автоматически подсчитываются
- ✅ Поддержка streaming
- ✅ Минимальные изменения кода

---

## 2. Полный пример использования

### Сценарий: Agent Execution с полным трейсингом

```python
from app.services.langfuse_integration import get_langfuse
from app.services.langfuse_decorators import trace_llm_call
from app.services.quality_metrics import QualityMetricsCollector

class ContextualAgent:
    @trace_llm_call(name="agent_llm_generation")
    async def _call_llm(self, messages, model, langfuse_trace=None):
        """LLM вызов с автоматическим трейсингом."""
        return await self.openai_client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=self.config.temperature,
        )
    
    async def execute(
        self,
        user_message: str,
        session_history: list[dict] | None = None,
        session_id: UUID | None = None,
        langfuse_trace: Any | None = None,
    ) -> dict[str, Any]:
        """Execute agent with full Langfuse tracing."""
        
        langfuse = get_langfuse()
        
        # Создать trace если не передан
        if not langfuse_trace and langfuse.enabled:
            langfuse_trace = langfuse.create_trace(
                name=f"agent_{self.agent_name}",
                user_id=self.user_id,
                workspace_id=session_id,
                metadata={
                    "agent_id": str(self.agent_id),
                    "agent_name": self.agent_name,
                    "model": self._get_model_name(),
                },
            )
        
        try:
            # 1. Context Retrieval Span
            async with langfuse.span_context(
                trace=langfuse_trace,
                name="context_retrieval",
                input_data={"query": user_message[:100]},
            ):
                context = await self.context_store.search(
                    query=user_message,
                    limit=self.config.context_search_limit,
                )
                
                # Записать релевантность контекста
                if context:
                    await QualityMetricsCollector.record_context_relevance(
                        trace_id=langfuse_trace.id,
                        relevance_score=context[0].score,
                        documents_count=len(context),
                    )
            
            # 2. Prepare Messages Span
            async with langfuse.span_context(
                trace=langfuse_trace,
                name="prepare_messages",
                input_data={"context_docs": len(context) if context else 0},
            ):
                messages = self._prepare_messages(
                    user_message=user_message,
                    context=context,
                    session_history=session_history,
                )
            
            # 3. LLM Generation Span (с автоматическим трейсингом через декоратор)
            response = await self._call_llm(
                messages=messages,
                model=self._get_model_name(),
                langfuse_trace=langfuse_trace,  # Передать trace в декоратор
            )
            
            # 4. Tool Execution Span (если нужно)
            if response.tool_calls:
                async with langfuse.span_context(
                    trace=langfuse_trace,
                    name="tool_execution",
                    input_data={
                        "tools": [tc.function.name for tc in response.tool_calls]
                    },
                ):
                    for tool_call in response.tool_calls:
                        tool_start = time.time()
                        try:
                            result = await self._execute_tool(tool_call)
                            tool_duration = int((time.time() - tool_start) * 1000)
                            
                            await QualityMetricsCollector.record_tool_execution(
                                trace_id=langfuse_trace.id,
                                tool_name=tool_call.function.name,
                                success=True,
                                execution_time_ms=tool_duration,
                            )
                        except Exception as e:
                            tool_duration = int((time.time() - tool_start) * 1000)
                            await QualityMetricsCollector.record_tool_execution(
                                trace_id=langfuse_trace.id,
                                tool_name=tool_call.function.name,
                                success=False,
                                execution_time_ms=tool_duration,
                                error_message=str(e),
                            )
            
            # Записать качество ответа
            task_duration = int((time.time() - execution_start) * 1000)
            await QualityMetricsCollector.record_task_completion(
                trace_id=langfuse_trace.id,
                success=True,
                duration_ms=task_duration,
            )
            
            # Flush данные при завершении
            langfuse.flush()
            
            return {
                "response": response.content,
                "trace_id": langfuse_trace.id if langfuse_trace else None,
            }
        
        except Exception as e:
            # Записать ошибку
            if langfuse_trace:
                await QualityMetricsCollector.record_task_completion(
                    trace_id=langfuse_trace.id,
                    success=False,
                    error_type=type(e).__name__,
                )
                langfuse.flush()
            
            raise
```

---

## 3. Интеграция с Frontend

### Пример: Отправка feedback после ответа

```javascript
// client.js
async function sendUserFeedback(traceId, rating, comment) {
    const response = await fetch(
        `/api/feedback/traces/${traceId}/rating?rating=${rating}&comment=${encodeURIComponent(comment)}`,
        {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${userToken}`,
            },
        }
    );
    
    const result = await response.json();
    console.log('Feedback recorded:', result);
    return result;
}

// Использование
const { trace_id } = await agent.execute(message);
await sendUserFeedback(trace_id, 5, 'Great answer!');
```

---

## 4. Мониторинг и аналитика

### Ключевые метрики в Langfuse

После внедрения улучшений можно отслеживать:

1. **Performance Metrics**
   - `agent_execution_latency` - время выполнения агента
   - `llm_generation_latency` - время LLM вызова
   - `tool_execution_latency` - время выполнения инструментов

2. **Quality Metrics**
   - `user_satisfaction` - оценка пользователя (1-5)
   - `context_relevance` - релевантность контекста (0-1)
   - `response_quality` - качество ответа (0-1)
   - `task_success` - успех выполнения задачи (0-1)

3. **Cost Metrics**
   - `llm_cost` - стоимость LLM вызова
   - `total_tokens` - общее количество токенов
   - `prompt_tokens` - количество prompt токенов

4. **Business Metrics**
   - `agent_handoff` - события передачи управления
   - `tool_execution_success` - успех выполнения инструментов

---

## 5. Рекомендации по миграции

### Phase 1: Базовая интеграция (1 неделя)

1. ✅ Добавить `@trace_llm_call` декоратор на LLM вызовы в ContextualAgent
2. ✅ Включить LiteLLM callbacks через `_setup_langfuse_callbacks()`
3. ✅ Добавить `span_context()` для основных шагов (context, llm, tools)

### Phase 2: Метрики качества (1 неделя)

4. ✅ Добавить `QualityMetricsCollector` вызовы для каждого шага
5. ✅ Интегрировать feedback API endpoints
6. ✅ Настроить сбор пользовательских оценок

### Phase 3: Аналитика (2 недели)

7. Создать Grafana dashboards для ключевых метрик
8. Настроить Prometheus alerts
9. Реализовать cost tracking по агентам

---

## 6. Best Practices

### Что логировать в Langfuse

✅ **Логировать:**
- Метаданные (user_id, agent_id, model)
- Timing метрики (latency, duration)
- Статусы (success, error, status codes)
- Token counts и stоимость
- Tool execution results (sanitized)
- User feedback и ratings

❌ **НЕ логировать:**
- API ключи и токены
- Пароли
- Full PII (email, phone, addresses)
- Sensitive database content

⚠️ **Логировать осторожно (sanitized):**
- User messages (маскировать PII)
- LLM responses (truncate большие)
- Tool parameters
- Database queries

### Управление данными

**Retention Policy:**
- Hot tier (0-7 дней): PostgreSQL, полный доступ
- Warm tier (7-30 дней): PostgreSQL, сжатие
- Cold tier (30-90 дней): S3 архив
- Удаление (>90 дней)

---

## 7. Troubleshooting

### Проблема: Traces не появляются в Langfuse

**Решение:**
1. Проверить `LANGFUSE_ENABLED=true` в .env
2. Проверить LANGFUSE_HOST доступность
3. Проверить credentials (public_key, secret_key)
4. Смотреть логи: `langfuse_trace_creation_failed`

### Проблема: Высокая latency на LLM вызовах

**Решение:**
1. Проверить Prometheus метрики `langfuse_trace_creation_latency_seconds`
2. Проверить размер payload (может быть truncated)
3. Проверить network connectivity к Langfuse
4. Увеличить batch_size в LiteLLM конфигурации

### Проблема: Много ошибок в callbacks

**Решение:**
1. Проверить `langfuse_callback_failures` метрику
2. Проверить логи для типов ошибок
3. Проверить конфигурацию Langfuse в LiteLLM
4. Проверить доступность Langfuse API

---

## 8. Дополнительные ресурсы

- [Langfuse Documentation](https://langfuse.com/docs)
- [LiteLLM Callbacks](https://docs.litellm.ai/docs/observability/callbacks)
- [OpenAI Python Client](https://github.com/openai/openai-python)

---

## История изменений

| Дата | Версия | Изменения |
|------|--------|-----------|
| 2026-03-12 | 1.0 | Первая версия с улучшениями |

