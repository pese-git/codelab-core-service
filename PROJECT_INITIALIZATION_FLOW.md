# Анализ: Инициализация проекта и создание default агентов

**Дата:** 17 февраля 2026
**Версия:** 2.0 (Updated: Default Starter Pack REQUIRED)
**Контекст:** Default Starter Pack должен создаваться при инициализации проекта

---

## 🎯 Короткий ответ

**ДА, проект ДОЛЖЕН создаваться с Default Starter Pack.**

Используется **Подход 2: Автоматическое создание default агентов**.

---

## 🔄 Два подхода к инициализации

### Подход 1: Явное создание агентов (РЕКОМЕНДУЕТСЯ)

```
1. User действие
   User: "Создам новый проект"
   └─ Client отправляет запрос

2. API запрос
   POST /my/projects/
   {
       "name": "my-app",
       "workspace_path": "/home/user/projects/my-app"
   }

3. Backend обработка
   ├─ Создать запись в user_projects
   ├─ Backend инициализирует пустой User Worker Space для проекта
   │  ├─ agent_cache: пусто
   │  ├─ Agent Bus: пусто
   │  └─ Qdrant collections: НЕ созданы (будут при нужде)
   └─ Вернуть информацию о проекте

4. Response
   {
       "id": "proj_001",
       "name": "my-app",
       "agents": []  # пусто!
   }

5. User видит
   Новый проект создан, но агентов нет
   User: "Теперь добавлю агентов"

6. User создает агентов
   POST /my/projects/{project_id}/agents/
   {
       "name": "agent_coder",
       "config": {...}
   }

   POST /my/projects/{project_id}/agents/
   {
       "name": "agent_analyzer",
       "config": {...}
   }
```

**Преимущества:**
- ✅ Простая инициализация
- ✅ User контролирует какие агенты ему нужны
- ✅ Гибкость в выборе конфигурации агентов
- ✅ Backend не создает лишние ресурсы

**Недостатки:**
- ❌ User должен сам создать агентов перед использованием

---

### Подход 2: Автоматическое создание default агентов (НЕ РЕКОМЕНДУЕТСЯ)

```
1. User действие
   User: "Создам новый проект"

2. API запрос
   POST /my/projects/
   {
       "name": "my-app",
       "workspace_path": "/home/user/projects/my-app"
   }

3. Backend обработка
   ├─ Создать запись в user_projects
   ├─ Автоматически создать default агентов:
   │  ├─ UserAgent(name="agent_coder", config={...})
   │  ├─ UserAgent(name="agent_analyzer", config={...})
   │  ├─ UserAgent(name="agent_writer", config={...})
   │  └─ UserAgent(name="agent_researcher", config={...})
   │
   ├─ Backend инициализирует User Worker Space с агентами
   │  ├─ agent_cache: заполнен 4 агентами
   │  ├─ Agent Bus: зарегистрировано 4 агента
   │  └─ Qdrant collections: созданы для всех
   │
   └─ Вернуть информацию о проекте

4. Response
   {
       "id": "proj_001",
       "name": "my-app",
       "agents": [
           {"id": "agent_coder", "name": "agent_coder"},
           {"id": "agent_analyzer", "name": "agent_analyzer"},
           {"id": "agent_writer", "name": "agent_writer"},
           {"id": "agent_researcher", "name": "agent_researcher"}
       ]
   }

5. User видит
   Новый проект готов с 4 default агентами
   User может сразу использовать систему
```

**Преимущества:**
- ✅ User может сразу использовать агентов без дополнительной конфигурации
- ✅ Zero-to-use в одном запросе

**Недостатки:**
- ❌ Backend создает ресурсы (Qdrant collections, Agent Bus registrations) которые может не использовать
- ❌ Если User создает много проектов, будет много ненужных ресурсов
- ❌ Менее гибкий (default агенты может не подходить)
- ❌ Сложнее с миграциями и изменениями default конфигурации

---

