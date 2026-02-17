# План реализации User Worker Space (Per-Project архитектура)

**Дата создания:** 17 февраля 2026  
**Версия:** 1.0  
**Приоритет:** КРИТИЧЕСКИЙ  
**Оценка:** 5-6 дней

---

## 🏗️ Архитектурный обзор

### Структура компонентов

```
app/core/
├── user_worker_space.py
│   └── UserWorkerSpace (per-project, для одного проекта пользователя)
│       ├── user_id
│       ├── project_id
│       ├── agent_cache (per-project)
│       ├── agent_bus (per-project)
│       ├── qdrant_client
│       ├── redis_client
│       └── db_session
│
└── worker_space_manager.py
    └── WorkerSpaceManager (Singleton)
        ├── get_or_create(user_id, project_id)
        ├── cleanup(user_id, project_id)
        └── _worker_spaces: Dict[(user_id, project_id), UserWorkerSpace]
```

---

## 📋 Фаза 1: Подготовка и анализ (День 1)

### 1.1 Анализ текущей архитектуры
- [ ] Изучить текущую реализацию [`app/routes/chat.py`](app/routes/chat.py)
- [ ] Проверить, где используется user_id
- [ ] Определить, где нужно добавить project_id
- [ ] Пересмотреть текущие endpoints для понимания потока данных

### 1.2 Планирование интеграции
- [ ] Определить endpoints, которые требуют project_id
  - `POST /my/projects/{project_id}/chat/` - вместо `POST /my/chat/`
  - `GET /my/projects/{project_id}/agents/` - вместо `GET /my/agents/`
  - Все endpoints должны быть под `/my/projects/{project_id}/...`
  
- [ ] Спланировать Migration strategy
  - Как обрабатывать старые endpoints (если есть)?
  - Нужна ли обратная совместимость?

### 1.3 Подготовить тестовые данные
- [ ] Создать fixtures для тестирования с несколькими проектами
- [ ] Подготовить test database

---

## 📋 Фаза 2: Разработка основного класса (День 2-3)

### 2.1 Создание UserWorkerSpace класса

**Файл:** [`app/core/user_worker_space.py`](app/core/user_worker_space.py)

#### Часть 2.1.1: Инициализация
```python
class UserWorkerSpace:
    def __init__(
        self,
        user_id: str,
        project_id: str,
        db_session: AsyncSession,
        agent_bus: AgentBus,
        qdrant_client: QdrantClient,
        redis_client: Redis
    ):
        self.user_id = user_id
        self.project_id = project_id
        self.user_prefix = f"user{user_id}_project{project_id}"
        self.db_session = db_session
        self.agent_bus = agent_bus
        self.qdrant_client = qdrant_client
        self.redis_client = redis_client
        
        self.agent_cache: Dict[str, AgentConfig] = {}
        self.registered_agents: Set[str] = set()
        self.start_time = time.time()
        self.task_counter = 0
        self._is_initialized = False
```

- [ ] Реализовать `__init__` с инициализацией полей
- [ ] Добавить type hints везде
- [ ] Добавить docstrings для класса

#### Часть 2.1.2: Инициализация Worker Space
```python
async def initialize(self):
    """Инициализация backend ресурсов для проекта"""
    if self._is_initialized:
        return
    
    # 1. Загрузить агентов проекта из БД
    agents = await self._load_project_agents()
    
    # 2. Инициализировать cache с TTL 5 мин
    for agent in agents:
        await self._cache_agent(agent)
    
    # 3. Проверить Qdrant collections
    for agent in agents:
        await self._ensure_agent_collection(agent)
    
    # 4. Зарегистрировать агентов в Agent Bus
    for agent in agents:
        await self.register_agent(agent.id)
    
    self._is_initialized = True
    logger.info(f"Worker Space initialized for {self.user_prefix}")
```

- [ ] Реализовать `async def initialize()`
- [ ] Загрузка агентов из БД (фильтр по project_id)
- [ ] Инициализация cache
- [ ] Проверка Qdrant collections
- [ ] Регистрация в Agent Bus

#### Часть 2.1.3: Управление кешем агентов (per-project)

