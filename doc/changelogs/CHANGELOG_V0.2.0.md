# Лог изменений v0.2.0

**Дата релиза:** 2026-02-17  
**Тип:** Major Release  
**Статус:** ✅ Stable

---

## 🎯 Обзор v0.2.0

v0.2.0 завершает миграцию на **per-project архитектуру**. Все endpoints теперь требуют явного указания `project_id`, что обеспечивает:

✅ Полную изоляцию проектов  
✅ Масштабируемую архитектуру  
✅ Четкую иерархию данных  
✅ Упрощенный код клиентов  

---

## ❌ Breaking Changes

### Удаленные API endpoints

#### Agent Management (5 endpoints удалены)
- ❌ `POST /my/agents/` - **УДАЛЕН** → `POST /my/projects/{project_id}/agents/`
- ❌ `GET /my/agents/` - **УДАЛЕН** → `GET /my/projects/{project_id}/agents/`
- ❌ `GET /my/agents/{agent_id}` - **УДАЛЕН** → `GET /my/projects/{project_id}/agents/{agent_id}`
- ❌ `PUT /my/agents/{agent_id}` - **УДАЛЕН** → `PUT /my/projects/{project_id}/agents/{agent_id}`
- ❌ `DELETE /my/agents/{agent_id}` - **УДАЛЕН** → `DELETE /my/projects/{project_id}/agents/{agent_id}`

#### Chat Management (6 endpoints удалены)
- ❌ `POST /my/chat/sessions/` - **УДАЛЕН** → `POST /my/projects/{project_id}/chat/sessions/`
- ❌ `GET /my/chat/sessions/` - **УДАЛЕН** → `GET /my/projects/{project_id}/chat/sessions/`
- ❌ `GET /my/chat/sessions/{session_id}/messages/` - **УДАЛЕН** → `GET /my/projects/{project_id}/chat/sessions/{session_id}/messages/`
- ❌ `POST /my/chat/{session_id}/message/` - **УДАЛЕН** → `POST /my/projects/{project_id}/chat/{session_id}/message/`
- ❌ `DELETE /my/chat/sessions/{session_id}` - **УДАЛЕН** → `DELETE /my/projects/{project_id}/chat/sessions/{session_id}`
- ❌ `GET /my/chat/{session_id}/events/` - **УДАЛЕН** → `GET /my/projects/{project_id}/chat/{session_id}/events/`

#### Streaming (1 router удален)
- ❌ `router` (deprecated с `/my/chat/{session_id}/events/`) - **УДАЛЕН**
- ✅ `project_router` (с `/my/projects/{project_id}/chat/{session_id}/events/`) - **ОСТАЕТСЯ**

### Удаленные файлы

| Файл | Причина |
|------|---------|
| `app/routes/agents.py` | Содержал только deprecated endpoints |
| `app/routes/chat.py` | Содержал только deprecated endpoints |
| `tests/test_agents_api.py` | Тесты для удаленных endpoints |
| `tests/test_chat_api.py` | Тесты для удаленных endpoints |

### Обновленные файлы

| Файл | Изменение |
|------|-----------|
| `app/routes/streaming.py` | Удален deprecated `router`, оставлен только `project_router` |
| `app/main.py` | Удалены импорты и подключение старых роутеров |
| `pyproject.toml` | Версия обновлена с 0.1.0 на 0.2.0 |

---

## ✅ Что осталось без изменений

### Per-Project endpoints (все работают как прежде)

#### Per-Project Agent Management
- ✅ `POST /my/projects/{project_id}/agents/` - создание агента
- ✅ `GET /my/projects/{project_id}/agents/` - список агентов
- ✅ `GET /my/projects/{project_id}/agents/{agent_id}` - получить агента
- ✅ `PUT /my/projects/{project_id}/agents/{agent_id}` - обновить агента
- ✅ `DELETE /my/projects/{project_id}/agents/{agent_id}` - удалить агента

#### Per-Project Chat Management
- ✅ `POST /my/projects/{project_id}/chat/sessions/` - создать сессию
- ✅ `GET /my/projects/{project_id}/chat/sessions/` - список сессий
- ✅ `GET /my/projects/{project_id}/chat/sessions/{session_id}/messages/` - история
- ✅ `POST /my/projects/{project_id}/chat/{session_id}/message/` - отправить сообщение
- ✅ `DELETE /my/projects/{project_id}/chat/sessions/{session_id}` - удалить сессию
- ✅ `GET /my/projects/{project_id}/chat/{session_id}/events/` - потоковые события

#### Project Management
- ✅ `GET /my/projects/` - список проектов
- ✅ `POST /my/projects/` - создание проекта
- ✅ `GET /my/projects/{project_id}` - получить проект
- ✅ `PUT /my/projects/{project_id}` - обновить проект
- ✅ `DELETE /my/projects/{project_id}` - удалить проект

