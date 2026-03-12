# Design: Langfuse Integration

## Context

### Current State
- OpenTelemetry + structlog для общего трейсинга и логирования
- LiteLLM для управления LLM провайдерами (OpenAI, Claude, OpenRouter и т.д.)
- Agent service для многошаговых операций
- Нет LLM-specific observability (промпты, токены, стоимость, LLM-latency)

### Problem
1. **LLM-specific metrics** отсутствуют в текущей observability системе
2. **Стоимость LLM операций** не отслеживается
3. **Качество промптов** невозможно оценить и оптимизировать
4. **Multi-step workflows** не имеют видимости на уровне LLM операций
5. **Ограничение текущей платформы**: OpenTelemetry не предназначена для LLM-specific трейсинга

### Constraints
- Система должна быть graceful при недоступности Langfuse
- Minimal overhead на LLM запрос (< 100ms async)
- Self-hosted Langfuse (контроль над данными)
- Multi-tenant isolation (user_id, workspace_id)
- Все логирование должно быть на русском языке
- 100% тестовое покрытие (TDD)

### Stakeholders
- Backend engineers (реализация)
- Product team (аналитика, cost tracking)
- DevOps (deployment, self-hosted Langfuse)
- QA (тестирование graceful degradation)

---

## Goals / Non-Goals

### Goals
1. **LLM-native observability**: Захватывать промпты, ответы, токены, стоимость, ошибки LLM операций
2. **Multi-step tracing**: Поддерживать трейсинг агентных workflows с spans для каждого шага
3. **Quality feedback**: Позволять записывать scores (user feedback, metrics) для traces
4. **Analytics API**: Предоставлять REST API для получения traces с фильтрацией и аналитикой
5. **Graceful degradation**: При недоступности Langfuse система продолжает работу (no-op mode)
6. **Cost tracking**: Автоматический расчет и отслеживание стоимости LLM операций
7. **Self-hosted**: Поддержка self-hosted Langfuse через Docker Compose

### Non-Goals
- Real-time streaming трейсов в dashboard (async batch отправка)
- Custom обучение моделей на traces (только сбор данных)
- Замена OpenTelemetry для общего трейсинга (дополнение)
- Трейсинг всех операций в системе (только LLM + agent workflows)
- Автоматическое оптимизирование промптов на основе scores

---

## Decisions

### Decision 1: LangfuseIntegration Service Wrapper

**What**: Создать обертку (`app/services/langfuse_integration.py`) вокруг Langfuse SDK для:
- Управления lifecycle (инициализация, shutdown, reconnection)
- Graceful degradation при ошибках
- Context propagation (user_id, workspace_id из structlog)
- Unified API для создания traces, spans, scores

**Why**:
- Отделение логики от SDK
- Возможность мокирования в тестах
- Graceful handling ошибок без проброса exception'ов
- Возможность добавления кастомной логики (рейт-лимитинг, batching)

**Alternatives Considered**:
- **Прямое использование Langfuse SDK**: Не гибко, сложнее тестировать, нет graceful degradation
- **Custom трейсинг систем**: Слишком много work, не нужно переизобретать

**Implementation**:
```python
class LangfuseIntegration:
    def __init__(self, enabled: bool, ...):
        self.enabled = enabled
        self.client = Langfuse(...) if enabled else None
    
    def create_trace(self, name: str, user_id, workspace_id, metadata):
        if not self.enabled:
            return None
        try:
            return self.client.trace(...)
        except Exception as e:
            logger.error("Langfuse error", exc_info=e)
            return None
    
    def create_span(self, trace_id, name, input, output):
        # Similar graceful handling
        ...
    
    def record_score(self, trace_id, name, value, comment):
        # Similar graceful handling
        ...
```

---

### Decision 2: LiteLLM Callbacks for Auto-Capture

**What**: Использовать встроенные Langfuse callbacks в LiteLLM для автоматического захватывания каждого LLM запроса.

**Why**:
- Zero code changes в agent service для базового трейсинга
- LiteLLM уже имеет встроенную поддержку Langfuse
- Асинхронная отправка (не блокирует LLM запрос)
- Автоматический расчет стоимости
- Захватывает все метаданные: model, tokens, latency, errors

