# Требования к обновлению OpenSpec спецификаций

**Дата:** 17 февраля 2026  
**Версия:** 1.0  
**Контекст:** Какие спецификации OpenSpec нужно обновить с учетом новых требований

---

## 🎯 Короткий ответ

**ДА, нужно обновить OpenSpec спецификации**, потому что выявлены критические требования:
1. ✅ Per-project архитектура (вместо per-user)
2. ✅ Default Starter Pack при создании проекта
3. ✅ Project Management endpoints
4. ✅ Database schema с project_id

---

## 📋 Что нужно обновить в OpenSpec

### 1. **Основная спецификация:** `openspec/changes/implement-core-service/`

#### 1.1 User Worker Space спецификация
**Файл:** `openspec/changes/implement-core-service/specs/user-worker-space/spec.md`

**Что обновить:**
- ✅ Уточнить, что User Worker Space создается **per-project**, а не per-user
- ✅ Добавить requirement для Default Starter Pack
- ✅ Описать инициализацию User Worker Space при создании проекта

**Новые requirements:**
```markdown
### Requirement: Per-Project Architecture
User Worker Space ДОЛЖЕН быть создан для каждого проекта пользователя (не per-user).

#### Scenario: Каждый проект имеет отдельный Worker Space
- **WHEN** пользователь создает несколько проектов
- **THEN** каждый проект имеет свой изолированный User Worker Space

### Requirement: Default Starter Pack
User Worker Space инициализируется с 4 default агентами при создании проекта.

#### Scenario: Default агенты создаются при создании проекта
- **WHEN** пользователь создает новый проект
- **THEN** автоматически создаются 4 default агента:
  - agent_coder (software developer)
  - agent_analyzer (data analyst)
  - agent_writer (technical writer)
  - agent_researcher (research specialist)
```

---

#### 1.2 REST API Endpoints спецификация
**Файл:** `openspec/changes/implement-core-service/specs/rest-api-endpoints/spec.md`

**Что обновить:**
- ✅ Добавить Project Management endpoints
- ✅ Обновить все URL pattern'ы (добавить `/my/projects/{project_id}/`)
- ✅ Описать инициализацию проекта с Starter Pack

**Новые endpoints:**
```markdown
### Project Management Endpoints

#### POST /my/projects/
Создать новый проект с Default Starter Pack

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
    "name": "my-app",
    "workspace_path": "/home/user/projects/my-app",
    "agents": [
        {"id": "agent_001", "name": "agent_coder"},
        {"id": "agent_002", "name": "agent_analyzer"},
        {"id": "agent_003", "name": "agent_writer"},
        {"id": "agent_004", "name": "agent_researcher"}
    ],
    "created_at": "2026-02-17T08:00:00Z"
}
```

#### GET /my/projects/
Получить список всех проектов пользователя

#### GET /my/projects/{project_id}/
Получить информацию о конкретном проекте

#### PUT /my/projects/{project_id}/
Обновить информацию о проекте

#### DELETE /my/projects/{project_id}/
Удалить проект

### Chat API (Updated)
Все endpoints добавляют project_id:
- POST /my/projects/{project_id}/chat/
- GET /my/projects/{project_id}/chat/
- POST /my/projects/{project_id}/chat/{session_id}/message/
- ...

### Agents API (Updated)
Все endpoints добавляют project_id:
- GET /my/projects/{project_id}/agents/
- POST /my/projects/{project_id}/agents/
- PUT /my/projects/{project_id}/agents/{agent_id}/
- DELETE /my/projects/{project_id}/agents/{agent_id}/
- ...
```

---

#### 1.3 Database Models спецификация
**Файл:** `openspec/changes/implement-core-service/specs/rest-api-endpoints/spec.md` (или новая)

**Что добавить:**
```markdown
### Database Models (Updated)

#### UserProject (New Model)
```sql
user_projects
  - id: UUID (PK)
  - user_id: UUID (FK)
  - name: String
  - workspace_path: String (nullable)
  - created_at: DateTime
  - updated_at: DateTime
```

#### UserAgent (Updated)
```sql
user_agents
  - id: UUID (PK)
  - user_id: UUID (FK)
  - project_id: UUID (FK) ← NEW
  - name: String
  - config: JSON
  - status: String
  - created_at: DateTime
```

#### ChatSession (Updated)
```sql
chat_sessions
  - id: UUID (PK)
  - user_id: UUID (FK)
  - project_id: UUID (FK) ← NEW
  - created_at: DateTime
```

#### UserOrchestrator (Updated)
```sql
user_orchestrators
  - id: UUID (PK)
  - user_id: UUID (FK)
  - project_id: UUID (FK) ← NEW
  - config: JSON
  - created_at: DateTime
```
```

---

### 2. **Дополнительная спецификация:** `openspec/changes/clarify-workspace-access/`

#### 2.1 Delta Spec для User Worker Space (per-project)
**Файл:** `openspec/changes/clarify-workspace-access/specs/user-worker-space/spec.md`

**Что обновить:**
- ✅ Уточнить, что per-project (уже есть в текущем spec.md)
- ✅ Добавить требование для Default Starter Pack

**Новое requirement:**
```markdown
### Requirement: Default Starter Pack Initialization
User Worker Space инициализируется с 4 default агентами при создании проекта.

