# Анализ: Endpoints для управления проектами в per-project архитектуре

**Дата:** 17 февраля 2026  
**Версия:** 1.0  
**Контекст:** Какие endpoints нужны для управления проектами пользователя

---

## 🎯 Короткий ответ

**ДА, нужны новые endpoints для управления проектами**, но это НЕ основные endpoints, а вспомогательные.

---

## 📊 Два типа управления

### User Workspace (управляется пользователем)
- 📁 Пользователь создает папки на своем диске
- 👤 Пользователь управляет файлами
- 🔧 Client приложение знает о папках
- ✗ Backend НЕ создает файлы

### Backend Resources (управляет backend)
- ⚙️ Backend должен знать о каждом проекте
- 📝 Backend регистрирует проект в `user_projects` таблице
- 🔗 Backend создает User Worker Space для проекта
- ✗ Backend НЕ создает файловую систему

---

## 🔄 Поток: Как пользователь добавляет проект

### Сценарий 1: Пользователь указывает путь к существующему проекту

```
1. User действие
   User: "Хочу использовать проект /home/user/projects/my-app"
   └─ Client приложение отправляет REST API запрос

2. API запрос
   POST /my/projects/
   {
       "name": "my-app",
       "workspace_path": "/home/user/projects/my-app"
   }

3. Backend обработка
   ├─ Валидировать, что путь доступен (опционально)
   ├─ Создать запись в user_projects таблице
   ├─ Backend инициализирует User Worker Space для проекта
   └─ Вернуть информацию о проекте

4. Response
   {
       "id": "proj_001",
       "user_id": "user_123",
       "name": "my-app",
       "workspace_path": "/home/user/projects/my-app",
       "created_at": "2026-02-17T08:00:00Z"
   }

5. User видит
   Проект "my-app" теперь доступен в Client приложении
```

### Сценарий 2: Пользователь получает список проектов

```
1. User действие
   User: "Покажи мне мои проекты"
   └─ Client приложение отправляет GET запрос

2. API запрос
   GET /my/projects/

3. Backend обработка
   ├─ Получить все user_projects для пользователя
   ├─ Вернуть список проектов

4. Response
   [
       {
           "id": "proj_001",
           "name": "my-app",
           "workspace_path": "/home/user/projects/my-app",
           "created_at": "2026-02-17T08:00:00Z"
       },
       {
           "id": "proj_002",
           "name": "data-analysis",
           "workspace_path": "/home/user/projects/data-analysis",
           "created_at": "2026-02-17T08:10:00Z"
       }
   ]

5. User видит
   Список всех своих проектов в Client приложении
```

---

## 📋 Требуемые endpoints для управления проектами

### 1. Создать проект

**Endpoint:** `POST /my/projects/`

```python
@router.post("/my/projects/")
async def create_project(
    project_data: ProjectCreate,  # name, workspace_path
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_db),
    worker_space_manager = Depends(get_worker_space_manager)
) -> ProjectResponse:
    """
    Создать новый проект для пользователя
    
    Параметры:
    - name: str - имя проекта
    - workspace_path: str (опционально) - путь к workspace
    
    Возвращает: ProjectResponse с информацией о проекте
    """
    
    # 1. Создать запись в user_projects
    project = UserProject(
        user_id=user_id,
        name=project_data.name,
        workspace_path=project_data.workspace_path
    )
    db.add(project)
    await db.commit()
    
    # 2. Backend инициализирует User Worker Space для проекта
    # Это автоматически происходит при первом запросе к проекту
    # но можно сделать и явно:
    worker_space = await worker_space_manager.get_or_create(
        user_id=user_id,
        project_id=str(project.id)
    )
    
    return ProjectResponse.from_orm(project)
```

**Request:**
```json
{
    "name": "my-app",
    "workspace_path": "/home/user/projects/my-app"
}
```

**Response:**
```json
{
    "id": "proj_001",
    "user_id": "user_123",
    "name": "my-app",
    "workspace_path": "/home/user/projects/my-app",
    "created_at": "2026-02-17T08:00:00Z"
}
```

---

### 2. Получить список проектов

**Endpoint:** `GET /my/projects/`

```python
@router.get("/my/projects/")
async def list_projects(
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_db)
) -> List[ProjectResponse]:
    """
    Получить список всех проектов пользователя
    """
    
    projects = await db.execute(
        select(UserProject).where(UserProject.user_id == user_id)
    )
    return [ProjectResponse.from_orm(p) for p in projects.scalars().all()]
```

