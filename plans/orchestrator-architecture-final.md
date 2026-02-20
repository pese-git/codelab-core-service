# Personal Orchestrator - Финальная архитектура

**Дата:** 20 февраля 2026  
**Версия:** 1.0 FINAL


## I. Backend Architecture

### Компоненты

```
┌─────────────────────────────────────────────────────────┐
│              User Request (Frontend)                     │
│         POST /my/projects/{project_id}/chat/             │
│                {session_id}/message/                     │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
         ┌───────────────────────┐
         │   Chat Handler        │
         │  (project_chat.py)    │
         └───────┬───────────────┘
                 │
        ┌────────┴────────┐
        │                 │
        ▼                 ▼
   target_agent?      NO target_agent
        │                 │
        │                 ▼
        │         ┌──────────────────┐
        │         │ Orchestrator     │
        │         │ UserAgent        │
        │         │ (координатор)    │
        │         └────┬─────────────┘
        │              │
        │              ▼
        │      ┌───────────────────┐
        │      │ Personal Planner  │
        │      │ (task planning)   │
        │      └────┬──────────────┘
        │           │
        │           ▼
        │   ┌──────────────────────┐
        │   │ Task Executor        │
        │   │ (execution coord)    │
        │   └────┬─────────────────┘
        │        │
        │        ▼
        │   ┌────────────────────────────┐
        │   │     Agent Bus              │
        │   │  (message routing)         │
        │   └─┬──────┬──────┬──────┬────┘
        │     │      │      │      │
        ▼     ▼      ▼      ▼      ▼
    ┌─────────────────────────────────┐
    │   UserAgent instances           │
    │   (loaded from database)        │
    │                                 │
    │   - ask (LOW risk)              │
    │   - debug (MEDIUM risk)         │
    │   - code (HIGH risk)            │
    │   - architect (LOW risk)        │
    │   - custom agents...            │
    └─────────────────────────────────┘
```

---

## III. Database Schema

### TaskPlan Model

```python
class TaskPlan(Base):
    """Task plan created by Personal Planner."""
    
    __tablename__ = "task_plans"
    
    id: UUID  # Primary key
    user_id: UUID  # Foreign key to users
    project_id: UUID  # Foreign key to user_projects
    session_id: UUID  # Foreign key to chat_sessions
    original_request: str  # Natural language request
    status: str  # created, pending_approval, executing, completed, failed, partial_success
    total_estimated_cost: float  # Dollars
    total_estimated_duration: float  # Seconds
    requires_approval: bool
    approval_reason: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    
    # Relationships
    tasks: list[TaskPlanTask]
    session: ChatSession
```

### TaskPlanTask Model

```python
class TaskPlanTask(Base):
    """Individual task within a plan."""
    
    __tablename__ = "task_plan_tasks"
    
    id: UUID  # Primary key
    plan_id: UUID  # Foreign key to task_plans
    task_id: str  # Logical task ID (task_0, task_1, ...)
    description: str  # Task description
    agent_id: UUID  # Foreign key to user_agents
    dependencies: JSON  # list[str] - task_ids this depends on
    estimated_cost: float
    estimated_duration: float
    risk_level: str  # LOW, MEDIUM, HIGH
    status: str  # pending, executing, completed, failed
    result: JSON | None  # Task execution result
    error: str | None  # Error message if failed
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    
    # Relationships
    plan: TaskPlan
    agent: UserAgent
```

### Indexes

```sql
CREATE INDEX ix_task_plans_user_id_project_id ON task_plans(user_id, project_id);
CREATE INDEX ix_task_plans_session_id ON task_plans(session_id);
CREATE INDEX ix_task_plans_status_created_at ON task_plans(status, created_at);

CREATE INDEX ix_task_plan_tasks_plan_id ON task_plan_tasks(plan_id);
CREATE INDEX ix_task_plan_tasks_agent_id ON task_plan_tasks(agent_id);
CREATE INDEX ix_task_plan_tasks_status ON task_plan_tasks(status);
```

---

## IV. Personal Planner

### Responsibilities

