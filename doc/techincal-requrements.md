# ТЕХНИЧЕСКОЕ ЗАДАНИЕ  
## Personal Multi-Agent AI Platform - ПОЛНАЯ ВЕРСИЯ  
**Версия 5.0 FINAL** | **11 февраля 2026**

***

## 1. ОБЩИЕ СВЕДЕНИЯ

| Параметр | Значение |
|----------|----------|
| **Название проекта** | Personal Multi-Agent AI Platform |
| **Заказчик** | Внутренний проект |
| **Исполнитель** | Команда разработки |
| **Дата утверждения** | 11 февраля 2026 |
| **Срок сдачи** | **22 марта 2026** |
| **Длительность** | **41 рабочий день** |
| **Бюджет** | Внутренний проект |

***

## 2. 🎯 ЦЕЛИ ПРОЕКТА

Создать **полностью децентрализованную персональную мультиагентную AI платформу** с:

1. **100% персональными агентами** - только свои агенты для каждого пользователя
2. **Полная изоляция** - User123 НЕТ доступа к User456 агентам
3. **Два режима работы**: 
   - 🧠 Автоматический (оркестратор планирует)
   - ⚡ Прямой вызов `@agent_name`
4. **Vector Context** - Qdrant RAG для долгосрочной памяти
5. **Real-time SSE** - мгновенные обновления
6. **Approval Manager** - контроль tools и планов

***

## 3. 🔬 АРХИТЕКТУРА СИСТЕМЫ

```
┌────────────────────┐    SSE    ┌──────────────────┐
│   User123          │◄───┬───FastAPI Gateway────┤ User123 Space   │
│ ├─Dashboard        │   │    │ User Isolation   │ ├─Orchestrator   │
│ ├─/my/agents/      │   │    │ Middleware       │ ├─Agents[3+]     │
│ └─Direct @coder    │   │    └──────────┬───────┘ ├─Task Bus       │
└────────────────────┘   │               │         ├─Qdrant Context │
┌────────────────────┐   │               │         └──────┬─────────┘
│   User456          │───┼───────┐       │                │
└────────────────────┘   │       │       │                │
                         ▼       ▼       ▼                ▼
                    ┌──────────────────────────────┐    │
                    │        INFRASTRUCTURE        │    │
                    │ ├─PostgreSQL (sharded)       │    │
                    │ ├─Redis (queues)             │    │
                    │ ├─Qdrant (vectors/user) ←NEW │◄───┘
                    │ └─LLM Pool                   │
                    └──────────────────────────────┘
```

***

## 4. 📋 ПОЛНЫЙ ФУНКЦИОНАЛЬНЫЙ СПЕЦИФИКАЦИЯ

### 4.1. Управление персональными агентами

| № | Эндпоинт | Метод | Описание |
|---|----------|-------|----------|
| F1 | `GET /my/agents/` | Мои агенты |
| F2 | `POST /my/agents/` | Создать агента |
| F3 | `PUT /my/agents/{agent_id}/` | Редактировать |
| F4 | `DELETE /my/agents/{agent_id}/` | Удалить |
| F5 | `GET /my/agents/available/{session_id}/` | **Доступные агенты** |

**Agent Config Schema:**
```json
{
  "name": "Мой кодер",
  "system_prompt": "Ты senior Python developer",
  "model": {"provider": "openai", "name": "gpt-4o-mini"},
  "tools": [{"tool_id": "web_search", "enabled": true}],
  "concurrency_limit": 3
}
```

### 4.2. Персональный оркестратор

| № | Эндпоинт | Метод | Описание |
|---|----------|-------|----------|
| F6 | `PUT /my/orchestrators/` | Настроить оркестратор |
| F7 | `POST /my/orchestrators/test/` | Тестировать |

### 4.3. Чат система (2 режима)

| № | Эндпоинт | Метод | Описание |
|---|----------|-------|----------|
| F8 | `POST /my/chat/sessions/` | Создать сессию |
| F9 | `POST /my/chat/{session_id}/message/` | **Сообщение (+target_agent)** |
| F10 | `GET /my/chat/{session_id}/events/` | SSE поток |
| F11 | `GET /my/chat/{session_id}/` | История |

**Direct Agent Call:**
```json
{
  "content": "Напиши FastAPI роуты",
  "target_agent": "user123_coder"  // ⚡ ПРЯМЫЙ вызов
}
```

### 4.4. Approval Manager

| № | Эндпоинт | Метод | Описание |
|---|----------|-------|----------|
| F12 | `POST /my/tools/{approval_id}/confirm/` | Подтвердить tool/plan |
| F13 | `POST /my/tools/{approval_id}/reject/` | Отклонить |

