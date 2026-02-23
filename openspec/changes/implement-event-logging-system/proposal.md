# Proposal: Implement Event Logging System

## Why

Текущая система генерирует события взаимодействия пользователя с агентами в реальном времени (MESSAGE_CREATED, AGENT_SWITCHED, TASK_STARTED, TOOL_REQUEST, APPROVAL_REQUIRED и т.д.) через SSE/WebSocket, однако события не сохраняются в базу данных и теряются при отключении клиента. Для анализа и аудита взаимодействий пользователей с агентами необходимо иметь полную историю всех событий с возможностью запроса и фильтрации.

## What Changes

- **Добавляется модель EventLog** для постоянного хранения всех событий в PostgreSQL (session_id, user_id, agent_id, event_type, payload, timestamp, metadata)
- **Создается EventLogger сервис** для логирования событий из различных компонентов системы
- **Интегрируется логирование** в StreamManager, AgentBus, ApprovalManager и другие ключевые компоненты
- **Добавляются REST API endpoints** для получения истории событий, фильтрации и аналитики взаимодействий
- **Реализуется EventRepository** для сложных запросов к истории событий (фильтрация по типам, агентам, периодам)

## Capabilities

### New Capabilities

- `event-logging-persistence`: Сохранение всех событий взаимодействия в БД с полным контекстом (EventLog модель, миграция БД)
- `event-logger-service`: Центральный сервис логирования событий, доступный для всех компонентов системы
- `interaction-analytics-api`: REST API endpoints для анализа взаимодействий (история событий, статистика, временная шкала)
- `event-instrumentation`: Интеграция логирования в ключевые точки системы (chat endpoints, agent operations, tool execution, approvals)

### Modified Capabilities

- `sse-event-streaming`: Требование интегрировать EventLogger в StreamManager для синхронного сохранения событий параллельно отправке клиентам

## Impact

**Затронутый код:**
- `app/models/` - добавляется модель EventLog
- `app/schemas/` - расширяются схемы для API событий
- `app/core/` - интеграция логирования в stream_manager.py, agent_bus.py, orchestrator_router.py, user_worker_space.py
- `app/routes/` - добавляются новые endpoints для analytics (project_analytics.py или расширение project_chat.py)
- `migrations/` - миграция БД для создания таблицы event_logs с индексами
- `tests/` - добавляются тесты логирования и аналитики

**API изменения:**
- Новые endpoints: `GET /my/projects/{project_id}/events`, `GET /my/projects/{project_id}/analytics`
- Новые query parameters для фильтрации: `event_type`, `agent_id`, `start_time`, `end_time`, `limit`, `offset`

**Зависимости:**
- Существующие: FastAPI, SQLAlchemy, PostgreSQL, Redis
- Нет новых внешних зависимостей

**Breaking changes:** Нет