1. **Load available agents from DB**
   ```python
   agents = await db.query(UserAgent).filter(
       UserAgent.project_id == project_id,
       UserAgent.status == "ready"
   ).all()
   ```

2. **Parse natural language request**
   - Rule-based keyword matching (MVP)
   - Extract tasks from request
   - Identify required capabilities

3. **Match tasks to agents by capabilities**
   ```python
   for task in tasks:
       for agent in agents:
           agent_caps = agent.config.get("metadata", {}).get("capabilities", [])
           if task.required_capability in agent_caps:
               task.agent_id = agent.id
               break
   ```

4. **Analyze dependencies**
   - Sequential patterns: "then", "after", "using"
   - Parallel patterns: "and", "also", "simultaneously"
   - Build dependency graph

5. **Detect circular dependencies (DFS)**
   ```python
   def has_cycle(task_id, visited, rec_stack):
       visited.add(task_id)
       rec_stack.add(task_id)
       for dep in task.dependencies:
           if dep not in visited:
               if has_cycle(dep, visited, rec_stack):
                   return True
           elif dep in rec_stack:
               return True
       rec_stack.remove(task_id)
       return False
   ```

6. **Topological sort for execution levels**
   ```python
   levels = []
   in_degree = {t.task_id: len(t.dependencies) for t in tasks}
   
   while any(d >= 0 for d in in_degree.values()):
       current_level = [tid for tid, deg in in_degree.items() if deg == 0]
       levels.append(current_level)
       
       for tid in current_level:
           in_degree[tid] = -1
           for other in tasks:
               if tid in other.dependencies:
                   in_degree[other.task_id] -= 1
   ```

7. **Estimate costs and duration**
   ```python
   for task in tasks:
       agent = agents_map[task.agent_id]
       task.estimated_cost = agent.config.get("metadata", {}).get("cost_per_call", 0.01)
   
   # Duration = sum of level durations (parallel within level)
   total_duration = sum(max(task.duration for task in level) for level in levels)
   ```

8. **Check approval requirement**
   ```python
   requires_approval = (
       len(tasks) >= 3 or
       total_cost > 0.10 or
       any(t.risk_level == "HIGH" for t in tasks) or
       total_duration > 30
   )
   ```

9. **Persist to PostgreSQL**
   ```python
   plan = TaskPlan(
       user_id=user_id,
       project_id=project_id,
       session_id=session_id,
       original_request=request,
       status="created",
       total_estimated_cost=total_cost,
       total_estimated_duration=total_duration,
       requires_approval=requires_approval
   )
   db.add(plan)
   
   for task in tasks:
       db.add(TaskPlanTask(
           plan_id=plan.id,
           task_id=task.task_id,
           agent_id=task.agent_id,
           dependencies=task.dependencies,
           ...
       ))
   
   await db.commit()
   ```

10. **Cache in Redis (TTL 24h)**
    ```python
    cache_key = f"plan:{user_id}:{project_id}:{hash(request)}"
    await redis.setex(cache_key, 86400, json.dumps(plan.to_dict()))
    ```

---

## V. Task Executor

### Responsibilities

1. **Load plan from DB**
   ```python
   plan = await db.query(TaskPlan).filter(
       TaskPlan.id == plan_id
   ).options(
       selectinload(TaskPlan.tasks).selectinload(TaskPlanTask.agent)
   ).first()
   ```

2. **Check approval status**
   ```python
   if plan.requires_approval and plan.status == "pending_approval":
       # Wait for user decision via /my/approvals/{id}/confirm
       return {"status": "waiting_for_approval"}
   ```

