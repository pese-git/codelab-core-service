# Design: Tool Execution Tracing

## Context

### Current State
- **Фаза 1-3 завершены**: Langfuse integration для LLM вызовов и embedding запросов
- **LangfuseIntegration service**: Управляет lifecycle, graceful degradation, context propagation
- **LiteLLM callbacks**: Автоматически отправляют LLM операции в Langfuse
- **Agent workflow tracing**: Root traces для multi-step workflows с nested spans
- **Tool execution system**: Существует Tool executor, risk assessor, approval workflow

### Problem
1. **Tool execution не трейсится в Langfuse** - невозможно увидеть какие tools вызывались, параметры, результаты
2. **Нет видимости цепочки**: LLM → Tool → Result - логирование разделено между разными системами
3. **Ошибки в tools не записываются** - нет visibility в случае failures без проброса exception'ов
4. **Отсутствует аналитика по tool usage** - нет данных о frequency, latency, success rate

### Constraints
- Tool execution ДОЛЖНА быть graceful - ошибки трейсинга не должны прерывать выполнение tool'а
- Minimal overhead - трейсинг не должен замедлить tool execution (< 50ms async)
- Nested spans - tool execution traces связаны с parent LLM call (если есть)
- Context propagation - user_id, workspace_id, agent_name извлекаются из structlog context
- Zero exception propagation из tracing кода

### Stakeholders
- Backend engineers (интеграция трейсинга в tool executor)
- Product team (аналитика tool usage, optimization)
- QA (тестирование graceful degradation для tools)

---

## Goals / Non-Goals

### Goals
1. **Tool execution capture**: Автоматический capture всех tool invocations с параметрами, результатом, временем
2. **Error resilience**: Ошибки в tool выполнении логируются без влияния на агент
3. **Nested trace hierarchy**: Tool execution spans связаны с parent LLM call и agent trace
4. **Tool performance analytics**: REST API для tool metrics (usage frequency, latency percentiles, success rate)
5. **Quality feedback for tools**: Возможность записать scores для tool execution (relevance, correctness)
6. **Graceful degradation**: При недоступности Langfuse tool выполнение продолжается без изменений

### Non-Goals
- Real-time tool execution monitoring dashboard (асинхронная batch отправка)
- Автоматическое блокирование tools на основе performance metrics
- Tracing tool execution внутри клиента (только backend server-side)
- Custom обучение моделей на tool execution traces

---

## Decisions

### Decision 1: Tool Execution Span Creation in LangfuseIntegration

**What**: Расширить `LangfuseIntegration.create_span()` для поддержки tool execution spans с автоматическим nested связыванием.

**Why**:
- Унифицированный API для всех spans (LLM, embedding, tool)
- Автоматическое связывание с parent span (если есть в context)
- Graceful handling ошибок без проброса exception'ов
- Простота тестирования

**Implementation**:
```python
class LangfuseIntegration:
    def create_tool_execution_span(
        self,
        tool_name: str,
        input_params: Dict,
        parent_span_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> Optional[ToolExecutionSpan]:
        """
        Создает span для tool execution.
        
        Если parent_span_id предоставлен - создает nested span.
        Если контекст содержит текущий span - автоматически используется как parent.
        """
        if not self.enabled:
            return None
        
        try:
            span = self.client.span(
                name=f"tool_{tool_name}",
                input={"params": input_params},
                parent_observation_id=parent_span_id or self._get_current_span_id(),
            )
            return ToolExecutionSpan(span=span, tool_name=tool_name)
        except Exception as e:
            logger.error(f"Failed to create tool span: {e}", exc_info=True)
            return None
    
    def end_tool_execution_span(
        self,
        span_obj: ToolExecutionSpan,
        result: Any = None,
        error: Optional[Exception] = None,
    ) -> None:
        """Завершает tool execution span с результатом или ошибкой."""
        if not span_obj or not self.enabled:
            return
        
        try:
            output = {
                "result": result if result is not None else {},
                "success": error is None,
            }
            if error:
                output["error"] = {
                    "type": type(error).__name__,
                    "message": str(error),
                }
            
            span_obj.span.end(output=output)
        except Exception as e:
            logger.error(f"Failed to end tool span: {e}", exc_info=True)
```

**Nested span hierarchy**:
```
trace (agent_workflow)
├── span (llm_call)
│   └── span (tool_execution_1)
│       ├── span (tool_validation)
│       ├── span (risk_assessment)
│       ├── span (approval_workflow)
│       └── span (tool_execution_client)
├── span (tool_execution_2)
└── span (llm_call)
```

---

### Decision 2: Tool Executor Integration Point

**What**: Интегрировать `LangfuseIntegration.create_tool_execution_span()` в `ToolExecutor.execute_tool()` для автоматического трейсинга.

**Why**:
- Tool executor - центральная точка для всех tool invocations
- Можем захватить полный lifecycle: validation → risk assessment → approval → execution
- Graceful degradation встроена в execution flow