**Implementation**:
```yaml
# litellm_config.yaml
litellm_settings:
  success_callback: ["langfuse"]
  failure_callback: ["langfuse"]
  flush_interval: 30  # batch every 30 sec

environment_variables:
  LANGFUSE_PUBLIC_KEY: "pk-..."
  LANGFUSE_SECRET_KEY: "sk-..."
  LANGFUSE_HOST: "http://langfuse:3000"
```

**Workflow**:
1. Agent вызывает `litellm.completion(...)`
2. LiteLLM выполняет запрос асинхронно
3. На успех → LiteLLM отправляет callback в Langfuse
4. На ошибку → failure callback
5. Batch отправка каждые 30 сек если очередь не пуста

---

### Decision 3: Agent Workflow Tracing with Manual Spans

**What**: Агент service сам создает root traces и spans для multi-step workflows используя LangfuseIntegration.

**Why**:
- Более гранулярная видимость (каждый шаг имеет свой span)
- Возможность добавления custom metadata
- Контроль над hierarchией spans
- LiteLLM callbacks автоматически добавляют LLM generation spans

**Implementation**:
```python
# app/services/agent_service.py
async def process_message(self, message, user_id, workspace_id):
    with self.langfuse.create_trace(
        name=f"agent_{self.name}",
        user_id=user_id,
        workspace_id=workspace_id,
        metadata={"agent": self.name, "model": self.model}
    ) as trace:
        # Step 1: prepare_context
        with trace.create_span("prepare_context") as span:
            context = await self.prepare_context(message)
            span.end(output={"context_size": len(context)})
        
        # Step 2: generate_response (LiteLLM callback auto-captured)
        with trace.create_span("generate_response") as span:
            response = await self.llm_client.completion(
                model=self.model,
                messages=[...],
                # LiteLLM callback автоматически логирует в Langfuse
            )
            # Callback уже создал generation span
        
        # Step 3: save_interaction
        with trace.create_span("save_interaction") as span:
            await self.db.save_message(...)
            span.end(output={"saved": True})
        
        return response
```

---

### Decision 4: REST API for Traces and Scores

**What**: Новые endpoints в FastAPI для получения traces и работы со scores.

**Why**:
- Предоставить аналитику для frontend
- Поддержить user feedback сбор
- Позволить пользователям видеть историю своих interactions

**Endpoints**:
```
GET    /traces?user_id=...&workspace_id=...&limit=100
GET    /traces/{trace_id}
GET    /traces/{trace_id}/scores
POST   /traces/{trace_id}/scores
GET    /analytics/traces/summary?period=7d
GET    /analytics/agents?workspace_id=...
GET    /analytics/cost?start_date=...&end_date=...
GET    /health/langfuse
```

**Implementation**:
- Отдельный route module `app/routes/traces.py`
- Сервис `app/services/traces_service.py` для query logic
- Paginated responses
- Permissions check (user может видеть только свои traces)

---

### Decision 5: Docker Compose for Self-Hosted Langfuse

**What**: Добавить `docker-compose.langfuse.yml` с Langfuse stack.

**Stack**:
- `langfuse-postgres` (PostgreSQL 16)
- `langfuse` (web app)
- `langfuse-redis` (cache)

**Why**:
- Контроль над данными (не передаем в облако)
- Local development поддержка
- Easy deployment на наш сервер

**Implementation**:
```yaml
# docker-compose.langfuse.yml
services:
  langfuse-postgres:
    image: postgres:16
    environment:
      POSTGRES_DB: langfuse
      POSTGRES_USER: langfuse
      POSTGRES_PASSWORD: ${LANGFUSE_DB_PASSWORD}
    volumes:
      - langfuse_postgres_data:/var/lib/postgresql/data
  
  langfuse:
    image: langfuse/langfuse:latest
    environment:
      DATABASE_URL: postgresql://langfuse:${LANGFUSE_DB_PASSWORD}@langfuse-postgres:5432/langfuse
      NEXTAUTH_SECRET: ${LANGFUSE_NEXTAUTH_SECRET}
    depends_on:
      - langfuse-postgres
    ports:
      - "3000:3000"
  
  langfuse-redis:
    image: redis:7-alpine
```