#### Scenario: Automatic agent creation on project creation
- **WHEN** пользователь создает новый проект через POST /my/projects/
- **THEN** backend автоматически создает 4 default агентов:
  - agent_coder (developer, model=gpt-4, temp=0.3)
  - agent_analyzer (analyst, model=gpt-4, temp=0.5)
  - agent_writer (writer, model=gpt-4, temp=0.7)
  - agent_researcher (researcher, model=gpt-4, temp=0.6)
```

---

### 3. **Новая спецификация (опционально):** Project Management

**Можно создать:** `openspec/changes/implement-core-service/specs/project-management/spec.md`

**Содержание:**
- Project CRUD endpoints
- Project initialization flow
- Default Starter Pack configuration
- Relationship with User Worker Space

---

## 📊 Матрица обновлений OpenSpec

| Спецификация | Файл | Обновление | Тип | Приоритет |
|---|---|---|---|---|
| User Worker Space | `implement-core-service/specs/user-worker-space/spec.md` | ✅ Уточнить per-project + Default Starter Pack | MODIFIED | HIGH |
| REST API Endpoints | `implement-core-service/specs/rest-api-endpoints/spec.md` | ✅ Добавить Project Management endpoints | MODIFIED | HIGH |
| Database Models | `implement-core-service/...` | ✅ Добавить UserProject, project_id в модели | MODIFIED | HIGH |
| Workspace Access | `clarify-workspace-access/specs/user-worker-space/spec.md` | ✅ Добавить Default Starter Pack requirement | MODIFIED | MEDIUM |
| Project Management | (new) | ✅ Создать новую спецификацию | NEW | MEDIUM |

---

## 🔄 Стратегия обновления OpenSpec

### Подход 1: Быстрое обновление (РЕКОМЕНДУЕТСЯ)

**Временная шкала:** 1-2 дня (параллельно с планированием реализации)

**Шаги:**
1. **День 1:** Обновить User Worker Space spec (per-project + Starter Pack)
2. **День 1:** Обновить REST API Endpoints spec (добавить Project endpoints)
3. **День 2:** Обновить Database Models spec (добавить project_id)
4. **День 2:** Обновить clarify-workspace-access spec

**Преимущества:**
- ✅ Быстро
- ✅ Спецификация актуальна перед реализацией
- ✅ Минимум дополнительной работы

---

### Подход 2: Детальное обновление (ПОЛНОЕ)

**Временная шкала:** 3-4 дня

**Дополнительная работа:**
- Создать новую спецификацию Project Management
- Создать migration guide (как переехать с per-user на per-project)
- Обновить все связанные документы
- Провести review с командой

---

## 📝 Что обновлять в каждой спецификации

### User Worker Space (CRITICAL)

**Текущий статус:**
- ✅ Per-project требование есть в clarify-workspace-access
- ❌ Per-project требование НЕ явно в implement-core-service spec
- ❌ Default Starter Pack requirement отсутствует везде

**Что добавить:**
```markdown
### ADDED Requirement: Per-Project Architecture

User Worker Space ДОЛЖЕН быть создан для КАЖДОГО проекта пользователя.

#### Scenario: Per-Project Isolation
- **WHEN** пользователь имеет несколько проектов
- **THEN** каждый проект имеет свой изолированный Worker Space
- **AND** данные одного проекта недоступны другому

### ADDED Requirement: Default Starter Pack

User Worker Space инициализируется с 4 default агентами при создании проекта.

#### Scenario: Automatic Default Agents
- **WHEN** пользователь создает проект
- **THEN** автоматически создаются:
  - agent_coder (developer)
  - agent_analyzer (analyst)
  - agent_writer (writer)
  - agent_researcher (researcher)
- **AND** все агенты регистрируются в Agent Bus
- **AND** User Worker Space полностью инициализирован
- **AND** система готова к использованию (zero-to-use)
```

---

### REST API Endpoints (CRITICAL)

**Текущий статус:**
- ❌ Project Management endpoints отсутствуют
- ❌ URL pattern'ы еще не включают project_id

**Что добавить:**
```markdown
### ADDED Section: Project Management Endpoints

#### POST /my/projects/
Create new project with Default Starter Pack

#### GET /my/projects/
List all user's projects

#### GET /my/projects/{project_id}/
Get project details with agents

#### PUT /my/projects/{project_id}/
Update project info

#### DELETE /my/projects/{project_id}/
Delete project and cleanup backend resources

### MODIFIED Section: Chat API

Все endpoints должны использовать:
POST /my/projects/{project_id}/chat/{session_id}/message/
(вместо: POST /my/chat/{session_id}/message/)

