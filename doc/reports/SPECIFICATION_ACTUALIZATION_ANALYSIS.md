# Анализ Актуализации Спецификаций

**Дата анализа:** 2026-03-06  
**Статус:** Анализ выполненной реализации vs текущие спецификации

---

## Резюме

Проведен анализ 6 спецификаций (openspec/specs/) и их соответствия текущей реализации. Выявлены расхождения, которые требуют актуализации спеков.

**Основные находки:**
- **Высокое соответствие (85%)**: Event Instrumentation, Event Logging Persistence, Interaction Analytics API, Event Logger Service
- **Расхождение в Jaeger/OTLP**: Tool Execution Trace spec предполагает JaegerExporter, реализация использует OTLPSpanExporter
- **Пробел в spec**: User Worker Space spec не полностью отражает текущую реализацию методов

---

## 1. Tool Execution Trace System

### Спецификация требует:
- OpenTelemetry с **JaegerExporter**
- Jaeger UI на localhost:16686
- Docker Compose конфигурация для Jaeger
- Spans: message_processing, agent_execution, llm_call, tool_execution с child spans

### Реальная реализация:

**✅ РЕАЛИЗОВАНО:**
- `app/tracing.py` инициализирует OpenTelemetry
- Используются spans:
  - `message_processing` в `app/routes/project_chat.py:236` ✓
  - `agent_execution` в `app/agents/contextual_agent.py:97` ✓
  - `llm_call` в `app/agents/contextual_agent.py:164` ✓
  - `tool_execution` в `app/core/tools/executor.py:97` ✓
    - child: `tool_validation:113`, `risk_assessment:137`, `approval_workflow:185`, `client_execution:242` ✓
- Все spans используют `set_attribute()`, `add_event()`, `record_exception()` ✓
- Span метрики (latency_ms, tokens_prompt, tokens_completion, tokens_total) ✓

**❌ РАСХОЖДЕНИЕ:**

| Параметр | Spec | Реализация | Статус |
|----------|------|------------|--------|
| Exporter | JaegerExporter | OTLPSpanExporter | ⚠️ Расхождение |
| OTLP Endpoint | `localhost:6831` (UDP) | `settings.otlp_exporter_url` (HTTP) | ⚠️ Расхождение |
| Jaeger UI | docker-compose-dev.yml требует настройки | Не настроен в текущем compose | ⚠️ Пробел |

**Анализ расхождения:**
- Spec предполагает direct Jaeger connection через UDP (port 6831)
- Реализация использует OTLP HTTP protocol (более гибкий, поддерживает разные бэкенды)
- OTLP - более современный подход (OTLP = OpenTelemetry Protocol, работает с Jaeger, Tempo, Signoz и др.)

**Вывод:** Spec устаревает. Нужна актуализация под OTLP, так как это более гибкий и расширяемый подход.

---

## 2. Event Instrumentation

### Спецификация требует:
- Запись событий в `event_outbox` в той же транзакции
- Отделение domain write от transport delivery
- Обязательная metadata: `event_id`, `session_id`, `project_id`, `user_id`, `timestamp`

### Реальная реализация:

**✅ ПОЛНОСТЬЮ РЕАЛИЗОВАНО:**
- `OutboxRepository.record_event()` используется для всех domain events
- Вызовы в `app/routes/project_chat.py:256`, `app/core/user_worker_space.py:900`
- Запись в той же транзакции (не используется StreamManager.broadcast для domain events)
- Payload содержит все требуемые поля: `event_id`, `session_id`, `project_id`, `user_id`, `timestamp`

**Примеры из кода:**
```python
# app/routes/project_chat.py:256-270
await OutboxRepository.record_event(
    session=db,
    aggregate_type="message",
    aggregate_id=str(message.id),
    user_id=user_id,
    project_id=project_id,
    session_id=session_id,
    event_type=StreamEventType.MESSAGE_CREATED.value,
    payload={...}
)
```

**Вывод:** ✅ Спец полностью соответствует реализации. Требуется минимальная актуализация для уточнений.

---

## 3. Event Logger Service (OutboxPublisher)