3. **Execute by levels (parallel within level)**
   ```python
   for level in plan.execution_levels:
       tasks_in_level = []
       
       for task_id in level:
           task = plan.get_task(task_id)
           
           # Get results from dependencies
           context = {
               f"result_{dep}": completed_tasks[dep].result
               for dep in task.dependencies
           }
           
           # Submit to AgentBus
           task_item = await agent_bus.submit_task(
               agent_id=task.agent_id,
               task_id=task.task_id,
               payload={
                   "user_message": task.description,
                   "context": context
               }
           )
           
           tasks_in_level.append(task_item)
       
       # Wait for all tasks in level
       await asyncio.gather(*[t.completed.wait() for t in tasks_in_level])
       
       # Update DB with results
       for task_item in tasks_in_level:
           await db.execute(
               update(TaskPlanTask)
               .where(TaskPlanTask.task_id == task_item.task_id)
               .values(
                   status="completed" if not task_item.error else "failed",
                   result=task_item.result,
                   error=str(task_item.error) if task_item.error else None,
                   completed_at=datetime.utcnow()
               )
           )
       
       # Send SSE events
       for task_item in tasks_in_level:
           await stream_manager.broadcast_event({
               "event_type": "task_completed",
               "task_id": task_item.task_id,
               "result": task_item.result
           })
   ```

4. **Handle partial failures**
   ```python
   failed_tasks = [t for t in tasks if t.status == "failed"]
   
   if failed_tasks:
       # Abort dependent tasks
       for task in tasks:
           if any(dep in failed_tasks for dep in task.dependencies):
               task.status = "aborted"
       
       plan.status = "partial_success"
   else:
       plan.status = "completed"
   
   await db.commit()
   ```

5. **Server restart recovery**
   ```python
   # On startup, find incomplete plans
   incomplete_plans = await db.query(TaskPlan).filter(
       TaskPlan.status.in_(["executing", "pending_approval"])
   ).all()
   
   for plan in incomplete_plans:
       # Resume execution from last completed task
       completed_task_ids = [
           t.task_id for t in plan.tasks if t.status == "completed"
       ]
       
       # Continue from next level
       await executor.execute_plan(plan, resume_from=completed_task_ids)
   ```

---

## VI. Approval Manager

### Workflow

```python
class ApprovalManager:
    async def request_plan_approval(
        self,
        plan: TaskPlan,
        stream_manager: StreamManager
    ) -> ApprovalRequest:
        """Request user approval for plan execution."""
        
        # Create approval request
        approval = ApprovalRequest(
            user_id=plan.user_id,
            type="plan",
            payload={
                "plan_id": str(plan.id),
                "tasks": [t.to_dict() for t in plan.tasks],
                "total_cost": plan.total_estimated_cost,
                "total_duration": plan.total_estimated_duration,
                "risk_level": max(t.risk_level for t in plan.tasks)
            },
            status="pending",
            timeout=300  # 5 minutes
        )
        db.add(approval)
        await db.commit()
        
        # Send SSE notification
        await stream_manager.broadcast_event({
            "event_type": "approval_required",
            "approval_id": str(approval.id),
            "plan": plan.to_dict(),
            "timeout": 300
        })
        
        # Update plan status
        plan.status = "pending_approval"
        await db.commit()
        
        return approval
    
    async def confirm_approval(self, approval_id: UUID, decision: str):
        """User confirms or rejects approval."""
        
        approval = await db.get(ApprovalRequest, approval_id)
        approval.status = "approved" if decision == "confirm" else "rejected"
        approval.resolved_at = datetime.utcnow()
        approval.decision = decision
        
        # Load plan
        plan_id = UUID(approval.payload["plan_id"])
        plan = await db.get(TaskPlan, plan_id)
        
        if decision == "confirm":
            # Start execution
            plan.status = "executing"
            await db.commit()
            
            # Send to Task Executor via AgentBus
            await agent_bus.publish(
                queue_name=f"executor:{plan.user_id}",
                message={
                    "type": "execute_plan",
                    "plan_id": str(plan.id)
                }
            )
        else:
            # Reject plan
            plan.status = "rejected"
            await db.commit()
```

---

## VII. User-Defined Agents

### Дефолтный Starter Pack

При создании проекта (`POST /my/projects/`) автоматически создаются 5 агентов:

