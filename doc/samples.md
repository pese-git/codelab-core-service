# 💻 Примеры кода - CodeLab Core Service v0.2.0

Практические примеры использования API и интеграции с платформой.

---

## 1. 🛡️ User Isolation Middleware

Автоматическая проверка изоляции пользователей на всех `/my/` endpoints.

```python
# app/middleware/user_isolation.py (реальная реализация)
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from app.logging_config import get_logger

logger = get_logger(__name__)

class UserIsolationMiddleware(BaseHTTPMiddleware):
    """Middleware для обеспечения изоляции пользователей на /my/* endpoints."""
    
    async def dispatch(self, request: Request, call_next):
        # Skip non-user endpoints
        if not request.url.path.startswith("/my/"):
            return await call_next(request)
        
        # Extract user from JWT token
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing or invalid Authorization header"
            )
        
        token = auth_header.split(" ")[1]
        try:
            # Decode JWT and extract user_id
            user_id = decode_jwt_token(token)  # Returns UUID
            request.state.user_id = user_id
            logger.info(f"User {user_id} accessing {request.url.path}")
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token"
            )
        
        response = await call_next(request)
        return response
```

---

## 2. 🏗️ Project-Based Architecture

Структура приложения организована вокруг проектов, а не пользователей.

```python
# app/models/user_project.py (база данных)
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from uuid import uuid4

class UserProject(Base):
    """User project model - основная единица изоляции."""
    
    __tablename__ = "user_projects"
    
    id = Column(UUID, primary_key=True, default=uuid4)
    user_id = Column(UUID, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    workspace_path = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relations
    agents = relationship("UserAgent", back_populates="project", cascade="all, delete-orphan")
    chat_sessions = relationship("ChatSession", back_populates="project", cascade="all, delete-orphan")
    user = relationship("User", back_populates="projects")
```

---

## 3. 📁 Endpoints - Создание проекта

**POST** `/my/projects/` - Создать проект с default Starter Pack агентами.

```python
# app/routes/projects.py
@router.post("/", status_code=status.HTTP_201_CREATED, response_model=ProjectResponse)
async def create_project(
    project_data: ProjectCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    manager: WorkerSpaceManager = Depends(get_worker_space_manager),
) -> ProjectResponse:
    """Создать новый проект с default Starter Pack."""
    
    user_id = get_current_user_id(request)
    
    # 1. Создать проект в БД
    project = UserProject(
        user_id=user_id,
        name=project_data.name,
        workspace_path=project_data.workspace_path
    )
    db.add(project)
    await db.flush()
    
    # 2. Инициализировать Starter Pack агентов
    # (CodeAssistant, DataAnalyst, DocumentWriter)
    await initialize_starter_pack(db, project.id, user_id)
    
    # 3. Создать WorkerSpace для проекта
    await manager.create_worker_space(project.id, user_id)
    
    await db.commit()
    
    logger.info(f"Project created: project_id={project.id}, user_id={user_id}")
    
    return ProjectResponse.from_orm(project)
```

**cURL пример:**
```bash
curl -X POST "http://localhost:8000/my/projects/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My AI Project",
    "workspace_path": "/Users/john/projects/ai-project"
  }'
```

---

## 4. 🤖 Agent Management - Per-Project

Все агенты привязаны к проекту, обеспечивая изоляцию.

```python
# app/routes/project_agents.py
@router.post("/", status_code=status.HTTP_201_CREATED, response_model=AgentResponse)
async def create_agent(
    project_id: UUID,
    config: AgentConfig,
    request: Request,
    project: UserProject = Depends(get_project_with_validation),
    manager: AgentManager = Depends(get_agent_manager),
) -> AgentResponse:
    """Создать агента в проекте."""
    
    user_id = get_current_user_id(request)
    
    # 1. Валидация: проект принадлежит пользователю
    if project.user_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # 2. Создать агента
    agent = UserAgent(
        project_id=project_id,
        user_id=user_id,
        name=config.name,
        status=AgentStatus.READY,
        config=config.model_dump()
    )
    db.add(agent)
    await db.flush()
    
    # 3. Инициализировать Qdrant коллекцию для агента
    await manager.initialize_agent_context(agent.id, config.name)
    
    await db.commit()
    
    return AgentResponse.from_orm(agent)
```

---

## 5. 💬 Chat - Direct Agent Call Mode ⚡

Быстрый режим вызова конкретного агента (1-2 сек).

