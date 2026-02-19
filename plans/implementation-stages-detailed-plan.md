# Подробный план реализации методов UserWorkerSpace (10.4-10.9)

**Дата:** 19 февраля 2026  
**Версия:** 1.0  
**Приоритет:** КРИТИЧЕСКИЙ

---

## 📋 Обзор этапов и зависимостей

```
Этап 1 (10.4) → Этап 2 (10.5) → Этап 3 (10.6) → Этап 4 (10.9)
[Qdrant методы] [Mode execute] [Metrics]      [Dependencies]
```

---

## 🟢 ЭТАП 1: Методы для работы с Qdrant контекстом (10.4)

### Обзор
Добавить методы для управления контекстом агентов через Qdrant. Эти методы будут использоваться в режимах выполнения задач.

### Текущее состояние
- ✅ `AgentContextStore` существует в `app/vectorstore/agent_context_store.py`
- ✅ `ContextualAgent.context_store` инициализируется при создании агента
- ❌ `UserWorkerSpace` НЕ имеет методов для работы с контекстом

### Что добавить в `app/core/user_worker_space.py`

#### 1.1 Метод `get_agent_context_store()`

```python
async def get_agent_context_store(
    self, 
    agent_id: UUID
) -> Optional[AgentContextStore]:
    """
    Получить хранилище контекста агента.
    
    Проверяет, активен ли агент, и возвращает его context_store.
    Используется для поиска и добавления контекста.
    
    Args:
        agent_id: ID агента
        
    Returns:
        AgentContextStore или None если агент не активен
        
    Raises:
        - Логирует warning если агент не найден
    """
```

**Логика:**
1. Проверить, инициализирован ли workspace
2. Найти агента в `self.active_agents[agent_id]`
3. Если не найден → логирование warning, return None
4. Вернуть `agent.context_store`

**Пример использования:**
```python
context_store = await workspace.get_agent_context_store(agent_id)
if context_store:
    results = await context_store.search(query="important context")
```

---

#### 1.2 Метод `search_context()`

```python
async def search_context(
    self,
    agent_id: UUID,
    query: str,
    limit: int = 10,
    filter_success: Optional[bool] = None,
    filter_type: Optional[str] = None
) -> list[dict[str, Any]]:
    """
    Поиск в контексте агента (vector search через Qdrant).
    
    Переходит в контекстное хранилище агента и выполняет
    семантический поиск по запросу.
    
    Args:
        agent_id: ID агента
        query: Поисковый запрос
        limit: Максимум результатов (default 10)
        filter_success: Фильтр по успешным взаимодействиям (optional)
        filter_type: Фильтр по типу взаимодействия (optional, e.g. "chat")
        
    Returns:
        Список результатов поиска с полями:
        - id: ID точки в Qdrant
        - score: Релевантность (0-1)
        - content: Текст взаимодействия
        - interaction_type: Тип ("chat", "task", etc)
        - timestamp: Когда произошло
        - metadata: Доп. данные
        
    Raises:
        - Логирует warning если агент не найден
        - Возвращает [] если ошибка поиска
    """
```

**Логика:**
1. Получить context_store через `get_agent_context_store(agent_id)`
2. Если None → return []
3. Вызвать `context_store.search(query, limit, filter_success, filter_type)`
4. Логировать результаты

**Пример использования:**
```python
results = await workspace.search_context(
    agent_id=agent_id,
    query="How to process payments?",
    limit=5,
    filter_success=True
)
# results[0]: {"score": 0.95, "content": "...", "timestamp": "2026-02-19..."}
```

---

#### 1.3 Метод `add_context()`