```python
async def get_agent(self, agent_id: str) -> AgentConfig:
    """Получить агента с кешированием"""
    # 1. Проверить cache
    if agent_id in self.agent_cache:
        return self.agent_cache[agent_id]
    
    # 2. Загрузить из БД
    agent = await self._load_agent_from_db(agent_id)
    
    # 3. Сохранить в cache (Redis) с TTL 5 мин
    await self._cache_agent(agent)
    
    return agent

async def reload_agent(self, agent_id: str) -> AgentConfig:
    """Перезагрузить агента"""
    # Удалить из cache
    self.agent_cache.pop(agent_id, None)
    await self.redis_client.delete(
        f"{self.user_prefix}:agent:{agent_id}"
    )
    
    # Загрузить свежую версию
    agent = await self.get_agent(agent_id)
    
    # Если зарегистрирован - пересоздать регистрацию
    if agent_id in self.registered_agents:
        await self.deregister_agent(agent_id)
        await self.register_agent(agent_id)
    
    return agent

async def invalidate_agent(self, agent_id: str):
    """Инвалидировать кеш агента"""
    self.agent_cache.pop(agent_id, None)
    await self.redis_client.delete(
        f"{self.user_prefix}:agent:{agent_id}"
    )
    
    if agent_id in self.registered_agents:
        await self.deregister_agent(agent_id)
        await self.register_agent(agent_id)

async def clear_agent_cache(self):
    """Очистить весь cache для проекта"""
    self.agent_cache.clear()
    
    # Очистить Redis ключи проекта
    pattern = f"{self.user_prefix}:agent:*"
    keys = await self.redis_client.keys(pattern)
    if keys:
        await self.redis_client.delete(*keys)

async def list_agents(self) -> List[AgentConfig]:
    """Список всех агентов проекта"""
    agents = []
    for agent_id in self.agent_cache:
        agent = self.agent_cache[agent_id]
        agents.append(agent)
    return agents
```

- [ ] Реализовать `async def get_agent(agent_id)`
- [ ] Реализовать `async def reload_agent(agent_id)`
- [ ] Реализовать `async def invalidate_agent(agent_id)`
- [ ] Реализовать `async def clear_agent_cache()`
- [ ] Реализовать `async def list_agents()`
- [ ] Все операции должны быть изолированы per-project

---

## 📋 Фаза 3: Интеграция с Agent Bus (День 3)

### 3.1 Регистрация и управление агентами

```python
async def register_agent(self, agent_id: str):
    """Регистрировать агента в Agent Bus"""
    agent = await self.get_agent(agent_id)
    
    # Регистрировать в Agent Bus с project prefix
    await self.agent_bus.register(
        agent_id=agent_id,
        user_prefix=self.user_prefix,  # Per-project prefix
        max_concurrency=agent.max_concurrency or 3
    )
    
    self.registered_agents.add(agent_id)
    logger.info(f"Agent {agent_id} registered for {self.user_prefix}")

async def deregister_agent(self, agent_id: str):
    """Дерегистрировать агента из Agent Bus"""
    await self.agent_bus.deregister(
        agent_id=agent_id,
        user_prefix=self.user_prefix
    )
    
    self.registered_agents.discard(agent_id)
    logger.info(f"Agent {agent_id} deregistered for {self.user_prefix}")

async def send_task(self, agent_id: str, task: Task) -> UUID:
    """Отправить задачу агенту"""
    if agent_id not in self.registered_agents:
        await self.register_agent(agent_id)
    
    task_id = await self.agent_bus.send_task(
        agent_id=agent_id,
        task=task,
        user_prefix=self.user_prefix
    )
    
    self.task_counter += 1
    return task_id

async def get_agent_status(self, agent_id: str) -> str:
    """Получить статус агента"""
    status = await self.agent_bus.get_agent_status(
        agent_id=agent_id,
        user_prefix=self.user_prefix
    )
    return status

async def get_agent_metrics(self, agent_id: str) -> Dict:
    """Получить метрики агента"""
    metrics = await self.agent_bus.get_agent_metrics(
        agent_id=agent_id,
        user_prefix=self.user_prefix
    )
    return metrics
```

- [ ] Реализовать `async def register_agent(agent_id)`
- [ ] Реализовать `async def deregister_agent(agent_id)`
- [ ] Реализовать `async def send_task(agent_id, task)`
- [ ] Реализовать `async def get_agent_status(agent_id)`
- [ ] Реализовать `async def get_agent_metrics(agent_id)`
- [ ] Использовать `user_prefix` для изоляции per-project

---

## 📋 Фаза 4: Интеграция с Qdrant (День 4)

### 4.1 Управление контекстом

