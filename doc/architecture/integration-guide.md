# Интеграционный гайд - User Worker Space

**Дата:** 18 февраля 2026  
**Версия:** 1.0  
**Назначение:** Практическое руководство по использованию User Worker Space архитектуры

## 📋 Оглавление

1. [Как добавить новый endpoint](#как-добавить-новый-endpoint)
2. [Использование workspace в эндпоинте](#использование-workspace-в-эндпоинте)
3. [Лучшие практики](#лучшие-практики)
4. [Тестирование](#тестирование)
5. [Troubleshooting](#troubleshooting)

---

## Как добавить новый endpoint

### Шаг 1: Создать функцию endpoint

```python
from fastapi import APIRouter, Depends, HTTPException, status
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.user_worker_space import UserWorkerSpace
from app.dependencies import get_worker_space
from app.database import get_db
from app.middleware.user_isolation import get_current_user_id

router = APIRouter(prefix="/my/projects/{project_id}/myfeature", tags=["my-feature"])

@router.get("/")
async def my_new_endpoint(
    project_id: UUID,
    request: Request,
    workspace: UserWorkerSpace = Depends(get_worker_space),  # ← КЛЮЧЕВОЕ
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Мой новый endpoint с автоматической инициализацией workspace.
    
    Args:
        project_id: UUID проекта из пути
        request: FastAPI request с user context
        workspace: Автоматически получается или создается
        db: Сессия БД
    
    Returns:
        Результат операции
    """
    user_id = get_current_user_id(request)
    
    # workspace уже инициализирован и содержит:
    # - workspace.agent_cache - кеш агентов
    # - workspace.agent_manager - доступ к БД
    # - workspace.agent_bus - шина задач
    # - workspace.active_agents - активные агенты
    
    # ✅ Пример 1: Получение агента
    agent = await workspace.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # ✅ Пример 2: Список агентов проекта
    agents = await workspace.list_agents_for_project()
    
    # ✅ Пример 3: Отправка задачи агенту
    success = await workspace.send_task_to_agent(
        agent_id=agent_id,
        task_payload={"message": "Hello", "data": ...}
    )
    
    # ✅ Пример 4: Получение статистики
    stats = await workspace.get_agent_stats()
    
    return {
        "status": "success",
        "user_id": str(user_id),
        "project_id": str(project_id),
        "agents_count": len(agents),
        "workspace_initialized": workspace.initialized,
    }
```

### Шаг 2: Зарегистрировать маршрут в app.main

```python
# app/main.py
from app.routes import myfeature

# В разделе "Include routers"
app.include_router(myfeature.router)
```

### Шаг 3: Писать тесты

```python
# tests/test_myfeature.py
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_my_new_endpoint(
    client: AsyncClient,
    auth_headers: dict,
    test_user,
    test_project,
    test_agent,
):
    """Тест нового endpoint."""
    project_id = str(test_project.id)
    
    response = await client.get(
        f"/my/projects/{project_id}/myfeature/",
        headers=auth_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["workspace_initialized"] is True
```

---

## Использование workspace в эндпоинте

### Pattern 1: Получение агента из cache

```python
@router.get("/{agent_id}")
async def get_agent_info(
    project_id: UUID,
    agent_id: UUID,
    workspace: UserWorkerSpace = Depends(get_worker_space),
) -> dict:
    """Получить информацию об агенте."""
    
    # Получить из кеша (если инициализирован)
    agent = await workspace.get_agent(agent_id)
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # agent - это ContextualAgent с конфигом
    return {
        "id": str(agent_id),
        "config": agent.config.model_dump(),
        "status": "active",
    }
```

### Pattern 2: Отправка задачи через Agent Bus

```python
@router.post("/tasks/{agent_id}")
async def send_task(
    project_id: UUID,
    agent_id: UUID,
    task_data: TaskRequest,
    workspace: UserWorkerSpace = Depends(get_worker_space),
) -> dict:
    """Отправить задачу агенту."""
    
    # Отправить задачу через Agent Bus
    success = await workspace.send_task_to_agent(
        agent_id=agent_id,
        task_payload=task_data.model_dump()
    )
    
    if not success:
        raise HTTPException(status_code=400, detail="Failed to queue task")
    
    return {
        "task_id": str(uuid4()),
        "status": "queued",
        "agent_id": str(agent_id),
    }
```

### Pattern 3: Работа со списком агентов

```python
@router.get("/agents/summary")
async def get_agents_summary(
    project_id: UUID,
    workspace: UserWorkerSpace = Depends(get_worker_space),
) -> dict:
    """Получить сводку по всем агентам проекта."""
    
    # Список всех агентов в workspace
    agent_ids = await workspace.list_agents_for_project()
    
    # Статистика workspace
    stats = await workspace.get_agent_stats()
    
    return {
        "total_agents": len(agent_ids),
        "cache_size": stats["cache_size"],
        "initialized": stats["initialized"],
        "initialization_time": stats["initialization_time"],
        "agent_ids": [str(aid) for aid in agent_ids],
    }
```

### Pattern 4: Обработка ошибок workspace

```python
@router.post("/execute")
async def execute_operation(
    project_id: UUID,
    workspace: UserWorkerSpace = Depends(get_worker_space),
) -> dict:
    """Выполнить операцию с обработкой ошибок."""
    
    try:
        # Проверить здоровье workspace
        if not workspace.is_healthy():
            raise HTTPException(
                status_code=503,
                detail="Workspace is not healthy"
            )
        
        # Выполнить операцию
        result = await workspace.get_agent_stats()
        
        return {
            "status": "success",
            "result": result,
        }
        
    except Exception as e:
        logger.error(f"Workspace error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )
```

---

## Лучшие практики

### ✅ ДО: Правильно

```python
# 1. Всегда используйте get_worker_space dependency
@router.get("/")
async def my_endpoint(
    workspace: UserWorkerSpace = Depends(get_worker_space),  # ✅
):
    pass

# 2. Проверяйте результаты операций
agent = await workspace.get_agent(agent_id)
if not agent:  # ✅ Обработайте None
    raise HTTPException(status_code=404)

# 3. Логируйте важные события
logger.info(f"Workspace initialized for project {project_id}")

# 4. Используйте workspace методы для работы с агентами
agents = await workspace.list_agents_for_project()  # ✅

# 5. Не создавайте AgentManager вручную в endpoint
async def my_endpoint(...):
    # ✅ Используйте workspace.agent_manager
    agents = await workspace.agent_manager.list_agents()
```

### ❌ НЕПРАВИЛЬНО: Антипаттерны

```python
# 1. ❌ Не получайте workspace вручную
@router.get("/")
async def bad_endpoint():
    manager = WorkerSpaceManager()  # ❌ Неправильно!
    space = await manager.get_or_create(...)  # ❌ Используйте dependency

# 2. ❌ Не создавайте AgentManager вручную для проекта
async def another_bad_endpoint():
    # ❌ Неправильно - каждый раз новый экземпляр
    manager = AgentManager(db=db, redis=redis, qdrant=qdrant, user_id=user_id)
    # ✅ Правильно:
    manager = workspace.agent_manager

# 3. ❌ Не игнорируйте errors
agent = await workspace.get_agent(agent_id)
# ❌ Не проверяйте, вызовет AttributeError если None
print(agent.config.model)

# 4. ❌ Не проверяйте initialized вручную
if workspace.initialized:  # ❌ Неправильно
    # workspace ВСЕГДА инициализирован при получении через dependency
    pass

# 5. ❌ Не вызывайте cleanup вручную в endpoint
await workspace.cleanup()  # ❌ Это вызывается автоматически!
```

### 📋 Чеклист при добавлении endpoint

- [ ] Dependency `workspace: UserWorkerSpace = Depends(get_worker_space)` добавлен
- [ ] Использованы методы workspace вместо прямого доступа к агентам
- [ ] Обработаны ошибки (None checks, HTTPException)
- [ ] Добавлено логирование важных операций
- [ ] Написаны тесты
- [ ] Маршрут зарегистрирован в `app.main`
- [ ] User isolation проверен (фильтр по project_id в БД запросах)

---

## Тестирование

### Тестирование с workspace

```python
import pytest
from httpx import AsyncClient
from uuid import uuid4

@pytest.mark.asyncio
async def test_endpoint_with_workspace(
    client: AsyncClient,
    auth_headers: dict,
    test_user,
    test_project,
    test_agent,
    db_session,
):
    """Тест endpoint с использованием workspace."""
    
    project_id = str(test_project.id)
    
    # ✅ Первый запрос - создает workspace
    response1 = await client.get(
        f"/my/projects/{project_id}/myfeature/",
        headers=auth_headers
    )
    assert response1.status_code == 200
    assert response1.json()["workspace_initialized"] is True
    
    # ✅ Второй запрос - использует кешированный workspace
    response2 = await client.get(
        f"/my/projects/{project_id}/myfeature/",
        headers=auth_headers
    )
    assert response2.status_code == 200
    # Workspace уже инициализирован


@pytest.mark.asyncio
async def test_workspace_isolation(
    client: AsyncClient,
    auth_headers: dict,
    test_user,
    db_session,
):
    """Тест изоляции workspace между проектами."""
    
    # Создать 2 проекта
    proj1 = await create_test_project(db_session, test_user, "proj1")
    proj2 = await create_test_project(db_session, test_user, "proj2")
    
    # ✅ Запрос к proj1
    resp1 = await client.get(
        f"/my/projects/{proj1.id}/agents/",
        headers=auth_headers
    )
    assert resp1.status_code == 200
    
    # ✅ Запрос к proj2 - отдельный workspace
    resp2 = await client.get(
        f"/my/projects/{proj2.id}/agents/",
        headers=auth_headers
    )
    assert resp2.status_code == 200
    
    # Workspaces должны быть независимыми
    # (проверяется автоматически через разные project_id)


@pytest.mark.asyncio
async def test_workspace_cleanup(
    client: AsyncClient,
    auth_headers: dict,
    test_user,
    test_project,
    db_session,
):
    """Тест cleanup workspace при удалении проекта."""
    
    project_id = str(test_project.id)
    
    # 1. Создать workspace через запрос
    await client.get(
        f"/my/projects/{project_id}/agents/",
        headers=auth_headers
    )
    
    # 2. Удалить проект
    response = await client.delete(
        f"/my/projects/{project_id}",
        headers=auth_headers
    )
    assert response.status_code == 204
    
    # 3. Workspace должен быть очищен
    # (это проверяется внутри cleanup)
```

---

## Troubleshooting

### Проблема: 500 Internal Server Error при инициализации

**Симптомы:**
```
worker_space_initialization_error: "1 validation error for AgentConfig"
```

**Причина:** AgentConfig не проходит валидацию при загрузке из БД

**Решение:**
```python
# Проверить конфиг агента в БД
# Должны быть все обязательные поля:
config = {
    "name": "...",  # ← обязательно
    "system_prompt": "...",  # ← обязательно
    "model": "...",  # имеет default
    "temperature": 0.7,  # имеет default
    "max_tokens": 2048,  # имеет default
}
```

### Проблема: Agent not found когда должен быть найден

**Симптомы:**
```
Agent not found in workspace: agent_id=xyz, project_id=abc
```

**Причина:** Агент принадлежит другому проекту или пользователю

**Решение:**
```python
# Убедитесь что:
1. project_id правильный (из пути)
2. agent_id принадлежит этому проекту
   SELECT * FROM user_agent WHERE id = ? AND project_id = ?

3. Workspace инициализирован для этого проекта
   await workspace.initialize()
```

### Проблема: Workspace не инициализируется

**Симптомы:**
```
workspace.initialized = False
active_agents = {}
```

**Причина:** Нет агентов в проекте или ошибка при инициализации

**Решение:**
```python
# 1. Проверить наличие агентов в проекте
# 2. Посмотреть логи ошибок инициализации
# 3. Вызвать workspace.reset()
await workspace.reset()
# 4. Проверить workspace.is_healthy()
if not workspace.is_healthy():
    logger.error("Workspace is unhealthy")
```

### Проблема: User isolation нарушена

**Симптомы:**
```
Пользователь может видеть/редактировать чужие проекты
```

**Причина:** Забыли добавить фильтр по user_id в запрос

**Решение:**
```python
# ❌ НЕПРАВИЛЬНО
stmt = select(ChatSession).where(ChatSession.project_id == project_id)

# ✅ ПРАВИЛЬНО
user_id = get_current_user_id(request)
stmt = select(ChatSession).where(
    ChatSession.project_id == project_id,
    ChatSession.user_id == user_id  # ← ВАЖНО!
)
```

### Проблема: Медленная инициализация workspace

**Симптомы:**
```
Первый запрос к проекту выполняется долго (2+ секунды)
```

**Причина:** Загрузка всех агентов и их регистрация в Agent Bus

**Решение:**
```python
# Это нормально - первый запрос медленнее
# Последующие используют кеш (fast path)

# Если очень медленно:
1. Проверьте количество агентов
2. Профилируйте workspace.initialize()
3. Проверьте производительность Qdrant/Redis
```

---

## Примеры реальных использований

### Пример: Chat endpoint с workspace

```python
@router.post("/{session_id}/message/")
async def send_message(
    project_id: UUID,
    session_id: UUID,
    message_request: MessageRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    workspace: UserWorkerSpace = Depends(get_worker_space),
) -> MessageResponse:
    """Отправить сообщение в чат сессию."""
    
    user_id = get_current_user_id(request)
    
    # 1. Проверить что session принадлежит пользователю и проекту
    session = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == user_id,
            ChatSession.project_id == project_id,
        )
    ).scalar_one_or_none()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # 2. Если указан целевой агент - использовать его из workspace
    if message_request.target_agent:
        agent = await workspace.get_agent(UUID(message_request.target_agent))
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        
        # 3. Отправить задачу агенту через Agent Bus
        success = await workspace.send_task_to_agent(
            agent_id=UUID(message_request.target_agent),
            task_payload={
                "message": message_request.content,
                "session_id": str(session_id),
            }
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to queue task")
    
    # 4. Сохранить сообщение пользователя
    user_message = Message(
        session_id=session_id,
        role="user",
        content=message_request.content,
    )
    db.add(user_message)
    await db.flush()
    
    return MessageResponse(
        id=user_message.id,
        role="user",
        content=message_request.content,
        timestamp=user_message.created_at,
    )
```

---

## Дополнительные ресурсы

- [`doc/architecture/workspace-lifecycle.md`](workspace-lifecycle.md) - Полная архитектура
- [`app/dependencies.py`](../../app/dependencies.py) - Реализация get_worker_space
- [`app/core/user_worker_space.py`](../../app/core/user_worker_space.py) - UserWorkerSpace класс
- [`app/core/worker_space_manager.py`](../../app/core/worker_space_manager.py) - Manager класс

