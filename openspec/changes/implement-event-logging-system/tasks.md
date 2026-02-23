# Implementation Tasks: Event Logging System

## 1. Database Schema и EventLog Model

- [ ] 1.1 Создать EventLog модель в `app/models/event_log.py` с полями: id, session_id, user_id, project_id, agent_id, event_type, payload, created_at, error_code, tool_name, approval_status
- [ ] 1.2 Добавить EventLog в `app/models/__init__.py` для экспорта
- [ ] 1.3 Создать Alembic миграцию для создания таблицы event_logs с индексами (session_id+created_at, user_id+created_at, agent_id, event_type, project_id+created_at)
- [ ] 1.4 Написать unit тесты для EventLog модели (создание, JSONB payload, constraints)
- [ ] 1.5 Протестировать миграцию: `alembic upgrade head` и `alembic downgrade -1`

## 2. EventLogger Service (асинхронный с буферизацией)

- [ ] 2.1 Создать `app/core/event_logger.py` с классом EventLogger (инициализация, log_event, _worker, lifecycle management)
- [ ] 2.2 Реализовать асинхронную очередь буфера (asyncio.Queue) и batch insert логику
- [ ] 2.3 Реализовать graceful shutdown: flush remaining events при завершении
- [ ] 2.4 Добавить retry логику для ошибок БД (exponential backoff)
- [ ] 2.5 Создать dependency injection функцию `get_event_logger()` в `app/dependencies.py`
- [ ] 2.6 Добавить инициализацию EventLogger в `app/main.py` (startup/shutdown lifespan)
- [ ] 2.7 Написать unit тесты для EventLogger (log_event, batch insert, error handling, shutdown)
- [ ] 2.8 Написать load тесты для проверки performance при 1000+ events/sec

## 3. EventRepository для запросов

- [ ] 3.1 Создать `app/core/event_repository.py` с методами: get_events(), get_events_by_session(), get_analytics()
- [ ] 3.2 Реализовать фильтрацию (event_type, agent_id, time range) с user isolation проверкой
- [ ] 3.3 Реализовать пагинацию (limit, offset) с максимальными ограничениями
- [ ] 3.4 Реализовать get_analytics() для статистики (event_type_counts, agent_interactions, error_stats)
- [ ] 3.5 Добавить кэширование результатов в Redis (optional, TTL 5 минут)
- [ ] 3.6 Написать unit тесты для EventRepository (фильтрация, пагинация, user isolation, analytics)

## 4. StreamManager Integration

- [ ] 4.1 Модифицировать `app/core/stream_manager.py`: добавить `event_logger` параметр в __init__
- [ ] 4.2 Реализовать логирование в `broadcast_event()`: вызов `await event_logger.log_event()` для каждого события
- [ ] 4.3 Обеспечить, что логирование неблокирующее (пускает событие в очередь)
- [ ] 4.4 Написать unit тесты для StreamManager логирования (с mocked EventLogger)
- [ ] 4.5 Написать integration тесты: отправка события клиентам + сохранение в БД

## 5. REST API Endpoints для Events и Analytics

- [ ] 5.1 Создать или расширить `app/routes/project_analytics.py` (или расширить `project_chat.py`)
- [ ] 5.2 Реализовать `GET /my/projects/{project_id}/events` с фильтрацией и пагинацией
- [ ] 5.3 Реализовать `GET /my/projects/{project_id}/events/{session_id}` для событий сессии
- [ ] 5.4 Реализовать `GET /my/projects/{project_id}/analytics` для статистики
- [ ] 5.5 Добавить response schemas в `app/schemas/analytics.py` (EventResponse, AnalyticsResponse)
- [ ] 5.6 Реализовать error handling (404, 400 с валидацией параметров)
- [ ] 5.7 Написать unit тесты для всех endpoints (фильтрация, пагинация, errors, user isolation)
- [ ] 5.8 Написать integration тесты: создание событий -> получение через API

## 6. Интеграция логирования в UserWorkerSpace

- [ ] 6.1 Модифицировать `app/core/user_worker_space.py`: добавить `event_logger` в зависимости
- [ ] 6.2 Реализовать логирование AGENT_SWITCHED события при выборе агента в orchestrated mode
- [ ] 6.3 Реализовать логирование DIRECT_AGENT_CALL события при direct execution
- [ ] 6.4 Реализовать логирование с параметрами (agent_id, agent_name, mode, input parameters)
- [ ] 6.5 Написать unit тесты для логирования операций WorkerSpace

## 7. Интеграция логирования в инструменты (ToolExecutor)