```python
# app/routes/project_chat.py (упрощенный пример)
@router.post("/{session_id}/message/", response_model=MessageResponse)
async def send_message(
    project_id: UUID,
    session_id: UUID,
    message_req: MessageRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    project: UserProject = Depends(get_project_with_validation),
) -> MessageResponse:
    """Отправить сообщение - режим прямого вызова или автоматический."""
    
    user_id = get_current_user_id(request)
    
    # 1. Сохранить пользовательское сообщение
    user_message = Message(
        session_id=session_id,
        role=MessageRole.USER,
        content=message_req.content,
        user_id=user_id
    )
    db.add(user_message)
    await db.flush()
    
    # 2. Определить режим работы
    if message_req.target_agent:
        # РЕЖИМ 1: Прямой вызов ⚡
        response_text = await direct_agent_call(
            project_id=project_id,
            agent_name=message_req.target_agent,
            content=message_req.content,
            db=db,
            user_id=user_id
        )
    else:
        # РЕЖИМ 2: Автоматический (оркестратор) 🧠
        response_text = await orchestrator_plan_and_execute(
            project_id=project_id,
            content=message_req.content,
            db=db,
            user_id=user_id
        )
    
    # 3. Сохранить ответ агента
    agent_message = Message(
        session_id=session_id,
        role=MessageRole.ASSISTANT,
        content=response_text,
        user_id=user_id
    )
    db.add(agent_message)
    await db.commit()
    
    return MessageResponse.from_orm(agent_message)
```

**Python пример:**
```python
import httpx

async def demo():
    token = "your-jwt-token"
    headers = {"Authorization": f"Bearer {token}"}
    
    project_id = "550e8400-e29b-41d4-a716-446655440000"
    session_id = "550e8400-e29b-41d4-a716-446655440001"
    
    async with httpx.AsyncClient() as client:
        # Прямой вызов агента (быстро)
        response = await client.post(
            f"http://localhost:8000/my/projects/{project_id}/chat/{session_id}/message/",
            headers=headers,
            json={
                "content": "Write a Python function to validate email",
                "target_agent": "CodeAssistant"  # Конкретный агент
            }
        )
        
        result = response.json()
        print(f"Agent response: {result['content']}")
```

---

## 6. 🤖 Contextual Agent - с Qdrant Vector Storage

Каждый агент имеет персональный Qdrant контекст для RAG.

```python
# app/agents/contextual_agent.py (реальная реализация)
from app.vectorstore.agent_context_store import AgentContextStore

class ContextualAgent:
    """Агент с семантической памятью через Qdrant."""
    
    def __init__(self, agent_id: UUID, config: AgentConfig, context_store: AgentContextStore):
        self.agent_id = agent_id
        self.config = config
        self.context_store = context_store
        self.llm_client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url  # Поддержка LiteLLM
        )
    
    async def execute(self, task_content: str, session_id: UUID) -> str:
        """Выполнить задачу с использованием контекста агента."""
        
        # 1. Извлечь релевантный контекст из Qdrant
        retrieved_context = await self.context_store.retrieve_similar(
            query=task_content,
            limit=5
        )
        
        # 2. Построить промпт с контекстом
        context_text = "\n".join([
            f"- {item['content']}" for item in retrieved_context
        ])
        
        system_prompt = f"""
{self.config.system_prompt}

ТВОЯ ПЕРСОНАЛЬНАЯ ПАМЯТЬ (актуальные примеры и знания):
{context_text if context_text else "Нет сохраненной информации"}
"""
        
        # 3. Вызвать LLM
        response = await self.llm_client.chat.completions.create(
            model=self.config.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": task_content}
            ],
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens
        )
        
        result_text = response.choices[0].message.content
        
        # 4. Сохранить взаимодействие в личный контекст агента
        await self.context_store.store_interaction(
            content=f"Query: {task_content}\nResponse: {result_text}",
            metadata={
                "session_id": str(session_id),
                "timestamp": datetime.utcnow().isoformat(),
                "success": True
            }
        )
        
        return result_text
```

**Использование:**
```python
# Каждый агент получает свой контекст
agent_context = AgentContextStore(
    agent_id="coder_agent_123",
    qdrant_client=qdrant_client
)

agent = ContextualAgent(
    agent_id=agent_id,
    config=agent_config,
    context_store=agent_context
)

# Выполнить задачу с автоматическим RAG
response = await agent.execute(
    task_content="Write a function to parse JSON",
    session_id=session_id
)
```

---

## 7. 🧭 Middleware - Project Validation

Автоматическая валидация доступа к проекту.

```python
# app/middleware/project_validation.py
from fastapi import Depends, HTTPException, status

async def get_project_with_validation(
    project_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> UserProject:
    """
    Получить проект с проверкой доступа.
    Гарантирует, что проект принадлежит текущему пользователю.
    """
    
    user_id = get_current_user_id(request)
    
    stmt = select(UserProject).where(
        UserProject.id == project_id,
        UserProject.user_id == user_id  # ← КЛЮЧЕВАЯ ПРОВЕРКА
    )
    
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    return project
```

---

## 8. 📡 SSE Events - Real-Time Streaming

Получение событий в реальном времени через Server-Sent Events.