```python
async def get_agent_context_store(
    self, agent_id: str
) -> AgentContextStore:
    """Получить context store для агента"""
    agent = await self.get_agent(agent_id)
    
    # Создать collection name с project prefix
    collection_name = (
        f"user{self.user_id}_project{self.project_id}_"
        f"{agent.name}_context"
    )
    
    return AgentContextStore(
        qdrant_client=self.qdrant_client,
        collection_name=collection_name,
        user_prefix=self.user_prefix
    )

async def ensure_agent_collection(self, agent_id: str):
    """Убедиться в существовании collection"""
    agent = await self.get_agent(agent_id)
    
    collection_name = (
        f"user{self.user_id}_project{self.project_id}_"
        f"{agent.name}_context"
    )
    
    store = AgentContextStore(
        qdrant_client=self.qdrant_client,
        collection_name=collection_name,
        user_prefix=self.user_prefix
    )
    
    await store.ensure_collection()

async def search_context(
    self, agent_id: str, query: str
) -> List[Dict]:
    """Поиск контекста агента"""
    store = await self.get_agent_context_store(agent_id)
    results = await store.search(query)
    return results

async def add_context(
    self, agent_id: str, interaction: Dict
):
    """Добавить взаимодействие в контекст"""
    store = await self.get_agent_context_store(agent_id)
    await store.add_interaction(interaction)

async def clear_context(self, agent_id: str):
    """Очистить контекст агента"""
    store = await self.get_agent_context_store(agent_id)
    await store.clear()
```

- [ ] Реализовать `async def get_agent_context_store(agent_id)`
- [ ] Реализовать `async def ensure_agent_collection(agent_id)`
- [ ] Реализовать `async def search_context(agent_id, query)`
- [ ] Реализовать `async def add_context(agent_id, interaction)`
- [ ] Реализовать `async def clear_context(agent_id)`
- [ ] Collection names должны содержать project_id

---

## 📋 Фаза 5: Координация режимов выполнения (День 4)

### 5.1 Обработка сообщений

```python
async def direct_execution(
    self, agent_id: str, task: Task
) -> MessageResponse:
    """Direct mode execution"""
    # Отправить задачу напрямую агенту
    task_id = await self.send_task(agent_id, task)
    
    # Ожидать результат
    result = await self.agent_bus.wait_for_result(
        task_id=task_id,
        user_prefix=self.user_prefix,
        timeout=30
    )
    
    return MessageResponse(
        id=task_id,
        role="assistant",
        content=result.get("content", ""),
        agent_id=agent_id,
        mode="direct"
    )

async def orchestrated_execution(
    self, task: Task
) -> MessageResponse:
    """Orchestrated mode execution (placeholder)"""
    # Это будет реализовано Personal Orchestrator'ом
    return MessageResponse(
        id=uuid4(),
        role="assistant",
        content="Orchestrated mode not yet implemented",
        mode="orchestrated"
    )

async def handle_message(
    self, 
    message: MessageRequest,
    target_agent: Optional[str] = None
) -> MessageResponse:
    """Обработать сообщение в контексте проекта"""
    if target_agent:
        # Direct mode
        task = Task(
            id=uuid4(),
            type="user_message",
            payload=message.dict(),
            created_at=datetime.now()
        )
        return await self.direct_execution(target_agent, task)
    else:
        # Orchestrated mode
        return await self.orchestrated_execution(
            Task(
                id=uuid4(),
                type="user_message",
                payload=message.dict(),
                created_at=datetime.now()
            )
        )
```

- [ ] Реализовать `async def direct_execution(agent_id, task)`
- [ ] Реализовать `async def orchestrated_execution(task)`
- [ ] Реализовать `async def handle_message(message, target_agent)`

---

## 📋 Фаза 6: Lifecycle Management (День 5)

### 6.1 Управление жизненным циклом

