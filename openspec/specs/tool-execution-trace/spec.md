# Specification: Tool Execution Trace System

## Обзор
Система трассировки для полного отслеживания flow выполнения инструментов от запроса пользователя до ответа агента, включая промежуточные этапы валидации, risk assessment, одобрения и выполнения.

---

## SECTION: OpenTelemetry Instrumentation

### Requirement: Инициализация OpenTelemetry в приложении
Приложение ДОЛЖНО инициализировать OpenTelemetry с OTLPSpanExporter при старте.

#### Scenario: Трассировка включена при старте
- **WHEN** приложение запускается с `enable_tracing=true`
- **THEN** создается `TracerProvider` с сервисом `codelab-core-service`
- **AND** добавляется `BatchSpanProcessor` с `OTLPSpanExporter`
- **AND** автоматически инструментируются FastAPI и SQLAlchemy

#### Scenario: Трассировка может быть отключена
- **WHEN** приложение запускается с `enable_tracing=false`
- **THEN** инициализация пропускается
- **AND** no-op трейсер используется

#### Scenario: OTLP эксортер доступен на конфигурируемом адресе
- **WHEN** настроена `OTLP_EXPORTER_URL` (по умолчанию `http://localhost:4318`)
- **THEN** `OTLPSpanExporter` подключается к этому адресу
- **AND** spans отправляются на этот адрес через HTTP protocol

### Requirement: Основные span операции
Система ДОЛЖНА создавать spans для основных операций message processing и tool execution.

#### Scenario: message_processing span
- **WHEN** пользователь отправляет сообщение в `send_project_message`
- **THEN** создается span с именем `message_processing`
- **AND** span содержит атрибуты: `session.id`, `user.id`, `project.id`
- **AND** span обхватывает весь flow до отправки ответа

#### Scenario: agent_execution span
- **WHEN** агент выполняет `execute()`
- **THEN** создается span с именем `agent_execution`
- **AND** span содержит атрибуты: `agent.id`, `agent.name`, `model`
- **AND** это child span от `message_processing`

#### Scenario: llm_call span
- **WHEN** вызывается `openai_client.chat.completions.create()`
- **THEN** создается span с именем `llm_call`
- **AND** span содержит атрибуты: `model`, `temperature`, `provider`
- **AND** span содержит метрики: `latency_ms`, `tokens_prompt`, `tokens_completion`, `tokens_total`
- **AND** это child span от `agent_execution`

#### Scenario: tool_execution span
- **WHEN** вызывается `ToolExecutor.execute_tool()`
- **THEN** создается span с именем `tool_execution`
- **AND** span содержит атрибуты: `tool.name`
- **AND** span содержит child spans: `tool_validation`, `risk_assessment`, `approval_workflow`, `client_execution`
- **AND** это child span от `agent_execution`

#### Scenario: tool_validation span
- **WHEN** вызывается `_validate_tool_params()`
- **THEN** создается child span `tool_validation` от `tool_execution`
- **AND** span содержит атрибут: `validation_status` (passed/failed)
- **AND** если ошибка, span содержит event `validation_error` с сообщением

#### Scenario: risk_assessment span
- **WHEN** вызывается `risk_assessor.assess_tool_risk()`
- **THEN** создается child span `risk_assessment` от `tool_execution`
- **AND** span содержит атрибуты: `risk_level`, `risk_score`

#### Scenario: approval_workflow span
- **WHEN** требуется одобрение (HIGH/MEDIUM risk)
- **THEN** создается child span `approval_workflow` от `tool_execution`
- **AND** span содержит атрибуты: `approval_id`, `timeout_seconds`
- **AND** span содержит атрибут: `approval_status` (approved/rejected)

#### Scenario: client_execution span
- **WHEN** отправляется запрос на клиент для выполнения инструмента
- **THEN** создается child span `client_execution` от `tool_execution`
- **AND** span содержит атрибут: `request_sent` (true/false)