```python
async def add_context(
    self,
    agent_id: UUID,
    content: str,
    interaction_type: str = "chat",
    task_id: Optional[str] = None,
    success: bool = True,
    metadata: Optional[dict[str, Any]] = None
) -> Optional[str]:
    """
    Добавить взаимодействие в контекст агента.
    
    Сохраняет новое взаимодействие (user-agent conversation)
    в Qdrant для использования в будущих запросах.
    
    Args:
        agent_id: ID агента
        content: Текст взаимодействия (user message + agent response)
        interaction_type: Тип ("chat", "task_execution", "error_handling", etc)
        task_id: ID задачи, если связано с задачей (optional)
        success: Успешно ли взаимодействие (default True)
        metadata: Доп. данные (tokens, model, latency, etc)
        
    Returns:
        ID точки в Qdrant или None если ошибка
        
    Raises:
        - Логирует warning если агент не найден
        - Логирует error если ошибка добавления в Qdrant
    """
```

**Логика:**
1. Получить context_store
2. Если None → логирование, return None
3. Вызвать `context_store.add_interaction(...)`
4. Логировать успешное добавление

**Пример использования:**
```python
point_id = await workspace.add_context(
    agent_id=agent_id,
    content="User: What's the weather? Agent: It's sunny today.",
    interaction_type="chat",
    task_id=str(session_id),
    metadata={"model": "gpt-4", "tokens": 150}
)
```

---

#### 1.4 Метод `clear_context()`

```python
async def clear_context(self, agent_id: UUID) -> bool:
    """
    Очистить весь контекст агента.
    
    Удаляет все взаимодействия агента из Qdrant.
    Используется при сбросе или удалении агента.
    
    Args:
        agent_id: ID агента
        
    Returns:
        True если успешно, False если ошибка или агент не найден
        
    Raises:
        - Логирует warning если агент не найден
        - Логирует error если ошибка Qdrant
    """
```

**Логика:**
1. Получить context_store
2. Если None → return False
3. Вызвать `context_store.clear()`
4. Логировать

**Пример использования:**
```python
success = await workspace.clear_context(agent_id=agent_id)
if success:
    print("Context cleared")
```

---

### Файлы для изменения
- **`app/core/user_worker_space.py`**: Добавить 4 метода (в конец класса перед cleanup)

### Добавляемые импорты
```python
# Уже должны быть:
from app.vectorstore.agent_context_store import AgentContextStore
```

### Тестовые сценарии
1. ✅ search_context для несуществующего агента → return []
2. ✅ add_context сохраняет взаимодействие
3. ✅ search_context находит добавленное взаимодействие
4. ✅ clear_context удаляет все контексты

---

## 🟢 ЭТАП 2: Методы координации режимов выполнения (10.5)

### Обзор
Добавить методы для двух режимов выполнения задач и единого API для обработки сообщений.

### Текущее состояние
- ✅ `send_task_to_agent()` уже существует (sends to Agent Bus)
- ✅ В `app/routes/project_chat.py` уже есть логика direct/orchestrated режимов
- ❌ Методы НЕ обёрнуты в UserWorkerSpace API
- ❌ Нет единого `handle_message()` API

### Архитектура режимов

```
DIRECT MODE:
User → Message → UserWorkerSpace.direct_execution()
  ↓
  Specify agent_id → Get agent from cache
  ↓
  Add input context → Execute agent → Add output context
  ↓
  Return response

ORCHESTRATED MODE:
User → Message → UserWorkerSpace.orchestrated_execution()
  ↓
  Get Project Orchestrator
  ↓
  Route to best agent(s)
  ↓
  Execute → Aggregate results
  ↓
  Return response
```

### Что добавить в `app/core/user_worker_space.py`

#### 2.1 Метод `direct_execution()`