## 🏗️ Рекомендуемый поток: Default Starter Pack

### Фаза 1: Создание проекта с default агентами

```python
# Default Starter Pack configuration
DEFAULT_STARTER_AGENTS = [
    {
        "name": "agent_coder",
        "config": {
            "model": "gpt-4",
            "temperature": 0.3,
            "max_tokens": 4096,
            "system_prompt": "You are an expert code developer..."
        }
    },
    {
        "name": "agent_analyzer",
        "config": {
            "model": "gpt-4",
            "temperature": 0.5,
            "max_tokens": 2048,
            "system_prompt": "You are an expert data analyst..."
        }
    },
    {
        "name": "agent_writer",
        "config": {
            "model": "gpt-4",
            "temperature": 0.7,
            "max_tokens": 2048,
            "system_prompt": "You are a professional technical writer..."
        }
    },
    {
        "name": "agent_researcher",
        "config": {
            "model": "gpt-4",
            "temperature": 0.6,
            "max_tokens": 3096,
            "system_prompt": "You are a thorough researcher..."
        }
    }
]

@router.post("/my/projects/")
async def create_project(
    project_data: ProjectCreate,
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_db),
    worker_space_manager = Depends(get_worker_space_manager)
) -> ProjectWithAgentsResponse:
    """
    Создать новый проект С default Starter Pack агентами
    """
    
    # 1. Создать запись в user_projects
    project = UserProject(
        user_id=user_id,
        name=project_data.name,
        workspace_path=project_data.workspace_path
    )
    db.add(project)
    await db.commit()
    
    # 2. Создать default агентов для проекта
    created_agents = []
    for agent_config in DEFAULT_STARTER_AGENTS:
        agent = UserAgent(
            user_id=user_id,
            project_id=project.id,
            name=agent_config["name"],
            config=agent_config["config"]
        )
        db.add(agent)
        created_agents.append(agent)
    
    await db.commit()
    
    # 3. Инициализировать User Worker Space с агентами
    worker_space = await worker_space_manager.get_or_create(
        user_id=user_id,
        project_id=str(project.id)
    )
    
    # 4. Загрузить всех agentов в cache и зарегистрировать в Agent Bus
    for agent in created_agents:
        await worker_space.register_agent(str(agent.id))
    
    # 5. Создать Qdrant collections для всех агентов
    for agent in created_agents:
        await worker_space.ensure_agent_collection(str(agent.id))
    
    return ProjectWithAgentsResponse(
        id=str(project.id),
        user_id=str(project.user_id),
        name=project.name,
        workspace_path=project.workspace_path,
        agents=[AgentResponse.from_orm(a) for a in created_agents],
        created_at=project.created_at
    )
```

**Response (с 4 default агентами):**
```json
{
    "id": "proj_001",
    "user_id": "user_123",
    "name": "my-app",
    "workspace_path": "/home/user/projects/my-app",
    "agents": [
        {
            "id": "agent_001",
            "name": "agent_coder",
            "config": {
                "model": "gpt-4",
                "temperature": 0.3,
                "max_tokens": 4096
            }
        },
        {
            "id": "agent_002",
            "name": "agent_analyzer",
            "config": {
                "model": "gpt-4",
                "temperature": 0.5,
                "max_tokens": 2048
            }
        },
        {
            "id": "agent_003",
            "name": "agent_writer",
            "config": {
                "model": "gpt-4",
                "temperature": 0.7,
                "max_tokens": 2048
            }
        },
        {
            "id": "agent_004",
            "name": "agent_researcher",
            "config": {
                "model": "gpt-4",
                "temperature": 0.6,
                "max_tokens": 3096
            }
        }
    ],
    "created_at": "2026-02-17T08:00:00Z"
}
```

### Фаза 2: Получить список проектов