**Implementation**:
```python
class ToolExecutor:
    def __init__(self, langfuse_integration: LangfuseIntegration):
        self.langfuse = langfuse_integration
    
    async def execute_tool(
        self,
        tool_name: str,
        params: Dict,
        user_id: str,
        workspace_id: str,
    ) -> ToolResult:
        """
        Выполняет tool с полным трейсингом.
        """
        # Создаем root span для tool execution
        tool_span = self.langfuse.create_tool_execution_span(
            tool_name=tool_name,
            input_params=params,
            metadata={
                "user_id": user_id,
                "workspace_id": workspace_id,
            }
        )
        
        result = None
        error = None
        
        try:
            # Валидация
            validation_span = self.langfuse.create_tool_execution_span(
                tool_name=f"{tool_name}_validation",
                input_params={},
                parent_span_id=tool_span.span_id if tool_span else None,
            )
            try:
                validated_params = self._validate_tool_params(tool_name, params)
                self.langfuse.end_tool_execution_span(validation_span, result={"valid": True})
            except Exception as e:
                self.langfuse.end_tool_execution_span(validation_span, error=e)
                raise
            
            # Risk assessment
            risk_span = self.langfuse.create_tool_execution_span(
                tool_name=f"{tool_name}_risk_assessment",
                input_params={},
                parent_span_id=tool_span.span_id if tool_span else None,
            )
            try:
                risk_level = await self.risk_assessor.assess_tool_risk(tool_name, params)
                self.langfuse.end_tool_execution_span(
                    risk_span,
                    result={"risk_level": risk_level.value}
                )
            except Exception as e:
                self.langfuse.end_tool_execution_span(risk_span, error=e)
                raise
            
            # Approval workflow (если нужно)
            if risk_level in [RiskLevel.HIGH, RiskLevel.MEDIUM]:
                approval_span = self.langfuse.create_tool_execution_span(
                    tool_name=f"{tool_name}_approval",
                    input_params={},
                    parent_span_id=tool_span.span_id if tool_span else None,
                )
                try:
                    approval = await self.approval_manager.request_approval(tool_name, params)
                    self.langfuse.end_tool_execution_span(
                        approval_span,
                        result={"approved": approval.status == ApprovalStatus.APPROVED}
                    )
                except Exception as e:
                    self.langfuse.end_tool_execution_span(approval_span, error=e)
                    raise
            
            # Execution
            execution_span = self.langfuse.create_tool_execution_span(
                tool_name=f"{tool_name}_execution",
                input_params={},
                parent_span_id=tool_span.span_id if tool_span else None,
            )
            try:
                result = await self._invoke_tool(tool_name, validated_params)
                self.langfuse.end_tool_execution_span(execution_span, result=result)
            except Exception as e:
                self.langfuse.end_tool_execution_span(execution_span, error=e)
                raise
            
        except Exception as e:
            error = e
            logger.error(f"Tool execution failed: {tool_name}", exc_info=True)
            # NOT re-raising - graceful degradation
        finally:
            # Завершаем root span
            self.langfuse.end_tool_execution_span(tool_span, result=result, error=error)
        
        return ToolResult(
            tool_name=tool_name,
            success=error is None,
            result=result,
            error=error,
        )
```

**Flow with graceful degradation**:
```
1. Tool executor получает запрос
2. Если Langfuse enabled → create root span
3. Выполняем validation (traced)
4. Выполняем risk assessment (traced)
5. Если нужно - approval workflow (traced)
6. Выполняем инструмент (traced)
7. Завершаем span с результатом или ошибкой
8. Возвращаем результат агенту
   ↳ Если Langfuse unavailable → все шаги выполняются, spans создаются как no-op
```

---

### Decision 3: Tool Performance Analytics API

**What**: Создать REST endpoints в `app/routes/traces.py` для получения tool metrics из Langfuse.

**Why**:
- Product team может анализировать tool usage patterns
- Identify underperforming tools (high latency, low success rate)
- Make data-driven decisions на tool selection optimization

**Implementation**:
```python
@router.get("/api/traces/tools/metrics")
async def get_tool_metrics(
    workspace_id: str,
    tool_name: Optional[str] = None,
    period_days: int = 7,
    current_user: User = Depends(get_current_user),
) -> ToolMetricsResponse:
    """
    Возвращает metrics по tool execution за период.
    
    Response:
    {
        "tool_name": "search_docs",
        "total_invocations": 1245,
        "success_count": 1198,
        "error_count": 47,
        "success_rate": 0.962,
        "avg_latency_ms": 234.5,
        "p95_latency_ms": 456,
        "p99_latency_ms": 678,
        "most_common_errors": [
            {"error_type": "timeout", "count": 34},
            {"error_type": "validation_error", "count": 13},
        ]
    }
    """
    return await langfuse_integration.get_tool_metrics(
        workspace_id=workspace_id,
        tool_name=tool_name,
        period_days=period_days,
    )

@router.get("/api/traces/tools/ranking")
async def get_tool_ranking(
    workspace_id: str,
    metric: str = "success_rate",  # success_rate, avg_latency, invocation_count
    limit: int = 10,
    current_user: User = Depends(get_current_user),
) -> List[ToolMetrics]:
    """Возвращает ranked list tools по выбранной метрике."""
    return await langfuse_integration.get_tool_ranking(
        workspace_id=workspace_id,
        metric=metric,
        limit=limit,
    )
```