```python
# app/routes/streaming.py (пример подписки)
@router.get("/my/projects/{project_id}/chat/{session_id}/events/")
async def stream_chat_events(
    project_id: UUID,
    session_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    project: UserProject = Depends(get_project_with_validation),
):
    """Получить поток событий сессии (SSE)."""
    
    user_id = get_current_user_id(request)
    stream_manager = get_stream_manager()
    
    async def event_generator():
        # Подписаться на события этой сессии
        event_queue = await stream_manager.subscribe(session_id)
        
        try:
            while True:
                # Получить событие из очереди (с таймаутом)
                event = await asyncio.wait_for(
                    event_queue.get(),
                    timeout=60.0
                )
                
                # Отправить как SSE
                yield f"data: {json.dumps(event)}\n\n"
                
        except asyncio.TimeoutError:
            # Heartbeat - отправить ping для поддержания соединения
            yield f": heartbeat\n\n"
        finally:
            await stream_manager.unsubscribe(session_id, event_queue)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )
```

**JavaScript клиент:**
```javascript
// client/chat.js
class ChatStream {
    constructor(projectId, sessionId, token) {
        this.projectId = projectId;
        this.sessionId = sessionId;
        this.token = token;
    }
    
    subscribeToEvents(onEvent) {
        const eventSource = new EventSource(
            `/my/projects/${this.projectId}/chat/${this.sessionId}/events/`,
            {
                headers: {
                    'Authorization': `Bearer ${this.token}`
                }
            }
        );
        
        eventSource.onmessage = (event) => {
            const data = JSON.parse(event.data);
            console.log('Event:', data);
            onEvent(data);
        };
        
        eventSource.onerror = () => {
            console.error('SSE connection failed');
            eventSource.close();
        };
        
        return eventSource;
    }
}

// Использование
const stream = new ChatStream(projectId, sessionId, token);
stream.subscribeToEvents((event) => {
    if (event.type === 'agent_response') {
        updateUI(event.content);
    }
});
```

---

## 9. 🏗️ Starter Pack Initialization

Автоматическая инициализация default агентов при создании проекта.

```python
# app/core/starter_pack.py
async def initialize_starter_pack(
    db: AsyncSession,
    project_id: UUID,
    user_id: UUID
):
    """Создать default Starter Pack агентов для нового проекта."""
    
    starter_agents = [
        {
            "name": "CodeAssistant",
            "system_prompt": "You are an expert code developer. Help with programming tasks.",
            "model": "openrouter/openai/gpt-4.1",
            "tools": ["code_executor", "file_reader"],
            "metadata": {"role": "developer"}
        },
        {
            "name": "DataAnalyst",
            "system_prompt": "You are a data analyst. Analyze data and create visualizations.",
            "model": "openrouter/openai/gpt-4.1",
            "tools": ["python_exec", "data_visualizer"],
            "metadata": {"role": "analyst"}
        },
        {
            "name": "DocumentWriter",
            "system_prompt": "You are a technical writer. Create clear and concise documentation.",
            "model": "openrouter/openai/gpt-4.1",
            "tools": ["text_formatter"],
            "metadata": {"role": "writer"}
        }
    ]
    
    for agent_data in starter_agents:
        agent = UserAgent(
            project_id=project_id,
            user_id=user_id,
            name=agent_data["name"],
            status=AgentStatus.READY,
            config=agent_data
        )
        db.add(agent)
    
    await db.flush()
```

---

## 10. 🧪 Integration Test Example

Полный цикл тестирования с реальным API.

```python
# tests/test_full_flow.py
import pytest
import httpx
from uuid import uuid4

@pytest.mark.asyncio
async def test_project_creation_and_chat():
    """Тест: создание проекта → добавление агента → чат."""
    
    token = "test-jwt-token"
    headers = {"Authorization": f"Bearer {token}"}
    
    async with httpx.AsyncClient() as client:
        # 1. Создать проект
        project_response = await client.post(
            "http://localhost:8000/my/projects/",
            headers=headers,
            json={"name": "Test Project", "workspace_path": "/test"}
        )
        assert project_response.status_code == 201
        project = project_response.json()
        project_id = project["id"]
        
        # 2. Проверить, что Starter Pack агенты созданы
        agents_response = await client.get(
            f"http://localhost:8000/my/projects/{project_id}/agents/",
            headers=headers
        )
        assert agents_response.status_code == 200
        agents = agents_response.json()
        assert agents["total"] == 3  # CodeAssistant, DataAnalyst, DocumentWriter
        assert any(a["name"] == "CodeAssistant" for a in agents["agents"])
        
        # 3. Создать сессию чата
        session_response = await client.post(
            f"http://localhost:8000/my/projects/{project_id}/chat/sessions/",
            headers=headers,
            json={}
        )
        assert session_response.status_code == 201
        session = session_response.json()
        session_id = session["id"]
        
        # 4. Отправить сообщение с прямым вызовом агента
        message_response = await client.post(
            f"http://localhost:8000/my/projects/{project_id}/chat/{session_id}/message/",
            headers=headers,
            json={
                "content": "Write a hello world function",
                "target_agent": "CodeAssistant"
            }
        )
        assert message_response.status_code == 200
        message = message_response.json()
        assert "def " in message["content"] or "function" in message["content"].lower()
        
        # 5. Проверить историю чата
        history_response = await client.get(
            f"http://localhost:8000/my/projects/{project_id}/chat/sessions/{session_id}/messages/",
            headers=headers
        )
        assert history_response.status_code == 200
        history = history_response.json()
        assert history["total"] >= 2  # user message + agent response
```

