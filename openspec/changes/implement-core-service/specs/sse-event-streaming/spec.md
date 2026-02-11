# Спецификация: SSE Event Streaming

## ADDED Requirements

### Requirement: SSE endpoint для real-time событий
Система ДОЛЖНА предоставлять SSE endpoint для получения real-time обновлений.

#### Scenario: Подключение к SSE stream
- **WHEN** пользователь отправляет GET `/my/chat/{session_id}/events/`
- **THEN** система устанавливает SSE connection и начинает отправку событий

#### Scenario: Множественные подключения
- **WHEN** пользователь открывает несколько вкладок с одной сессией
- **THEN** система поддерживает множественные SSE connections для одной сессии

#### Scenario: Автоматический reconnect
- **WHEN** SSE connection прерывается
- **THEN** клиент автоматически переподключается и система восстанавливает stream

#### Scenario: Изоляция событий
- **WHEN** User123 подключается к SSE
- **THEN** система отправляет только события сессий User123

### Requirement: Event types
Система ДОЛЖНА поддерживать различные типы событий для разных сценариев.

#### Scenario: direct_agent_call событие
- **WHEN** выполняется direct call к агенту
- **THEN** система отправляет событие с типом "direct_agent_call" и payload: {agent_id, task_id, timestamp}

#### Scenario: agent_status_changed событие
- **WHEN** статус агента изменяется (ready → busy → ready)
- **THEN** система отправляет событие с типом "agent_status_changed" и payload: {agent_id, old_status, new_status, timestamp}

#### Scenario: task_plan_created событие
- **WHEN** orchestrator создает план задач
- **THEN** система отправляет событие с типом "task_plan_created" и payload: {plan_id, tasks[], estimated_cost, estimated_duration}

#### Scenario: task_started событие
- **WHEN** задача начинает выполняться
- **THEN** система отправляет событие с типом "task_started" и payload: {task_id, agent_id, timestamp}

#### Scenario: task_progress событие
- **WHEN** задача отправляет промежуточный прогресс
- **THEN** система отправляет событие с типом "task_progress" и payload: {task_id, progress_percent, message}

#### Scenario: task_completed событие
- **WHEN** задача успешно завершается
- **THEN** система отправляет событие с типом "task_completed" и payload: {task_id, result, duration, timestamp}

#### Scenario: tool_request событие
- **WHEN** агент запрашивает approval для использования tool
- **THEN** система отправляет событие с типом "tool_request" и payload: {approval_id, tool_name, parameters, agent_id}

#### Scenario: plan_request событие
- **WHEN** orchestrator запрашивает approval для плана
- **THEN** система отправляет событие с типом "plan_request" и payload: {approval_id, plan, estimated_cost, estimated_duration}

#### Scenario: context_retrieved событие
- **WHEN** агент получает RAG контекст из Qdrant
- **THEN** система отправляет событие с типом "context_retrieved" и payload: {agent_id, context_items_count, relevance_scores[]}

#### Scenario: approval_required событие
- **WHEN** требуется подтверждение пользователя
- **THEN** система отправляет событие с типом "approval_required" и payload: {approval_id, type, details, timeout}

### Requirement: JSON payload format
Система ДОЛЖНА отправлять события в стандартизированном JSON формате.

#### Scenario: Структура события
- **WHEN** событие отправляется
- **THEN** JSON содержит поля: event_type, payload, timestamp, session_id

#### Scenario: Сериализация datetime
- **WHEN** событие содержит timestamp
- **THEN** timestamp сериализуется в ISO8601 формат

#### Scenario: Вложенные объекты
- **WHEN** payload содержит сложные объекты
- **THEN** система корректно сериализует вложенные структуры

#### Scenario: Размер payload
- **WHEN** payload большой (например, результат задачи)
- **THEN** система ограничивает размер до 10KB, большие данные доступны через API

### Requirement: Connection lifecycle management
Система ДОЛЖНА управлять жизненным циклом SSE connections.

#### Scenario: Heartbeat для поддержания connection
- **WHEN** SSE connection активно
- **THEN** система отправляет heartbeat комментарий каждые 30 секунд