```python
async def direct_execution(
    self,
    agent_id: UUID,
    user_message: str,
    session_history: Optional[list[dict[str, str]]] = None,
    task_id: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None
) -> dict[str, Any]:
    """
    Выполнить задачу напрямую через конкретного агента.
    
    РЕЖИМ: Пользователь явно выбирает агента.
    
    Процесс:
    1. Получить агента из кеша workspace
    2. Добавить входное сообщение в контекст
    3. Выполнить agent.execute()
    4. Добавить результат в контекст
    5. Вернуть результат
    
    Args:
        agent_id: ID целевого агента
        user_message: Сообщение пользователя
        session_history: История сессии (optional)
        task_id: ID задачи для корреляции (optional)
        metadata: Доп. данные о запросе (optional)
        
    Returns:
        {
            "success": bool,
            "response": str,  # Ответ агента
            "agent_id": str,
            "agent_name": str,
            "context_used": int,  # Сколько контекстных результатов использовано
            "tokens_used": int,   # Tokens от LLM
            "timestamp": str,
            "execution_time_ms": float
        }
        
    Raises:
        - ValueError если agent_id не найден
        - LogError если ошибка выполнения
    """
```

**Детальная логика:**

```python
async def direct_execution(self, agent_id: UUID, user_message: str, ...):
    # 1. Validate
    if not self.initialized:
        await self.initialize()
    
    # 2. Get agent
    agent = await self.get_agent(agent_id)
    if not agent:
        logger.error(f"Agent {agent_id} not found")
        raise ValueError(f"Agent not found: {agent_id}")
    
    # 3. Add input context (optional, только если нужно отслеживание)
    await self.add_context(
        agent_id=agent_id,
        content=f"[INPUT] {user_message}",
        interaction_type="direct_execution_input",
        task_id=task_id,
        metadata=metadata
    )
    
    # 4. Execute
    start_time = time.time()
    result = await agent.execute(
        user_message=user_message,
        session_history=session_history,
        task_id=task_id
    )
    execution_time = (time.time() - start_time) * 1000  # ms
    
    # 5. Add output context if successful
    if result.get("success"):
        await self.add_context(
            agent_id=agent_id,
            content=f"[OUTPUT] {result.get('response')}",
            interaction_type="direct_execution_output",
            task_id=task_id,
            success=True,
            metadata={
                "tokens": result.get("tokens_used"),
                "execution_time_ms": execution_time
            }
        )
    
    # 6. Return structured response
    return {
        "success": result.get("success"),
        "response": result.get("response") or result.get("error"),
        "agent_id": str(agent_id),
        "agent_name": agent.config.name,
        "context_used": result.get("context_used", 0),
        "tokens_used": result.get("tokens_used", 0),
        "timestamp": datetime.utcnow().isoformat(),
        "execution_time_ms": execution_time
    }
```

**Пример использования:**
```python
result = await workspace.direct_execution(
    agent_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
    user_message="What is Python?",
    task_id="chat_session_001"
)
# result: {
#   "success": True,
#   "response": "Python is a programming language...",
#   "agent_id": "123e4567...",
#   "context_used": 3,
#   "tokens_used": 245,
#   "execution_time_ms": 1250
# }
```

---

#### 2.2 Метод `orchestrated_execution()`

```python
async def orchestrated_execution(
    self,
    user_message: str,
    session_history: Optional[list[dict[str, str]]] = None,
    task_id: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None
) -> dict[str, Any]:
    """
    Выполнить задачу через Project Orchestrator (智能路由).
    
    РЕЖИМ: Система сама выбирает лучшего агента для запроса.
    
    Процесс:
    1. Получить Orchestrator проекта
    2. Orchestrator анализирует запрос и выбирает агент(ов)
    3. Выполнить на выбранном агенте через direct_execution
    4. Вернуть результат
    
    Args:
        user_message: Сообщение пользователя
        session_history: История сессии (optional)
        task_id: ID задачи (optional)
        metadata: Доп. данные (optional)
        
    Returns:
        {
            "success": bool,
            "response": str,
            "selected_agent_id": str,  # Какой агент выбран
            "selected_agent_name": str,
            "routing_score": float,     # Confidence score маршрутизации
            "context_used": int,
            "tokens_used": int,
            "timestamp": str,
            "execution_time_ms": float
        }
        
    Raises:
        - ValueError если нет доступных агентов
        - LogError если ошибка Orchestrator
    """
```

