# traces-analytics-api Specification

## Назначение

REST API endpoints для получения traces с фильтрацией по user_id, workspace_id, agent_name и metadata, с поддержкой пагинации и аналитики.

## ADDED Requirements

### Requirement: Получение traces для аналитики

Система ДОЛЖНА предоставлять API для получения traces с фильтрацией и пагинацией.

#### Scenario: Получение traces пользователя
- **WHEN** клиент отправляет GET /traces?user_id=uuid&workspace_id=uuid&limit=100
- **THEN** Langfuse возвращает список traces с metadata и spans

#### Scenario: Фильтрация traces по критериям
- **WHEN** клиент отправляет GET /traces?metadata.agent=research_agent&limit=50
- **THEN** Langfuse возвращает только traces с agent="research_agent"

### Requirement: GET /traces endpoint

Endpoint ДОЛЖЕН поддерживать получение traces с фильтрацией и пагинацией.

#### Scenario: Базовое получение traces
- **WHEN** клиент отправляет GET /traces?user_id=<uuid>&workspace_id=<uuid>
- **THEN** система возвращает 200 OK с массивом traces, каждый содержит: {id, name, user_id, workspace_id, session_id, metadata, spans, scores, created_at}

#### Scenario: Пагинация
- **WHEN** клиент отправляет GET /traces?limit=50&offset=100
- **THEN** система возвращает 50 traces, пропустив первые 100
- **AND** response содержит total_count для расчета pagination

#### Scenario: Фильтрация по временному диапазону
- **WHEN** клиент отправляет GET /traces?user_id=<uuid>&start_date=2026-03-01&end_date=2026-03-10
- **THEN** система возвращает только traces созданные в этом диапазоне

### Requirement: GET /traces/{trace_id} endpoint

Endpoint ДОЛЖЕН предоставлять детальную информацию о specific trace.

#### Scenario: Получение детальной информации о trace
- **WHEN** клиент отправляет GET /traces/{trace_id}
- **THEN** система возвращает 200 OK с полной информацией: trace {id, name, user_id, workspace_id, spans[], scores[], metadata, latency, status}

#### Scenario: Span детали
- **WHEN** клиент получает trace
- **THEN** каждый span содержит: {id, name, input, output, start_time, end_time, duration, metadata, status, error_info}

### Requirement: GET /traces/{trace_id}/scores endpoint

Endpoint ДОЛЖЕН предоставлять scores для specific trace.

#### Scenario: Получение scores для trace
- **WHEN** клиент отправляет GET /traces/{trace_id}/scores
- **THEN** система возвращает массив всех scores для этого trace: {id, name, value, comment, created_at}

### Requirement: Фильтрация по метаданным

Система ДОЛЖНА поддерживать гибкую фильтрацию по метаданным.

#### Scenario: Фильтрация по agent_name
- **WHEN** клиент отправляет GET /traces?metadata.agent_name=research_agent
- **THEN** система фильтрует traces только с agent_name="research_agent"

#### Scenario: Фильтрация по model
- **WHEN** клиент отправляет GET /traces?metadata.model=gpt-4&metadata.provider=openai
- **THEN** система возвращает traces которые использовали именно эту модель

#### Scenario: Мультиуровневая фильтрация
- **WHEN** клиент отправляет GET /traces?user_id=<uuid>&metadata.agent_name=assistant&status=success
- **THEN** система применяет все фильтры AND логикой, возвращает matching traces

### Requirement: Сортировка результатов

API ДОЛЖЕН поддерживать сортировку results.

#### Scenario: Сортировка по времени создания
- **WHEN** клиент отправляет GET /traces?user_id=<uuid>&sort=created_at&order=desc
- **THEN** система возвращает traces отсортированные по created_at в убывающем порядке

#### Scenario: Сортировка по latency
- **WHEN** клиент отправляет GET /traces?sort=duration&order=asc
- **THEN** система возвращает traces отсортированные по duration в возрастающем порядке

### Requirement: Аггрегированная аналитика

API ДОЛЖЕН предоставлять endpoints для аналитических метрик.

#### Scenario: Получение summary статистики
- **WHEN** клиент отправляет GET /analytics/traces/summary?user_id=<uuid>&period=7d
- **THEN** система возвращает: {total_traces, avg_duration, success_rate, error_count, unique_agents, unique_models}

#### Scenario: Метрики по агентам
- **WHEN** клиент отправляет GET /analytics/agents?workspace_id=<uuid>
- **THEN** система возвращает: {agent_name, trace_count, avg_duration, success_rate, avg_user_satisfaction_score}

#### Scenario: Cost анализ
- **WHEN** клиент отправляет GET /analytics/cost?user_id=<uuid>&start_date=2026-03-01
- **THEN** система возвращает: {total_cost, by_model: [{model, tokens_used, cost}], by_agent: [{agent, cost}]}

### Requirement: Авторизация и permissions

API ДОЛЖЕН проверять права доступа пользователя.

#### Scenario: Юзер может видеть только свои traces
- **WHEN** пользователь A отправляет GET /traces?user_id=<uuid_B>
- **THEN** система возвращает 403 Forbidden если uuid_B не принадлежит пользователю
- **AND** только workspace владельцы могут видеть workspace traces

#### Scenario: Workspace isolation
- **WHEN** пользователь отправляет GET /traces?workspace_id=<uuid>
- **THEN** система проверяет что пользователь имеет доступ к этому workspace
- **AND** возвращает только traces из разрешенного workspace