```python
@router.get("/my/projects/{project_id}/")
async def get_project(
    project_id: str,
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_db)
) -> ProjectDetailResponse:
    """
    Получить информацию о проекте с агентами
    """
    
    project = await db.execute(
        select(UserProject).where(
            (UserProject.id == project_id) & 
            (UserProject.user_id == user_id)
        )
    )
    
    project = project.scalar_one()
    
    # Получить агентов проекта
    agents = await db.execute(
        select(UserAgent).where(
            (UserAgent.project_id == project_id) &
            (UserAgent.user_id == user_id)
        )
    )
    
    return ProjectDetailResponse(
        **ProjectResponse.from_orm(project).dict(),
        agents=[AgentResponse.from_orm(a) for a in agents.scalars().all()]
    )
```

**Response (если агентов нет):**
```json
{
    "id": "proj_001",
    "name": "my-app",
    "workspace_path": "/home/user/projects/my-app",
    "agents": [],  # ← пусто
    "created_at": "2026-02-17T08:00:00Z"
}
```

### Фаза 3: User создает первого агента

```python
@router.post("/my/projects/{project_id}/agents/")
async def create_agent(
    project_id: str,
    agent_config: AgentCreate,
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_db),
    worker_space_manager = Depends(get_worker_space_manager)
) -> AgentResponse:
    """
    Создать агента в проекте
    """
    
    # 1. Создать запись в user_agents
    agent = UserAgent(
        user_id=user_id,
        project_id=project_id,
        name=agent_config.name,
        config=agent_config.config.dict()
    )
    db.add(agent)
    await db.commit()
    
    # 2. Инициализировать User Worker Space при нужде
    # (если первый агент - создать Worker Space)
    worker_space = await worker_space_manager.get_or_create(
        user_id=user_id,
        project_id=project_id
    )
    
    # 3. Загрузить агента в cache
    await worker_space.reload_agent(str(agent.id))
    
    return AgentResponse.from_orm(agent)
```

**Request:**
```json
{
    "name": "agent_coder",
    "config": {
        "model": "gpt-4",
        "temperature": 0.7,
        "max_tokens": 2048
    }
}
```

### Фаза 4: User начинает использовать систему

```python
@router.post("/my/projects/{project_id}/chat/{session_id}/message/")
async def send_message(
    project_id: str,
    session_id: str,
    message: MessageRequest,
    user_id: str = Depends(get_user_id),
    worker_space: UserWorkerSpace = Depends(get_user_worker_space)
):
    """
    Отправить сообщение
    Worker Space уже инициализирован в Фазе 3
    """
    
    return await worker_space.handle_message(message)
```

---

## 🎯 Инициализация с Default Starter Pack

```
Timeline:

POST /my/projects/ (с Starter Pack)
├─ Create project record in DB
├─ Create 4 default agents (coder, analyzer, writer, researcher)
├─ Initialize User Worker Space
├─ Register all agents in Agent Bus
├─ Create Qdrant collections for all agents
└─ Return project info with 4 agents

GET /my/projects/{project_id}/
├─ Return project info with 4 agents
└─ User Worker Space: READY to use

POST /my/projects/{project_id}/agents/ (опционально)
├─ Add custom agent in DB
├─ Register in existing Worker Space
├─ Create Qdrant collection
└─ User can add more agents if needed

POST /my/projects/{project_id}/chat/{session_id}/message/
├─ Get User Worker Space (already fully initialized)
├─ Handle message with 4+ agents
└─ User Worker Space: FULLY OPERATIONAL
```

**Преимущества:**
- ✅ Zero-to-use (система сразу готова)
- ✅ Стандартный набор агентов (coder, analyzer, writer, researcher)
- ✅ User может сразу начать использовать
- ✅ Гибкость (user может добавить своих агентов)

---

## 📝 Default Starter Pack конфигурация

### Рекомендуемый набор агентов