### MODIFIED Section: Agents API

Все endpoints должны использовать:
GET /my/projects/{project_id}/agents/
(вместо: GET /my/agents/)
```

---

### Database Models (CRITICAL)

**Текущий статус:**
- ❌ UserProject модель отсутствует
- ❌ project_id не в других моделях

**Что добавить:**
```markdown
### ADDED: UserProject Model

```sql
class UserProject:
    id: UUID (PK)
    user_id: UUID (FK users.id)
    name: String(255)
    workspace_path: String(500) nullable
    created_at: DateTime
    updated_at: DateTime
    
    # Relationships
    agents: List[UserAgent]
    chat_sessions: List[ChatSession]
    orchestrators: List[UserOrchestrator]
```

### MODIFIED: All Related Models

Add `project_id: UUID (FK user_projects.id)` to:
- UserAgent
- ChatSession
- UserOrchestrator
- (Optional) Message
```

---

## ✅ Чеклист обновления OpenSpec

### Обновить существующие спецификации
- [ ] User Worker Space spec
  - [ ] Добавить per-project requirement
  - [ ] Добавить Default Starter Pack requirement
  
- [ ] REST API Endpoints spec
  - [ ] Добавить Project Management endpoints
  - [ ] Обновить URL patterns (/my/projects/{project_id}/...)
  - [ ] Обновить Database Models section
  
- [ ] Workspace Access spec (clarify-workspace-access)
  - [ ] Добавить Default Starter Pack requirement
  - [ ] Уточнить per-project (уже есть)

### Создать новые спецификации (опционально)
- [ ] Project Management spec
  - [ ] CRUD операции
  - [ ] Default Starter Pack configuration
  - [ ] Project initialization flow

### Review и merge
- [ ] Code review обновленных спецификаций
- [ ] Approval от team lead
- [ ] Merge в main OpenSpec

---

## 🎯 Рекомендация

**Используйте Подход 1: Быстрое обновление (РЕКОМЕНДУЕТСЯ)**

**Шаги:**
1. Обновить User Worker Space spec (per-project + Starter Pack)
2. Обновить REST API Endpoints spec (Project endpoints + URL patterns)
3. Обновить Database Models section (UserProject + project_id)
4. Обновить clarify-workspace-access spec (Starter Pack)
5. Merge все обновления

**Временная шкала:** 1-2 дня (параллельно с планированием реализации)

**Преимущества:**
- ✅ Спецификация актуальна перед разработкой
- ✅ Минимум дополнительной работы
- ✅ Команда будет знать точные требования
- ✅ Код будет соответствовать спецификации

---

## 📌 Критичные изменения в спецификации

### ⭐ MUST HAVE

1. **Per-Project Architecture**
   - User Worker Space per-project (не per-user)
   - Полная изоляция данных между проектами

2. **Default Starter Pack**
   - 4 default агента при создании проекта
   - Автоматическая инициализация Worker Space
   - Zero-to-use парадигма

3. **Project Management Endpoints**
   - POST /my/projects/ (create with Starter Pack)
   - GET /my/projects/ (list)
   - DELETE /my/projects/{project_id}/ (cleanup)

4. **Database Schema**
   - UserProject model (new)
   - project_id in related models (updated)

### 🟡 SHOULD HAVE

1. Detailed configuration of Default Starter Pack agents
2. Migration guide (per-user → per-project)
3. New Project Management specification

---

## 💾 Как обновить OpenSpec

### Вариант 1: Обновить существующие спецификации

```
openspec/changes/implement-core-service/
├── specs/user-worker-space/spec.md (EDIT)
│   └── Add: Per-Project + Default Starter Pack
│
├── specs/rest-api-endpoints/spec.md (EDIT)
│   ├── Add: Project Management endpoints
│   ├── Update: URL patterns with project_id
│   └── Update: Database Models section
│
└── specs/chat-system-modes/spec.md (UPDATE if needed)
    └── Update references to project context
```

### Вариант 2: Создать новую delta spec

```
openspec/changes/project-management-and-starter-pack/
├── .openspec.yaml
├── proposal.md
├── design.md
├── tasks.md
└── specs/
    ├── project-management/spec.md (NEW)
    ├── default-starter-pack/spec.md (NEW)
    └── database-models-update/spec.md (NEW)
```

---

## 🚀 Итоговая рекомендация

**ДА, обновите OpenSpec спецификации.**

**Что обновить (CRITICAL):**
1. ✅ User Worker Space spec (per-project + Starter Pack)
2. ✅ REST API Endpoints spec (Project endpoints + patterns)
3. ✅ Database Models (UserProject + project_id)
4. ✅ Workspace Access spec (Starter Pack requirement)

**Временная шкала:** 1-2 дня

**Преимущества:**
- Спецификация актуальна перед разработкой
- Команда знает точные требования
- Избегаем переделок в процессе разработки
- Соответствие между спецификацией и кодом