### Requirement: Span атрибуты и события
Spans ДОЛЖНЫ содержать структурированные атрибуты и события для анализа.

#### Scenario: Span завершение
- **WHEN** операция завершается
- **THEN** span автоматически содержит duration_ms (рассчитывается как разница start_time и end_time)
- **AND** span содержит атрибут: `status` (success/failed/pending)

#### Scenario: Span события
- **WHEN** происходят значимые события
- **THEN** они фиксируются через `span.add_event()` с structuredданными
- **EXAMPLES**:
  - `message_received` с `content_length`
  - `llm_response_received` с `model`, `tokens`
  - `tool_executed` с `tool_name`, `status`
  - `validation_error` с `error` сообщением

#### Scenario: Исключения в spans
- **WHEN** возникает исключение в операции
- **THEN** оно фиксируется через `span.record_exception(e)`
- **AND** span содержит атрибут: `status: error`
- **AND** span НЕ повторно выбрасывает исключение (просто записывает)

### Requirement: Контекстная изоляция spans
Spans ДОЛЖНЫ поддерживать иерархию parent-child для вложенных вызовов.

#### Scenario: Parent-child relationship
- **WHEN** span A создает span B внутри себя
- **THEN** span B автоматически устанавливает span A как parent
- **AND** в Jaeger UI видна иерархия

#### Scenario: Concurrent spans
- **WHEN** несколько инструментов выполняются последовательно
- **THEN** каждый инструмент имеет отдельный child span
- **AND** все они имеют одного родителя (`agent_execution`)

---

## SECTION: OTLP Collector и UI Integration

### Requirement: OTLP Collector должен быть доступен локально
OTLP Collector (с Jaeger UI опционально) ДОЛЖЕН быть доступен на `http://localhost:4318` для разработки.

#### Scenario: Docker Compose для OTLP Collector
- **WHEN** запускается `docker-compose -f docker-compose-dev.yml up -d otel-collector`
- **THEN** OTLP Collector контейнер поднимается
- **AND** OTLP receiver слушает на HTTP port 4318 (`/v1/traces` endpoint)
- **AND** Jaeger backend поднимается как часть compose setup
- **AND** Jaeger UI доступен на http://localhost:16686

#### Scenario: OTLP Collector health check
- **WHEN** контейнер поднимается
- **THEN** health check проверяет `/status` endpoint
- **AND** контейнер помечается как healthy

### Requirement: Поиск и фильтрация трейсов в Jaeger
Jaeger ДОЛЖЕН позволять искать трейсы по операциям и тегам.

#### Scenario: Поиск по сервису
- **WHEN** выбирается Service = `codelab-core-service`
- **THEN** отображаются все доступные операции
- **OPTIONS**:
  - `message_processing`
  - `agent_execution`
  - `tool_execution`
  - `llm_call`

#### Scenario: Фильтрация по тегам
- **WHEN** устанавливаются tags фильтры
- **THEN** отображаются только трейсы, соответствующие фильтру
- **EXAMPLES**:
  - `status=error`
  - `tool.name=read_file`
  - `risk_level=high`
  - `model=gpt-4`

#### Scenario: Просмотр деталей трейса
- **WHEN** кликается на трейс в результатах
- **THEN** отображается детальная информация:
  - Timeline всех spans
  - Атрибуты каждого span
  - События и исключения
  - Продолжительность в ms для каждого span

---

## SECTION: Configuration

### Requirement: Конфигурационные параметры
Система ДОЛЖНА быть конфигурируема через environment переменные.