#### Health Check
- ✅ `GET /` - root endpoint
- ✅ `GET /health` - health check

---

## 📚 Документация и гайды

### Новые документы
- 📄 **`doc/MIGRATION_V0.2.0.md`** - Подробный гайд по миграции с примерами
- 📄 **`plans/v0.2.0-release-plan.md`** - План реализации и проверочный список

### Обновленные документы
- 📄 **`CHANGELOG_V0.2.0.md`** - Этот файл (логирование изменений)

---

## 🔄 Путь миграции для пользователей

**Шаг 1:** Получить Project ID
```bash
GET /my/projects/
```

**Шаг 2:** Обновить все вызовы клиента

Заменить все пути:
- `/my/agents/` → `/my/projects/{project_id}/agents/`
- `/my/chat/` → `/my/projects/{project_id}/chat/`

**Шаг 3:** Тестирование

Проверить, что все endpoints работают с новыми путями.

**📖 Детальный гайд:** `doc/MIGRATION_V0.2.0.md`

---

## 🧪 Тестирование

### Тесты, которые остались
- ✅ `tests/test_project_agents.py` - Per-project agent endpoints
- ✅ `tests/test_project_chat.py` - Per-project chat endpoints
- ✅ `tests/test_create_project_with_starter_pack.py` - Project creation
- ✅ `tests/test_user_worker_space.py` - Worker space functionality
- ✅ `tests/test_sse.py` - SSE/streaming functionality

### Тесты, которые удалены
- ❌ `tests/test_agents_api.py` - Deprecated agent endpoints
- ❌ `tests/test_chat_api.py` - Deprecated chat endpoints

### Инструкции по запуску тестов

```bash
# Все тесты
pytest tests/ -v

# Per-project endpoints
pytest tests/test_project_agents.py -v
pytest tests/test_project_chat.py -v

# С покрытием
pytest tests/ -v --cov=app --cov-report=html
```

---

## 📊 Статистика изменений

| Метрика | Значение |
|---------|----------|
| **Удаленные endpoints** | 11 |
| **Сохраненные endpoints** | 15+ |
| **Удаленные файлы** | 4 |
| **Обновленные файлы** | 3 |
| **Новые документы** | 2 |
| **Версия** | 0.1.0 → 0.2.0 |
| **Breaking Changes** | ✅ Есть |
| **Backward Compatibility** | ❌ Нет |

---

## 🏗️ Архитектурные улучшения

### Per-Project изоляция
```
User (JWT)
  ├── Project A
  │   ├── Agents (изолированы)
  │   ├── Chat Sessions (изолированы)
  │   └── Streaming Events (изолированы)
  ├── Project B
  │   ├── Agents (изолированы)
  │   ├── Chat Sessions (изолированы)
  │   └── Streaming Events (изолированы)
  └── Project C
      └── ...
```

### Преимущества
- 🔒 Каждый проект полностью изолирован
- 📈 Масштабируемость улучшена
- 🎯 Четкая иерархия данных
- 🧹 Упрощенный код клиентов

---

## ⚡ Производительность

Нет изменений в производительности - все endpoints работают идентично v0.1.0, только с обязательным `project_id`.

---

## 🔒 Безопасность

- ✅ JWT валидация (без изменений)
- ✅ User isolation middleware (без изменений)
- ✅ Project validation middleware (без изменений)
- ✅ Добавлена project ownership проверка

---

## 🛠️ Инструменты разработчика

### OpenAPI/Swagger
```bash
# Посмотрите обновленные endpoints
curl http://localhost:8000/openapi.json | jq .
```

### Структура проекта
```
app/routes/
├── health.py              ✅ Не изменен
├── projects.py            ✅ Не изменен
├── project_agents.py      ✅ Не изменен (per-project)
├── project_chat.py        ✅ Не изменен (per-project)
├── streaming.py           🔄 Обновлен (удален deprecated router)
├── agents.py              ❌ УДАЛЕН
└── chat.py                ❌ УДАЛЕН
```

---

## 📝 Известные проблемы и ограничения

### Нет проблем
✅ Все per-project endpoints стабильны  
✅ Все тесты проходят  
✅ OpenAPI schema корректна  

---

## 🙏 Спасибо

Спасибо всем пользователям за использование v0.1.0! Надеемся, что v0.2.0 с новой per-project архитектурой будет еще лучше.

---

## 📞 Поддержка

Если у вас есть вопросы по миграции:

1. **Прочитайте:** `doc/MIGRATION_V0.2.0.md`
2. **Проверьте:** OpenAPI docs на `/docs`
3. **Откройте issue:** Сообщайте об ошибках

---

**Release Manager:** OpenIdeaLab  
**Release Date:** 2026-02-17  
**Status:** ✅ Ready for Production
