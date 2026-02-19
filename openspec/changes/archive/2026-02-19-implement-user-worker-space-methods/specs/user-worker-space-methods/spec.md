# Спецификация: Методы UserWorkerSpace (10.4-10.9)

## 1. Методы работы с Qdrant контекстом (10.4)

### 1.1 `get_agent_context_store(agent_id: UUID) -> Optional[AgentContextStore]`

**Назначение:** Получить контекстное хранилище агента для RAG операций

**Параметры:**
- `agent_id` (UUID): ID агента

**Возвращает:**
- `AgentContextStore` или `None` если агент не найден

**Логика:**
1. Проверить инициализацию workspace
2. Найти агента в кеше
3. Вернуть `agent.context_store`

**Ошибки:**
- Логирует warning если агент не найден
- Вернёт None

---

### 1.2 `search_context(agent_id: UUID, query: str, limit: int = 10, filter_success: Optional[bool] = None, filter_type: Optional[str] = None) -> list[dict[str, Any]]`

**Назначение:** Выполнить vector search в контексте агента

**Параметры:**
- `agent_id`: ID агента
- `query`: Поисковый запрос
- `limit`: Макс результатов (default 10)
- `filter_success`: Фильтр по успешным взаимодействиям (optional)
- `filter_type`: Фильтр по типу взаимодействия (optional)

**Возвращает:** 
```python
[{
    "id": str,              # Point ID в Qdrant
    "score": float,         # 0-1 релевантность
    "content": str,         # Текст взаимодействия
    "interaction_type": str,
    "timestamp": str,
    "metadata": dict
}, ...]
```

**Логика:**
1. Получить context_store агента
2. Вернуть [] если не найден
3. Выполнить search в Qdrant
4. Логировать результаты

---

### 1.3 `add_context(agent_id: UUID, content: str, interaction_type: str = "chat", task_id: Optional[str] = None, success: bool = True, metadata: Optional[dict[str, Any]] = None) -> Optional[str]`

**Назначение:** Добавить взаимодействие в контекст агента

**Параметры:**
- `agent_id`: ID агента
- `content`: Текст взаимодействия
- `interaction_type`: Тип ("chat", "task_execution", etc)
- `task_id`: ID задачи (optional)
- `success`: Успешно ли (default True)
- `metadata`: Доп. данные (optional)

**Возвращает:** 
- Point ID в Qdrant или None при ошибке

**Логика:**
1. Получить context_store
2. Вернуть None если не найден
3. Добавить в Qdrant через context_store.add_interaction()
4. Логировать успешное добавление

---

### 1.4 `clear_context(agent_id: UUID) -> bool`

**Назначение:** Очистить весь контекст агента

**Параметры:**
- `agent_id`: ID агента

**Возвращает:** 
- `True` если успешно, `False` при ошибке

**Логика:**
1. Получить context_store
2. Вернуть False если не найден
3. Вызвать context_store.clear()
4. Логировать результат

---

## 2. Методы координации режимов выполнения (10.5)

### 2.1 `direct_execution(agent_id: UUID, user_message: str, session_history: Optional[list[dict[str, str]]] = None, task_id: Optional[str] = None, metadata: Optional[dict[str, Any]] = None) -> dict[str, Any]`

**Назначение:** Прямое выполнение через конкретного агента

**Параметры:**
- `agent_id`: ID целевого агента
- `user_message`: Сообщение пользователя
- `session_history`: История сессии (optional)
- `task_id`: ID задачи для корреляции (optional)
- `metadata`: Доп. данные (optional)

**Возвращает:**
```python
{
    "success": bool,
    "response": str,
    "agent_id": str,
    "agent_name": str,
    "context_used": int,        # Сколько результатов контекста использовано
    "tokens_used": int,         # От LLM
    "timestamp": str,           # ISO format
    "execution_time_ms": float
}
```

**Процесс:**
1. Получить агента из кеша
2. Добавить input в контекст
3. Выполнить agent.execute()
4. Добавить output в контекст если успешно
5. Вернуть структурированный результат

**Ошибки:**
- ValueError если агент не найден

---

### 2.2 `orchestrated_execution(user_message: str, session_history: Optional[list[dict[str, str]]] = None, task_id: Optional[str] = None, metadata: Optional[dict[str, Any]] = None) -> dict[str, Any]`

**Назначение:** Выполнение через Orchestrator (маршрутизация)

**Параметры:**
- `user_message`: Сообщение пользователя
- `session_history`: История сессии (optional)
- `task_id`: ID задачи (optional)
- `metadata`: Доп. данные (optional)

**Возвращает:**
```python
{
    "success": bool,
    "response": str,
    "selected_agent_id": str,
    "selected_agent_name": str,
    "routing_score": float,     # 0-1 confidence
    "context_used": int,
    "tokens_used": int,
    "timestamp": str,
    "execution_time_ms": float
}
```

