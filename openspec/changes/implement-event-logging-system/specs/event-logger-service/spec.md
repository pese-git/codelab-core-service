# Specification: Event Logger Service

## ADDED Requirements

### Requirement: EventLogger асинхронный сервис с буферизацией
Система ДОЛЖНА предоставлять EventLogger сервис, который логирует события асинхронно с буферизацией и batch insert для оптимизации производительности.

#### Scenario: Логирование события без блокирования
- **WHEN** код вызывает `await event_logger.log_event(event, user_id, project_id)`
- **THEN** метод возвращает управление немедленно (неблокирующий), событие добавляется в очередь буфера

#### Scenario: Batch insert при достижении размера буфера
- **WHEN** буфер накопил 100 событий (по умолчанию)
- **THEN** фоновая задача пакетно вставляет все события в БД single INSERT query

#### Scenario: Flush по таймеру
- **WHEN** прошло 100 миллисекунд с последней вставки
- **THEN** все накопленные в буфере события вставляются в БД, даже если буфер не полный

#### Scenario: Graceful shutdown
- **WHEN** приложение останавливается
- **THEN** EventLogger ждет завершения всех pending операций и вставляет оставшиеся события перед shutdown

### Requirement: EventLogger инициализируется при запуске приложения
EventLogger ДОЛЖЕН быть инициализирован как singleton при запуске FastAPI приложения и зарегистрирован в зависимостях.

#### Scenario: EventLogger доступен через dependency injection
- **WHEN** эндпоинт имеет параметр `event_logger: EventLogger = Depends(get_event_logger)`
- **THEN** Dependency получает текущий экземпляр EventLogger

#### Scenario: Lifecycle управление в app/main.py
- **WHEN** приложение стартует (event lifespan.startup)
- **THEN** EventLogger инициализируется и фоновая задача для batch worker запускается

#### Scenario: Cleanup при shutdown
- **WHEN** приложение завершает работу (event lifespan.shutdown)
- **THEN** batch worker задача отменяется, оставшиеся события вставляются, соединение закрывается

### Requirement: EventLogger обрабатывает ошибки логирования
EventLogger ДОЛЖЕН обрабатывать ошибки БД и сетевые ошибки без прерывания основного потока выполнения.

#### Scenario: Ошибка при вставке логируется, но не выбрасывается
- **WHEN** batch insert в БД падает с DatabaseError
- **THEN** ошибка логируется через logger.error(), но исключение не пробрасывается наружу (batch worker продолжает работать)

#### Scenario: Retry логика при временных ошибках
- **WHEN** наблюдается временная ошибка БД (connection timeout)
- **THEN** EventLogger повторяет попытку insert с exponential backoff (1ms, 2ms, 4ms)

### Requirement: Структура и метод EventLogger
EventLogger класс ДОЛЖЕН иметь следующий интерфейс:

#### Scenario: Метод log_event
- **WHEN** код вызывает `event_logger.log_event(event: StreamEvent, user_id: UUID, project_id: UUID)`
- **THEN** метод с типом возврата Coroutine[Any, Any, None], дозволяет асинхронный вызов

#### Scenario: Внутренняя очередь буфера
- **WHEN** EventLogger инициализируется
- **THEN** создается asyncio.Queue с максимальным размером 10000 для буферизации событий

#### Scenario: Конфигурируемый размер батча и интервал flush
- **WHEN** EventLogger инициализируется с параметрами `buffer_size=100, flush_interval=0.1`
- **THEN** батч insert выполняется при 100 событиях или через 100ms

### Requirement: EventLogger преобразует StreamEvent в EventLog
EventLogger ДОЛЖЕН преобразовывать incoming StreamEvent в EventLog модель для сохранения в БД.

#### Scenario: Payload сохраняется как JSONB
- **WHEN** event имеет payload (dict)
- **THEN** payload сохраняется как JSONB в колонке event_logs.payload

#### Scenario: Денормализованные поля заполняются из payload
- **WHEN** event_type == "ERROR"
- **THEN** error_code извлекается из event.payload['error_code'] и сохраняется в денормализованную колонку

#### Scenario: agent_id может быть NULL
- **WHEN** событие не относится к агенту (например, TASK_PLAN_CREATED)
- **THEN** agent_id устанавливается в NULL

### Requirement: Unit тесты для EventLogger
Код ДОЛЖЕН иметь полное покрытие тестами для EventLogger функциональности.

#### Scenario: Тест асинхронного логирования
- **WHEN** выполняется `await event_logger.log_event(event, user_id, project_id)`
- **THEN** тест проверяет, что событие добавилось в буфер и не осталось в памяти бесконечно

#### Scenario: Тест batch insert
- **WHEN** буфер содержит 100 событий
- **THEN** тест с mocked БД проверяет, что вставлялся 1 batch insert query, не 100 individual queries

#### Scenario: Тест обработки ошибок
- **WHEN** мок БД выбрасывает DatabaseError при insert
- **THEN** тест проверяет, что EventLogger логирует ошибку и продолжает работать (не выбрасывает исключение)