**Integration**:
- `docker-compose.yml` включает эту composition с `extends` или `include`
- Network: все сервисы в одной Docker сети (`codelab`)
- `LANGFUSE_HOST=http://langfuse:3000` для core-service

---

### Decision 6: Graceful Degradation

**What**: Если Langfuse недоступен или отключен, система продолжает работу без трейсинга.

**Implementation**:
```python
# app/services/langfuse_integration.py
class LangfuseIntegration:
    def __init__(self):
        self.enabled = False
        try:
            client = Langfuse(...)
            # Health check
            client.get_traces(limit=1)
            self.enabled = True
        except Exception as e:
            logger.warning(f"Langfuse disabled: {e}")
            self.client = None
    
    def create_trace(...):
        if not self.enabled:
            return None  # No-op
        # ... normal operation
```

**Behavior**:
- Startup: Langfuse optional, всегда успешен
- Runtime: Если Langfuse ошибка → logირვე, continue (не пробрасываем exception)
- Health check endpoint: `GET /health/langfuse` показывает статус

---

### Decision 7: Configuration and Environment Variables

**What**: Langfuse параметры через config.

**Variables**:
```
LANGFUSE_ENABLED=true|false
LANGFUSE_PUBLIC_KEY=pk-...
LANGFUSE_SECRET_KEY=sk-...
LANGFUSE_HOST=http://localhost:3000
LANGFUSE_RETENTION_DAYS=90
```

**Storage**:
- `app/config.py`: Parse из environment
- `.env.example`: Template
- Default values: LANGFUSE_ENABLED=false, RETENTION_DAYS=90

---

## Architecture Diagram

```mermaid
graph TB
    subgraph "Application Layer"
        FastAPI["FastAPI App"]
        Agent["Agent Service"]
        LLMClient["LiteLLM Client"]
        LangfuseService["LangfuseIntegration<br/>Service"]
    end
    
    subgraph "Request Flow"
        RestAPI["REST API<br/>Routes"]
        TracesService["Traces Service<br/>(Query/Filter)"]
    end
    
    subgraph "Langfuse Integration"
        Callbacks["LiteLLM Callback<br/>(auto-capture)"]
        LangfuseSdk["Langfuse SDK<br/>Client"]
    end
    
    subgraph "Langfuse Stack"
        LangfuseAPI["Langfuse API<br/>& Web UI"]
        LangfuseDB["PostgreSQL"]
        LangfuseRedis["Redis Cache"]
    end
    
    Agent -->|create trace| LangfuseService
    Agent -->|LiteLLM call| LLMClient
    LLMClient -->|async callback| Callbacks
    Callbacks -->|HTTP POST| LangfuseAPI
    LangfuseService -->|SDK calls| LangfuseSdk
    LangfuseSdk -->|HTTP| LangfuseAPI
    LangfuseAPI -->|read/write| LangfuseDB
    LangfuseAPI -->|cache| LangfuseRedis
    RestAPI -->|query| TracesService
    TracesService -->|fetch| LangfuseAPI
    FastAPI -->|use| RestAPI
```

---

## Risks / Trade-offs

### Risk 1: Langfuse Performance Overhead
**Risk**: Langfuse инициализация или callbacks медленные → блокирует LLM запросы

**Mitigation**:
- Callbacks асинхронные (не блокируют)
- flush_interval=30 сек для batching
- LangfuseIntegration имеет timeout на инициализацию
- Monitoring: prometheus metrics для callback latency

---

### Risk 2: Database Growth
**Risk**: Traces могут быстро заполнить базу (особенно с high volume)

**Mitigation**:
- Retention policy: удаление traces старше 90 дней
- Configurable LANGFUSE_RETENTION_DAYS
- Optional archiving в S3 перед удалением
- Cron task ежедневно в 02:00 UTC

---

### Risk 3: Multi-tenant Data Isolation
**Risk**: Утечка данных между users/workspaces в traces

