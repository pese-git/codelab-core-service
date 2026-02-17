# Гайд по миграции: v0.1.0 → v0.2.0

**Дата релиза:** 2026-02-17  
**Тип:** Major Release с breaking changes  
**Статус:** ✅ Stable

---

## ⚠️ Важно: Breaking Changes

v0.2.0 удаляет все deprecated endpoints из v0.1.0. Это **major версия** с breaking changes. **Все клиенты должны обновить свой код перед обновлением на v0.2.0.**

---

## 🗑️ Удаленные endpoints

### Endpoints управления агентами (удалены)

| HTTP метод | Старый path (v0.1.0) | Новый path (v0.2.0) |
|-----------|-------------------|-------------------|
| POST | `/my/agents/` | `/my/projects/{project_id}/agents/` |
| GET | `/my/agents/` | `/my/projects/{project_id}/agents/` |
| GET | `/my/agents/{agent_id}` | `/my/projects/{project_id}/agents/{agent_id}` |
| PUT | `/my/agents/{agent_id}` | `/my/projects/{project_id}/agents/{agent_id}` |
| DELETE | `/my/agents/{agent_id}` | `/my/projects/{project_id}/agents/{agent_id}` |

### Endpoints управления чатом (удалены)

| HTTP метод | Старый path (v0.1.0) | Новый path (v0.2.0) |
|-----------|-------------------|-------------------|
| POST | `/my/chat/sessions/` | `/my/projects/{project_id}/chat/sessions/` |
| GET | `/my/chat/sessions/` | `/my/projects/{project_id}/chat/sessions/` |
| GET | `/my/chat/sessions/{session_id}/messages/` | `/my/projects/{project_id}/chat/sessions/{session_id}/messages/` |
| POST | `/my/chat/{session_id}/message/` | `/my/projects/{project_id}/chat/{session_id}/message/` |
| DELETE | `/my/chat/sessions/{session_id}` | `/my/projects/{project_id}/chat/sessions/{session_id}` |
| GET | `/my/chat/{session_id}/events/` | `/my/projects/{project_id}/chat/{session_id}/events/` |

---

## 🔄 Путь миграции

### Шаг 1: Получите ID вашего проекта

Перед вызовом любого per-project endpoint, нужно получить ID проекта:

```bash
curl -X GET "http://localhost:8000/my/projects/" \
  -H "Authorization: Bearer ВАШ_JWT_ТОКЕН"
```

**Ответ:**
```json
{
  "projects": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "Мой проект",
      "created_at": "2026-02-17T00:00:00Z"
    }
  ],
  "total": 1
}
```

Сохраните `project_id` для всех последующих API вызовов.

### Шаг 2: Мигрируйте управление агентами

#### До (v0.1.0):
```bash
# Создание агента (старый способ)
curl -X POST "http://localhost:8000/my/agents/" \
  -H "Authorization: Bearer ВАШ_JWT_ТОКЕН" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Research Agent",
    "description": "Агент для исследований",
    "model": "gpt-4",
    "temperature": 0.7
  }'
```

#### После (v0.2.0):
```bash
# Создание агента (новый способ)
curl -X POST "http://localhost:8000/my/projects/550e8400-e29b-41d4-a716-446655440000/agents/" \
  -H "Authorization: Bearer ВАШ_JWT_ТОКЕН" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Research Agent",
    "description": "Агент для исследований",
    "model": "gpt-4",
    "temperature": 0.7
  }'
```

#### Еще примеры агентов:

**Список агентов:**
```bash
# До (v0.1.0)
GET /my/agents/

# После (v0.2.0)
GET /my/projects/{project_id}/agents/
```

**Получить конкретного агента:**
```bash
# До (v0.1.0)
GET /my/agents/{agent_id}

# После (v0.2.0)
GET /my/projects/{project_id}/agents/{agent_id}
```

**Обновить агента:**
```bash
# До (v0.1.0)
PUT /my/agents/{agent_id}

# После (v0.2.0)
PUT /my/projects/{project_id}/agents/{agent_id}
```

**Удалить агента:**
```bash
# До (v0.1.0)
DELETE /my/agents/{agent_id}

# После (v0.2.0)
DELETE /my/projects/{project_id}/agents/{agent_id}
```

### Шаг 3: Мигрируйте управление чатом

#### До (v0.1.0):
```bash
# Создание сессии чата (старый способ)
curl -X POST "http://localhost:8000/my/chat/sessions/" \
  -H "Authorization: Bearer ВАШ_JWT_ТОКЕН"
```

#### После (v0.2.0):
```bash
# Создание сессии чата (новый способ)
curl -X POST "http://localhost:8000/my/projects/550e8400-e29b-41d4-a716-446655440000/chat/sessions/" \
  -H "Authorization: Bearer ВАШ_JWT_ТОКЕН"
```

#### Еще примеры чата:

**Список сессий чата:**
```bash
# До (v0.1.0)
GET /my/chat/sessions/

# После (v0.2.0)
GET /my/projects/{project_id}/chat/sessions/
```

**Получить сообщения чата:**
```bash
# До (v0.1.0)
GET /my/chat/sessions/{session_id}/messages/

# После (v0.2.0)
GET /my/projects/{project_id}/chat/sessions/{session_id}/messages/
```

