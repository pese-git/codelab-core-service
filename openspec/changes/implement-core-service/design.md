# Design Document: Personal Multi-Agent AI Platform - Core Service

**Change:** implement-core-service  
**Version:** 1.0  
**Date:** 11 февраля 2026

---

## Context

### Background

Создаем полностью децентрализованную персональную мультиагентную AI платформу, где каждый пользователь имеет изолированную команду AI агентов. Текущее состояние - это пустой проект, требующий реализации с нуля.

### Current State

- Пустая кодовая база (новый проект)
- Документация с техническими требованиями существует
- Инфраструктура (PostgreSQL, Redis, Qdrant) будет развернута отдельно
- FastAPI выбран как основной фреймворк

### Constraints

- **Изоляция пользователей** - критичное требование, violations = 0
- **Performance SLA**:
  - Direct calls: P95 < 2 сек
  - Task planning: < 5 сек
  - Qdrant search: < 50ms
  - SSE latency: P99 < 100ms
- **Scalability**: 1000+ SSE connections per user, 1M+ vectors per agent
- **Rate limiting**: 100 req/min per user
- **Python 3.11+**, async/await everywhere

### Stakeholders

- **End Users** - владельцы персональных AI команд
- **Backend Team** - разработчики core service
- **DevOps** - deployment и monitoring
- **Security** - аудит изоляции пользователей

---

## Goals / Non-Goals

### Goals

1. **100% User Isolation**
   - Middleware-слой для автоматической изоляции всех запросов
   - JWT authentication на все `/my/*` endpoints
   - Автоматическая фильтрация queries по user_id
   - Zero violations policy

2. **Dual-Mode Chat System**
   - Direct mode: прямой вызов агента (⚡ 1-2 сек)
   - Orchestrated mode: автоматическое планирование графа задач (🧠 5-10 сек)
   - Seamless переключение между режимами

3. **Personal Agent Management**
   - CRUD операции для агентов
   - Per-agent Qdrant context (RAG)
   - Agent status tracking (ready, busy, error)
   - Concurrency control per agent

4. **Real-time Communication**
   - SSE streaming для UI updates
   - Event types: agent_status, task_progress, approval_required, etc.
   - 1000+ concurrent connections per user

5. **Approval Workflow**
   - Tool approval перед опасными операциями
   - Plan approval для сложных multi-agent планов
   - Timeout 300 сек с graceful decline

6. **Scalable Architecture**
   - Async/await throughout
   - Agent Bus для координации
   - Redis для кеширования и queues
   - Qdrant для semantic memory

### Non-Goals

- ❌ **Frontend implementation** - только REST API + SSE
- ❌ **Authentication service** - используем существующий JWT provider
- ❌ **LLM hosting** - используем OpenAI/Anthropic APIs
- ❌ **Multi-tenancy на уровне инфраструктуры** - каждый user = isolated space в одной БД
- ❌ **Agent marketplace** - только персональные агенты
- ❌ **Cross-user collaboration** - полная изоляция

---

## Decisions

### Decision 1: Middleware-Based User Isolation

**Choice:** Использовать FastAPI middleware для автоматической изоляции пользователей

**Rationale:**
- Централизованная точка контроля доступа
- Автоматическое извлечение user_id из JWT
- Injection user context в request.state для всех handlers
- Невозможно забыть добавить фильтрацию в новом endpoint

**Alternatives Considered:**
- ❌ **Manual filtering в каждом endpoint** - error-prone, легко забыть
- ❌ **Database-level RLS (Row Level Security)** - сложнее debugging, меньше контроля
- ❌ **Separate databases per user** - не масштабируется, сложная миграция

**Implementation:**
```python
# middleware/user_isolation.py
class UserIsolationMiddleware:
    async def __call__(self, request: Request, call_next):
        if request.url.path.startswith("/my/"):
            user_id = extract_user_from_jwt(request.headers["Authorization"])
            request.state.user_id = user_id
            request.state.user_prefix = f"user{user_id}"
            request.state.db_filter = {"user_id": user_id}
        return await call_next(request)
```

---

### Decision 2: Per-Agent Qdrant Collections

**Choice:** Создавать отдельную Qdrant collection для каждого агента (`user123_coder_context`)