**Mitigation**:
- Session ID = workspace_id (встроенная изоляция)
- API эндпоинты проверяют permissions перед возвратом
- Database row-level security (PostgreSQL RLS) опционально
- All queries фильтруют по user_id

---

### Risk 4: API Key Security
**Risk**: LANGFUSE_SECRET_KEY может случайно залогироваться

**Mitigation**:
- Secret key НИКОГДА не логируется (только success/fail)
- Config validation при инициализации
- Error handling не пробрасывает keys
- Secrets не попадают в error messages

---

### Risk 5: Third-Party Dependency
**Risk**: Langfuse не доступна → потеря трейсинга

**Mitigation**:
- Graceful degradation (no-op mode)
- Health check endpoint
- Alerts если Langfuse down > 5 минут
- Fallback: structlog остается работать для базового логирования

---

## Migration Plan

### Phase 1: Infrastructure (Week 1)
1. Add `docker-compose.langfuse.yml`
2. Deploy Langfuse stack locally и на staging
3. Configure LANGFUSE_* variables в .env
4. Verify connectivity

### Phase 2: Core Integration (Week 2-3)
1. Implement `LangfuseIntegration` service
2. Add LiteLLM callbacks configuration
3. Update `agent_service.py` для trace creation
4. 100% test coverage (unit + integration tests)

### Phase 3: API & Analytics (Week 3-4)
1. Implement `app/routes/traces.py` endpoints
2. Implement `TracesService` для queries
3. Permissions checks
4. Tests + documentation

### Phase 4: Monitoring & Ops (Week 4)
1. Add health check endpoint
2. Prometheus metrics
3. Retention policy cronjob
4. Documentation для ops

### Phase 5: Rollout (Week 5)
1. Deploy на staging
2. E2E tests
3. Deploy на production (LANGFUSE_ENABLED=false by default)
4. Monitor для issues

### Rollback Plan
- LANGFUSE_ENABLED=false → полное отключение (graceful no-op)
- Удалить routes, service остается (backward compatible)
- Delete docker-compose.langfuse.yml если нужно полное удаление

---

## Open Questions

1. **Analytics Dashboard**: Нужен ли custom dashboard или используем Langfuse web UI?
2. **Billing Integration**: Нужно ли интегрировать cost tracking с billing?
3. **User Notifications**: Уведомлять ли users об их traces в Langfuse?
4. **API Rate Limiting**: Нужно ли rate limitировать GET /traces endpoints?
5. **Audit Logging**: Логировать ли доступ к traces в audit log?

---

## Testing Strategy

### Unit Tests
- `tests/test_langfuse_integration.py`: LangfuseIntegration service (mocked Langfuse)
- `tests/test_langfuse_callbacks.py`: LiteLLM callback mocking
- `tests/test_traces_service.py`: Query logic, filtering, permissions
- Coverage: 100% (critical path)

### Integration Tests
- `tests/test_langfuse_e2e.py`: With real Langfuse (local Docker)
- Full workflow: Agent → LiteLLM → Langfuse → API Query
- Test graceful degradation (Langfuse down)

### Performance Tests
- Callback overhead: < 100ms
- Trace creation: < 50ms
- API query: < 2s (with limit=100)

---

## Implementation Files

**New Files**:
- `app/services/langfuse_integration.py` — LangfuseIntegration service
- `app/services/traces_service.py` — Query/filter logic
- `app/routes/traces.py` — REST API endpoints
- `app/routes/feedback.py` — Scores/feedback endpoints
- `docker-compose.langfuse.yml` — Langfuse stack
- `tests/test_langfuse_integration.py` — Unit tests
- `tests/test_langfuse_e2e.py` — Integration tests

**Updated Files**:
- `app/config.py` — Add LANGFUSE_* variables
- `app/services/agent_service.py` — Add trace creation
- `pyproject.toml` — Add langfuse dependency
- `docker-compose.yml` — Include langfuse stack
- `litellm_config.yaml` — Configure callbacks

---

**Status**: Ready for Implementation  
**Last Updated**: 2026-03-10  
**Approved By**: Architecture Review