**Отправить сообщение:**
```bash
# До (v0.1.0)
POST /my/chat/{session_id}/message/

# После (v0.2.0)
POST /my/projects/{project_id}/chat/{session_id}/message/
```

**Удалить сессию:**
```bash
# До (v0.1.0)
DELETE /my/chat/sessions/{session_id}

# После (v0.2.0)
DELETE /my/projects/{project_id}/chat/sessions/{session_id}
```

**Подписаться на события (streaming):**
```bash
# До (v0.1.0)
GET /my/chat/{session_id}/events/

# После (v0.2.0)
GET /my/projects/{project_id}/chat/{session_id}/events/
```

---

## 💻 Миграция SDK/клиента

### Пример Python клиента

**До (v0.1.0):**
```python
from openidelab_sdk import PersonalAIClient

client = PersonalAIClient(token="ваш_jwt_токен")

# Создать агента
agent = client.create_agent(name="Research Agent", model="gpt-4")

# Создать сессию чата
session = client.create_session()

# Отправить сообщение
response = client.send_message(session.id, "Привет")
```

**После (v0.2.0):**
```python
from openidelab_sdk import PersonalAIClient

client = PersonalAIClient(token="ваш_jwt_токен")

# Получить проект (или создать)
projects = client.list_projects()
project_id = projects[0].id

# Создать агента в проекте
agent = client.create_agent(
    project_id=project_id,
    name="Research Agent",
    model="gpt-4"
)

# Создать сессию чата в проекте
session = client.create_session(project_id=project_id)

# Отправить сообщение в проекте
response = client.send_message(
    project_id=project_id,
    session_id=session.id,
    message="Привет"
)
```

### Пример JavaScript/TypeScript клиента

**До (v0.1.0):**
```typescript
const client = new PersonalAIClient({ token: "ваш_jwt_токен" });

// Создать агента
const agent = await client.createAgent({
  name: "Research Agent",
  model: "gpt-4"
});

// Создать сессию чата
const session = await client.createSession();

// Отправить сообщение
const response = await client.sendMessage(session.id, "Привет");
```

**После (v0.2.0):**
```typescript
const client = new PersonalAIClient({ token: "ваш_jwt_токен" });

// Получить проект (или создать)
const projects = await client.listProjects();
const projectId = projects[0].id;

// Создать агента в проекте
const agent = await client.createAgent(projectId, {
  name: "Research Agent",
  model: "gpt-4"
});

// Создать сессию чата в проекте
const session = await client.createSession(projectId);

// Отправить сообщение в проекте
const response = await client.sendMessage(projectId, session.id, "Привет");
```

---

## ❓ Часто задаваемые вопросы

### В: Что такое Project и почему он теперь обязателен?

**О:** Project - это контейнер для агентов и сессий чата. Он предоставляет:
- **Изоляцию**: Отдельные рабочие пространства для разных целей
- **Организацию**: Группировка связанных агентов и разговоров
- **Контроль доступа**: Управление правами доступа за проект
- **Мультитенантность**: Поддержка нескольких изолированных окружений для одного пользователя

### В: Можно ли мигрировать данные из v0.1.0 в v0.2.0?

**О:** Схема БД поддерживает как старые, так и новые данные. Однако:
- Старые агенты/сессии без `project_id` не будут доступны через endpoints v0.2.0
- Рекомендуем создавать новые агенты/сессии в v0.2.0 в рамках проектов
- Старые агенты/сессии могут быть вручную назначены проекту при необходимости

### В: Будут ли работать старые endpoints в v0.2.0?

**О:** Нет, все старые endpoints полностью удалены в v0.2.0. Вы **должны** обновить код клиента.

### В: Как откатиться с v0.2.0 на v0.1.0?

**О:** Мы не рекомендуем откатываться. v0.2.0 - текущая стабильная версия:
- Используйте v0.2.0 с обновленным кодом клиента
- Откройте issue, если у вас возникли проблемы с миграцией

### В: Что если у меня несколько проектов?

**О:** Каждый проект изолирован:
```bash
# Получить все проекты
GET /my/projects/

# Получить агентов в проекте A
GET /my/projects/{project_a_id}/agents/

# Получить агентов в проекте B
GET /my/projects/{project_b_id}/agents/
```

Они не делят данные - каждый проект имеет своих агентов и сессии.

### В: Есть ли слой совместимости?

**О:** Нет, v0.2.0 - это major release с breaking changes. Нет слоя обратной совместимости. Все клиенты должны быть обновлены.

---

## 📚 Дополнительные ресурсы

- **API документация:** `doc/architecture/api-specification.md`
- **Release notes:** Смотрите CHANGELOG.md
- **Управление проектами:** endpoints `/my/projects/`

---

## 🆘 Нужна помощь?

Если у вас возникли проблемы при миграции:

1. **Проверьте OpenAPI docs:** `http://localhost:8000/docs`
2. **Просмотрите этот гайд:** Найдите ваш конкретный сценарий выше
3. **Проверьте error responses:** v0.2.0 предоставляет подробные сообщения об ошибках
4. **Откройте issue:** Сообщайте об ошибках или неясных шагах миграции

---

**Последнее обновление:** 2026-02-17  
**Статус миграции:** Ready for Production