---

### Decision 4: Error Handling Strategy - Graceful Degradation

**What**: Все ошибки трейсинга обрабатываются асинхронно без propagation в основной execution flow.

**Why**:
- Tool execution НИКОГДА не должна быть blocked на tracing
- Langfuse может быть недоступен/overloaded - система продолжает работать
- Graceful degradation - ключевое требование Фазы 3

**Implementation**:
```python
class LangfuseIntegration:
    async def _send_trace_async(self, trace_data: Dict) -> None:
        """
        Отправляет trace асинхронно в фоне.
        Ошибки логируются но не propagate.
        """
        try:
            # Отправляем с таймаутом - не ждем больше 5 секунд
            async with asyncio.timeout(5):
                await self.client.send_async(trace_data)
        except asyncio.TimeoutError:
            logger.warning(f"Langfuse trace timeout, dropping batch")
        except Exception as e:
            # Логируем но не propagate
            logger.error(
                f"Failed to send trace to Langfuse: {e}",
                extra={"error_type": type(e).__name__},
            )
            # Optionally: collect metric для monitoring
            self.metrics.increment("langfuse.send_errors")

class ToolExecutor:
    def end_tool_execution_span(self, span_obj, result, error):
        """
        Завершает span асинхронно.
        Гарантирует что ошибки не propagate.
        """
        if not span_obj:
            return
        
        # Fire-and-forget async task
        asyncio.create_task(
            self._end_span_async(span_obj, result, error)
        )
    
    async def _end_span_async(self, span_obj, result, error):
        """Вспомогательная функция для async завершения span."""
        try:
            span_obj.end(output={"result": result, "error": error})
        except Exception as e:
            logger.error(f"Failed to end span: {e}", exc_info=False)
```

---

## Risks / Trade-offs

### Risk 1: Tool Execution Latency Impact
**Risk**: Создание/завершение spans может добавить latency к tool execution.
**Mitigation**:
- Span creation/completion асинхронные (не блокируют)
- Batch отправка в Langfuse (не посылаем каждый span отдельно)
- Тестируем performance под нагрузкой (benchmark с метриками)

### Risk 2: Nested Span Complexity
**Risk**: Глубокая иерархия spans (tool_validation → validation status) может запутать пользователей.
**Mitigation**:
- Документируем иерархию in Langfuse UI
- Группируем related spans (например tool_execution_client as a single step)
- Предоставляем быстрые фильтры в API

### Risk 3: Context Propagation Issues
**Risk**: user_id, workspace_id может быть недоступен в nested contexts (например async tasks).
**Mitigation**:
- Явно передаем context в параметрах функций
- Используем structlog context vars для fallback
- Тестируем с async/concurrent tool execution

### Risk 4: Analytics API Performance
**Risk**: Querying Langfuse для metrics может быть медленно при большом volume.
**Mitigation**:
- Используем pagination и period-based filters
- Кэшируем результаты (Redis 1 час TTL)
- Добавляем rate limiting на analytics endpoints

---

## Migration Plan

### Phase 1: Core Tracing
1. Расширить `LangfuseIntegration` с методами для tool execution spans
2. Интегрировать в `ToolExecutor.execute_tool()` 
3. Написать unit tests для graceful degradation
4. Verify nested span hierarchy в Langfuse UI

### Phase 2: Analytics API
1. Implement REST endpoints для tool metrics
2. Add filtering (tool_name, period, workspace)
3. Implement caching layer
4. Add rate limiting

### Phase 3: Testing & Monitoring
1. Load testing tool execution tracing (latency impact)
2. Chaos testing (Langfuse unavailable scenarios)
3. Add metrics: span creation/completion failures
4. Document analytics API for Product team

### Rollout
1. Deploy с `LANGFUSE_ENABLED=true` (graceful если false)
2. Monitor span creation rates, error rates
3. Gradually enable on all workspaces
4. Product team uses analytics for optimization

---

## Open Questions

1. **Nested span depth**: Сколько уровней nested spans нужно? (validation → tool_validation_status?)
   - Текущий план: 5 уровней (root → validation → risk → approval → execution)
   - Альтернатива: Уменьшить на 1 level для простоты

2. **Tool execution timeout tracking**: Нужно ли отслеживать timeout'ы отдельно от errors?
   - Текущий план: В output.error записывать error_type="timeout"
   - Требует clarification от Product team

3. **Real-time notifications**: Нужно ли alerts при high error rate tools?
   - Выходит за scope Фазы 4 (analytics только)
   - Может быть Phase 5 (deployment & monitoring)