**Детальная логика:**

```python
async def orchestrated_execution(self, user_message: str, ...):
    # 1. Validate
    if not self.initialized:
        await self.initialize()
    
    agents = await self.list_agents_for_project()
    if not agents:
        raise ValueError("No agents available for orchestration")
    
    # 2. Get Orchestrator (from agent_manager or database)
    # Orchestrator должен быть специальным агентом для маршрутизации
    try:
        orchestrator = await self.agent_manager.get_orchestrator()
        if not orchestrator:
            # Fallback: используем первого доступного агента
            selected_agent_id = agents[0]
            routing_score = 1.0
        else:
            # Orchestrator выбирает лучшего агента
            routing_result = await orchestrator.select_best_agent(
                query=user_message,
                available_agents=agents,
                session_history=session_history
            )
            selected_agent_id = routing_result["agent_id"]
            routing_score = routing_result["score"]
    except Exception as e:
        logger.error(f"Orchestration error: {e}")
        # Fallback на первого агента
        selected_agent_id = agents[0]
        routing_score = 0.5
    
    # 3. Execute через direct_execution
    start_time = time.time()
    result = await self.direct_execution(
        agent_id=selected_agent_id,
        user_message=user_message,
        session_history=session_history,
        task_id=task_id,
        metadata=metadata
    )
    execution_time = (time.time() - start_time) * 1000
    
    # 4. Return with routing info
    return {
        **result,
        "selected_agent_id": str(selected_agent_id),
        "routing_score": routing_score,
        "execution_time_ms": execution_time
    }
```

**Пример использования:**
```python
result = await workspace.orchestrated_execution(
    user_message="How do I reset my password?",
    task_id="chat_session_002"
)
# result: {
#   "success": True,
#   "response": "To reset your password...",
#   "selected_agent_id": "789...",
#   "selected_agent_name": "Support Agent",
#   "routing_score": 0.95,
#   "tokens_used": 320,
#   "execution_time_ms": 2100
# }
```

---

#### 2.3 Метод `handle_message()` (Единый API)

```python
async def handle_message(
    self,
    message_content: str,
    target_agent_id: Optional[UUID] = None,
    session_history: Optional[list[dict[str, str]]] = None,
    task_id: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None
) -> dict[str, Any]:
    """
    Единый API для обработки сообщений (выбирает режим автоматически).
    
    Логика:
    - Если target_agent_id задан → DIRECT mode
    - Если target_agent_id не задан → ORCHESTRATED mode
    
    Args:
        message_content: Текст сообщения
        target_agent_id: ID целевого агента (optional)
        session_history: История (optional)
        task_id: ID задачи (optional)
        metadata: Доп. данные (optional)
        
    Returns:
        Результат direct_execution или orchestrated_execution
        
    Raises:
        ValueError если invalid аргументы
    """
```

**Логика:**
```python
async def handle_message(
    self,
    message_content: str,
    target_agent_id: Optional[UUID] = None,
    ...
) -> dict[str, Any]:
    if not message_content:
        raise ValueError("message_content cannot be empty")
    
    if target_agent_id:
        # Direct execution mode
        logger.info(f"Direct execution for agent {target_agent_id}")
        return await self.direct_execution(
            agent_id=target_agent_id,
            user_message=message_content,
            session_history=session_history,
            task_id=task_id,
            metadata=metadata
        )
    else:
        # Orchestrated execution mode
        logger.info("Orchestrated execution")
        return await self.orchestrated_execution(
            user_message=message_content,
            session_history=session_history,
            task_id=task_id,
            metadata=metadata
        )
```

---

### Файлы для изменения
- **`app/core/user_worker_space.py`**: Добавить 3 метода

### Требуемые импорты
```python
import time
from datetime import datetime
# Уже должны быть
```

### Зависимости от Этапа 1
- ✅ `add_context()` - используется для логирования взаимодействий
- ✅ `get_agent()` - получение агента из кеша