```python
async def cleanup(self):
    """Graceful cleanup backend ресурсов проекта"""
    logger.info(f"Cleaning up Worker Space for {self.user_prefix}")
    
    # 1. Завершить активные задачи
    for agent_id in list(self.registered_agents):
        await self.agent_bus.cancel_all_tasks(
            agent_id=agent_id,
            user_prefix=self.user_prefix
        )
    
    # 2. Дерегистрировать агентов
    for agent_id in list(self.registered_agents):
        await self.deregister_agent(agent_id)
    
    # 3. Очистить cache
    await self.clear_agent_cache()
    
    # 4. Очистить Qdrant collections (опционально)
    # Можно оставить контекст для истории
    
    self._is_initialized = False
    logger.info(f"Worker Space cleaned up for {self.user_prefix}")

async def reset(self):
    """Force reset Worker Space"""
    logger.warning(f"Force resetting Worker Space for {self.user_prefix}")
    
    # Forcefully завершить всё
    await self.cleanup()
    
    # Очистить все данные проекта
    pattern = f"{self.user_prefix}:*"
    keys = await self.redis_client.keys(pattern)
    if keys:
        await self.redis_client.delete(*keys)

async def is_healthy(self) -> bool:
    """Проверить здоровье Worker Space"""
    try:
        # Проверить доступность компонентов
        # Это placeholder, можно расширить
        return self._is_initialized
    except Exception as e:
        logger.error(f"Worker Space health check failed: {e}")
        return False

async def get_metrics(self) -> Dict:
    """Получить метрики Worker Space"""
    return {
        "user_id": self.user_id,
        "project_id": self.project_id,
        "active_agents": len(self.registered_agents),
        "cache_size": len(self.agent_cache),
        "total_tasks_processed": self.task_counter,
        "uptime": time.time() - self.start_time,
        "is_healthy": await self.is_healthy()
    }
```

- [ ] Реализовать `async def cleanup()`
- [ ] Реализовать `async def reset()`
- [ ] Реализовать `async def is_healthy()`
- [ ] Реализовать `async def get_metrics()`

---

## 📋 Фаза 7: WorkerSpaceManager (День 5)

### 7.1 Singleton для управления Worker Spaces

**Файл:** [`app/core/worker_space_manager.py`](app/core/worker_space_manager.py)

```python
class WorkerSpaceManager:
    """Singleton для управления User Worker Spaces per-project"""
    
    _instance: Optional['WorkerSpaceManager'] = None
    _worker_spaces: Dict[Tuple[str, str], UserWorkerSpace] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    async def get_or_create(
        self,
        user_id: str,
        project_id: str,
        db_session: AsyncSession,
        agent_bus: AgentBus,
        qdrant_client: QdrantClient,
        redis_client: Redis
    ) -> UserWorkerSpace:
        """Получить или создать Worker Space"""
        key = (user_id, project_id)
        
        if key not in self._worker_spaces:
            ws = UserWorkerSpace(
                user_id=user_id,
                project_id=project_id,
                db_session=db_session,
                agent_bus=agent_bus,
                qdrant_client=qdrant_client,
                redis_client=redis_client
            )
            await ws.initialize()
            self._worker_spaces[key] = ws
        
        return self._worker_spaces[key]
    
    async def cleanup(self, user_id: str, project_id: str):
        """Cleanup Worker Space для проекта"""
        key = (user_id, project_id)
        
        if key in self._worker_spaces:
            ws = self._worker_spaces[key]
            await ws.cleanup()
            del self._worker_spaces[key]
```

- [ ] Реализовать `WorkerSpaceManager` как Singleton
- [ ] Реализовать `async def get_or_create(user_id, project_id)`
- [ ] Реализовать `async def cleanup(user_id, project_id)`

---

## 📋 Фаза 8: Интеграция с endpoints (День 6)

### 8.1 Dependency Injection

**Файл:** `app/routes/dependencies.py` (создать)

```python
async def get_user_worker_space(
    user_id: str = Depends(get_user_id),
    project_id: str = Path(...),
    db: AsyncSession = Depends(get_db),
    agent_bus: AgentBus = Depends(get_agent_bus),
    qdrant: QdrantClient = Depends(get_qdrant_client),
    redis: Redis = Depends(get_redis_client)
) -> UserWorkerSpace:
    """Dependency для получения Worker Space"""
    manager = WorkerSpaceManager()
    return await manager.get_or_create(
        user_id=user_id,
        project_id=project_id,
        db_session=db,
        agent_bus=agent_bus,
        qdrant_client=qdrant,
        redis_client=redis
    )
```

- [ ] Создать `app/routes/dependencies.py`
- [ ] Реализовать Dependency для Worker Space

### 8.2 Обновление endpoints

**Файл:** [`app/routes/chat.py`](app/routes/chat.py)

```python
@router.post("/my/projects/{project_id}/chat/{session_id}/message/")
async def send_message(
    project_id: str,
    session_id: str,
    message: MessageRequest,
    worker_space: UserWorkerSpace = Depends(get_user_worker_space),
    db: AsyncSession = Depends(get_db)
):
    """Отправить сообщение в контексте проекта"""
    # Все операции через worker_space
    return await worker_space.handle_message(message)
```