#### Scenario: Параметры OpenTelemetry
- **REQUIRED**:
  - `ENABLE_TRACING` (bool, default=true)
  - `OTLP_EXPORTER_URL` (str, default=http://localhost:4318)

#### Scenario: Парамы для Phase 2 (приготовлены)
- **OPTIONAL** (для будущего use):
  - `ENABLE_TRACE_DB_PERSISTENCE` (bool, default=false)
  - `TRACE_RETENTION_DAYS` (int, default=30)
  - `TRACE_SAMPLING_RATE` (float, default=1.0)
  - `TRACE_BATCH_SIZE` (int, default=512)

#### Scenario: Загрузка из .env
- **WHEN** приложение стартует
- **THEN** параметры загружаются из `.env` через `pydantic_settings`
- **AND** используются значения по умолчанию если не определены

---

## SECTION: Code Integration Points

### Requirement: Инструментация project_chat.py
Маршрут `send_project_message` ДОЛЖЕН создавать `message_processing` span.

#### Scenario: Span обхватывает весь request
- **WHEN** вызывается `send_project_message`
- **THEN** создается span `message_processing` в начале функции
- **AND** span завершается в конце функции (или при исключении)
- **AND** весь код функции находится внутри span контекста

#### Scenario: Атрибуты span
- **THEN** span содержит атрибуты:
  - `message.type: user_message`
  - `session.id`
  - `user.id`
  - `project.id`

#### Scenario: События span
- **THEN** span содержит события:
  - `message_received` при получении
  - `response_generated` при формировании ответа

### Requirement: Инструментация contextual_agent.py
Метод `execute()` ДОЛЖЕН создавать `agent_execution`, `llm_call` и `tool_execution` spans.

#### Scenario: agent_execution span
- **WHEN** вызывается `execute()`
- **THEN** создается span `agent_execution`
- **AND** в начале span содержит атрибуты: `agent.id`, `agent.name`, `model`

#### Scenario: llm_call span
- **WHEN** вызывается `openai_client.chat.completions.create()`
- **THEN** создается child span `llm_call`
- **AND** span содержит атрибуты: `model`, `temperature`, `provider`, `latency_ms`, `tokens_*`
- **AND** span содержит event `llm_response_received`

#### Scenario: tool_execution spans
- **WHEN** есть tool calls в ответе LLM
- **THEN** для каждого инструмента создается child span `tool_execution`
- **AND** внутри имеются child spans: `tool_validation`, `risk_assessment`

### Requirement: Инструментация executor.py
Метод `execute_tool()` ДОЛЖЕН создавать иерархию spans для полного flow.

#### Scenario: tool_execution span
- **WHEN** вызывается `execute_tool()`
- **THEN** создается span `tool_execution` (если нет parent span, иначе child)
- **AND** span содержит атрибут: `tool.name`

#### Scenario: tool_validation span
- **WHEN** вызывается `_validate_tool_params()`
- **THEN** создается child span `tool_validation` от текущего span
- **AND** span содержит атрибут: `validation_status`

#### Scenario: risk_assessment span
- **WHEN** вызывается `risk_assessor.assess_tool_risk()`
- **THEN** создается child span `risk_assessment`
- **AND** span содержит атрибуты: `risk_level`, `risk_score`

#### Scenario: approval_workflow span
- **WHEN** требуется одобрение
- **THEN** создается child span `approval_workflow`
- **AND** span содержит атрибуты: `approval_id`, `approval_status`

---

## SECTION: Performance & Reliability

### Requirement: Минимальный overhead на производительность
Инструментация НЕ ДОЛЖНА существенно увеличивать latency запросов.

#### Scenario: BatchSpanProcessor
- **WHEN** spans экспортируются в Jaeger
- **THEN** используется `BatchSpanProcessor` (async batch export)
- **AND** request-path не блокируется на отправку spans
- **AND** spans буферируются и отправляются batch'ами

#### Scenario: P99 latency guardrail
- **WHEN** инструментация включена
- **THEN** P99 request latency деградирует не более чем на 5% (типично 1-2%)
- **AND** overhead обычно < 10ms на request

### Requirement: Обработка ошибок в трассировке
Ошибки в трассировке НЕ ДОЛЖНЫ влиять на основной flow.

#### Scenario: Jaeger недоступен
- **WHEN** Jaeger не доступен при экспорте spans
- **THEN** spans буферируются и retry выполняется асинхронно
- **AND** request продолжает работать нормально
- **AND** в логах записывается warning

#### Scenario: SpanProcessor ошибка
- **WHEN** возникает ошибка в экспорте
- **THEN** exception не выбрасывается в request-path
- **AND** логируется ошибка для отладки

---

## SECTION: Testing

### Requirement: Unit тесты для трассировки
Система трассировки ДОЛЖНА быть покрыта тестами.

#### Scenario: Инициализация OTel
- **TEST**: проверить что `initialize_tracing()` создает `TracerProvider`
- **TEST**: проверить что tracer доступен через `get_tracer()`
- **TEST**: проверить что инициализация работает при `enable_tracing=false`

#### Scenario: Span creation
- **TEST**: проверить что spans создаются с корректными атрибутами
- **TEST**: проверить что parent-child relationship устанавливается
- **TEST**: проверить что события добавляются в spans

#### Scenario: Exception handling
- **TEST**: проверить что исключения записываются в spans
- **TEST**: проверить что span status устанавливается на error при исключении

### Requirement: Integration тесты
Трассировка ДОЛЖНА работать end-to-end с реальным flow.

#### Scenario: Message processing
- **TEST**: отправить сообщение и проверить что создались все spans:
  - `message_processing`
  - `agent_execution`
  - `llm_call`
  - `tool_execution` (если были tool calls)

#### Scenario: Jaeger export
- **TEST**: экспортировать spans и проверить что они видны в Jaeger
- **REQUIRES**: Jaeger контейнер запущен в test environment

---

## SECTION: Documentation

### Requirement: Документация для разработчиков
Система трассировки ДОЛЖНА быть задокументирована.

#### Scenario: Architectural Documentation
- **FILE**: `doc/TOOL_EXECUTION_TRACE_DESIGN.md`
- **CONTAINS**:
  - Обзор системы и проблемы
  - Architecture diagram
  - Phase 1 vs Phase 2 сравнение
  - Полные примеры span использования

#### Scenario: Code Examples
- **INCLUDE** в документации:
  - Инициализация OTel
  - Примеры spans в contextual_agent.py
  - Примеры spans в executor.py
  - Примеры spans в project_chat.py

#### Scenario: Jaeger UI Guide
- **INCLUDE**:
  - Как запустить Jaeger локально
  - Как искать трейсы
  - Как фильтровать по тегам
  - Примеры queries

### Requirement: Inline код документация
Весь код трассировки ДОЛЖЕН иметь docstrings и комментарии.

#### Scenario: app/tracing.py
- **DOCSTRING**: для `initialize_tracing()`
- **DOCSTRING**: для `get_tracer()`
- **COMMENTS**: объясняющие что делает каждая часть инициализации

#### Scenario: Span usage
- **COMMENTS**: объясняющие почему создается span
- **COMMENTS**: объясняющие структуру атрибутов и событий

---

## Phase 1 & Phase 2 Roadmap

### Phase 1 (NOW - OpenTelemetry Only)
✅ OpenTelemetry инициализация  
✅ JaegerExporter для локальной разработки  
✅ Spans в contextual_agent.py, executor.py, project_chat.py  
✅ Jaeger UI для debugging  
✅ Конфигурация через environment  

### Phase 2 (LATER - DB Persistence & Analytics)
⏳ ExecutionTrace, ToolExecutionTrace, LLMCallTrace таблицы  
⏳ Custom TraceDBExporter для сохранения spans в PostgreSQL  
⏳ REST API endpoints для аналитики  
⏳ OTLP для production (Tempo, DataDog)  
⏳ Ретеншн политика для старых spans  

---

## Non-Goals

❌ Full distributed tracing в production (Phase 2)  
❌ REST API для трейсов (Phase 2)  
❌ Database persistence (Phase 2)  
❌ Advanced sampling policies (Phase 2)  
❌ Custom collectors (будущее)  