### Тестовые сценарии
1. ✅ direct_execution с валидным agent_id
2. ✅ direct_execution с невалидным agent_id → ValueError
3. ✅ orchestrated_execution выбирает агента
4. ✅ handle_message с target_agent_id → direct
5. ✅ handle_message без target_agent_id → orchestrated

---

## 🟡 ЭТАП 3: Методы для получения метрик (10.6)

### Обзор
Добавить методы для полного мониторинга состояния workspace и агентов.

### Текущее состояние
- ✅ `get_agent_stats()` уже существует (базовая статистика)
- ❌ `get_metrics()` (расширенные) - НЕ реализован
- ❌ `get_agent_status()` - НЕ реализован

### Что добавить

#### 3.1 Метод `get_metrics()` (расширенный)

```python
async def get_metrics(self) -> dict[str, Any]:
    """
    Получить полные метрики Worker Space.
    
    Включает:
    - Общая информация (user_id, project_id)
    - Статус инициализации
    - Информация об агентах
    - Статистика кеша
    - Статистика Qdrant контекста
    - Статус здоровья
    
    Returns:
        {
            "user_id": str,
            "project_id": str,
            "initialized": bool,
            "initialization_time": str (ISO format),
            "uptime_seconds": float,
            
            "agents": {
                "total": int,
                "active": int,
                "list": [
                    {
                        "id": str,
                        "name": str,
                        "status": "active" | "inactive",
                        "cache_hits": int,
                        "context_vectors": int
                    },
                    ...
                ]
            },
            
            "cache": {
                "size": int,
                "max_size": int,
                "hit_rate": float (0-1),
                "ttl_seconds": int
            },
            
            "context": {
                "total_vectors": int,
                "collections_count": int,
                "avg_vectors_per_agent": float
            },
            
            "health": {
                "is_healthy": bool,
                "last_check": str (ISO format),
                "issues": list[str]  # Описание проблем если есть
            },
            
            "timestamp": str (ISO format)
        }
    """
```

#### 3.2 Метод `get_agent_status()`

```python
async def get_agent_status(
    self,
    agent_id: UUID
) -> Optional[dict[str, Any]]:
    """
    Получить детальный статус конкретного агента.
    
    Args:
        agent_id: ID агента
        
    Returns:
        {
            "agent_id": str,
            "agent_name": str,
            "is_active": bool,
            "is_in_cache": bool,
            
            "execution": {
                "total_executions": int,
                "successful": int,
                "failed": int,
                "last_execution": str (ISO format),
                "avg_execution_time_ms": float,
                "last_execution_time_ms": float
            },
            
            "context": {
                "total_vectors": int,
                "recent_interactions": int,
                "context_search_enabled": bool
            },
            
            "performance": {
                "cache_hit_rate": float,
                "error_rate": float,
                "avg_tokens_per_execution": float
            },
            
            "config": {
                "model": str,
                "temperature": float,
                "max_tokens": int,
                "concurrency_limit": int
            }
        }
        
    Returns None если агент не найден
    """
```

### Файлы для изменения
- **`app/core/user_worker_space.py`**: Добавить 2 метода

### Зависимости от других этапов
- ✅ Этап 1 для информации о контексте

### Тестовые сценарии
1. ✅ get_metrics возвращает корректную структуру
2. ✅ get_agent_status для активного агента
3. ✅ get_agent_status для неактивного агента → None
4. ✅ Метрики обновляются после выполнения задач

---

## 🟡 ЭТАП 4: Обновление зависимостей (10.9)

### Обзор
Проверка и обновление `app/dependencies.py` для поддержки новых методов.

### Текущее состояние
- ✅ `get_worker_space()` уже существует и корректен
- ❌ Нет дополнительных зависимостей для новых методов

### Что проверить/обновить

#### 4.1 Проверка существующего `get_worker_space()`

