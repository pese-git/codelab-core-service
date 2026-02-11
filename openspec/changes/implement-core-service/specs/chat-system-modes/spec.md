# Спецификация: Chat System Modes

## ADDED Requirements

### Requirement: Единый endpoint для обоих режимов
Система ДОЛЖНА предоставлять единый endpoint для direct и orchestrated режимов.

#### Scenario: Direct mode через target_agent
- **WHEN** пользователь отправляет POST `/my/chat/{session_id}/message/` с полем target_agent="coder"
- **THEN** система выполняет direct call к агенту "coder" обходя orchestrator

#### Scenario: Orchestrated mode без target_agent
- **WHEN** пользователь отправляет POST `/my/chat/{session_id}/message/` без поля target_agent
- **THEN** система передает запрос orchestrator для планирования графа задач

#### Scenario: Невалидный target_agent
- **WHEN** пользователь указывает несуществующего target_agent
- **THEN** система возвращает 404 Not Found с сообщением "Agent not found"

#### Scenario: Формат запроса
- **WHEN** запрос отправляется
- **THEN** тело запроса содержит обязательное поле content и опциональное target_agent

### Requirement: Direct mode execution
Система ДОЛЖНА выполнять direct calls с минимальной задержкой.

#### Scenario: Немедленное выполнение
- **WHEN** direct call выполняется
- **THEN** система немедленно отправляет задачу указанному агенту через Agent Bus

#### Scenario: Производительность direct mode
- **WHEN** direct call обрабатывается
- **THEN** latency от запроса до начала выполнения < 100ms (P95)

#### Scenario: Полное время выполнения
- **WHEN** direct call завершается
- **THEN** общее время от запроса до ответа < 2 секунд (P95)

#### Scenario: SSE события в direct mode
- **WHEN** direct call выполняется
- **THEN** система отправляет SSE события: direct_agent_call, agent_status_changed, task_completed

### Requirement: Orchestrated mode execution
Система ДОЛЖНА выполнять orchestrated calls с автоматическим планированием.

#### Scenario: Планирование графа задач
- **WHEN** orchestrated call выполняется
- **THEN** система передает запрос orchestrator который создает граф задач

#### Scenario: Approval для сложных планов
- **WHEN** orchestrator создает сложный план (3+ задачи или стоимость > $0.10)
- **THEN** система запрашивает approval у пользователя через SSE

#### Scenario: Выполнение после approval
- **WHEN** пользователь одобряет план
- **THEN** система начинает выполнение задач согласно графу

#### Scenario: SSE события в orchestrated mode
- **WHEN** orchestrated call выполняется
- **THEN** система отправляет SSE события: task_plan_created, plan_request, task_started, task_progress, task_completed

### Requirement: Session management
Система ДОЛЖНА управлять chat сессиями для каждого пользователя.

#### Scenario: Создание новой сессии
- **WHEN** пользователь отправляет POST `/my/chat/sessions/`
- **THEN** система создает новую сессию с уникальным session_id и возвращает 201 Created

#### Scenario: Получение списка сессий
- **WHEN** пользователь отправляет GET `/my/chat/sessions/`
- **THEN** система возвращает список всех сессий пользователя с metadata

#### Scenario: Получение сессии по ID
- **WHEN** пользователь отправляет GET `/my/chat/sessions/{session_id}`
- **THEN** система возвращает детали сессии включая последние сообщения

#### Scenario: Удаление сессии
- **WHEN** пользователь отправляет DELETE `/my/chat/sessions/{session_id}`
- **THEN** система удаляет сессию и все связанные сообщения

#### Scenario: Изоляция сессий
- **WHEN** User123 запрашивает сессии
- **THEN** система возвращает только сессии User123, сессии других пользователей недоступны

### Requirement: Message history
Система ДОЛЖНА сохранять и предоставлять историю сообщений для каждой сессии.

#### Scenario: Сохранение user message
- **WHEN** пользователь отправляет сообщение
- **THEN** система сохраняет сообщение в БД с role="user", content, timestamp

