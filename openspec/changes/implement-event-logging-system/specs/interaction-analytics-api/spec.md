# Specification: Interaction Analytics API

## ADDED Requirements

### Requirement: REST API endpoint для получения истории событий
Система ДОЛЖНА предоставлять REST API endpoint `GET /my/projects/{project_id}/events` для получения истории событий с фильтрацией и пагинацией.

#### Scenario: Получение всех событий проекта
- **WHEN** клиент отправляет `GET /my/projects/abc123/events`
- **THEN** система возвращает список всех событий в проекте с пагинацией (по умолчанию 50 событий, сортировка по created_at DESC)

#### Scenario: Фильтрация по event_type
- **WHEN** клиент отправляет `GET /my/projects/abc123/events?event_type=TOOL_REQUEST`
- **THEN** система возвращает только события типа TOOL_REQUEST

#### Scenario: Фильтрация по agent_id
- **WHEN** клиент отправляет `GET /my/projects/abc123/events?agent_id=agent-uuid`
- **THEN** система возвращает только события, относящиеся к указанному агенту (или NULL если agent_id=null)

#### Scenario: Фильтрация по временному диапазону
- **WHEN** клиент отправляет `GET /my/projects/abc123/events?start_time=2026-02-23T10:00:00Z&end_time=2026-02-23T11:00:00Z`
- **THEN** система возвращает события, созданные в указанном диапазоне (inclusive)

#### Scenario: Комбинированная фильтрация
- **WHEN** клиент отправляет `GET /my/projects/abc123/events?event_type=ERROR&agent_id=agent-uuid&start_time=2026-02-23T10:00:00Z`
- **THEN** система возвращает события, соответствующие всем критериям (AND логика)

#### Scenario: Пагинация
- **WHEN** клиент отправляет `GET /my/projects/abc123/events?limit=20&offset=40`
- **THEN** система возвращает события с offset 40, максимум 20 элементов; response включает total count

### Requirement: REST API endpoint для истории всех событий сессии (для аналитики)
Система ДОЛЖНА предоставлять endpoint `GET /my/projects/{project_id}/analytics/sessions/{session_id}/events` для получения полной истории всех событий (включая системные) одной chat сессии.

#### Scenario: Получение всех событий сессии (аналитика)
- **WHEN** клиент отправляет `GET /my/projects/proj-id/analytics/sessions/sess-id/events`
- **THEN** система возвращает ВСЕ события для сессии, включая системные (TOOL_REQUEST, CONTEXT_RETRIEVED и т.д.) в хронологическом порядке (created_at ASC)

#### Scenario: User isolation для аналитических events
- **WHEN** пользователь A пытается получить события сессии, принадлежащей пользователю B
- **THEN** система возвращает 404 NOT FOUND (не 403, чтобы не раскрывать существование ресурса)

### Requirement: Analytics endpoint для статистики взаимодействий
Система ДОЛЖНА предоставлять endpoint `GET /my/projects/{project_id}/analytics` для получения статистики и метрик проекта.

#### Scenario: Статистика по типам событий
- **WHEN** клиент отправляет `GET /my/projects/abc123/analytics`
- **THEN** система возвращает объект с полем event_type_counts: { "MESSAGE_CREATED": 150, "TOOL_REQUEST": 42, "ERROR": 3, ... }

#### Scenario: Статистика по агентам
- **WHEN** клиент отправляет `GET /my/projects/abc123/analytics`
- **THEN** система возвращает поле agent_interactions: [{ agent_id: "...", agent_name: "...", event_count: 50, ... }, ...]

#### Scenario: Статистика ошибок
- **WHEN** клиент отправляет `GET /my/projects/abc123/analytics`
- **THEN** система возвращает поле error_stats: { total_errors: 3, error_types: { "InvalidToolError": 2, "TimeoutError": 1 }, ... }

#### Scenario: Статистика за период
- **WHEN** клиент отправляет `GET /my/projects/abc123/analytics?start_time=2026-02-20T00:00:00Z&end_time=2026-02-23T23:59:59Z`
- **THEN** система возвращает аналитику только за указанный период

### Requirement: Response schema для event в API
API endpoints ДОЛЖНЫ возвращать события в унифицированном формате.

#### Scenario: Структура события в response
- **WHEN** клиент получает ответ от `/events`
- **THEN** каждое событие содержит поля: id (UUID), session_id, user_id (для своих событий), agent_id (может быть null), event_type, payload, created_at

#### Scenario: Payload доступен как object
- **WHEN** клиент десериализует JSON ответ
- **THEN** поле payload доступно как JSON object (не string), может быть любая структура