---

## 11. 📊 Monitoring & Metrics

Пример сбора метрик для мониторинга.

```python
# app/monitoring/metrics.py
from prometheus_client import Counter, Histogram

# Метрики
PROJECT_CREATIONS = Counter(
    'project_creations_total',
    'Total project creations',
    ['user_id']
)

AGENT_EXECUTIONS = Counter(
    'agent_executions_total',
    'Total agent executions',
    ['agent_id', 'status']
)

AGENT_EXECUTION_TIME = Histogram(
    'agent_execution_seconds',
    'Agent execution time',
    ['agent_id'],
    buckets=(0.5, 1.0, 2.0, 5.0, 10.0)
)

QDRANT_SEARCH_LATENCY = Histogram(
    'qdrant_search_latency_seconds',
    'Qdrant search latency',
    ['agent_id']
)

# Использование
PROJECT_CREATIONS.labels(user_id=user_id).inc()
AGENT_EXECUTIONS.labels(agent_id=agent_id, status="success").inc()
with AGENT_EXECUTION_TIME.labels(agent_id=agent_id).time():
    result = await agent.execute(task)
```

---

## 12. 🔌 LiteLLM Integration

Поддержка альтернативных LLM провайдеров через LiteLLM.

```python
# app/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # OpenAI / LiteLLM конфигурация
    openai_api_key: str = Field(default="")
    openai_base_url: str | None = Field(default=None)  # Для LiteLLM
    openai_model: str = Field(default="openrouter/openai/gpt-4.1")

# app/agents/contextual_agent.py
client = AsyncOpenAI(
    api_key=settings.openai_api_key,
    base_url=settings.openai_base_url or "https://api.openai.com/v1"
)

# Использование с LiteLLM:
# OPENAI_API_KEY=sk-litellm-key
# OPENAI_BASE_URL=http://localhost:4000
# OPENAI_MODEL=gpt-4
```

---

## 13. 🚀 Deployment - Docker Compose

Полная инфраструктура для локального развития и production.

```yaml
version: '3.8'

services:
  # Core Service API
  codelab-core-service:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: codelab-core-service
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql+asyncpg://postgres:postgres@postgres:5432/codelab
      REDIS_URL: redis://redis:6379/0
      QDRANT_URL: http://qdrant:6333
      OPENAI_API_KEY: ${OPENAI_API_KEY}
      OPENAI_BASE_URL: ${OPENAI_BASE_URL:-}
      OPENAI_MODEL: ${OPENAI_MODEL:-openrouter/openai/gpt-4.1}
      JWT_SECRET_KEY: ${JWT_SECRET_KEY:-change-me-in-production}
      DEBUG: ${DEBUG:-false}
    depends_on:
      - postgres
      - redis
      - qdrant
    volumes:
      - .:/app
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

  # PostgreSQL Database
  postgres:
    image: postgres:16-alpine
    container_name: codelab-postgres
    environment:
      POSTGRES_DB: codelab
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  # Redis Cache & Queues
  redis:
    image: redis:7-alpine
    container_name: codelab-redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

  # Qdrant Vector Database
  qdrant:
    image: qdrant/qdrant:v1.7.1
    container_name: codelab-qdrant
    ports:
      - "6333:6333"
    volumes:
      - qdrant_data:/qdrant/storage

volumes:
  postgres_data:
  redis_data:
  qdrant_data:
```

---

## Заключение

Эти примеры охватывают ключевые аспекты платформы:

✅ **User Isolation** - Middleware + Project-based модель  
✅ **Project Management** - CRUD операции с проектами  
✅ **Agent Management** - Per-project агенты  
✅ **Chat API** - Прямой вызов и автоматический режимы  
✅ **Vector Context** - Qdrant RAG для каждого агента  
✅ **Real-time Events** - SSE streaming  
✅ **Integration** - LiteLLM поддержка  
✅ **Testing** - End-to-end тесты  
✅ **Monitoring** - Prometheus метрики  
✅ **Deployment** - Docker Compose  

**Готово к production!** 🚀