***

## 5. 🗄️ БАЗА ДАННЫХ (PostgreSQL 16+)

```sql
-- Пользователи
users (id, email, created_at)

-- ПЕРСОНАЛЬНЫЕ АГЕНТЫ
user_agents (
  id, user_id, agent_id, name, config JSONB, is_active
)

-- ПЕРСОНАЛЬНЫЕ ОРКЕСТРАТОРЫ  
user_orchestrators (user_id, config JSONB)

-- СЕССИИ И СООБЩЕНИЯ
chat_sessions (id, user_id, title)
messages (id, session_id, user_id, content, role, agent_id, target_agent)

-- ЗАДАЧИ
tasks (id, session_id, user_id, task_id, assigned_agent, status, dependencies JSONB)

-- APPROVALS
approval_requests (id, session_id, user_id, type, status, result JSONB)
```

**QDRANT Vector Collections:**
```
user123_context → 1M+ vectors (messages, RAG search)
user456_context → изолированная коллекция
```

***

## 6. 🛡️ USER ISOLATION МIDDLEWARE

```python
class UserIsolationMiddleware:
    """100% изоляция пользователей"""
    async def __call__(self, scope, receive, send):
        user = await get_current_user(scope)
        scope["user_id"] = user.id
        scope["user_prefix"] = f"user{user.id}_"
        scope["db_filters"] = {"user_id": user.id}
        await self.app(scope, receive, send)
```

***

## 7. 👥 USER WORKER SPACE (КОР)

```python
class UserWorkerSpace:
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.agent_cache = {}
        self.agent_bus = PersonalAgentBus(user_id)
        self.qdrant_context = QdrantUserContext(user_id)
        self.approval_manager = ApprovalManager(self)
    
    async def process_message(self, session_id: int, message: dict):
        if message.get("target_agent"):
            return await self._direct_agent_call(...)  # ⚡ 1-2 сек
        return await self.orchestrator.plan_and_execute(...)  # 🧠 5-10 сек
```

***

## 8. 🔄 МУЛЬТИАГЕНТНОЕ ВЗАИМОДЕЙСТВИЯ

```
1. ПРЯМЫЕ ВЫЗОВЫ (@coder): User → Agent → Qdrant → Response
2. АВТО ПЛАН: User → Orchestrator → TaskGraph → AgentBus → Parallel → SSE

AGENT BUS (asyncio.Queue per agent):
user123_coder    ←── task1
user123_research ←── task2  
user123_writer   ←── task3
       ↓
TOPOLOGICAL SORT → Parallel Execution (max 3)
```

***

## 9. 🧠 QDRANT RAG КОНТЕКСТ

```
RAG Pipeline:
Query → OpenAI embedding → Qdrant hybrid search → Top-5 context → LLM

Коллекции: user{id}_context (1M+ vectors/user)
Filters: user_id + session_id + call_type
Latency: < 50ms search
```

***

## 10. 🛡️ APPROVAL MANAGER

**Tool Approval:**
```
Agent: "Нужно фото?" → SSE(tool_request) → Modal → User OK → JS Camera → POST confirm
```

**Plan Approval:**
```
Orchestrator: "План: 7 задач, $2.45, 10мин" → SSE(plan_request) → User OK → Execute
```

***

## 11. 🌐 SSE EVENT STREAM

```json
{
  "type": "direct_agent_call", "agent_id": "user123_coder", "status": "ready"
}
{
  "type": "task_plan_created", "tasks": 5, "estimated_cost": "$1.23"
}
{
  "type": "tool_request", "tool_id": "camera", "approval_id": "abc123"
}
{
  "type": "tasks_progress", "completed": 3, "total": 5
}
```

***

## 12. 🎨 USER DASHBOARD UI

```
👤 User123 - ЛИЧНЫЙ AI ЦЕНТР

┌─────────────────┬──────────────────┐
│ Мои агенты (3)  │ Мои чаты (7)     │
│ 🟢 @researcher  │ ├─ API Dev        │
│ 🟡 @coder (busy)│ ├─ Travel Plan    │
│ 🔴 @writer err  │ └─ [+ Новый]      │
│ [+ Создать]     │                  │
└─────────────────┴──────────────────┘

📝 Чат: [🔧@coder] [🎯Auto] "Напиши код..."
        ↑ Direct call selector
```

***

## 13. ⚙️ ТЕХНИЧЕСКИЙ СТЕК

