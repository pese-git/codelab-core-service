# Архитектура codelab-core-service

## Общая архитектура системы

```mermaid
graph TB
    subgraph Клиент["👤 Клиентский слой"]
        UI["Web/Gradio UI"]
        API["REST API Клиент"]
    end

    subgraph API_Layer["🔌 API Маршруты"]
        Health["Health Check"]
        Projects["Projects API"]
        Chat["Project Chat API"]
        Agents["Project Agents API"]
        Streaming["Streaming API"]
        Monitor["Monitoring API"]
    end

    subgraph Middleware_Layer["🛡️ Middleware"]
        UserIsolation["User Isolation Middleware"]
        ProjectValidation["Project Validation Middleware"]
        Auth["JWT Authentication"]
    end

    subgraph Core_Orchestrator["🎯 Personal Orchestrator"]
        OrchestratorAgent["Orchestrator Agent"]
        TaskPlanner["Task Planner"]
        DependencyAnalyzer["Dependency Analyzer"]
        CostEstimator["Cost Estimator"]
        TimeEstimator["Time Estimator"]
        ExecutionEngine["Execution Engine"]
    end

    subgraph Core_Bus["📡 Agent Bus Messaging"]
        AgentBus["Agent Bus"]
        MessageQueue["Message Queue"]
        EventBroker["Event Broker"]
    end

    subgraph Core_System["⚙️ Core Services"]
        WorkerSpaceManager["Worker Space Manager"]
        UserWorkerSpace["User Worker Space"]
        ApprovalManager["Approval Manager"]
        StreamManager["Stream Manager"]
        ContextAgent["Contextual Agent"]
        OutboxPublisher["Outbox Publisher"]
    end

    subgraph Agent_System["🤖 Agent System"]
        ManagerAgent["Manager Agent"]
        UserAgents["User-Defined Agents"]
        StarterPack["Default Starter Pack Agents"]
        AgentToolsSystem["Agent Tools System"]
    end

    subgraph Storage_Layer["💾 Data Layer"]
        PostgreSQL["PostgreSQL Database"]
        Models["SQLAlchemy Models"]
        Migrations["Alembic Migrations"]
        EventOutbox["Event Outbox Table"]
    end

    subgraph Cache_Layer["⚡ Cache Layer"]
        Redis["Redis Cache"]
        VectorStore["Vector Store / Qdrant"]
        AgentContextStore["Agent Context Store"]
    end

    subgraph LLM_Layer["🧠 LLM Integration"]
        LiteLLM["LiteLLM Router"]
        OpenAI["OpenAI API"]
        Anthropic["Anthropic API"]
        OtherLLMs["Other LLM Providers"]
    end

    subgraph Monitoring["📊 Monitoring & Logging"]
        Prometheus["Prometheus Metrics"]
        Grafana["Grafana Dashboards"]
        Logging["Structured Logging"]
        ErrorTracking["Error Tracking"]
    end

    Клиент -->|HTTP| API_Layer
    API_Layer --> Middleware_Layer
    Middleware_Layer -->|Routes| Core_Orchestrator
    Middleware_Layer -->|Routes| Core_System
    Middleware_Layer -->|Routes| Agent_System

    Core_Orchestrator -->|Create/Execute Plans| Storage_Layer
    Core_Orchestrator -->|Plan Cache| Cache_Layer
    Core_Orchestrator -->|Assign Agents| Agent_System
    Core_Orchestrator -->|Estimate Costs| LLM_Layer

    Core_System -->|Manage Tasks| Core_Bus
    Core_System -->|Send Messages| Core_Bus
    Core_System -->|Record Domain Events| Storage_Layer
    OutboxPublisher -->|Polling| Storage_Layer
    OutboxPublisher -->|Publish| Streaming
    Core_Bus -->|Event Stream| Streaming

    Agent_System -->|Execute Tasks| LLM_Layer
    Agent_System -->|Store Context| Cache_Layer
    Agent_System -->|Tools Integration| Core_Bus

    Storage_Layer -->|Models| Core_Orchestrator
    Storage_Layer -->|Models| Core_System
    Storage_Layer -->|Models| Agent_System

    Cache_Layer -->|Cache Plans| Core_Orchestrator
    Cache_Layer -->|Vector Search| Agent_System

    LLM_Layer -->|Token Costs| Core_Orchestrator

    Monitoring -->|Collect Metrics| Core_Orchestrator
    Monitoring -->|Collect Metrics| Core_System
    Monitoring -->|Collect Metrics| Agent_System

    style Клиент fill:#e1f5ff
    style API_Layer fill:#f3e5f5
    style Middleware_Layer fill:#fff3e0
    style Core_Orchestrator fill:#c8e6c9
    style Core_Bus fill:#ffccbc
    style Core_System fill:#ffe0b2
    style Agent_System fill:#b3e5fc
    style Storage_Layer fill:#f0f4c3
    style Cache_Layer fill:#dcedc8
    style LLM_Layer fill:#f8bbd0
    style Monitoring fill:#d1c4e9
```