**Rationale:**
- Изоляция контекста на уровне агента (не только пользователя)
- Каждый агент имеет специализированную память
- Проще управление lifecycle (удаление агента = удаление collection)
- Лучшая производительность поиска (меньше vectors per collection)

**Alternatives Considered:**
- ❌ **One collection per user** - смешивание контекстов разных агентов
- ❌ **Global collection с metadata filtering** - медленнее, сложнее изоляция
- ❌ **Separate Qdrant instance per user** - слишком дорого

**Trade-offs:**
- ➕ Лучшая изоляция и производительность
- ➖ Больше collections (но Qdrant масштабируется хорошо)

---

### Decision 3: Agent Bus Pattern для Координации

**Choice:** Использовать Agent Bus (asyncio.Queue per agent) для управления задачами

**Rationale:**
- Централизованная координация агентов
- Контроль concurrency per agent (max 3 tasks simultaneously)
- Простая интеграция с orchestrator
- Backpressure handling через queue size limits

**Alternatives Considered:**
- ❌ **Direct agent calls** - нет контроля concurrency, сложнее orchestration
- ❌ **Celery/RQ** - overkill для in-process coordination, добавляет latency
- ❌ **Actor model (Ray)** - слишком сложно для текущих требований

**Implementation:**
```python
# core/agent_bus.py
class AgentBus:
    def __init__(self):
        self.queues: Dict[str, asyncio.Queue] = {}
        self.workers: Dict[str, asyncio.Task] = {}
    
    async def register_agent(self, agent_id: str, max_concurrency: int = 3):
        self.queues[agent_id] = asyncio.Queue(maxsize=100)
        self.workers[agent_id] = asyncio.create_task(
            self._worker(agent_id, max_concurrency)
        )
```

---

### Decision 4: Dual-Mode Chat System

**Choice:** Единый endpoint `/my/chat/{session_id}/message/` с опциональным `target_agent`

**Rationale:**
- Простой API для клиента (один endpoint)
- Автоматический выбор режима на основе `target_agent` presence
- Direct mode обходит orchestrator для скорости
- Orchestrated mode использует planning для сложных задач

**Alternatives Considered:**
- ❌ **Separate endpoints** (`/direct/` и `/orchestrated/`) - дублирование кода
- ❌ **Always orchestrate** - медленно для простых запросов
- ❌ **Client-side routing** - сложнее для клиента

**Flow:**
```
POST /my/chat/{session_id}/message/
{
  "content": "Fix bug in auth.py",
  "target_agent": "coder"  // Optional
}

IF target_agent:
  → Direct Mode (1-2 sec)
ELSE:
  → Orchestrator → Plan → Approval → Execute (5-10 sec)
```

---

### Decision 5: SSE для Real-time Events

**Choice:** Server-Sent Events (SSE) вместо WebSockets

**Rationale:**
- Unidirectional communication (server → client) достаточно
- Проще implementation (HTTP-based)
- Автоматический reconnect в браузерах
- Меньше overhead чем WebSockets
- Работает через HTTP/2 multiplexing

**Alternatives Considered:**
- ❌ **WebSockets** - overkill для one-way communication
- ❌ **Long polling** - неэффективно, больше latency
- ❌ **GraphQL subscriptions** - добавляет сложность

**Event Types:**
```python
# schemas/events.py
class SSEEvent(BaseModel):
    event_type: Literal[
        "direct_agent_call",
        "agent_status_changed", 
        "task_plan_created",
        "task_started",
        "task_progress",
        "task_completed",
        "tool_request",
        "plan_request",
        "context_retrieved",
        "approval_required"
    ]
    payload: Dict[str, Any]
    timestamp: datetime
```

---

### Decision 6: Approval Manager Pattern

**Choice:** Centralized Approval Manager для tool и plan approvals

**Rationale:**
- Единая точка контроля для всех approval workflows
- Timeout management (300 сек)
- SSE integration для UI notifications
- Graceful decline при timeout

**Alternatives Considered:**
- ❌ **Per-agent approval logic** - дублирование кода
- ❌ **Synchronous approval** - блокирует agent execution
- ❌ **No approval system** - небезопасно для production