**Response:**
```json
[
    {
        "id": "proj_001",
        "name": "my-app",
        "workspace_path": "/home/user/projects/my-app",
        "created_at": "2026-02-17T08:00:00Z"
    },
    {
        "id": "proj_002",
        "name": "data-analysis",
        "workspace_path": "/home/user/projects/data-analysis",
        "created_at": "2026-02-17T08:10:00Z"
    }
]
```

---

### 3. Получить информацию о конкретном проекте

**Endpoint:** `GET /my/projects/{project_id}/`

```python
@router.get("/my/projects/{project_id}/")
async def get_project(
    project_id: str,
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_db)
) -> ProjectResponse:
    """
    Получить информацию о конкретном проекте
    """
    
    project = await db.execute(
        select(UserProject).where(
            (UserProject.id == project_id) & 
            (UserProject.user_id == user_id)
        )
    )
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    return ProjectResponse.from_orm(project.scalar_one())
```

**Response:**
```json
{
    "id": "proj_001",
    "name": "my-app",
    "workspace_path": "/home/user/projects/my-app",
    "created_at": "2026-02-17T08:00:00Z"
}
```

---

### 4. Обновить информацию о проекте

**Endpoint:** `PUT /my/projects/{project_id}/`

```python
@router.put("/my/projects/{project_id}/")
async def update_project(
    project_id: str,
    project_data: ProjectUpdate,  # name, workspace_path
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_db)
) -> ProjectResponse:
    """
    Обновить информацию о проекте
    """
    
    project = await db.execute(
        select(UserProject).where(
            (UserProject.id == project_id) & 
            (UserProject.user_id == user_id)
        )
    )
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    project = project.scalar_one()
    
    # Обновить поля
    if project_data.name:
        project.name = project_data.name
    if project_data.workspace_path:
        project.workspace_path = project_data.workspace_path
    
    project.updated_at = datetime.utcnow()
    
    await db.commit()
    
    return ProjectResponse.from_orm(project)
```

---

### 5. Удалить проект

**Endpoint:** `DELETE /my/projects/{project_id}/`

```python
@router.delete("/my/projects/{project_id}/")
async def delete_project(
    project_id: str,
    user_id: str = Depends(get_user_id),
    db: AsyncSession = Depends(get_db),
    worker_space_manager = Depends(get_worker_space_manager)
) -> dict:
    """
    Удалить проект
    
    Примечание: удаляются только backend ресурсы (User Worker Space),
    файлы в User Workspace НЕ удаляются
    """
    
    project = await db.execute(
        select(UserProject).where(
            (UserProject.id == project_id) & 
            (UserProject.user_id == user_id)
        )
    )
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # 1. Cleanup backend ресурсов (User Worker Space)
    await worker_space_manager.cleanup(user_id, project_id)
    
    # 2. Удалить из БД
    # Cascade удалит все связанные agents, sessions, etc
    await db.delete(project.scalar_one())
    await db.commit()
    
    return {"status": "deleted"}
```

**Response:**
```json
{
    "status": "deleted"
}
```

---

## 📊 Полная структура endpoints

### Project Management endpoints (новые)
```
POST /my/projects/                      # Создать проект
GET /my/projects/                       # Список проектов
GET /my/projects/{project_id}/          # Информация о проекте
PUT /my/projects/{project_id}/          # Обновить проект
DELETE /my/projects/{project_id}/       # Удалить проект
GET /my/projects/{project_id}/stats/    # Статистика проекта (опционально)
```

### Chat API endpoints (обновленные)
```
POST /my/projects/{project_id}/chat/                      # Создать сессию
GET /my/projects/{project_id}/chat/                       # Список сессий
GET /my/projects/{project_id}/chat/{session_id}/          # Получить сессию
POST /my/projects/{project_id}/chat/{session_id}/message/ # Отправить сообщение
GET /my/projects/{project_id}/chat/{session_id}/messages/ # История
DELETE /my/projects/{project_id}/chat/{session_id}/       # Удалить сессию
```

### Agents API endpoints (обновленные)
```
GET /my/projects/{project_id}/agents/                     # Список агентов
POST /my/projects/{project_id}/agents/                    # Создать агента
GET /my/projects/{project_id}/agents/{agent_id}/          # Информация о агенте
PUT /my/projects/{project_id}/agents/{agent_id}/          # Обновить агента
DELETE /my/projects/{project_id}/agents/{agent_id}/       # Удалить агента
```

