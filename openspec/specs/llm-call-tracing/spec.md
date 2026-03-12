# llm-call-tracing Specification

## Назначение

Автоматическое захватывание LLM вызовов через LiteLLM callbacks с отправкой полной информации в Langfuse.

## Requirements

### Requirement: Автоматическое логирование LLM вызовов через LiteLLM callbacks

LiteLLM ДОЛЖЕН отправлять данные о LLM операциях в Langfuse через встроенные callbacks.

#### Scenario: Успешное логирование LLM вызова
- **WHEN** агент вызывает litellm.completion(model="gpt-4", messages=[...])
- **THEN** LiteLLM автоматически отправляет в Langfuse: {model, prompt_tokens, completion_tokens, latency, cost, user_id, workspace_id}

#### Scenario: Логирование ошибок LLM
- **WHEN** LLM запрос завершается с ошибкой (timeout, API error, invalid key)
- **THEN** LiteLLM отправляет в Langfuse: {error_type, error_message, stack_trace, timestamp}

#### Scenario: Метаданные обогащаются в callbacks
- **WHEN** LiteLLM callback срабатывает
- **THEN** callback содержит: user_id (из structlog context), workspace_id, agent_name, metadata

### Requirement: Конфигурация LiteLLM для Langfuse

LiteLLM ДОЛЖЕН быть сконфигурирован для отправки callbacks в Langfuse.

#### Scenario: Включение callbacks
- **WHEN** litellm_config.yaml загружается
- **THEN** litellm_settings содержит success_callback: ["langfuse"], failure_callback: ["langfuse"]

#### Scenario: Передача API ключей
- **WHEN** LiteLLM инициализируется
- **THEN** environment содержит LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST
- **AND** LiteLLM использует эти переменные для автоматической отправки данных

#### Scenario: Асинхронная обработка callbacks
- **WHEN** LiteLLM отправляет callback
- **THEN** callback обрабатывается асинхронно (не блокирует LLM запрос)
- **AND** flush_interval=30 (batch отправка каждые 30 сек)
- **AND** если Langfuse недоступен, LiteLLM продолжает работать (fail-open)

### Requirement: Обогащение контекста в LiteLLM callbacks

Callbacks ДОЛЖНЫ содержать полный контекст пользователя и рабочего пространства.

#### Scenario: Извлечение user_id и workspace_id из контекста
- **WHEN** LiteLLM callback срабатывает
- **THEN** система извлекает user_id и workspace_id из structlog context (контекстные переменные)
- **AND** если контекст отсутствует, callback продолжает работу с minimal metadata

#### Scenario: Добавление agent_name в callback
- **WHEN** LLM запрос выполняется в контексте агента
- **THEN** callback содержит метаданные: agent_name, agent_id из контекста
- **AND** данные отправляются в Langfuse в поле metadata.agent_name
