# Спецификация: REST API Endpoints

## ADDED Requirements

### Requirement: Project management endpoints
Система ДОЛЖНА предоставлять REST API endpoints для управления проектами.

#### Scenario: POST /my/projects/ - создание проекта с Default Starter Pack
- **WHEN** пользователь отправляет POST `/my/projects/` с name и workspace_path
- **THEN** система создает проект и автоматически создает 4 default агентов
- **AND** возвращает 201 Created с project_id и списком агентов
- **AND** User Worker Space инициализирован и готов к использованию

#### Scenario: GET /my/projects/ - список проектов
- **WHEN** пользователь отправляет GET `/my/projects/`
- **THEN** система возвращает 200 OK с массивом всех проектов пользователя

#### Scenario: GET /my/projects/{project_id}/ - получение проекта
- **WHEN** пользователь отправляет GET `/my/projects/{project_id}/`
- **THEN** система возвращает 200 OK с деталями проекта и списком агентов

#### Scenario: PUT /my/projects/{project_id}/ - обновление проекта
- **WHEN** пользователь отправляет PUT `/my/projects/{project_id}/` с обновленными данными
- **THEN** система обновляет проект и возвращает 200 OK

#### Scenario: DELETE /my/projects/{project_id}/ - удаление проекта
- **WHEN** пользователь отправляет DELETE `/my/projects/{project_id}/`
- **THEN** система удаляет проект и очищает backend ресурсы (User Worker Space)
- **AND** файлы в User Workspace НЕ удаляются
- **AND** возвращает 204 No Content

### Requirement: Agent management endpoints (Updated for per-project)
Система ДОЛЖНА предоставлять REST API endpoints для управления агентами в контексте проекта.

#### Scenario: GET /my/agents/ - список агентов
- **WHEN** пользователь отправляет GET `/my/agents/`
- **THEN** система возвращает 200 OK с массивом агентов пользователя

#### Scenario: POST /my/agents/ - создание агента
- **WHEN** пользователь отправляет POST `/my/agents/` с валидной конфигурацией
- **THEN** система создает агента и возвращает 201 Created с данными агента

#### Scenario: GET /my/agents/{agent_id} - получение агента
- **WHEN** пользователь отправляет GET `/my/agents/{agent_id}`
- **THEN** система возвращает 200 OK с полной конфигурацией агента

#### Scenario: PUT /my/agents/{agent_id} - обновление агента
- **WHEN** пользователь отправляет PUT `/my/agents/{agent_id}` с обновленной конфигурацией
- **THEN** система обновляет агента и возвращает 200 OK

#### Scenario: DELETE /my/agents/{agent_id} - удаление агента
- **WHEN** пользователь отправляет DELETE `/my/agents/{agent_id}`
- **THEN** система удаляет агента и возвращает 204 No Content

### Requirement: Orchestrator configuration endpoints
Система ДОЛЖНА предоставлять endpoints для конфигурации orchestrator.

#### Scenario: GET /my/orchestrator/config - получение конфигурации
- **WHEN** пользователь отправляет GET `/my/orchestrator/config`
- **THEN** система возвращает 200 OK с текущей конфигурацией orchestrator

#### Scenario: PUT /my/orchestrator/config - обновление конфигурации
- **WHEN** пользователь отправляет PUT `/my/orchestrator/config` с новыми настройками
- **THEN** система обновляет конфигурацию и возвращает 200 OK

#### Scenario: POST /my/orchestrator/plan - создание плана
- **WHEN** пользователь отправляет POST `/my/orchestrator/plan` с запросом
- **THEN** система создает план без выполнения и возвращает 200 OK с графом задач

#### Scenario: GET /my/orchestrator/plans/{plan_id} - получение плана
- **WHEN** пользователь отправляет GET `/my/orchestrator/plans/{plan_id}`
- **THEN** система возвращает 200 OK с деталями плана и его статусом

### Requirement: Chat endpoints
Система ДОЛЖНА предоставлять endpoints для управления чатами и сообщениями.

#### Scenario: POST /my/projects/{project_id}/chat/sessions/ - создание сессии
- **WHEN** пользователь отправляет POST `/my/projects/{project_id}/chat/sessions/`
- **THEN** система создает новую сессию в контексте проекта
- **AND** возвращает 201 Created с session_id

#### Scenario: GET /my/projects/{project_id}/chat/sessions/ - список сессий
- **WHEN** пользователь отправляет GET `/my/projects/{project_id}/chat/sessions/`
- **THEN** система возвращает 200 OK с массивом сессий проекта

#### Scenario: GET /my/projects/{project_id}/chat/sessions/{session_id} - получение сессии
- **WHEN** пользователь отправляет GET `/my/projects/{project_id}/chat/sessions/{session_id}`
- **THEN** система возвращает 200 OK с деталями сессии

#### Scenario: DELETE /my/projects/{project_id}/chat/sessions/{session_id} - удаление сессии
- **WHEN** пользователь отправляет DELETE `/my/projects/{project_id}/chat/sessions/{session_id}`
- **THEN** система удаляет сессию и возвращает 204 No Content