#### Scenario: Сохранение agent response
- **WHEN** агент отвечает на сообщение
- **THEN** система сохраняет ответ с role="assistant", content, agent_id, timestamp

#### Scenario: Получение истории сообщений
- **WHEN** пользователь отправляет GET `/my/chat/{session_id}/messages/`
- **THEN** система возвращает все сообщения сессии в хронологическом порядке

#### Scenario: Пагинация истории
- **WHEN** сессия содержит много сообщений
- **THEN** система поддерживает пагинацию с параметрами limit и offset

#### Scenario: Фильтрация по role
- **WHEN** пользователь запрашивает сообщения с query параметром `?role=assistant`
- **THEN** система возвращает только сообщения от агентов

### Requirement: Mode selection logic
Система ДОЛЖНА автоматически выбирать режим на основе параметров запроса.

#### Scenario: Определение direct mode
- **WHEN** запрос содержит target_agent
- **THEN** система устанавливает mode="direct" и обходит orchestrator

#### Scenario: Определение orchestrated mode
- **WHEN** запрос не содержит target_agent
- **THEN** система устанавливает mode="orchestrated" и использует orchestrator

#### Scenario: Логирование выбора режима
- **WHEN** режим выбран
- **THEN** система логирует выбор с session_id, mode, timestamp

#### Scenario: Метрики по режимам
- **WHEN** система обрабатывает запросы
- **THEN** система собирает метрики: direct_calls_count, orchestrated_calls_count, average_duration по режимам

### Requirement: Context injection для агентов
Система ДОЛЖНА предоставлять контекст сессии агентам при выполнении.

#### Scenario: Передача истории сообщений
- **WHEN** агент вызывается в рамках сессии
- **THEN** система передает агенту последние N сообщений из истории сессии

#### Scenario: Ограничение размера контекста
- **WHEN** история сессии большая
- **THEN** система передает только последние 10 сообщений или 4000 токенов

#### Scenario: RAG контекст агента
- **WHEN** агент выполняет задачу
- **THEN** система автоматически выполняет RAG поиск в Qdrant контексте агента

#### Scenario: Объединение контекстов
- **WHEN** агент получает задачу
- **THEN** система объединяет session history + RAG context + task description

### Requirement: Error handling
Система ДОЛЖНА корректно обрабатывать ошибки в обоих режимах.

#### Scenario: Ошибка в direct mode
- **WHEN** агент не может выполнить задачу в direct mode
- **THEN** система возвращает ошибку пользователю с деталями и сохраняет в историю

#### Scenario: Ошибка в orchestrated mode
- **WHEN** одна из задач в плане failed
- **THEN** система останавливает зависимые задачи и возвращает partial результат

#### Scenario: Timeout обработки
- **WHEN** задача выполняется дольше 10 минут
- **THEN** система отменяет задачу и возвращает timeout error

#### Scenario: Agent unavailable
- **WHEN** целевой агент недоступен (status=error)
- **THEN** система возвращает 503 Service Unavailable с рекомендацией повторить позже

### Requirement: Concurrent requests handling
Система ДОЛЖНА корректно обрабатывать параллельные запросы в рамках одной сессии.

#### Scenario: Последовательная обработка в сессии
- **WHEN** пользователь отправляет несколько сообщений в одну сессию
- **THEN** система обрабатывает их последовательно сохраняя порядок

#### Scenario: Параллельные сессии
- **WHEN** пользователь имеет несколько активных сессий
- **THEN** система обрабатывает запросы к разным сессиям параллельно

#### Scenario: Блокировка сессии
- **WHEN** сообщение обрабатывается в сессии
- **THEN** система блокирует новые сообщения в эту сессию до завершения текущего

#### Scenario: Очередь сообщений
- **WHEN** пользователь отправляет сообщения быстрее чем они обрабатываются
- **THEN** система ставит сообщения в очередь (max 10 на сессию)
