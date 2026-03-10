# langfuse-integration Specification (Delta)

## ADDED Requirements

### Requirement: LangfuseIntegration service

Приложение ДОЛЖНО иметь обертку (service) вокруг Langfuse SDK для unified интеграции.

#### Scenario: Инициализация сервиса
- **WHEN** приложение запускается
- **THEN** LangfuseIntegration читает LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST из config
- **AND** если Langfuse недоступен, сервис переходит в режим disabled (enabled=False)
- **AND** все методы gracefully return None если disabled

#### Scenario: Методы сервиса
- **WHEN** код вызывает langfuse.create_trace(), langfuse.create_span(), langfuse.record_score()
- **THEN** методы направляют запросы в Langfuse API или return None если disabled

#### Scenario: Обработка ошибок
- **WHEN** Langfuse API вернет ошибку
- **THEN** ошибка логируется но не пробрасывается (fail-safe)
- **AND** приложение продолжает работу без трейсинга

### Requirement: Docker Compose для Langfuse

Система ДОЛЖНА поддерживать развертывание self-hosted Langfuse через Docker Compose.

#### Scenario: Развертывание Langfuse stack
- **WHEN** выполняется docker-compose up -d langfuse
- **THEN** запускаются: langfuse-postgres (PostgreSQL 16), langfuse (web app), Redis (кэш)
- **AND** healthchecks настроены для каждого сервиса
- **AND** environment variables загружаются из .env

#### Scenario: Конфигурация базы данных
- **WHEN** Langfuse инициализируется
- **THEN** DATABASE_URL=postgresql://langfuse:${LANGFUSE_DB_PASSWORD}@langfuse-postgres:5432/langfuse
- **AND** таблицы автоматически создаются при первом запуске

#### Scenario: Интеграция с существующей сетью
- **WHEN** codelab-core-service запускается
- **THEN** LANGFUSE_HOST=http://langfuse:3000 (в той же Docker сети)
- **AND** приложение может подключиться к Langfuse через http://langfuse:3000

### Requirement: Политика хранения данных

Система ДОЛЖНА автоматически удалять старые traces в соответствии с retention policy.

#### Scenario: Удаление traces старше 90 дней
- **WHEN** крон-задача запускается ежедневно в 02:00 UTC
- **THEN** traces созданные более 90 дней назад удаляются из базы
- **AND** перед удалением опционально архивируются в S3

#### Scenario: Конфигурируемый период хранения
- **WHEN** устанавливается LANGFUSE_RETENTION_DAYS=60
- **THEN** retention policy использует 60 дней вместо default 90

### Requirement: Мониторинг и health checks

Система ДОЛЖНА предоставлять health check для Langfuse.

#### Scenario: Health check endpoint
- **WHEN** клиент отправляет GET /health/langfuse
- **THEN** система пытается подключиться к Langfuse и выполнить простой запрос
- **AND** если успех: {status: "healthy", service: "langfuse"}
- **AND** если ошибка: {status: "unhealthy", service: "langfuse", error: "..."}, HTTP 503

#### Scenario: Метрики для мониторинга
- **WHEN** prometheus scrapes метрики
- **THEN** доступны: langfuse_traces_total, langfuse_spans_total, langfuse_callback_failures, langfuse_db_size

### Requirement: API ключи Langfuse НЕ логируются

Система ДОЛЖНА гарантировать что API ключи НИКОГДА не попадают в логи.

#### Scenario: Безопасность при инициализации
- **WHEN** LangfuseIntegration инициализируется с public/secret ключами
- **THEN** ключи НЕ логируются даже если произойдет ошибка
- **AND** логируется только erfolg/fail статус инициализации

#### Scenario: Безопасность при ошибках
- **WHEN** Langfuse API возвращает 401 Unauthorized
- **THEN** error message логируется как "Langfuse authentication failed" но не содержит самих ключей