#### Scenario: Pagination metadata в response
- **WHEN** клиент получает ответ от `/events` с пагинацией
- **THEN** response содержит поля: events (array), total (int), limit (int), offset (int)

### Requirement: Error handling для analytics endpoints
Endpoints ДОЛЖНЫ обрабатывать ошибки и возвращать соответствующие HTTP status коды.

#### Scenario: 404 для несуществующего проекта
- **WHEN** клиент отправляет `GET /my/projects/nonexistent-id/events`
- **THEN** система возвращает 404 NOT FOUND

#### Scenario: 400 для invalid query parameters
- **WHEN** клиент отправляет `GET /my/projects/abc123/events?limit=10000` (превышает максимум)
- **THEN** система возвращает 400 BAD REQUEST с описанием ошибки

#### Scenario: 400 для invalid date format
- **WHEN** клиент отправляет `GET /my/projects/abc123/events?start_time=invalid-date`
- **THEN** система возвращает 400 BAD REQUEST с сообщением об invalid ISO 8601 format

### Requirement: Performance и пагинация limits
API ДОЛЖНА иметь ограничения для предотвращения performance issues.

#### Scenario: Максимальный limit для одного запроса
- **WHEN** клиент отправляет `GET /my/projects/abc123/events?limit=200`
- **THEN** система обрезает limit до 100 (максимум) и возвращает только 100 событий

#### Scenario: Default limit
- **WHEN** клиент отправляет `GET /my/projects/abc123/events` без параметра limit
- **THEN** система использует default limit=50

#### Scenario: Максимальный диапазон времени
- **WHEN** клиент отправляет `GET /my/projects/abc123/events?start_time=2025-01-01T00:00:00Z&end_time=2026-12-31T23:59:59Z`
- **THEN** система обрезает диапазон к разумному значению (например, 90 дней) или возвращает 400

### Requirement: User isolation для всех analytics endpoints
Все endpoints ДОЛЖНЫ проверять, что текущий пользователь имеет доступ к проекту и его событиям.

#### Scenario: User может видеть только свои события
- **WHEN** пользователь A получает `/my/projects/proj-id/events`
- **THEN** система возвращает только события сессий пользователя A в этом проекте (event_logs.user_id == current_user_id)

#### Scenario: User not member of project
- **WHEN** пользователь A пытается получить события проекта, к которому не имеет доступа
- **THEN** система возвращает 404 (проект невидим для пользователя)

### Requirement: Интеграция с EventRepository
Analytics endpoints ДОЛЖНЫ использовать EventRepository для выполнения запросов к БД.

#### Scenario: EventRepository.get_events()
- **WHEN** endpoint вызывает `await event_repo.get_events(user_id, project_id, filters)`
- **THEN** метод возвращает список EventLog объектов с применением фильтров

#### Scenario: EventRepository.get_analytics()
- **WHEN** endpoint вызывает `await event_repo.get_analytics(user_id, project_id)`
- **THEN** метод возвращает объект с полями: event_type_counts, agent_interactions, error_stats, etc.

### Requirement: Chat history содержит только user-facing сообщения
История чата (из существующего endpoint `GET /my/projects/{project_id}/chat/{session_id}/messages/`) ДОЛЖНА содержать только сообщения, предназначенные для пользователя, исключая внутренние системные события и промежуточные логи агентов.

#### Scenario: Chat history возвращает только user-facing сообщения
- **WHEN** клиент запрашивает `GET /my/projects/{project_id}/chat/{session_id}/messages/`
- **THEN** система возвращает только Message объекты (роль: user, assistant, system с user-friendly ошибками), исключая системные события типов TOOL_REQUEST, TOOL_RESULT, CONTEXT_RETRIEVED и другие внутренние события

#### Scenario: Distinction между chat history и analytics events
- **WHEN** клиент требует разные данные:
  - Chat UI: пользователь видит историю чата (`/chat/{session_id}/messages/`) - только user-facing сообщения
  - Analytics: аналитик получает все события (`/events?...` или `/analytics/sessions/{session_id}/events`) - включая системные события
- **THEN** эти два endpoint возвращают разные наборы данных: первый - только Message объекты, второй - все Event объекты включая TOOL_REQUEST, CONTEXT_RETRIEVED и т.д.

#### Scenario: Agent output в chat history
- **WHEN** агент генерирует ответ пользователю
- **THEN** Message в `/chat/{session_id}/messages/` содержит только финальный output для показа пользователю, не содержит внутренний reasoning, промежуточные шаги, или debug информацию

#### Scenario: Error messages как user-facing events в chat
- **WHEN** происходит ошибка при обработке сообщения
- **THEN** в `/chat/{session_id}/messages/` появляется Message (role: system) с user-friendly error message (не raw exception)
