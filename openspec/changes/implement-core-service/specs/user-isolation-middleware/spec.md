# Спецификация: User Isolation Middleware

## ADDED Requirements

### Requirement: Извлечение JWT токена
Middleware ДОЛЖЕН извлекать user_id из JWT токена в заголовке Authorization для всех запросов к `/my/*` endpoints.

#### Scenario: Валидный JWT токен
- **WHEN** запрос содержит валидный JWT токен в заголовке Authorization
- **THEN** middleware извлекает user_id и инжектирует его в request.state.user_id

#### Scenario: Отсутствует заголовок Authorization
- **WHEN** запрос к `/my/*` endpoint не содержит заголовок Authorization
- **THEN** middleware возвращает 401 Unauthorized с сообщением "Missing authorization token"

#### Scenario: Невалидный JWT токен
- **WHEN** запрос содержит некорректный или истекший JWT токен
- **THEN** middleware возвращает 401 Unauthorized с сообщением "Invalid or expired token"

#### Scenario: Незащищенный endpoint
- **WHEN** запрос к endpoint не начинающемуся с `/my/`
- **THEN** middleware пропускает запрос без JWT валидации

### Requirement: Инжекция контекста пользователя
Middleware ДОЛЖЕН инжектировать контекст пользователя в request.state для использования в handlers.

#### Scenario: Успешная инжекция контекста
- **WHEN** user_id успешно извлечен из JWT
- **THEN** middleware инжектирует request.state.user_id, request.state.user_prefix (формат: "user{id}"), и request.state.db_filter (dict: {"user_id": user_id})

#### Scenario: Доступность контекста в handlers
- **WHEN** request handler обращается к request.state.user_id
- **THEN** handler получает ID аутентифицированного пользователя без дополнительного парсинга

### Requirement: Автоматическая фильтрация запросов
Middleware ДОЛЖЕН предоставлять db_filter в request.state для автоматической фильтрации всех database queries по user_id.

#### Scenario: Database query с фильтром
- **WHEN** handler выполняет database query используя request.state.db_filter
- **THEN** query автоматически фильтрует результаты только для записей аутентифицированного пользователя

#### Scenario: Валидация формата фильтра
- **WHEN** middleware создает db_filter
- **THEN** фильтр является словарем с ключом "user_id" и значением ID аутентифицированного пользователя

### Requirement: Контроль доступа
Middleware ДОЛЖЕН обеспечивать доступ пользователей только к их собственным ресурсам через `/my/*` endpoints.

#### Scenario: Пользователь обращается к своим ресурсам
- **WHEN** аутентифицированный пользователь делает запрос к `/my/agents/`
- **THEN** middleware разрешает запрос и инжектирует контекст пользователя

#### Scenario: Попытка несанкционированного доступа
- **WHEN** запрос пытается получить доступ к `/my/*` без валидной аутентификации
- **THEN** middleware блокирует запрос с 401 Unauthorized до достижения handler

### Requirement: Нулевые нарушения изоляции
Middleware ДОЛЖЕН обеспечивать нулевые нарушения изоляции между пользователями со 100% enforcement.

#### Scenario: Предотвращение cross-user доступа
- **WHEN** User123 аутентифицирован и делает любой запрос
- **THEN** middleware гарантирует что User123 не может получить доступ к данным User456 через автоматическую фильтрацию

#### Scenario: Предотвращение обхода middleware
- **WHEN** любой запрос к защищенному endpoint выполняется
- **THEN** middleware выполняется до любой handler логики, предотвращая обход

### Requirement: Формат ответов об ошибках
Middleware ДОЛЖЕН возвращать стандартизированные ответы об ошибках при сбоях аутентификации.

#### Scenario: Ответ об ошибке аутентификации
- **WHEN** аутентификация не удалась по любой причине
- **THEN** middleware возвращает JSON ответ с полями: {"detail": "error message", "error_code": "AUTH_ERROR", "timestamp": "ISO8601"}

#### Scenario: HTTP статус коды
- **WHEN** аутентификация не удалась
- **THEN** middleware возвращает 401 для отсутствующих/невалидных токенов и 403 для ошибок авторизации

### Requirement: Требования к производительности
Middleware ДОЛЖЕН обрабатывать аутентификацию с минимальной задержкой.

#### Scenario: Производительность JWT валидации
- **WHEN** middleware валидирует JWT токен
- **THEN** валидация завершается менее чем за 5ms (P95)

#### Scenario: Производительность инжекции контекста
- **WHEN** middleware инжектирует контекст пользователя
- **THEN** инжекция завершается менее чем за 1ms (P99)

### Requirement: Логирование и мониторинг
Middleware ДОЛЖЕН логировать события аутентификации для мониторинга безопасности.

#### Scenario: Логирование успешной аутентификации
- **WHEN** пользователь успешно аутентифицируется
- **THEN** middleware логирует событие с user_id, endpoint, timestamp и IP адресом

#### Scenario: Логирование неудачной аутентификации
- **WHEN** аутентификация не удалась
- **THEN** middleware логирует сбой с причиной, attempted endpoint, timestamp и IP адресом для security audit

#### Scenario: Обнаружение нарушений изоляции
- **WHEN** обнаружено потенциальное нарушение изоляции
- **THEN** middleware логирует критическое предупреждение с полными деталями запроса для немедленного расследования
