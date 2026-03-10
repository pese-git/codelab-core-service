# llm-provider-audit Specification

## Purpose
TBD - created by archiving change llm-providers-management. Update Purpose after archive.
## Requirements
### Requirement: Система логирует создание провайдеров
При успешном или неудачном создании провайдера ДОЛЖНА быть создана запись аудита с информацией о действии, пользователе и результате.

#### Scenario: Логирование успешного создания
- **WHEN** пользователь успешно создает провайдер
- **THEN** система вставляет запись в llm_provider_audit_log: {user_id, provider_id, action: "create", success: true, new_values: {display_name, provider_type}, created_at: now}

#### Scenario: Логирование ошибки при создании
- **WHEN** пользователь пытается создать провайдер и LiteLLM возвращает ошибку
- **THEN** система вставляет запись: {user_id, provider_id: null, action: "create", success: false, error_message: "...", created_at: now}

### Requirement: Система логирует обновления конфигурации
При обновлении конфигурации провайдера ДОЛЖНА быть записана информация о старых и новых значениях.

#### Scenario: Логирование изменения display_name
- **WHEN** пользователь обновляет display_name провайдера
- **THEN** система вставляет запись: {user_id, provider_id, action: "update", old_values: {display_name: "Old"}, new_values: {display_name: "New"}, success: true, created_at: now}

### Requirement: Система логирует удаление провайдеров
При удалении провайдера ДОЛЖНА быть создана запись аудита.

#### Scenario: Логирование успешного удаления
- **WHEN** пользователь успешно удаляет провайдер
- **THEN** система вставляет запись: {user_id, provider_id, action: "delete", success: true, created_at: now}

#### Scenario: Логирование отказа в удалении
- **WHEN** пользователь пытается удалить провайдер в использовании и операция отклоняется
- **THEN** система вставляет запись: {user_id, provider_id, action: "delete", success: false, error_message: "Cannot delete: N agent(s) using", created_at: now}

### Requirement: Система логирует тестирование провайдеров
При тестировании провайдера ДОЛЖНА быть создана запись аудита с результатом.

#### Scenario: Логирование успешного теста
- **WHEN** пользователь успешно тестирует провайдер
- **THEN** система вставляет запись: {user_id, provider_id, action: "test", success: true, created_at: now}

#### Scenario: Логирование ошибки при тесте
- **WHEN** пользователь тестирует провайдер и получает ошибку (невалидный ключ, timeout и т.д.)
- **THEN** система вставляет запись: {user_id, provider_id, action: "test", success: false, error_message: "...", created_at: now}

### Requirement: Система логирует использование провайдеров
При использовании провайдера в агенте ДОЛЖНА быть создана запись аудита.

#### Scenario: Логирование использования при выполнении агента
- **WHEN** агент с привязанным провайдером выполняет prompt к LLM
- **THEN** система вставляет запись: {user_id, provider_id, action: "use", success: true, created_at: now}

### Requirement: Система собирает контекст операций
При создании записи аудита ДОЛЖНА быть собрана дополнительная информация: IP адрес пользователя и user agent.

#### Scenario: Сбор IP адреса из запроса
- **WHEN** пользователь выполняет операцию с провайдером через HTTP API
- **THEN** система извлекает IP адрес из request.client.host или X-Forwarded-For header и сохраняет в audit log

#### Scenario: Сбор user agent из запроса
- **WHEN** пользователь выполняет операцию с провайдером
- **THEN** система извлекает User-Agent header и сохраняет в audit log

### Requirement: Пользователь может просматривать свой audit log
Пользователь ДОЛЖЕН иметь возможность получить историю операций со своими провайдерами с фильтрацией и пагинацией.

#### Scenario: Получение полного audit log пользователя
- **WHEN** пользователь отправляет GET /my/llm-providers/audit?skip=0&limit=100
- **THEN** система возвращает 200 OK с отсортированным по created_at DESC списком всех операций пользователя

#### Scenario: Фильтрация audit log по действию
- **WHEN** пользователь отправляет GET /my/llm-providers/audit?action=create&skip=0&limit=100
- **THEN** система возвращает 200 OK со списком только операций создания провайдеров

#### Scenario: Пагинация audit log
- **WHEN** пользователь отправляет GET /my/llm-providers/audit?skip=100&limit=50
- **THEN** система возвращает 200 OK со второй страницей результатов (записи 100-150)

### Requirement: Система НЕ логирует API ключи
API ключи НИКОГДА НЕ ДОЛЖНЫ быть сохранены в audit_log или логах приложения.

#### Scenario: API ключ не попадает в audit log
- **WHEN** пользователь создает провайдер с api_key: "sk-123456789"
- **THEN** система не сохраняет api_key в new_values audit log, только метаданные (display_name, provider_type)

#### Scenario: API ключ не логируется при ошибке
- **WHEN** пользователь создает провайдер с невалидным ключом и операция фейлится
- **THEN** error_message в audit log содержит "Invalid API key" но не содержит самого ключа

### Requirement: Система ведет аудит долгосрочно
Записи audit log ДОЛЖНЫ быть сохранены для долгосрочного хранения и анализа (retention policy может быть определена позже).

#### Scenario: Запись сохраняется в базе
- **WHEN** пользователь выполняет операцию с провайдером
- **THEN** запись вставляется в llm_provider_audit_log и остается там, доступная для просмотра при необходимости

#### Scenario: Индекс на user_id и created_at
- **WHEN** приложение создает audit log
- **THEN** таблица имеет индекс на (user_id, created_at DESC) для быстрого поиска операций пользователя

### Requirement: Интеграция audit logs с Langfuse traces
Audit logs ДОЛЖНЫ быть связаны с соответствующими Langfuse traces для расширенного трейсинга LLM операций.

#### Scenario: Логирование события использования провайдера с Langfuse
- **WHEN** агент использует провайдер для LLM вызова
- **THEN** система создает запись audit log AND одновременно создает/обновляет Langfuse span с metadata={provider_id, provider_type, action: "use"}

#### Scenario: Связь между audit events и LLM traces
- **WHEN** пользователь просматривает audit log для провайдера
- **THEN** каждая запись "use" содержит trace_id из Langfuse для быстрого переключения на детальный трейс LLM операции

#### Scenario: Отслеживание стоимости в контексте провайдера
- **WHEN** Langfuse записывает LLM запрос с provider_id в metadata
- **THEN** система может агрегировать стоимость по провайдерам/workspace'ам через join audit_log и Langfuse traces