## Схема базы данных (Task Plans)

```mermaid
erDiagram
    USERS ||--o{ TASK_PLANS : has
    USERS ||--o{ USER_PROJECTS : creates
    USERS ||--o{ USER_AGENTS : defines
    USER_PROJECTS ||--o{ USER_AGENTS : contains
    USER_PROJECTS ||--o{ CHAT_SESSIONS : has
    CHAT_SESSIONS ||--o{ TASK_PLANS : "initiates from"
    TASK_PLANS ||--o{ TASK_PLAN_TASKS : contains
    USER_AGENTS ||--o{ TASK_PLAN_TASKS : "assigned to"

    TASK_PLANS {
        uuid id PK
        uuid user_id FK
        uuid project_id FK
        uuid session_id FK
        string original_request
        string status
        float total_estimated_cost
        float total_estimated_duration
        boolean requires_approval
        string approval_reason
        timestamp created_at
        timestamp started_at
        timestamp completed_at
    }

    TASK_PLAN_TASKS {
        uuid id PK
        uuid plan_id FK
        string task_id "logical ID"
        string description
        uuid agent_id FK
        json dependencies "list of task_ids"
        float estimated_cost
        float estimated_duration
        string risk_level
        string status
        json result
        string error
        timestamp created_at
        timestamp started_at
        timestamp completed_at
    }

    USERS {
        uuid id PK
        string email
        string username
        timestamp created_at
    }

    USER_PROJECTS {
        uuid id PK
        uuid user_id FK
        string name
        timestamp created_at
    }

    USER_AGENTS {
        uuid id PK
        uuid user_id FK
        uuid project_id FK
        string name
        json config
        string status
        timestamp created_at
    }

    CHAT_SESSIONS {
        uuid id PK
        uuid user_id FK
        uuid project_id FK
        string topic
        timestamp created_at
    }
```

## Workflow Personal Orchestrator

```mermaid
sequenceDiagram
    participant User as Пользователь
    participant API as API Handler
    participant Orchestrator as Personal Orchestrator
    participant Planner as Task Planner
    participant ApprovalMgr as Approval Manager
    participant Executor as Execution Engine
    participant Agent as Agent
    participant DB as PostgreSQL
    participant Cache as Redis Cache

    User->>API: POST /chat (естественный язык)
    API->>Orchestrator: Создать план из запроса
    
    Orchestrator->>Planner: Анализировать и построить граф задач
    Planner->>DB: Загрузить доступные агенты
    Planner->>Planner: Парсить зависимости и обнаружить циклы
    
    Planner->>Orchestrator: Вернуть граф задач
    Orchestrator->>Orchestrator: Оценить стоимость и время
    
    Orchestrator->>DB: Сохранить план (status: created)
    
    alt requires_approval
        Orchestrator->>ApprovalMgr: Отправить на утверждение
        ApprovalMgr->>User: Отобразить детали плана
        User->>ApprovalMgr: Утвердить/Отклонить
        ApprovalMgr->>Orchestrator: Решение по утверждению
    else auto_execute
        Orchestrator->>Executor: Запустить выполнение
    end
    
    Orchestrator->>DB: Обновить статус плана (executing)
    
    Executor->>Executor: Топологическая сортировка
    Executor->>Agent: Выполнить задачу (с контекстом)
    
    Agent->>Agent: Обработать с LLM
    Agent->>Cache: Сохранить промежуточные результаты
    
    Agent->>Executor: Вернуть результат
    Executor->>DB: Сохранить результат задачи
    
    Executor->>Executor: Проверить готовые зависимые задачи
    Executor->>Agent: Выполнить следующую задачу
    
    alt task_failed
        Executor->>DB: Пометить план как failed/partial_success
        Executor->>API: Отправить SSE error event
    else task_completed
        Executor->>DB: Пометить план как completed
        Executor->>API: Отправить SSE completion event
        Executor->>Cache: Кешировать успешный план
    end
    
    API->>User: Транслировать результаты через SSE
```

## Процесс оценки стоимости

```mermaid
graph LR
    A["Анализ задач"] --> B["Выбор агентов"]
    B --> C["Расчет стоимости LLM"]
    C --> D["Стоимость embeddings"]
    D --> E["Общая оценка"]
    E --> F{"Cost > $0.10?"}
    F -->|Да| G["requires_approval = true"]
    F -->|Нет| H["Авто-выполнение"]
    G --> I["Отправить на утверждение"]
    H --> J["В очередь выполнения"]
    I --> K["Обзор пользователем"]
    K --> J
```

## Взаимодействие ключевых подсистем