```python
DEFAULT_AGENTS = [
    {
        "name": "ask",
        "system_prompt": "You are a knowledgeable technical assistant...",
        "model": "openrouter/openai/gpt-4.1",
        "tools": [],
        "metadata": {
            "capabilities": ["answer_question", "explain_concept", "analyze_code"],
            "risk_level": "LOW",
            "cost_per_call": 0.01,
            "estimated_duration": 5.0
        }
    },
    {
        "name": "debug",
        "system_prompt": "You are an expert software debugger...",
        "model": "openrouter/openai/gpt-4.1",
        "tools": ["read_file", "execute_command"],
        "metadata": {
            "capabilities": ["investigate_error", "add_logging", "trace_execution"],
            "risk_level": "MEDIUM",
            "cost_per_call": 0.02,
            "estimated_duration": 10.0
        }
    },
    {
        "name": "code",
        "system_prompt": "You are a highly skilled software engineer...",
        "model": "openrouter/openai/gpt-4.1",
        "tools": ["read_file", "write_file", "execute_command"],
        "metadata": {
            "capabilities": ["implement_feature", "fix_bug", "refactor_code"],
            "risk_level": "HIGH",
            "cost_per_call": 0.05,
            "estimated_duration": 15.0
        }
    },
    {
        "name": "architect",
        "system_prompt": "You are an experienced technical leader...",
        "model": "openrouter/openai/gpt-4.1",
        "tools": [],
        "metadata": {
            "capabilities": ["design_architecture", "create_specifications", "validate_standards"],
            "risk_level": "LOW",
            "cost_per_call": 0.02,
            "estimated_duration": 10.0
        }
    },
    {
        "name": "orchestrator",
        "system_prompt": "You are a strategic workflow orchestrator...",
        "model": "openrouter/openai/gpt-4.1",
        "tools": [],
        "metadata": {
            "capabilities": ["coordinate_workflow", "route_tasks", "aggregate_results"],
            "risk_level": "LOW",
            "cost_per_call": 0.01,
            "estimated_duration": 5.0
        }
    }
]
```

### Пользовательская настройка

**Добавление агента:**
```http
POST /my/projects/{project_id}/agents/
{
  "name": "database-expert",
  "system_prompt": "You are a PostgreSQL expert...",
  "model": "openrouter/anthropic/claude-3.5-sonnet",
  "tools": ["execute_sql", "analyze_query"],
  "metadata": {
    "capabilities": ["optimize_query", "design_schema", "debug_sql"],
    "risk_level": "MEDIUM",
    "cost_per_call": 0.03
  }
}
```

**Обновление capabilities:**
```http
PUT /my/projects/{project_id}/agents/{agent_id}
{
  "config": {
    "metadata": {
      "capabilities": ["implement_feature", "fix_bug", "write_tests"],
      "risk_level": "HIGH"
    }
  }
}
```

---

## VIII. Полный Flow

### Scenario: "Fix auth error"

```
1. Frontend → Backend
   POST /my/projects/abc-123/chat/session-456/message/
   { "content": "Fix auth error", "target_agent": null }

2. Chat Handler
   - target_agent is null → use Orchestrator Agent
   - Load Orchestrator Agent from DB:
     SELECT * FROM user_agents 
     WHERE project_id='abc-123' AND name='orchestrator'

3. Orchestrator Agent (UserAgent instance)
   - Calls Personal Planner

4. Personal Planner
   - Load available agents:
     SELECT * FROM user_agents 
     WHERE project_id='abc-123' AND status='ready'
   
   - Parse request → extract tasks:
     Task 1: "Investigate auth error" → needs ["investigate_error"]
     Task 2: "Fix the error" → needs ["fix_bug"]
   
   - Match to agents:
     Task 1 → Debug Agent (has "investigate_error" capability)
     Task 2 → Code Agent (has "fix_bug" capability)
   
   - Analyze dependencies:
     Task 2 depends on Task 1 (sequential)
   
   - Topological sort:
     Level 0: [Task 1]
     Level 1: [Task 2]
   
   - Estimate:
     Cost: $0.02 + $0.05 = $0.07
     Duration: 10s + 15s = 25s
   
   - Check approval:
     tasks=2 < 3 ✓
     cost=$0.07 < $0.10 ✓
     risk=MEDIUM (not HIGH) ✓
     duration=25s < 30s ✓
     → NO approval needed
   
   - Save to DB:
     INSERT INTO task_plans (...)
     INSERT INTO task_plan_tasks (...) -- Task 1, Task 2
   
   - Cache in Redis:
     SET plan:user123:abc-123:hash(request) {...} EX 86400

5. Task Executor
   - Load plan from DB
   - Level 0: Execute Task 1 (Debug Agent)
     * Submit to AgentBus
     * Debug Agent investigates → returns diagnostic
     * Update DB: task_plan_tasks.result = {...}
     * Send SSE: task_completed
   
   - Level 1: Execute Task 2 (Code Agent)
     * Submit to AgentBus with Task 1 result as context
     * Code Agent fixes → returns implementation
     * Update DB: task_plan_tasks.result = {...}
     * Send SSE: task_completed
   
   - Update plan status:
     plan.status = "completed"
     plan.completed_at = now()

6. Frontend receives SSE events
   - task_started (Task 1)
   - task_completed (Task 1)
   - task_started (Task 2)
   - task_completed (Task 2)
   - plan_completed
```