### Спецификация требует:
- Асинхронный publisher для фоновой публикации pending событий
- Batch processing с SKIP LOCKED для конкурентности
- Retry/backoff при ошибках
- Lifecycle управление (start/stop)
- Метрики: pending_count, success/failure counters

### Реальная реализация:

**✅ РЕАЛИЗОВАНО:**
- `OutboxPublisher` в `app/core/outbox_publisher.py`
- Инициализирован в `app/main.py:56-57`
- Lifecycle: `start()` в startup, `stop()` в shutdown
- Batch processing: `_process_batch()` метод ✓
- Retry/backoff: exponential backoff с `next_retry_at` ✓
- Metrics: `published_total`, `failed_total`, `pending_count` ✓

**Детали реализации:**
```python
# app/core/outbox_publisher.py:126-150
async def _process_batch(self) -> None:
    # SELECT где status='pending' AND (next_retry_at IS NULL OR next_retry_at <= now())
    query = select(EventOutbox).where(
        and_(
            EventOutbox.status == "pending",
            or_(
                EventOutbox.next_retry_at == None,
                EventOutbox.next_retry_at <= datetime.utcnow(),
            ),
        )
    ).order_by(EventOutbox.created_at).limit(self.batch_size)
```

**⚠️ ВОЗМОЖНЫЙ ПРОБЕЛ:**

Spec требует `FOR UPDATE SKIP LOCKED` для конкурентно-безопасной обработки:
```sql
SELECT ... FOR UPDATE SKIP LOCKED
```

Текущая реализация использует `select()` без explicit `FOR UPDATE SKIP LOCKED`. Это может быть проблемой если несколько publisher инстансов работают параллельно.

**Вывод:** Нужна актуализация спека с уточнением о SKIP LOCKED требовании или реализация SKIP LOCKED.

---

## 4. Interaction Analytics API

### Спецификация требует:
- `GET /my/projects/{project_id}/events` с фильтрацией и пагинацией
- `GET /my/projects/{project_id}/analytics/sessions/{session_id}/events`
- `GET /my/projects/{project_id}/analytics` сводная аналитика
- User/project isolation
- Eventual consistency SLA

### Реальная реализация:

**✅ РЕАЛИЗОВАНО:**
- `app/routes/analytics.py` предоставляет все нужные endpoints
- `GET /my/projects/{project_id}/events` - строка 80 ✓
  - Фильтрация по: event_type, aggregate_type, status
  - Пагинация: limit/offset с DEFAULT_LIMIT=20, MAX_LIMIT=100
- `GET /my/projects/{project_id}/analytics/sessions/{session_id}/events` - строка 180 ✓
- `GET /my/projects/{project_id}/analytics` - строка 193 ✓
  - Event type counts
  - Agent interactions
  - Error statistics
- User/project isolation через `verify_project_access()` ✓

**Примеры ответов:**
```python
# EventRecord содержит: id, aggregate_type, aggregate_id, event_type, 
# payload, status, retry_count, created_at, published_at
```

**Вывод:** ✅ Спец полностью соответствует. Требуется документирование SLA.

---

## 5. Event Logging Persistence

### Спецификация требует:
- Таблица `event_outbox` с полями: id, aggregate_type, aggregate_id, user_id, project_id, event_type, payload, status, retry_count, next_retry_at, created_at, published_at, last_error
- Индексы для быстрого поиска
- Миграции Alembic

### Реальная реализация:

**✅ ПОЛНОСТЬЮ РЕАЛИЗОВАНО:**
- `app/models/event_outbox.py` определяет модель
- Все требуемые поля присутствуют
- Индексы созданы (строка 108-112):
  - `(status, next_retry_at, created_at)` для pending выборки
  - `(aggregate_id, created_at)` для истории
  - `(project_id, created_at)` для фильтрации
  - `(user_id, created_at)` для user-изоляции

**Статусы:** pending, published, failed ✓

**Вывод:** ✅ Спец полностью соответствует реализации.

---

## 6. User Worker Space