### 1. **Personal Orchestrator**
   - Анализирует естественный язык запросов
   - Строит графы зависимостей между задачами
   - Оценивает стоимость и длительность
   - Управляет workflow утверждения
   - Выполняет планы с правильной последовательностью

### 2. **Agent System**
   - Загружает агенты пользователя из БД
   - Выбирает агентов по требованиям задач
   - Выполняет задачи с назначенными LLM
   - Возвращает промежуточные результаты

### 3. **Storage Layer**
   - Сохраняет планы и задачи для восстановления
   - Ведет audit trail выполнения
   - Хранит промежуточные результаты

### 4. **Cache Layer**
   - Redis: Кеширует похожие планы (TTL 24h)
   - Qdrant: Векторный поиск по контексту
   - Сокращает время планирования

### 5. **Approval Manager**
   - Перехватывает планы, требующие утверждения
   - Предоставляет детали плана пользователю
   - Управляет timeout утверждения (300s)

### 6. **Agent Bus**
   - Маршрутизирует сообщения между агентами
   - Ведет event stream для SSE
   - Координирует параллельное выполнение

### 7. **Event Outbox + Publisher (Event Logging System)**
   - **Event Outbox**: Таблица для дурабельного хранения доменных событий
     - Записывает message_created, agent_switched и другие доменные события атомарно с изменением состояния
     - Использует JSONB для гибкого payload, индексы на (status, next_retry_at), (user_id), (project_id)
     - Гарантирует: нет потери событий, все-или-ничего при коммите
   
   - **Outbox Publisher**: Background сервис для надежной доставки
     - Периодически выбирает pending события с блокировкой FOR UPDATE SKIP LOCKED
     - Публикует в StreamManager через broadcast_event()
     - Exponential backoff retry (5s→10s→20s→40s→80s→300s)
     - Обновляет статус: pending → published/failed
     - Metrics: pending_count, published_total, failed_total, latency
   
   - **Analytics API**: Read-model на основе event_outbox
     - GET /my/projects/{project_id}/events (фильтры, пагинация)
     - GET /my/projects/{project_id}/analytics/sessions/{session_id}/events
     - GET /my/projects/{project_id}/analytics (агрегированные метрики)
     - User/Project изоляция через verify_project_access()

### 8. **Идемпотентность и надежность**
   - **Event ID**: outbox.id используется как event_id, стабилен при ретраях
   - **Consumer Deduplication**: Клиенты дедуплицируют по event_id в payload
   - **Exactly-Once Semantics**: At-least-once доставка + client-side deduplication
   - **Архитектурное разделение**:
     - Доменные события (message_created, agent_switched) → outbox-only
     - Технические события (DIRECT_AGENT_CALL, TASK_STARTED) → direct streaming + optional outbox

## Переходы статусов

```mermaid
stateDiagram-v2
    [*] --> created: План создан
    created --> pending_approval: Требуется утверждение
    created --> executing: Авто-выполнение
    pending_approval --> executing: Пользователь одобрил
    pending_approval --> [*]: Отклонено / timeout
    executing --> completed: Все задачи успешны
    executing --> failed: Задача ошибка
    executing --> partial_success: Некоторые задачи ошибка
    completed --> [*]
    failed --> [*]
    partial_success --> [*]
```

## Индексы БД для производительности

```sql
-- таблица task_plans
CREATE INDEX ix_task_plans_user_id_project_id ON task_plans(user_id, project_id);
CREATE INDEX ix_task_plans_session_id ON task_plans(session_id);
CREATE INDEX ix_task_plans_status_created_at ON task_plans(status, created_at);

-- таблица task_plan_tasks
CREATE INDEX ix_task_plan_tasks_plan_id ON task_plan_tasks(plan_id);
CREATE INDEX ix_task_plan_tasks_agent_id ON task_plan_tasks(agent_id);
CREATE INDEX ix_task_plan_tasks_status ON task_plan_tasks(status);

-- таблица event_outbox (Event Logging System)
CREATE INDEX ix_event_outbox_status_next_retry ON event_outbox(status, next_retry_at, created_at);
CREATE INDEX ix_event_outbox_aggregate_id_created ON event_outbox(aggregate_id, created_at);
CREATE INDEX ix_event_outbox_project_id_created ON event_outbox(project_id, created_at);
CREATE INDEX ix_event_outbox_user_id_created ON event_outbox(user_id, created_at);
-- GIN индекс для JSONB поля payload (опционально для полнотекстового поиска)
CREATE INDEX ix_event_outbox_payload_gin ON event_outbox USING GIN (payload);
```

## Точки интеграции

1. **REST API Layer** → Маршрутизирует запросы в orchestrator
2. **User Isolation Middleware** → Обеспечивает контекст user_id
3. **Project Validation** → Валидирует доступ к project_id
4. **Authentication** → Валидация JWT токена
5. **Streaming API** → SSE события во время выполнения
6. **Monitoring** → Сбор метрик для dashboard