#### Scenario: POST /my/projects/{project_id}/chat/{session_id}/message/ - отправка сообщения
- **WHEN** пользователь отправляет POST `/my/projects/{project_id}/chat/{session_id}/message/` с content
- **THEN** система обрабатывает сообщение в контексте Worker Space проекта
- **AND** возвращает 202 Accepted

#### Scenario: GET /my/projects/{project_id}/chat/{session_id}/messages/ - история сообщений
- **WHEN** пользователь отправляет GET `/my/projects/{project_id}/chat/{session_id}/messages/`
- **THEN** система возвращает 200 OK с сообщениями сессии проекта

#### Scenario: GET /my/projects/{project_id}/chat/{session_id}/events/ - SSE stream
- **WHEN** пользователь отправляет GET `/my/projects/{project_id}/chat/{session_id}/events/`
- **THEN** система устанавливает SSE connection для проекта
- **AND** начинает отправку событий Worker Space

### Requirement: Approval endpoints
Система ДОЛЖНА предоставлять endpoints для управления approvals.

#### Scenario: GET /my/projects/{project_id}/approvals/ - список approvals
- **WHEN** пользователь отправляет GET `/my/projects/{project_id}/approvals/`
- **THEN** система возвращает 200 OK с approval requests проекта

#### Scenario: GET /my/projects/{project_id}/approvals/{approval_id} - получение approval
- **WHEN** пользователь отправляет GET `/my/projects/{project_id}/approvals/{approval_id}`
- **THEN** система возвращает 200 OK с деталями approval request

#### Scenario: POST /my/projects/{project_id}/approvals/{approval_id}/confirm - подтверждение
- **WHEN** пользователь отправляет POST `/my/projects/{project_id}/approvals/{approval_id}/confirm` с decision
- **THEN** система обрабатывает решение в контексте проекта
- **AND** возвращает 200 OK

#### Scenario: POST /my/projects/{project_id}/approvals/batch-confirm - batch подтверждение
- **WHEN** пользователь отправляет POST `/my/projects/{project_id}/approvals/batch-confirm` с массивом approval_ids
- **THEN** система обрабатывает все approvals проекта
- **AND** возвращает 200 OK с результатами

### Requirement: Context management endpoints
Система ДОЛЖНА предоставлять endpoints для управления контекстом агентов.

#### Scenario: GET /my/agents/{agent_id}/context/stats - статистика контекста
- **WHEN** пользователь отправляет GET `/my/agents/{agent_id}/context/stats`
- **THEN** система возвращает 200 OK со статистикой Qdrant collection

#### Scenario: POST /my/agents/{agent_id}/context/search - поиск в контексте
- **WHEN** пользователь отправляет POST `/my/agents/{agent_id}/context/search` с query
- **THEN** система выполняет RAG поиск и возвращает 200 OK с результатами

#### Scenario: DELETE /my/agents/{agent_id}/context/clear - очистка контекста
- **WHEN** пользователь отправляет DELETE `/my/agents/{agent_id}/context/clear`
- **THEN** система очищает Qdrant collection и возвращает 204 No Content

#### Scenario: POST /my/agents/{agent_id}/context/prune - pruning контекста
- **WHEN** пользователь отправляет POST `/my/agents/{agent_id}/context/prune` с параметрами
- **THEN** система удаляет старые vectors и возвращает 200 OK с количеством удаленных

#### Scenario: GET /my/agents/{agent_id}/context/export - экспорт контекста
- **WHEN** пользователь отправляет GET `/my/agents/{agent_id}/context/export`
- **THEN** система возвращает 200 OK с JSON файлом контекста

### Requirement: JWT Authentication
Все endpoints под `/my/*` ДОЛЖНЫ требовать JWT authentication.

#### Scenario: Запрос с валидным JWT
- **WHEN** запрос содержит валидный JWT токен в Authorization header
- **THEN** middleware извлекает user_id и endpoint обрабатывает запрос

#### Scenario: Запрос без JWT
- **WHEN** запрос к `/my/*` не содержит Authorization header
- **THEN** система возвращает 401 Unauthorized

#### Scenario: Запрос с истекшим JWT
- **WHEN** запрос содержит истекший JWT токен
- **THEN** система возвращает 401 Unauthorized с сообщением "Token expired"

#### Scenario: Формат Authorization header
- **WHEN** JWT токен отправляется
- **THEN** формат header: "Authorization: Bearer {token}"

### Requirement: JSON Schema validation
Все endpoints ДОЛЖНЫ валидировать request/response данные с помощью Pydantic schemas.

#### Scenario: Валидация request body
- **WHEN** пользователь отправляет POST/PUT запрос
- **THEN** система валидирует body против Pydantic schema перед обработкой

#### Scenario: Ошибка валидации
- **WHEN** request body не соответствует schema
- **THEN** система возвращает 422 Unprocessable Entity с деталями ошибок валидации

#### Scenario: Валидация query parameters
- **WHEN** endpoint принимает query параметры
- **THEN** система валидирует их типы и значения