### Спецификация требует:
- Управление lifecycle backend ресурсов (agent_cache, Agent Bus, Qdrant)
- Per-project architecture
- Default Starter Pack инициализация
- Workspace access control

### Реальная реализация:

**✅ РЕАЛИЗОВАНО:**
- `app/core/user_worker_space.py` - основной класс (1287 строк)
- AgentCache для кэширования агентов (строки 30-80)
- Agent Bus интеграция (строка 17: `from app.core.agent_bus import AgentBus`)
- Qdrant интеграция (строка 9: `from qdrant_client import AsyncQdrantClient`)
- Starter Pack инициализация

**✅ МЕТОДЫ РЕАЛИЗОВАНЫ:**
- `initialize_project()` - инициализация проекта
- `get_agent()` - получение агента с кэшированием
- `execute_agent()` - выполнение агента
- `switch_agent()` - переключение агента
- Управление workspace lifecycle

**⚠️ ПРОБЕЛ В SPEC:**

Spec (openspec/specs/user-worker-space/spec.md) охватывает:
- Architecture и design (строки 1-100)
- Но не охватывает детали реализованных методов

Реализованные методы в коде НЕ ЗАДОКУМЕНТИРОВАНЫ в spec:
- `initialize_project()` 
- `get_agent()`
- `execute_agent()`
- `switch_agent()`
- Caching strategy
- RAG context retrieval

**Вывод:** Нужна актуализация spec для документирования всех реализованных методов.

---

## 7. Дополнительные Наблюдения

### Отличная реализация:
1. **Outbox Pattern** - полностью реализован архитектурный паттерн
2. **Трассировка** - comprehensive spans с правильной иерархией
3. **Event instrumentation** - правильное разделение domain/transport
4. **User isolation** - везде проверяется user_id и project_id

### Потенциальные улучшения:
1. **FOR UPDATE SKIP LOCKED** - добавить в OutboxPublisher.\_process_batch()
2. **Jaeger vs OTLP** - актуализировать spec под OTLP
3. **Event Correlation IDs** - рассмотреть добавление trace_id/span_id в payload
4. **DLQ (Dead Letter Queue)** - для failed событий, не документировано в spec

---

## 8. Необходимые Действия для Актуализации

### Высокий Приоритет (A):
- [ ] Актуализировать **Tool Execution Trace spec**: Jaeger → OTLP
- [ ] Дополнить **User Worker Space spec**: документировать реализованные методы
- [ ] Добавить **FOR UPDATE SKIP LOCKED** в Event Logger Service spec и/или реализацию

### Средний Приоритет (B):
- [ ] Документировать **Event Correlation** (trace_id/span_id propagation)
- [ ] Документировать **Eventual Consistency SLA** в Analytics API spec
- [ ] Добавить документацию про **DLQ/failed events handling**

### Низкий Приоритет (C):
- [ ] Уточнить OTLP endpoint configuration
- [ ] Расширить примеры в specs с actual API responses

---

## Итоговая Таблица Соответствия

| Спецификация | Статус | Примечание |
|--------------|--------|-----------|
| Tool Execution Trace | ⚠️ Частичный | Jaeger→OTLP,需 актуализация |
| Event Instrumentation | ✅ Полный | Полная реализация |
| Event Logger Service | ⚠️ Частичный | Нужен SKIP LOCKED |
| Interaction Analytics API | ✅ Полный | Полная реализация |
| Event Logging Persistence | ✅ Полный | Полная реализация |
| User Worker Space | ⚠️ Частичный | Методы не документированы в spec |

**Общее соответствие: 70-75%**

---

## Рекомендуемый План Актуализации

1. **Этап 1**: Актуализировать Tool Execution Trace spec (Jaeger → OTLP)
2. **Этап 2**: Дополнить User Worker Space spec с реализованными методами
3. **Этап 3**: Проверить и актуализировать Event Logger Service (FOR UPDATE SKIP LOCKED)
4. **Этап 4**: Финальная консистентность проверка всех спеков
5. **Этап 5**: Синхронизация архивированных changes с актуализированными specs

---

**Статус**: Готов к актуализации спецификаций