```python
DEFAULT_STARTER_AGENTS = [
    {
        "name": "agent_coder",
        "description": "Expert code developer",
        "config": {
            "model": "gpt-4",
            "temperature": 0.3,
            "max_tokens": 4096,
            "max_concurrency": 3,
            "system_prompt": """You are an expert software developer.
            You help users write, debug, and improve code.
            You understand multiple programming languages and frameworks."""
        }
    },
    {
        "name": "agent_analyzer",
        "description": "Data analyst and researcher",
        "config": {
            "model": "gpt-4",
            "temperature": 0.5,
            "max_tokens": 2048,
            "max_concurrency": 3,
            "system_prompt": """You are an expert data analyst and researcher.
            You help users analyze data, find patterns, and generate insights.
            You are thorough and detail-oriented."""
        }
    },
    {
        "name": "agent_writer",
        "description": "Technical writer",
        "config": {
            "model": "gpt-4",
            "temperature": 0.7,
            "max_tokens": 2048,
            "max_concurrency": 3,
            "system_prompt": """You are a professional technical writer.
            You help users write clear, concise documentation and content.
            You understand technical concepts and can explain them simply."""
        }
    },
    {
        "name": "agent_researcher",
        "description": "Research specialist",
        "config": {
            "model": "gpt-4",
            "temperature": 0.6,
            "max_tokens": 3096,
            "max_concurrency": 3,
            "system_prompt": """You are a thorough researcher and information specialist.
            You help users find, evaluate, and synthesize information.
            You are critical thinker and detail-oriented."""
        }
    }
]
```

### Когда создаются agents

- **Всегда** при создании проекта (обязательно)
- **Не опционально** - это часть intialization
- **Нельзя отключить** - все проекты имеют 4 default агентов

### Что user может сделать с agents

- ✅ Использовать default агентов сразу
- ✅ Добавить своих агентов через `POST /my/projects/{project_id}/agents/`
- ✅ Обновить конфигурацию существующего агента
- ✅ Удалить агента (даже default)
- ✅ Создать свой starter pack (если понадобится в будущем)

---

## ✅ Финальная рекомендация

### Используйте Подход 2: Default Starter Pack (ТРЕБУЕТСЯ)

**Процесс:**
1. User создает проект через `POST /my/projects/`
2. Backend автоматически создает 4 default агентов (coder, analyzer, writer, researcher)
3. Backend инициализирует User Worker Space со всеми агентами
4. Backend создает Qdrant collections для всех агентов
5. User сразу может использовать систему (zero-to-use)
6. User может добавить своих агентов при необходимости

**Алгоритм в коде:**
```
POST /my/projects/
  ├─ Create project record
  ├─ Create 4 default agents
  ├─ Initialize User Worker Space
  ├─ Register all agents in Agent Bus
  ├─ Create Qdrant collections
  └─ Return project with agents

GET /my/projects/{project_id}/
  └─ Return project with 4 agents ready to use

POST /my/projects/{project_id}/agents/ (опционально)
  ├─ Add custom agent
  ├─ Register in Worker Space
  └─ Create Qdrant collection

POST /my/projects/{project_id}/chat/...
  └─ Use any of the 4+ agents immediately
```

**Преимущества:**
- ✅ Zero-to-use (система готова сразу)
- ✅ Стандартный набор (универсальные агенты)
- ✅ Простая инициализация
- ✅ Гибкость (можно добавить своих агентов)
- ✅ Лучший UX (user не нужно создавать агентов)

---

## 📊 Summary

| Аспект | Значение |
|--------|----------|
| **Инициализация** | С 4 default агентами (обязательно) |
| **Default агенты** | agent_coder, agent_analyzer, agent_writer, agent_researcher |
| **User контроль** | Может добавить своих агентов |
| **Zero-to-use** | ✅ Да, система готова сразу |
| **Ресурсы** | Инициализируются при создании проекта |
| **Гибкость** | ✅ Максимальная (можно расширить) |
| **Сложность реализации** | Средняя (создать 4 агента в один запрос) |
| **СТАТУС** | ✅ ТРЕБУЕТСЯ |