#### Scenario: Response serialization
- **WHEN** endpoint возвращает данные
- **THEN** система сериализует response через Pydantic model

### Requirement: Rate limiting
Система ДОЛЖНА применять rate limiting на все endpoints.

#### Scenario: Rate limit per user
- **WHEN** пользователь делает запросы
- **THEN** система ограничивает до 100 запросов в минуту

#### Scenario: Превышение rate limit
- **WHEN** пользователь превышает 100 req/min
- **THEN** система возвращает 429 Too Many Requests с header Retry-After

#### Scenario: Rate limit headers
- **WHEN** запрос обрабатывается
- **THEN** response содержит headers: X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset

#### Scenario: Разные лимиты для разных endpoints
- **WHEN** endpoint требует больше ресурсов (например, /context/search)
- **THEN** система применяет более строгий лимит (например, 20 req/min)

### Requirement: Swagger documentation
Система ДОЛЖНА предоставлять автоматически генерируемую Swagger документацию.

#### Scenario: Доступ к Swagger UI
- **WHEN** пользователь открывает `/my/docs`
- **THEN** система отображает Swagger UI со всеми endpoints

#### Scenario: OpenAPI schema
- **WHEN** пользователь запрашивает `/my/openapi.json`
- **THEN** система возвращает полную OpenAPI 3.0 спецификацию

#### Scenario: Документация endpoints
- **WHEN** endpoint определен
- **THEN** Swagger содержит: описание, параметры, request/response schemas, примеры

#### Scenario: Try it out функциональность
- **WHEN** пользователь использует Swagger UI
- **THEN** можно тестировать endpoints с JWT authentication

### Requirement: Error responses
Система ДОЛЖНА возвращать стандартизированные error responses.

#### Scenario: Формат error response
- **WHEN** происходит ошибка
- **THEN** response содержит JSON: {"detail": "message", "error_code": "CODE", "timestamp": "ISO8601"}

#### Scenario: 400 Bad Request
- **WHEN** запрос некорректно сформирован
- **THEN** система возвращает 400 с деталями проблемы

#### Scenario: 404 Not Found
- **WHEN** ресурс не найден
- **THEN** система возвращает 404 с сообщением "Resource not found"

#### Scenario: 422 Unprocessable Entity
- **WHEN** валидация данных не прошла
- **THEN** система возвращает 422 с массивом validation errors

#### Scenario: 500 Internal Server Error
- **WHEN** происходит внутренняя ошибка
- **THEN** система возвращает 500 и логирует полный stack trace

#### Scenario: Isolation violation error
- **WHEN** обнаружена попытка нарушения изоляции
- **THEN** система возвращает 403 Forbidden с деталями нарушения

### Requirement: CORS configuration
Система ДОЛЖНА корректно настраивать CORS для frontend интеграции.

#### Scenario: CORS headers
- **WHEN** frontend делает запрос
- **THEN** система возвращает корректные CORS headers: Access-Control-Allow-Origin, Access-Control-Allow-Methods

#### Scenario: Preflight requests
- **WHEN** браузер отправляет OPTIONS preflight request
- **THEN** система возвращает 200 OK с разрешенными методами и headers

#### Scenario: Credentials support
- **WHEN** frontend отправляет credentials
- **THEN** система поддерживает Access-Control-Allow-Credentials: true

#### Scenario: Конфигурируемые origins
- **WHEN** система настраивается
- **THEN** можно указать список разрешенных origins в конфигурации

### Requirement: Pagination support
Endpoints возвращающие списки ДОЛЖНЫ поддерживать pagination.

#### Scenario: Pagination параметры
- **WHEN** endpoint возвращает список
- **THEN** поддерживаются query параметры: limit (default 50, max 100), offset (default 0)

#### Scenario: Pagination metadata
- **WHEN** список возвращается с pagination
- **THEN** response содержит: total_count, limit, offset, has_next

#### Scenario: Cursor-based pagination для больших списков
- **WHEN** список очень большой (например, messages)
- **THEN** endpoint поддерживает cursor-based pagination с параметром cursor

#### Scenario: Ссылки на следующую/предыдущую страницу
- **WHEN** pagination используется
- **THEN** response содержит links: next_url, prev_url (если применимо)

### Requirement: Filtering и sorting
List endpoints ДОЛЖНЫ поддерживать фильтрацию и сортировку.

#### Scenario: Фильтрация по полям
- **WHEN** пользователь запрашивает список с query параметрами (например, `?status=ready`)
- **THEN** система возвращает только записи соответствующие фильтру

#### Scenario: Множественные фильтры
- **WHEN** пользователь применяет несколько фильтров (например, `?status=ready&type=coder`)
- **THEN** система применяет все фильтры с логикой AND

#### Scenario: Sorting
- **WHEN** пользователь указывает `?sort_by=created_at&order=desc`
- **THEN** система возвращает список отсортированный по указанному полю

#### Scenario: Валидация фильтров
- **WHEN** пользователь указывает невалидное поле для фильтрации
- **THEN** система возвращает 400 Bad Request с сообщением о невалидном поле