| Компонент | Технология |
|-----------|------------|
| Framework | FastAPI 0.115+ |
| ORM | SQLAlchemy 2.0 (asyncpg) |
| Vector DB | **Qdrant** (user collections) |
| Cache | Redis 7+ |
| DB | PostgreSQL 16+ (sharded) |
| SSE | StreamingResponse |
| Frontend | React 18 / Vanilla JS |
| Deployment | Docker + Kubernetes |

***

## 14. 🚀 НЕФУНКЦИОНАЛЬНЫЕ ТРЕБОВАНИЯ

| Метрика | Требование |
|---------|------------|
| **SSE connections** | 1000+ per user |
| **Direct call latency** | P95 < 2 сек |
| **Task planning** | < 5 сек |
| **Qdrant search** | < 50ms |
| **User isolation** | violations = 0 |
| **Uptime** | 99.9% |

***

## 15. 📊 МЕТРИКИ МОНИТОРИНГА

```
user_agent_count_avg = 3.2
direct_call_latency_p95 = 1.8s
qdrant_search_latency = 45ms
user_isolation_violations = 0
orchestrator_bypass_rate = 67%
approval_response_time = 3.2s
```

***

## 16. 🛠️ ЭТАПЫ РАЗРАБОТКИ

| Этап | Задачи | Длительность | Срок |
|------|--------|--------------|------|
| 1 | FastAPI + User Isolation | 4 дня | 14.02 |
| 2 | Personal Agents + CRUD | 5 дней | 19.02 |
| 3 | Orchestrators + AgentBus | 5 дней | 24.02 |
| 4 | Chat SSE + Direct Calls | 6 дней | 02.03 |
| 5 | Qdrant RAG Context | 6 дней | 08.03 |
| 6 | Approval Manager + Tools | 5 дней | 13.03 |
| 7 | UI Dashboard + Testing | 6 дней | **22.03** |

***

## 17. ✅ КРИТЕРИИ ПРИЕМКИ

```
[ ] 100% User Isolation (violations=0)
[ ] Direct calls < 2s P95
[ ] Orchestrator plans complex tasks
[ ] Qdrant RAG context retrieval < 50ms
[ ] Approval modals work (tools + plans)
[ ] 1000 SSE connections per user
[ ] Swagger docs на /my/docs
[ ] Kubernetes deployment ready
[ ] 90%+ test coverage
```

***

## 18. 📋 DEPLOYMENT

```yaml
# docker-compose.yml
services:
  api:          # FastAPI + UserWorkerSpaces
  postgres:     # Metadata (sharded by user_id)
  redis:        # Task queues + SSE buffers
  qdrant:       # Vector context (user collections)
  prometheus:   # Per-user metrics
  grafana:      # User-specific dashboards
```

***

## 19. 🎯 УНИКАЛЬНЫЕ ВОЗМОЖНОСТИ v5.0

```
✅ 100% ПЕРСОНАЛЬНЫЕ АГЕНТЫ - нет глобальных
✅ ⚡ ДИРЕКТНЫЕ ВЫЗОВЫ - @coder "напиши код" (1-2 сек)
✅ 🧠 АВТО ПЛАН - сложные задачи через оркестратор
✅ 🗄️ QDRANT RAG - семантическая память 1M+ сообщений
✅ 🛡️ APPROVAL CONTROL - tools + plans под контролем
✅ 🔄 AGENT BUS - параллельное выполнение задач
✅ 📡 REAL-TIME SSE - мгновенные обновления
✅ 🛡️ ZERO GLOBAL STATE - полная изоляция
```

***

## 20. 📞 РЕСПОНСИБИЛЬНОСТЬ

| Роль | Ответственный | Контакт |
|------|---------------|---------|
| Tech Lead | Иванов И.И. | techlead@company.com |
| Backend | Петров П.П. | backend@company.com |
| Frontend | Сидорова А.А. | frontend@company.com |
| DevOps | Козлов В.В. | devops@company.com |
| AI/ML | Смирнова Е.Е. | ai@company.com |

***

**✅ УТВЕРЖДЕНО Версия 5.0 FINAL**  
**Дата:** 11 февраля 2026  
**Срок сдачи:** 22 марта 2026  

***

## 🚀 ИТОГ

**Personal Multi-Agent AI Platform v5.0** - это **production-ready решение** для создания персональных AI команд с:

- Полной изоляцией пользователей
- Двумя режимами (прямой/автоматический)  
- Vector memory через Qdrant
- Real-time взаимодействием
- Approval контролем
- Масштабируемой архитектурой

**Каждый пользователь = независимая AI команда!** 🎯✨