# Спецификация: Approval Manager

## ADDED Requirements

### Requirement: Tool approval workflow
Система ДОЛЖНА запрашивать подтверждение пользователя перед использованием опасных tools.

#### Scenario: Запрос approval для tool
- **WHEN** агент хочет использовать tool требующий approval (например, file_delete, execute_command)
- **THEN** Approval Manager создает approval request и отправляет SSE событие tool_request пользователю

#### Scenario: Подтверждение tool использования
- **WHEN** пользователь отправляет POST `/my/approvals/{approval_id}/confirm` с decision="approve"
- **THEN** Approval Manager разблокирует агента и позволяет выполнить tool

#### Scenario: Отклонение tool использования
- **WHEN** пользователь отправляет POST `/my/approvals/{approval_id}/confirm` с decision="reject"
- **THEN** Approval Manager отклоняет запрос и агент получает ошибку "Tool usage rejected by user"

#### Scenario: Payload approval request
- **WHEN** approval request создается для tool
- **THEN** payload содержит: tool_name, parameters, agent_id, reason, risk_level

### Requirement: Plan approval workflow
Система ДОЛЖНА запрашивать подтверждение для сложных multi-agent планов.

#### Scenario: Запрос approval для плана
- **WHEN** orchestrator создает план с 3+ задачами или стоимостью > $0.10
- **THEN** Approval Manager создает approval request и отправляет SSE событие plan_request

#### Scenario: Подтверждение плана
- **WHEN** пользователь одобряет план
- **THEN** Approval Manager разблокирует orchestrator и план начинает выполняться

#### Scenario: Отклонение плана
- **WHEN** пользователь отклоняет план
- **THEN** Approval Manager отменяет план и все задачи помечаются как cancelled

#### Scenario: Payload plan approval
- **WHEN** approval request создается для плана
- **THEN** payload содержит: plan_id, tasks[], estimated_cost, estimated_duration, agents_involved[]

### Requirement: Timeout management
Approval Manager ДОЛЖЕН автоматически обрабатывать timeout для approval requests.

#### Scenario: Timeout для tool approval
- **WHEN** пользователь не отвечает на tool approval в течение 300 секунд
- **THEN** Approval Manager автоматически отклоняет запрос и агент получает timeout error

#### Scenario: Timeout для plan approval
- **WHEN** пользователь не отвечает на plan approval в течение 300 секунд
- **THEN** Approval Manager автоматически отклоняет план и отменяет все задачи

#### Scenario: Уведомление о приближении timeout
- **WHEN** до timeout остается 60 секунд
- **THEN** Approval Manager отправляет SSE событие approval_timeout_warning

#### Scenario: Конфигурируемый timeout
- **WHEN** approval request создается
- **THEN** можно указать custom timeout (по умолчанию 300 секунд)

### Requirement: SSE integration
Approval Manager ДОЛЖЕН интегрироваться с SSE для уведомления пользователей.

#### Scenario: Отправка SSE события при создании approval
- **WHEN** approval request создается
- **THEN** Approval Manager отправляет SSE событие approval_required с полным payload

#### Scenario: Отправка SSE события при подтверждении
- **WHEN** пользователь подтверждает или отклоняет approval
- **THEN** Approval Manager отправляет SSE событие approval_resolved с результатом

#### Scenario: Отправка SSE события при timeout
- **WHEN** approval request истекает по timeout
- **THEN** Approval Manager отправляет SSE событие approval_timeout

#### Scenario: Multiple SSE connections
- **WHEN** пользователь имеет несколько открытых вкладок
- **THEN** Approval Manager отправляет события всем активным SSE connections

### Requirement: Result handling
Approval Manager ДОЛЖЕН корректно обрабатывать результаты approval и разблокировать агентов.

#### Scenario: Разблокировка агента после approve
- **WHEN** tool approval подтвержден
- **THEN** Approval Manager немедленно разблокирует агента и передает ему разрешение

#### Scenario: Блокировка агента после reject
- **WHEN** tool approval отклонен
- **THEN** Approval Manager передает агенту ошибку и агент продолжает без использования tool

#### Scenario: Разблокировка orchestrator после approve плана
- **WHEN** plan approval подтвержден
- **THEN** Approval Manager разблокирует orchestrator и план начинает выполняться

#### Scenario: Отмена плана после reject
- **WHEN** plan approval отклонен
- **THEN** Approval Manager отменяет все задачи плана и освобождает ресурсы

### Requirement: Хранение истории approvals
Система ДОЛЖНА сохранять историю всех approval requests для аудита.

#### Scenario: Сохранение approval request
- **WHEN** approval request создается
- **THEN** система сохраняет запись в БД с полями: id, user_id, type, payload, status, created_at

#### Scenario: Обновление статуса approval
- **WHEN** пользователь отвечает на approval
- **THEN** система обновляет status (approved/rejected/timeout) и добавляет resolved_at, decision

#### Scenario: Получение истории approvals
- **WHEN** пользователь отправляет GET `/my/approvals/`
- **THEN** система возвращает список всех approval requests с фильтрацией по status, type, date