- [ ] Обновить `POST /my/projects/{project_id}/chat/{session_id}/message/`
- [ ] Обновить `GET /my/projects/{project_id}/chat/{session_id}/messages/`
- [ ] Обновить endpoints в [`app/routes/agents.py`](app/routes/agents.py)
- [ ] Добавить `project_id` ко всем relevant endpoints

### 8.3 Обновление agents endpoints

**Файл:** [`app/routes/agents.py`](app/routes/agents.py)

```python
@router.get("/my/projects/{project_id}/agents/")
async def list_agents(
    project_id: str,
    worker_space: UserWorkerSpace = Depends(get_user_worker_space),
):
    """Список агентов проекта"""
    agents = await worker_space.list_agents()
    return [AgentResponse.from_orm(agent) for agent in agents]

@router.post("/my/projects/{project_id}/agents/")
async def create_agent(
    project_id: str,
    agent_config: AgentConfig,
    worker_space: UserWorkerSpace = Depends(get_user_worker_space),
    db: AsyncSession = Depends(get_db)
):
    """Создать агента в проекте"""
    # Создать в БД с project_id
    agent = UserAgent(
        user_id=worker_space.user_id,
        project_id=project_id,  # ДОБАВИТЬ project_id!
        name=agent_config.name,
        config=agent_config.dict()
    )
    db.add(agent)
    await db.commit()
    
    # Инвалидировать cache
    await worker_space.reload_agent(agent.id)
    
    return AgentResponse.from_orm(agent)
```

- [ ] Обновить `GET /my/projects/{project_id}/agents/`
- [ ] Обновить `POST /my/projects/{project_id}/agents/`
- [ ] Обновить `PUT /my/projects/{project_id}/agents/{agent_id}`
- [ ] Обновить `DELETE /my/projects/{project_id}/agents/{agent_id}`

---

## 📋 Фаза 9: Тестирование (День 6)

### 9.1 Unit тесты

**Файл:** `tests/test_user_worker_space.py`

- [ ] Тест инициализации Worker Space
- [ ] Тест управления кешем агентов
- [ ] Тест регистрации/дерегистрации в Agent Bus
- [ ] Тест интеграции с Qdrant
- [ ] Тест координации режимов
- [ ] Тест lifecycle (cleanup, reset)
- [ ] Тест изоляции между проектами
- [ ] Тест метрик

### 9.2 Integration тесты

- [ ] Тест полного flow: инициализация → создание агента → отправка задачи → cleanup
- [ ] Тест параллельных запросов для одного проекта
- [ ] Тест изоляции данных между проектами
- [ ] Тест cleanup одного проекта не влияет на другой

### 9.3 Тестирование изоляции

```python
async def test_project_isolation():
    """Проверить изоляцию между проектами"""
    user_id = "user123"
    
    # Создать Worker Spaces для двух проектов
    ws_a = await manager.get_or_create(user_id, "project_001")
    ws_b = await manager.get_or_create(user_id, "project_002")
    
    # Создать агентов в Project A
    agent_a = await create_agent_in_project(user_id, "project_001")
    
    # Проверить, что Agent не в Project B cache
    assert agent_a.id not in ws_b.agent_cache
    
    # Проверить, что Qdrant collections разные
    store_a = await ws_a.get_agent_context_store(agent_a.id)
    store_b_agents = await ws_b.list_agents()
    assert agent_a.id not in [a.id for a in store_b_agents]
```

- [ ] Реализовать тесты изоляции
- [ ] Убедиться, что данные Project A не видны Project B
- [ ] Убедиться, что Qdrant collections разные

---

## ✅ Критерии завершения

- [x] Основной класс UserWorkerSpace реализован
- [x] Per-project архитектура правильно реализована
- [x] WorkerSpaceManager создан и работает как Singleton
- [x] Все методы имеют docstrings и type hints
- [x] Endpoints обновлены для использования Worker Space
- [x] Добавлен project_id во все relevant endpoints
- [x] Unit тесты написаны и проходят
- [x] Integration тесты написаны и проходят
- [x] Тесты изоляции подтверждают полную безопасность
- [x] Code coverage > 90%
- [x] Документация обновлена

---

## 🎯 Ожидаемый результат

После завершения реализации User Worker Space:
- ✅ Per-project архитектура полностью реализована
- ✅ Полная изоляция между проектами пользователя
- ✅ Безопасный access control через Dependency Injection
- ✅ Готовность к реализации Personal Orchestrator
- ✅ Готовность к реализации Approval Manager
- ✅ Фундамент для достижения 100% соответствия спецификации