**Flow:**
```
Agent → ApprovalManager.request_approval()
  → SSE event to UI
  → User approves/rejects
  → POST /my/approvals/{id}/confirm
  → Agent unblocked
```

---

### Decision 7: SQLAlchemy 2.0 Async ORM

**Choice:** SQLAlchemy 2.0 с asyncpg для async database access

**Rationale:**
- Native async/await support
- Type-safe ORM
- Миграции через Alembic
- Хорошая производительность с connection pooling

**Alternatives Considered:**
- ❌ **Tortoise ORM** - меньше community support
- ❌ **Raw asyncpg** - больше boilerplate, нет ORM benefits
- ❌ **Sync SQLAlchemy** - блокирует event loop

**Schema Design:**
```sql
-- Core tables
users (id, email, created_at)
user_agents (id, user_id, name, config, status, created_at)
user_orchestrators (id, user_id, config, created_at)
chat_sessions (id, user_id, created_at)
messages (id, session_id, role, content, created_at)
tasks (id, session_id, agent_id, status, result, created_at)
approval_requests (id, user_id, type, payload, status, created_at)
```

---

### Decision 8: Redis для Caching и Queues

**Choice:** Redis для agent config cache, task queues, SSE buffers

**Rationale:**
- Fast in-memory access для hot data
- Pub/Sub для SSE event distribution
- TTL support для cache invalidation
- Atomic operations для concurrency control

**Alternatives Considered:**
- ❌ **In-memory Python dict** - не работает с multiple workers
- ❌ **Memcached** - нет pub/sub, меньше features
- ❌ **PostgreSQL для всего** - медленнее для cache use cases

**Usage:**
```python
# Cache agent configs (TTL 5 min)
redis.setex(f"agent:{agent_id}:config", 300, json.dumps(config))

# SSE event buffer (per session)
redis.lpush(f"sse:{session_id}:events", json.dumps(event))

# Task queue metadata
redis.hset(f"task:{task_id}", mapping={"status": "running", "started_at": now()})
```

---

### Decision 9: Pydantic для Validation

**Choice:** Pydantic 2.0 для всех request/response schemas

**Rationale:**
- Type-safe validation
- Automatic OpenAPI schema generation
- JSON serialization/deserialization
- Integration с FastAPI

**Alternatives Considered:**
- ❌ **Marshmallow** - менее type-safe
- ❌ **Manual validation** - error-prone
- ❌ **Dataclasses** - нет validation logic

---

### Decision 10: Modular Architecture

**Choice:** Разделение на модули по domain boundaries

**Structure:**
```
codelab-core-service/
├── middleware/          # User isolation
├── workers/             # User Worker Space
├── agents/              # Agent management + ContextualAgent
├── core/                # Agent Bus, Orchestrator, Approval Manager
├── routes/              # FastAPI endpoints
├── vectorstore/         # Qdrant integration
├── models/              # SQLAlchemy ORM
├── schemas/             # Pydantic models
├── services/            # Business logic
└── utils/               # Helpers
```

**Rationale:**
- Clear separation of concerns
- Easy to navigate codebase
- Testable modules
- Scalable для future features

---

## Risks / Trade-offs

### Risk 1: User Isolation Violations
**Risk:** Баг в middleware может привести к утечке данных между пользователями  
**Mitigation:**
- Comprehensive unit tests для middleware
- Integration tests с multiple users
- Security audit перед production
- Monitoring для unauthorized access attempts
- Fail-safe: если user_id не найден → 401 Unauthorized

---

### Risk 2: SSE Connection Scalability
**Risk:** 1000+ SSE connections per user может перегрузить сервер  
**Mitigation:**
- Connection pooling и limits
- Redis pub/sub для event distribution (не держим все в памяти)
- Horizontal scaling с load balancer
- Client-side reconnect logic с exponential backoff
- Monitoring connection count per user

---

### Risk 3: Qdrant Collection Explosion
**Risk:** Много агентов → много collections → overhead  
**Mitigation:**
- Lazy collection creation (только при первом использовании)
- Cleanup старых/неиспользуемых collections
- Monitoring collection count и размера
- Qdrant хорошо масштабируется (tested до 10K+ collections)