---

## IX. Key Design Decisions

### 1. User-Defined Agents (NOT hardcoded types)
- ✅ Agents stored in `user_agents` table
- ✅ Capabilities in `config.metadata.capabilities`
- ✅ Пользователь может добавлять/удалять/редактировать
- ✅ Изоляция по user_id + project_id

### 2. Full State Persistence in PostgreSQL
- ✅ TaskPlan + TaskPlanTask models
- ✅ Все оценки, зависимости, результаты в БД
- ✅ Восстановление после перезагрузки сервера
- ✅ Audit trail для всех операций

### 3. Redis Cache for Performance
- ✅ Кеш планов для похожих запросов (TTL 24ч)
- ✅ Ускорение планирования
- ✅ Автоматическая инвалидация при изменении агентов

### 4. Async Coordination via AgentBus
- ✅ TaskItem с asyncio.Event для ожидания результатов
- ✅ Параллельное выполнение задач одного уровня
- ✅ Concurrency control per agent

### 5. Approval Manager Integration
- ✅ Проверка перед выполнением (3+ tasks, >$0.10, HIGH risk, >30s)
- ✅ SSE уведомления пользователю
- ✅ Timeout 300 сек с auto-reject
- ✅ История approvals в БД

---

## X. Implementation Phases

| Phase | Component | Tasks | Dependencies |
|-------|-----------|-------|--------------|
| 1 | Database Models | TaskPlan, TaskPlanTask, migration | - |
| 2 | Personal Planner | Planning logic, DB persistence, Redis cache | Phase 1 |
| 3 | Task Executor | Execution, recovery, SSE events | Phase 1, 2 |
| 4 | Approval Manager | Foundation, workflows, timeout | Phase 1 |
| 5 | Approval Integration | Orchestrator + Approval Manager | Phase 2, 3, 4 |
| 6-8 | REST API Endpoints | Orchestrator, Approval, Context APIs | Phase 1-5 |
| 9 | Security & Rate Limiting | Middleware, validation | Phase 6-8 |
| 10 | Comprehensive Testing | Unit, integration, security tests | All phases |
| 11 | Monitoring | Prometheus, Grafana, tracing | All phases |
| 12 | Documentation | Architecture docs, API docs, guides | All phases |

---

## XI. Critical Requirements

✅ **User-Defined Agents** — агенты загружаются из БД, не hardcoded  
✅ **Capabilities Matching** — выбор агентов по `config.metadata.capabilities`  
✅ **Full State in PostgreSQL** — планы + задачи + результаты для восстановления  
✅ **User Isolation** — фильтрация по user_id + project_id везде  
✅ **Async Coordination** — через AgentBus + asyncio.Event  
✅ **Real-time Feedback** — SSE события через StreamManager  
✅ **Approval Workflow** — для HIGH risk и сложных планов  
✅ **Server Restart Recovery** — загрузка incomplete plans из БД  

Архитектура готова к реализации.
