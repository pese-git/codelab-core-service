```mermaid
flowchart TD
    %% USERS & UI
    User[User / IDE Plugin]
    User -->|HTTP / WS| APIGateway[API Gateway / BFF]

    %% ORCHESTRATOR
    APIGateway --> Orchestrator[Dialogue Orchestrator - state machine, session mgmt]
    
    %% CHAT HISTORY & TASK STATE
    Orchestrator --> ChatHistoryDB[Chat History DB - user-visible messages]
    Orchestrator --> TaskStateDB[Task / Session State DB - current task, code snippets, summaries]

    %% AGENTS
    Orchestrator --> Planner[Planner Agent - plan generation, project structure]
    Orchestrator --> Executor[Executor Agent - code generation, file edits]
    Orchestrator --> Critic[Critic Agent - code review, QA, semantic memory]
    Orchestrator --> HIL[Human-in-the-loop - approve, edit, guidance]

    %% MEMORY
    Planner -->|read/write| MemoryAPI[Memory API - user patterns, coding style, lessons]
    Executor -->|read/write| MemoryAPI
    Critic -->|read/write| MemoryAPI
    MemoryAPI --> VectorDB[Vector DB / Knowledge Base]

    %% TOOL EXECUTION
    Executor --> ToolRunner[Tool Runner - Linter, Test Runner, CI/CD, Git]
    ToolRunner --> ToolStore[Tool Execution Store - raw outputs, logs]
    ToolRunner --> TaskStateDB

    %% CHAT HISTORY WRITES
    Planner --> ChatHistoryDB
    Executor --> ChatHistoryDB
    Critic --> ChatHistoryDB
    HIL --> ChatHistoryDB

    %% CONTEXT FEED
    Planner -->|context| Orchestrator
    Executor -->|context| Orchestrator
    Critic -->|context| Orchestrator
    HIL -->|context| Orchestrator

    %% HUMAN IN LOOP FLOW
    ToolRunner -->|summary| HIL
    HIL -->|approval/override| TaskStateDB
```


```mermaid
flowchart TD
    %% USER & SESSIONS
    User[User / IDE Plugin]

    %% SESSIONS
    User -->|connects| SessionA[Session A]
    User -->|connects| SessionB[Session B]

    %% CONVERSATIONS
    SessionA --> ConvA1[Conversation A1]
    SessionA --> ConvA2[Conversation A2]
    SessionB --> ConvB1[Conversation B1]

    %% ORCHESTRATOR
    ConvA1 --> OrchestratorA[Orchestrator - state machine]
    ConvA2 --> OrchestratorA2[Orchestrator]
    ConvB1 --> OrchestratorB[Orchestrator]

    %% CHAT HISTORY & TASK STATE
    OrchestratorA --> ChatHistoryA[Chat History DB - user-visible messages]
    OrchestratorA --> TaskStateA[Task State DB - current code snippets, task summary]
    OrchestratorA2 --> ChatHistoryA2[Chat History DB]
    OrchestratorA2 --> TaskStateA2[Task State DB]
    OrchestratorB --> ChatHistoryB[Chat History DB]
    OrchestratorB --> TaskStateB[Task State DB]

    %% AGENTS
    OrchestratorA --> PlannerA[Planner Agent]
    OrchestratorA --> ExecutorA[Executor Agent]
    OrchestratorA --> CriticA[Critic Agent]
    OrchestratorA --> HIL_A[Human-in-the-loop]

    %% MEMORY
    PlannerA -->|read| MemoryAPI[Memory API - user patterns, coding style]
    ExecutorA -->|read| MemoryAPI
    CriticA -->|write/reflection| MemoryAPI
    MemoryAPI --> VectorDB[Vector DB / Knowledge Base]

    %% TOOL EXECUTION
    ExecutorA --> ToolRunnerA[Tool Runner - linters, CI/CD, Git]
    ToolRunnerA --> ToolStoreA[Tool Execution Store - raw outputs, logs]
    ToolRunnerA --> TaskStateA[summary only]

    %% CHAT HISTORY WRITES
    PlannerA --> ChatHistoryA
    ExecutorA --> ChatHistoryA
    CriticA --> ChatHistoryA
    HIL_A --> ChatHistoryA

    %% CONTEXT FEED
    OrchestratorA -->|context prompt| PlannerA
    OrchestratorA -->|context prompt| ExecutorA
    OrchestratorA -->|context prompt| CriticA
    OrchestratorA -->|context prompt| HIL_A

    %% HUMAN IN LOOP FLOW
    ToolRunnerA -->|summary| HIL_A
    CriticA -->|review summary| HIL_A
    HIL_A -->|approval/override| TaskStateA

    %% RESTORE CONTEXT FLOW
    SessionA -->|resume| OrchestratorA
    OrchestratorA -->|load| ChatHistoryA
    OrchestratorA -->|load| TaskStateA
    OrchestratorA -->|load| MemoryAPI (user patterns, lessons)
    OrchestratorA -->|load| ToolStoreA summary only

    SessionB -->|resume| OrchestratorB
    OrchestratorB -->|load| ChatHistoryB
    OrchestratorB -->|load| TaskStateB
    OrchestratorB -->|load| MemoryAPI
    OrchestratorB -->|load| ToolStore summary only
```


```mermaid
flowchart TD
    %% Пользователь
    User[User / IDE Plugin]
    User -->|request| APIGateway[API Gateway / BFF]

    %% Orchestrator маршрутизирует запрос
    APIGateway --> Orchestrator[Dialogue Orchestrator - state machine]

    %% Выбор агента
    Orchestrator --> SelectedAgent[Selected Agent - Planner, Executor, Critic]

    %% Вызов LLM
    SelectedAgent -->|structured JSON request| LLM[LLM / Model API]
    LLM -->|JSON response| SelectedAgent

    %% JSON fields separation
    SelectedAgent -->|validate JSON schema| JSONParser[JSON Parser]
    
    %% User-facing fields
    JSONParser -->|user_message| UserFacing[User-facing content: clarification_requests + summary description]
    UserFacing -->|render text/markdown| User

    %% Internal fields
    JSONParser -->|followup_tasks| TaskStateDB[Task State DB]
    JSONParser -->|context_analysis| EpisodicMemory[Episodic Memory - current session]
    JSONParser -->|architecture_decision + rationale + risks| HIL[Human-in-the-loop]
    
    %% Memory update after HIL
    HIL -->|approval + reflection| MemoryAPI[Memory Service API]
    MemoryAPI --> VectorDB[Vector DB / Knowledge Base]

    %% Optional tool execution
    SelectedAgent -->|tool_call instructions| ToolRunner[Tool Runner - CI/CD, linters]
    ToolRunner --> ToolStore[Tool Execution Store - raw outputs]
    ToolRunner --> TaskStateDB[Task summary only]

    %% Notes
    classDef internal fill:#f9f,stroke:#333,stroke-width:1px;
    class JSONParser,HIL,MemoryAPI,VectorDB,TaskStateDB,ToolRunner,ToolStore internal;
```