Должен быть:
```python
async def get_worker_space(
    project_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    qdrant: AsyncQdrantClient | None = Depends(get_qdrant),
) -> UserWorkerSpace:
    """Dependency для получения UserWorkerSpace"""
    # ✅ Уже реализован корректно
```

#### 4.2 Опциональное добавление удобных зависимостей

**Вариант 1: Зависимость для AgentContextStore (опционально)**

```python
async def get_agent_context_store(
    agent_id: UUID,
    workspace: UserWorkerSpace = Depends(get_worker_space)
) -> Optional[AgentContextStore]:
    """Dependency для получения контекстного хранилища агента"""
    return await workspace.get_agent_context_store(agent_id)
```

**Использование в routes:**
```python
@router.get("/agents/{agent_id}/context/search")
async def search_context(
    agent_id: UUID,
    query: str,
    context_store: Optional[AgentContextStore] = Depends(get_agent_context_store)
):
    if not context_store:
        raise HTTPException(status_code=404)
    return await context_store.search(query)
```

### Файлы для изменения
- **`app/dependencies.py`**: Проверка корректности + опциональное добавление

### Минимальные требования
- ✅ `get_worker_space()` правильно работает
- ✅ Выполняется инициализация workspace

---

## 🔄 ИНТЕГРАЦИЯ С ENDPOINTS (дополнительный этап)

### Файлы для обновления
- **`app/routes/project_chat.py`**: Использовать новые методы workspace

### Примеры обновления

**Было:**
```python
# Логика direct mode разбросана по всему файлу
```

**Будет:**
```python
@router.post("/{session_id}/message/")
async def send_message(...):
    if message_request.target_agent:
        result = await workspace.direct_execution(
            agent_id=message_request.target_agent,
            user_message=message_request.content,
            ...
        )
    else:
        result = await workspace.orchestrated_execution(
            user_message=message_request.content,
            ...
        )
```

---

## ✅ КРИТЕРИИ ЗАВЕРШЕНИЯ

### Этап 1 (Qdrant методы)
- [x] `get_agent_context_store()` реализован
- [x] `search_context()` реализован
- [x] `add_context()` реализован
- [x] `clear_context()` реализован
- [x] Все методы имеют docstrings и type hints
- [x] Логирование и error handling

### Этап 2 (Mode execution)
- [x] `direct_execution()` реализован с полной логикой
- [x] `orchestrated_execution()` реализован с fallback
- [x] `handle_message()` использует оба режима
- [x] Метаданные выполнения сохраняются
- [x] Время выполнения отслеживается

### Этап 3 (Metrics)
- [x] `get_metrics()` вернет полную информацию
- [x] `get_agent_status()` вернет детали агента
- [x] Метрики обновляются в реальном времени

### Этап 4 (Dependencies)
- [x] `get_worker_space()` проверен
- [x] Опциональные зависимости (если нужны)

### Общее
- [x] Все методы async
- [x] Per-project изоляция соблюдается
- [x] Ошибки логируются правильно
- [x] Нет утечек между проектами
- [x] Type hints везде

---

## 📝 РЕКОМЕНДОВАННЫЙ ПОРЯДОК РЕАЛИЗАЦИИ

1. **День 1**: Этап 1 (Qdrant методы) - базис для остального
2. **День 2**: Этап 2 (Mode execution) - основная функциональность
3. **День 3**: Этап 3 (Metrics) - мониторинг и обсервабилити
4. **День 3**: Этап 4 (Dependencies) - финальная проверка
5. **День 4**: Integration тесты и обновление endpoints

---

## 📊 МАТРИЦА ЗАВИСИМОСТЕЙ

```
10.4 (Qdrant) ──┐
                ├─→ 10.5 (Execute) ──┐
                                     ├─→ 10.6 (Metrics) ──→ 10.9 (Deps)
10.1-3 (AgentManager, etc) ────────┘
```

---

## 🚀 НАЧАЛО РЕАЛИЗАЦИИ

Готовы перейти в Code mode и начать с Этапа 1?