#### Scenario: Детали approval request
- **WHEN** пользователь отправляет GET `/my/approvals/{approval_id}`
- **THEN** система возвращает полную информацию включая payload, timestamps, decision

### Requirement: Типы approval requests
Approval Manager ДОЛЖЕН поддерживать различные типы approval requests.

#### Scenario: Tool approval type
- **WHEN** создается tool approval
- **THEN** type устанавливается в "tool" и payload содержит tool-specific данные

#### Scenario: Plan approval type
- **WHEN** создается plan approval
- **THEN** type устанавливается в "plan" и payload содержит plan-specific данные

#### Scenario: Custom approval type
- **WHEN** система требует другой тип approval
- **THEN** можно создать approval с custom type и payload

#### Scenario: Фильтрация по типу
- **WHEN** пользователь запрашивает approvals с query параметром `?type=tool`
- **THEN** система возвращает только tool approvals

### Requirement: Concurrent approvals handling
Approval Manager ДОЛЖЕН корректно обрабатывать множественные одновременные approval requests.

#### Scenario: Множественные pending approvals
- **WHEN** несколько агентов одновременно запрашивают approval
- **THEN** Approval Manager создает отдельный approval request для каждого

#### Scenario: Порядок обработки approvals
- **WHEN** пользователь имеет несколько pending approvals
- **THEN** система отображает их в порядке создания (FIFO)

#### Scenario: Batch approval
- **WHEN** пользователь хочет одобрить несколько approvals сразу
- **THEN** система поддерживает POST `/my/approvals/batch-confirm` с массивом approval_ids

#### Scenario: Изоляция approvals между пользователями
- **WHEN** User123 и User456 имеют pending approvals
- **THEN** каждый видит только свои approval requests

### Requirement: Risk level assessment
Approval Manager ДОЛЖЕН оценивать уровень риска для tool approvals.

#### Scenario: High risk tools
- **WHEN** агент запрашивает использование high risk tool (file_delete, execute_command)
- **THEN** Approval Manager устанавливает risk_level="high" и выделяет в UI

#### Scenario: Medium risk tools
- **WHEN** агент запрашивает использование medium risk tool (file_write, api_call)
- **THEN** Approval Manager устанавливает risk_level="medium"

#### Scenario: Low risk tools
- **WHEN** агент запрашивает использование low risk tool (file_read, search)
- **THEN** Approval Manager устанавливает risk_level="low"

#### Scenario: Auto-approve для low risk
- **WHEN** tool имеет risk_level="low" и пользователь включил auto_approve_low_risk
- **THEN** Approval Manager автоматически одобряет без запроса пользователю

### Requirement: Retry mechanism
Approval Manager ДОЛЖЕН позволять повторить отклоненные requests.

#### Scenario: Retry после reject
- **WHEN** пользователь отклонил approval и агент повторяет запрос
- **THEN** Approval Manager создает новый approval request с пометкой "retry"

#### Scenario: Лимит retries
- **WHEN** агент пытается повторить approval более 3 раз
- **THEN** Approval Manager отклоняет запрос с ошибкой "Max retries exceeded"

#### Scenario: История retries
- **WHEN** approval является retry
- **THEN** payload содержит ссылку на предыдущий approval_id

#### Scenario: Cooldown между retries
- **WHEN** агент повторяет approval
- **THEN** Approval Manager требует минимум 10 секунд между попытками

### Requirement: Monitoring и metrics
Approval Manager ДОЛЖЕН предоставлять метрики для мониторинга.

#### Scenario: Метрики approvals
- **WHEN** система работает
- **THEN** Approval Manager собирает метрики: total_approvals, approved_count, rejected_count, timeout_count

#### Scenario: Метрики по типам
- **WHEN** approvals обрабатываются
- **THEN** система собирает breakdown по type: tool_approvals, plan_approvals

#### Scenario: Метрики времени ответа
- **WHEN** пользователи отвечают на approvals
- **THEN** система собирает метрики: average_response_time, p95_response_time

#### Scenario: Алерты при проблемах
- **WHEN** timeout_rate > 20%
- **THEN** Approval Manager генерирует алерт "High approval timeout rate"

### Requirement: User preferences
Approval Manager ДОЛЖЕН поддерживать пользовательские настройки approval.

#### Scenario: Auto-approve настройки
- **WHEN** пользователь настраивает auto_approve для определенных tools
- **THEN** Approval Manager автоматически одобряет эти tools без запроса

#### Scenario: Notification preferences
- **WHEN** пользователь настраивает notification preferences
- **THEN** Approval Manager отправляет уведомления согласно настройкам (SSE, email, none)

#### Scenario: Timeout preferences
- **WHEN** пользователь устанавливает custom default timeout
- **THEN** Approval Manager использует этот timeout для новых approvals

#### Scenario: Сохранение preferences
- **WHEN** пользователь изменяет preferences
- **THEN** система сохраняет их в БД и применяет ко всем будущим approvals