### SSE/Events endpoints (обновленные)
```
GET /my/projects/{project_id}/events/                     # Stream events SSE
```

### Approval endpoints (обновленные)
```
GET /my/projects/{project_id}/approvals/                  # Список approvals
POST /my/projects/{project_id}/approvals/{id}/confirm/    # Подтвердить
```

---

## 🏗️ Architektura Dependency Injection

### Текущая изоляция (per-user)
```python
def get_user_id(token: str = Depends(oauth2_scheme)) -> str:
    # Извлечь user_id из JWT
    return decoded_token.sub
```

### Новая изоляция (per-project)
```python
def get_project_id(project_id: str = Path(...)) -> str:
    # project_id из URL параметра
    return project_id

def get_user_worker_space(
    user_id: str = Depends(get_user_id),
    project_id: str = Depends(get_project_id),
    worker_space_manager = Depends(get_worker_space_manager)
) -> UserWorkerSpace:
    # Автоматически получить isolированный Worker Space
    return await worker_space_manager.get_or_create(user_id, project_id)
```

---

## 📊 Pydantic Schemas

### ProjectCreate
```python
class ProjectCreate(BaseModel):
    name: str  # обязательно
    workspace_path: Optional[str] = None  # опционально
```

### ProjectUpdate
```python
class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    workspace_path: Optional[str] = None
```

### ProjectResponse
```python
class ProjectResponse(BaseModel):
    id: str
    user_id: str
    name: str
    workspace_path: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True
```

### ProjectWithStats (опционально)
```python
class ProjectWithStats(ProjectResponse):
    agents_count: int  # количество агентов
    sessions_count: int  # количество сессий
    active_workers: int  # активные Worker Spaces
```

---

## 🎯 Когда нужны Project endpoints?

### ОБЯЗАТЕЛЬНО нужны:
- ✅ `POST /my/projects/` - регистрация нового проекта
- ✅ `GET /my/projects/` - получить список проектов
- ✅ `DELETE /my/projects/{project_id}/` - удалить проект

### РЕКОМЕНДУЕТСЯ:
- ⚠️ `GET /my/projects/{project_id}/` - информация о проекте
- ⚠️ `PUT /my/projects/{project_id}/` - обновить информацию
- ⚠️ `GET /my/projects/{project_id}/stats/` - статистика

---

## ⚠️ Важные моменты

### 1. Workspace создается пользователем
```
User создает папку ~/projects/my-app/
├── src/
├── data/
└── config.json
```

### 2. Backend узнает о проекте через API
```python
POST /my/projects/
{
    "name": "my-app",
    "workspace_path": "~/projects/my-app"
}
```

### 3. Backend инициализирует User Worker Space
```python
# Автоматически при первом запросе
POST /my/projects/{project_id}/chat/{session_id}/message/
│
└─→ Dependency Injection получает Worker Space для (user_id, project_id)
    └─→ WorkerSpaceManager создает + инициализирует
        └─→ agent_cache, Agent Bus, Qdrant collections для этого проекта
```

### 4. Удаление проекта НЕ удаляет User Workspace
```python
DELETE /my/projects/{project_id}/
│
├─→ Cleanup backend ресурсов (User Worker Space)
│   ├─ Завершить активные задачи
│   ├─ Дерегистрировать агентов
│   ├─ Очистить cache
│   └─ Удалить от Agent Bus
│
└─→ Удалить из БД (user_projects таблица)

✗ НЕ удаляет файлы из ~/projects/my-app/
```

---

## 📝 Итоговая рекомендация

**ДА, нужны Project Management endpoints**, потому что:

1. ✅ Per-project архитектура требует управления проектами
2. ✅ Backend должен знать о каждом проекте для управления Worker Space
3. ✅ Пользователь должен иметь API для регистрации/управления проектами
4. ✅ Endpoints обеспечивают правильную изоляцию данных

**Минимальный набор:**
- `POST /my/projects/` - создать
- `GET /my/projects/` - список
- `DELETE /my/projects/{project_id}/` - удалить

**Полный набор:**
- Вышеперечисленные плюс
- `GET /my/projects/{project_id}/`
- `PUT /my/projects/{project_id}/`
- Опционально: stats, cleanup, reset endpoints