- [ ] 7.1 Модифицировать `app/core/tools/executor.py`: добавить `event_logger` в зависимости
- [ ] 7.2 Реализовать TOOL_REQUEST событие перед выполнением (tool_name, tool_type, input_params)
- [ ] 7.3 Реализовать логирование результата выполнения (успех или ошибка)
- [ ] 7.4 Реализовать ERROR событие при исключении (error_code, error_message, stack_trace)
- [ ] 7.5 Реализовать логирование risk assessment (risk_level, risk_factors)
- [ ] 7.6 Написать unit тесты для инструментов логирования

## 8. Интеграция логирования в ApprovalManager

- [ ] 8.1 Модифицировать `app/core/approval_manager.py`: добавить `event_logger`
- [ ] 8.2 Реализовать APPROVAL_REQUIRED событие при создании запроса
- [ ] 8.3 Реализовать APPROVAL_RESOLVED событие при принятии/отклонении
- [ ] 8.4 Реализовать APPROVAL_TIMEOUT_WARNING событие за 30 сек до истечения
- [ ] 8.5 Реализовать APPROVAL_TIMEOUT событие при истечении
- [ ] 8.6 Написать unit тесты для одобрений логирования

## 9. Интеграция логирования в OrchestratorRouter

- [ ] 9.1 Модифицировать `app/core/orchestrator_router.py`: добавить `event_logger`
- [ ] 9.2 Реализовать AGENT_SWITCHED событие при смене агента
- [ ] 9.3 Реализовать TASK_PLAN_CREATED событие
- [ ] 9.4 Реализовать TASK_STARTED, TASK_PROGRESS, TASK_COMPLETED события
- [ ] 9.5 Реализовать CONTEXT_RETRIEVED событие
- [ ] 9.6 Написать unit тесты для orchestrator логирования

## 10. Интеграция логирования в AgentBus

- [ ] 10.1 Модифицировать `app/core/agent_bus.py`: добавить `event_logger`
- [ ] 10.2 Реализовать логирование при submit_task() (task_id, agent_id, queue_position)
- [ ] 10.3 Реализовать логирование при обработке задачи worker'ом
- [ ] 10.4 Написать unit тесты для AgentBus логирования

## 11. Тестирование и валидация

- [ ] 11.1 Написать end-to-end тесты: полный flow сообщения -> вызов инструмента -> сохранение событий
- [ ] 11.2 Написать тесты user isolation (пользователь видит только свои события)
- [ ] 11.3 Запустить load тесты (1000+ events/sec, проверить CPU/memory)
- [ ] 11.4 Проверить, что все тесты проходят: `pytest tests/` с coverage >80%
- [ ] 11.5 Запустить linting: `ruff check app/`
- [ ] 11.6 Проверить миграции: `alembic current`, `alembic heads`

## 12. Документация

- [ ] 12.1 Написать docstrings на русском для всех публичных методов (EventLogger, EventRepository, endpoints)
- [ ] 12.2 Добавить inline комментарии в сложных местах (batch insert логика, user isolation проверки)
- [ ] 12.3 Обновить API документацию (swagger, примеры использования endpoints)
- [ ] 12.4 Создать CHANGELOG запись для этого feature
- [ ] 12.5 Написать документ по использованию event logging API (для клиентов)

## 13. Deployment и мониторинг

- [ ] 13.1 Добавить конфигурацию для event_logs таблицы retention policy (удаление событий старше 90 дней)
- [ ] 13.2 Добавить metrics/monitoring для EventLogger (queue size, batch insert duration, errors)
- [ ] 13.3 Настроить алерты для критических ошибок логирования
- [ ] 13.4 Написать инструкции для deployment новой версии с миграцией

## Dependencies между задачами

```
1.1-1.5 (Database) → 2.1-2.8 (EventLogger) → 4.1-4.5 (StreamManager)
                                            → 3.1-3.6 (EventRepository) → 5.1-5.8 (API)
                                            → 6.1-6.5, 7.1-7.6, 8.1-8.6, 9.1-9.6, 10.1-10.4
                                            → 11.1-11.6 (Testing)
                                            → 12.1-12.5 (Docs)
                                            → 13.1-13.4 (Deployment)
```

## Приоритизация

**Critical (Day 1-2):**
- Section 1: Database setup
- Section 2: EventLogger service
- Section 4: StreamManager integration (основной канал логирования)

**High Priority (Day 2-3):**
- Section 3: EventRepository
- Section 5: API endpoints
- Section 11: Base testing

**Medium Priority (Day 3-4):**
- Sections 6-10: Полная инструментация компонентов

**Low Priority (Day 4):**
- Section 12: Documentation
- Section 13: Deployment и мониторинг