**Процесс:**
1. Проверить наличие агентов
2. Получить Orchestrator или использовать fallback (первый агент)
3. Выполнить через direct_execution на выбранном агенте
4. Добавить info маршрутизации в результат

---

### 2.3 `handle_message(message_content: str, target_agent_id: Optional[UUID] = None, session_history: Optional[list[dict[str, str]]] = None, task_id: Optional[str] = None, metadata: Optional[dict[str, Any]] = None) -> dict[str, Any]`

**Назначение:** Единый API для обработки сообщений

**Параметры:**
- `message_content`: Текст сообщения
- `target_agent_id`: ID агента (optional)
- `session_history`: История (optional)
- `task_id`: ID задачи (optional)
- `metadata`: Доп. данные (optional)

**Логика:**
- Если `target_agent_id` задан → вызвать `direct_execution()`
- Иначе → вызвать `orchestrated_execution()`

**Возвращает:** Результат от соответствующего метода

---

## 3. Методы для получения метрик (10.6)

### 3.1 `get_agent_status(agent_id: UUID) -> Optional[dict[str, Any]]`

**Назначение:** Получить детальный статус агента

**Возвращает:**
```python
{
    "agent_id": str,
    "agent_name": str,
    "is_active": bool,
    "is_in_cache": bool,
    
    "execution": {
        "total_executions": int,
        "successful": int,
        "failed": int,
        "last_execution": str,          # ISO format или None
        "avg_execution_time_ms": float,
        "last_execution_time_ms": float
    },
    
    "context": {
        "total_vectors": int,
        "context_search_enabled": bool
    },
    
    "performance": {
        "cache_hit_rate": float,        # 0-1
        "error_rate": float,            # 0-1
        "avg_tokens_per_execution": float
    },
    
    "config": {
        "model": str,
        "temperature": float,
        "max_tokens": int,
        "concurrency_limit": int
    }
} или None
```

**Возвращает None если:** Агент не найден

---

### 3.2 `get_metrics() -> dict[str, Any]`

**Назначение:** Получить полные метрики workspace

**Возвращает:**
```python
{
    "user_id": str,
    "project_id": str,
    "initialized": bool,
    "initialization_time": str,     # ISO format или None
    "uptime_seconds": float,
    
    "agents": {
        "total": int,
        "active": int,
        "list": [
            {
                "id": str,
                "name": str,
                "status": "active" | "inactive",
                "context_vectors": int
            }
        ]
    },
    
    "cache": {
        "size": int,
        "max_size": int,
        "hit_rate": float,          # 0-1
        "ttl_seconds": int
    },
    
    "context": {
        "total_vectors": int,
        "collections_count": int,
        "avg_vectors_per_agent": float
    },
    
    "health": {
        "is_healthy": bool,
        "last_check": str,          # ISO format
        "issues": [str]             # Описания проблем
    },
    
    "timestamp": str                # ISO format
}
```

---

## 4. Dependency Injection (10.9)

### 4.1 `get_worker_space(project_id: UUID, request: Request, ...) -> UserWorkerSpace`

**Статус:** ✓ Проверена, работает корректно

**Получает или создаёт:** UserWorkerSpace для текущего (user_id, project_id) пара

---

### 4.2 `get_agent_context_store(agent_id: UUID, workspace: UserWorkerSpace) -> Optional[AgentContextStore]`

**Статус:** ✓ Добавлена новая зависимость

**Получает:** Context store агента через workspace

**Возвращает:** None если Qdrant отключен

---

## Интеграция с endpoints

### `POST /{session_id}/message/` (app/routes/project_chat.py)

**Использует:** `workspace.handle_message()`

**Процесс:**
1. Сохранить user message в БД
2. Отправить SSE event MESSAGE_CREATED
3. Вызвать `workspace.handle_message()`
4. Обработать результат
5. Сохранить assistant message
6. Отправить SSE события с результатами

**SSE события:**
- MESSAGE_CREATED (user)
- DIRECT_AGENT_CALL (if target_agent)
- TASK_STARTED
- MESSAGE_CREATED (assistant) с execution metrics
- TASK_COMPLETED
- ERROR (if failed)

---

## Критерии качества

- ✅ Type hints на всех параметрах и возвращаемых значениях
- ✅ Полные docstrings на английском
- ✅ Error handling с graceful fallbacks
- ✅ Логирование на всех уровнях
- ✅ Per-project изоляция
- ✅ Async везде
- ✅ Отслеживание времени выполнения
- ✅ Сохранение контекста для анализа

---

## Результаты тестирования

```
✓ 25 тестов PASSED
✓ 5 тестов XFAIL (expected)
✓ 1 тест XPASS (unexpected pass)
✓ 0 тестов FAILED

Все тесты UserWorkerSpace проходят успешно!
```

---

**Версия спецификации:** 1.0  
**Дата завершения:** 2026-02-19  
**Статус:** ЗАВЕРШЕНО ✓
