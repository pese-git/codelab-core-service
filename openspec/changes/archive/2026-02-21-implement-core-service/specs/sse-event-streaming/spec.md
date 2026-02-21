# Спецификация: Streaming Fetch Event API

## ADDED Requirements

### Requirement: Streaming endpoint для real-time событий
Система ДОЛЖНА предоставлять streaming endpoint для получения real-time обновлений через Fetch API.

#### Scenario: Подключение к event stream
- **WHEN** пользователь отправляет GET `/my/chat/{session_id}/events/` с JWT в Authorization header
- **THEN** система устанавливает streaming connection и начинает отправку событий в формате JSON Lines (NDJSON)

#### Scenario: Множественные подключения
- **WHEN** пользователь открывает несколько вкладок с одной сессией
- **THEN** система поддерживает множественные streaming connections для одной сессии

#### Scenario: Контролируемый reconnect
- **WHEN** streaming connection прерывается
- **THEN** клиент может переподключиться с custom retry логикой и восстановить пропущенные события

#### Scenario: Изоляция событий
- **WHEN** User123 подключается к stream
- **THEN** система отправляет только события сессий User123

#### Scenario: JWT авторизация через headers
- **WHEN** клиент подключается к stream
- **THEN** система проверяет JWT токен из Authorization header (не из query params)

#### Scenario: Отмена запроса
- **WHEN** клиент использует AbortController для отмены
- **THEN** система корректно закрывает connection и освобождает ресурсы

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

#### Scenario: heartbeat событие
- **WHEN** нет активности в течение heartbeat интервала
- **THEN** система отправляет событие с типом "heartbeat" и payload: {timestamp}

### Requirement: JSON Lines (NDJSON) format
Система ДОЛЖНА отправлять события в формате JSON Lines (Newline Delimited JSON).

#### Scenario: Формат события
- **WHEN** событие отправляется
- **THEN** каждое событие - это отдельная JSON строка, завершающаяся символом новой строки `\n`

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

#### Scenario: Content-Type header
- **WHEN** клиент подключается к stream
- **THEN** система возвращает `Content-Type: application/x-ndjson`

### Requirement: Connection lifecycle management
Система ДОЛЖНА управлять жизненным циклом streaming connections.

#### Scenario: Heartbeat для поддержания connection
- **WHEN** streaming connection активно
- **THEN** система отправляет heartbeat событие каждые 30 секунд

#### Scenario: Timeout неактивного connection
- **WHEN** клиент не отправляет запросы 5 минут
- **THEN** система закрывает streaming connection

#### Scenario: Graceful close
- **WHEN** сессия завершается или удаляется
- **THEN** система отправляет финальное событие и закрывает все streaming connections сессии

#### Scenario: Cleanup при disconnect
- **WHEN** клиент отключается
- **THEN** система освобождает ресурсы и удаляет connection из реестра

#### Scenario: HTTP response headers
- **WHEN** streaming connection устанавливается
- **THEN** система возвращает headers: `Cache-Control: no-cache`, `Connection: keep-alive`, `X-Accel-Buffering: no`

### Requirement: Scalability для множественных connections
Система ДОЛЖНА поддерживать 1000+ одновременных streaming connections на пользователя.

#### Scenario: Множественные connections на пользователя
- **WHEN** пользователь открывает 100 вкладок
- **THEN** система поддерживает все 100 streaming connections без деградации

#### Scenario: Broadcasting событий
- **WHEN** событие генерируется для сессии
- **THEN** система отправляет событие всем активным streaming connections этой сессии

#### Scenario: Эффективное использование памяти
- **WHEN** система поддерживает множество connections
- **THEN** память на connection < 1MB

#### Scenario: Мониторинг количества connections
- **WHEN** система работает
- **THEN** система отслеживает количество активных streaming connections per user и per session

### Requirement: Event buffering
Система ДОЛЖНА буферизовать события для обработки временных отключений.

#### Scenario: Буферизация при disconnect
- **WHEN** streaming connection прерывается
- **THEN** система буферизует события в Redis (max 100 событий)

#### Scenario: Восстановление событий при reconnect
- **WHEN** клиент переподключается с query parameter `?since=<timestamp>`
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
- **WHEN** система поддерживает 1000 streaming connections
- **THEN** CPU usage < 50% на одном core

#### Scenario: Network bandwidth
- **WHEN** события отправляются
- **THEN** средний размер события < 1KB для эффективного использования bandwidth

### Requirement: Error handling
Система ДОЛЖНА корректно обрабатывать ошибки в streaming.

#### Scenario: Ошибка сериализации
- **WHEN** событие не может быть сериализовано в JSON
- **THEN** система логирует ошибку и пропускает событие

#### Scenario: Ошибка отправки
- **WHEN** отправка события failed (connection closed)
- **THEN** система удаляет connection из реестра и останавливает отправку

#### Scenario: Ошибка доступа
- **WHEN** пользователь пытается подключиться к чужой сессии
- **THEN** система возвращает 403 Forbidden и закрывает connection

#### Scenario: Ошибка авторизации
- **WHEN** JWT токен невалиден или отсутствует
- **THEN** система возвращает 401 Unauthorized

#### Scenario: Логирование ошибок
- **WHEN** происходит ошибка в streaming
- **THEN** система логирует ошибку с контекстом (user_id, session_id, error_type)

#### Scenario: Отправка error события
- **WHEN** происходит ошибка во время streaming
- **THEN** система отправляет событие с типом "error" и payload: {error, message} перед закрытием

### Requirement: Monitoring и metrics
Система ДОЛЖНА предоставлять метрики для мониторинга streaming.

#### Scenario: Метрики connections
- **WHEN** система работает
- **THEN** система собирает метрики: active_connections, connections_per_user, connections_per_session

#### Scenario: Метрики событий
- **WHEN** события отправляются
- **THEN** система собирает метрики: events_sent, events_per_type, average_event_size

#### Scenario: Метрики производительности
- **WHEN** streaming активен
- **THEN** система собирает метрики: p50/p95/p99_latency, throughput, error_rate

#### Scenario: Алерты при проблемах
- **WHEN** error_rate > 5% или latency > 500ms
- **THEN** система генерирует алерт для мониторинга

## CHANGED Requirements

### Requirement: Формат передачи данных
- **BEFORE**: События передавались в SSE формате (`data: {...}\n\n`)
- **AFTER**: События передаются в JSON Lines формате (`{...}\n`)
- **REASON**: JSON Lines проще парсить, не требует специального SSE парсера, лучше поддерживается современными инструментами

### Requirement: Авторизация
- **BEFORE**: JWT токен передавался через query parameters (небезопасно)
- **AFTER**: JWT токен передается через Authorization header
- **REASON**: Безопасность - токены не должны попадать в логи и URL history

### Requirement: Heartbeat механизм
- **BEFORE**: Heartbeat отправлялся как SSE комментарий (`: heartbeat\n\n`)
- **AFTER**: Heartbeat отправляется как JSON событие с типом "heartbeat"
- **REASON**: Единообразие формата, возможность добавить метаданные в heartbeat

### Requirement: Reconnect механизм
- **BEFORE**: Использовался SSE `Last-Event-ID` header
- **AFTER**: Используется query parameter `?since=<timestamp>`
- **REASON**: Больше контроля на клиенте, проще реализация custom retry логики