#### Scenario: Timeout неактивного connection
- **WHEN** клиент не отправляет запросы 5 минут
- **THEN** система закрывает SSE connection

#### Scenario: Graceful close
- **WHEN** сессия завершается или удаляется
- **THEN** система отправляет финальное событие и закрывает все SSE connections сессии

#### Scenario: Cleanup при disconnect
- **WHEN** клиент отключается
- **THEN** система освобождает ресурсы и удаляет connection из реестра

### Requirement: Scalability для множественных connections
Система ДОЛЖНА поддерживать 1000+ одновременных SSE connections на пользователя.

#### Scenario: Множественные connections на пользователя
- **WHEN** пользователь открывает 100 вкладок
- **THEN** система поддерживает все 100 SSE connections без деградации

#### Scenario: Broadcasting событий
- **WHEN** событие генерируется для сессии
- **THEN** система отправляет событие всем активным SSE connections этой сессии

#### Scenario: Эффективное использование памяти
- **WHEN** система поддерживает множество connections
- **THEN** память на connection < 1MB

#### Scenario: Мониторинг количества connections
- **WHEN** система работает
- **THEN** система отслеживает количество активных SSE connections per user и per session

### Requirement: Event buffering
Система ДОЛЖНА буферизовать события для обработки временных отключений.

#### Scenario: Буферизация при disconnect
- **WHEN** SSE connection прерывается
- **THEN** система буферизует события в Redis (max 100 событий)

#### Scenario: Восстановление событий при reconnect
- **WHEN** клиент переподключается с last_event_id
- **THEN** система отправляет пропущенные события из буфера

#### Scenario: TTL буфера
- **WHEN** события буферизуются
- **THEN** TTL буфера устанавливается на 5 минут

#### Scenario: Переполнение буфера
- **WHEN** буфер превышает 100 событий
- **THEN** система удаляет самые старые события (FIFO)

### Requirement: Performance requirements
Система ДОЛЖНА обеспечивать низкую latency доставки событий.

#### Scenario: Latency доставки событий
- **WHEN** событие генерируется
- **THEN** событие доставляется клиенту менее чем за 100ms (P99)

#### Scenario: Throughput событий
- **WHEN** система генерирует множество событий
- **THEN** система обрабатывает 1000+ событий в секунду на connection

#### Scenario: CPU usage
- **WHEN** система поддерживает 1000 SSE connections
- **THEN** CPU usage < 50% на одном core

#### Scenario: Network bandwidth
- **WHEN** события отправляются
- **THEN** средний размер события < 1KB для эффективного использования bandwidth

### Requirement: Error handling
Система ДОЛЖНА корректно обрабатывать ошибки в SSE streaming.

#### Scenario: Ошибка сериализации
- **WHEN** событие не может быть сериализовано в JSON
- **THEN** система логирует ошибку и пропускает событие

#### Scenario: Ошибка отправки
- **WHEN** отправка события failed (connection closed)
- **THEN** система удаляет connection из реестра и останавливает отправку

#### Scenario: Ошибка доступа
- **WHEN** пользователь пытается подключиться к чужой сессии
- **THEN** система возвращает 403 Forbidden и закрывает connection

#### Scenario: Логирование ошибок
- **WHEN** происходит ошибка в SSE streaming
- **THEN** система логирует ошибку с контекстом (user_id, session_id, error_type)

### Requirement: Monitoring и metrics
Система ДОЛЖНА предоставлять метрики для мониторинга SSE streaming.

#### Scenario: Метрики connections
- **WHEN** система работает
- **THEN** система собирает метрики: active_connections, connections_per_user, connections_per_session

#### Scenario: Метрики событий
- **WHEN** события отправляются
- **THEN** система собирает метрики: events_sent, events_per_type, average_event_size

#### Scenario: Метрики производительности
- **WHEN** SSE streaming активен
- **THEN** система собирает метрики: p50/p95/p99_latency, throughput, error_rate

#### Scenario: Алерты при проблемах
- **WHEN** error_rate > 5% или latency > 500ms
- **THEN** система генерирует алерт для мониторинга