---

### Risk 4: Orchestrator Planning Latency
**Risk:** Сложные планы могут занимать > 5 сек  
**Mitigation:**
- Timeout на planning (5 сек max)
- Fallback на simple sequential plan
- Caching похожих планов (Redis)
- User feedback через SSE ("Planning in progress...")
- Option для user: skip planning → direct mode

---

### Risk 5: Approval Timeout Handling
**Risk:** User не отвечает на approval request → agent зависает  
**Mitigation:**
- Hard timeout 300 сек
- Graceful decline с notification
- Cleanup pending approvals
- Retry logic для user (можно повторить запрос)

---

### Risk 6: Agent Concurrency Deadlocks
**Risk:** Circular dependencies в task graph → deadlock  
**Mitigation:**
- Topological sort перед execution
- Cycle detection в graph planning
- Timeout на task execution (10 min max)
- Monitoring для stuck tasks

---

### Risk 7: Database Connection Pool Exhaustion
**Risk:** Много concurrent requests → pool exhaustion  
**Mitigation:**
- Connection pool sizing (min=10, max=50)
- Connection timeout (30 сек)
- Monitoring pool usage
- Graceful degradation (503 Service Unavailable)

---

### Risk 8: Redis Memory Overflow
**Risk:** SSE buffers и cache могут заполнить Redis  
**Mitigation:**
- TTL на все cached data
- Max buffer size per session (1000 events)
- LRU eviction policy
- Monitoring Redis memory usage
- Separate Redis instance для critical data

---

## Migration Plan

### Phase 1: Infrastructure Setup (Week 1)
1. Deploy PostgreSQL, Redis, Qdrant
2. Setup database schema (Alembic migrations)
3. Configure JWT authentication
4. Setup monitoring (Prometheus + Grafana)

### Phase 2: Core Implementation (Week 2-3)
1. Implement User Isolation Middleware
2. Implement User Worker Space
3. Implement Agent Management (CRUD)
4. Implement Agent Context Store (Qdrant)
5. Implement Agent Bus

### Phase 3: Chat System (Week 4)
1. Implement Direct Mode
2. Implement Orchestrator + Planning
3. Implement SSE Streaming
4. Implement Approval Manager

### Phase 4: Testing & Optimization (Week 5)
1. Unit tests (90%+ coverage)
2. Integration tests (multi-user scenarios)
3. Load testing (1000+ SSE connections)
4. Security audit (isolation violations)
5. Performance optimization

### Phase 5: Deployment (Week 6)
1. Docker containerization
2. Kubernetes deployment
3. Production monitoring setup
4. Documentation (API docs, runbooks)
5. Rollout plan (canary → full)

### Rollback Strategy
- Database migrations reversible (Alembic downgrade)
- Feature flags для new endpoints
- Blue-green deployment для zero downtime
- Backup strategy (PostgreSQL daily, Qdrant snapshots)

---

## Open Questions

### Q1: LLM Provider Strategy
**Question:** Использовать только OpenAI или поддержать multiple providers (Anthropic, local models)?  
**Impact:** API design, cost estimation, fallback logic  
**Decision needed by:** Week 2

### Q2: Agent Tool System
**Question:** Как определять и регистрировать tools для агентов? JSON schema? Python decorators?  
**Impact:** Agent config structure, tool approval logic  
**Decision needed by:** Week 3

### Q3: Context Pruning Strategy
**Question:** Когда и как pruning старых vectors из Qdrant? По времени? По размеру?  
**Impact:** Memory management, performance  
**Decision needed by:** Week 4

### Q4: Rate Limiting Granularity
**Question:** 100 req/min per user достаточно? Нужны ли separate limits для разных endpoints?  
**Impact:** API design, user experience  
**Decision needed by:** Week 2

### Q5: Error Recovery
**Question:** Что делать при partial failure в orchestrated mode (1 из 3 агентов failed)?  
**Impact:** Orchestrator logic, user experience  
**Decision needed by:** Week 3

---

**Status:** ✅ Design Complete  
**Next Step:** Create detailed specs for each capability  
**Approved by:** Backend Team Lead  
**Date:** 11 февраля 2026
