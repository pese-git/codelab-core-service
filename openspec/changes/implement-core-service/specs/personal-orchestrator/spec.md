# Спецификация: Personal Orchestrator

## CRITICAL: User-Defined Agents Architecture

### Requirement: Агенты как пользовательские сущности (UserAgent)
Orchestrator ДОЛЖЕН работать с пользовательскими агентами из БД (UserAgent model), а не с жёстко закодированными типами.

#### Scenario: Загрузка агентов для проекта
- **WHEN** Orchestrator создаёт план для проекта
- **THEN** он загружает из БД: `SELECT * FROM user_agents WHERE project_id = ? AND status = 'ready'`
- **AND** никогда не предполагает наличие конкретного агента

#### Scenario: Извлечение capabilities из config.metadata
- **WHEN** Orchestrator анализирует агентов
- **THEN** он извлекает capabilities из поля `user_agents.config['metadata']['capabilities']` (JSON)
- **EXAMPLE**: `config = {"name": "coder", "metadata": {"capabilities": ["implement_feature", "fix_bug"], "risk_level": "HIGH"}}`

#### Scenario: Дефолтный starter pack
- **WHEN** пользователь создаёт новый проект
- **THEN** автоматически создаются 5 дефолтных агентов:
  - Ask Agent: capabilities=["answer_question", "explain_concept"], risk_level="LOW"
  - Debug Agent: capabilities=["investigate_error", "add_logging"], risk_level="MEDIUM"
  - Code Agent: capabilities=["implement_feature", "fix_bug"], risk_level="HIGH"
  - Architect Agent: capabilities=["design_architecture", "create_specifications"], risk_level="LOW"
  - Orchestrator Agent: capabilities=["coordinate_workflow", "route_tasks"], risk_level="LOW"

#### Scenario: Пользователь добавляет кастомного агента
- **WHEN** пользователь создаёт агента через API: `POST /my/projects/{project_id}/agents/`
- **THEN** новый UserAgent сохраняется в БД с пользовательскими capabilities и system_prompt
- **AND** при следующем планировании Orchestrator может использовать этого агента

#### Scenario: Пользователь обновляет capabilities агента
- **WHEN** пользователь обновляет агента: `PUT /my/projects/{project_id}/agents/{agent_id}`
- **THEN** изменения сохраняются в `user_agents.config` (JSON field)
- **AND** Orchestrator использует обновлённые capabilities при следующем планировании

#### Scenario: Пользователь удаляет агента
- **WHEN** пользователь выполняет `DELETE /my/projects/{project_id}/agents/{agent_id}`
- **THEN** агент удаляется из БД (cascade delete на related entities)
- **AND** Orchestrator больше не может использовать этого агента

#### Scenario: Изоляция агентов между проектами
- **WHEN** Orchestrator планирует для project_id=A и user_id=X
- **THEN** он загружает только: `SELECT * FROM user_agents WHERE user_id=X AND project_id=A`
- **AND** агенты из project_id=B недоступны

#### Scenario: Изоляция агентов между пользователями
- **WHEN** Orchestrator планирует для user_id=1
- **THEN** он видит только: `SELECT * FROM user_agents WHERE user_id=1`
- **AND** агенты user_id=2 полностью недоступны (даже на уровне БД)

#### Scenario: Агент недоступен при плохом health
- **WHEN** агент имеет status='error' или status='busy'
- **THEN** Orchestrator исключает его из доступных при планировании
- **AND** выбирает агент только если status='ready'

## ADDED Requirements

### Requirement: Планирование графа задач из natural language
Orchestrator ДОЛЖЕН анализировать запрос пользователя и создавать граф задач для выполнения.

#### Scenario: Простой запрос с одной задачей
- **WHEN** пользователь отправляет запрос "Проверь код в auth.py"
- **THEN** orchestrator создает граф с одной задачей для агента "coder"

#### Scenario: Сложный запрос с несколькими задачами
- **WHEN** пользователь отправляет запрос "Найди информацию о FastAPI и создай REST API"
- **THEN** orchestrator создает граф с задачами: 1) researcher ищет информацию, 2) coder создает API

#### Scenario: Запрос с параллельными задачами
- **WHEN** пользователь отправляет запрос требующий независимых действий
- **THEN** orchestrator создает граф где независимые задачи могут выполняться параллельно

#### Scenario: Невозможность выполнения
- **WHEN** запрос не может быть выполнен доступными агентами
- **THEN** orchestrator возвращает ошибку с объяснением почему задача невыполнима

### Requirement: Анализ зависимостей между задачами
Orchestrator ДОЛЖЕН определять зависимости между задачами и строить корректный граф.

#### Scenario: Последовательные зависимости
- **WHEN** задача B требует результата задачи A
- **THEN** orchestrator создает зависимость A → B в графе

#### Scenario: Множественные зависимости
- **WHEN** задача C требует результатов задач A и B
- **THEN** orchestrator создает зависимости A → C и B → C

#### Scenario: Обнаружение циклических зависимостей
- **WHEN** граф содержит цикл (A → B → C → A)
- **THEN** orchestrator обнаруживает цикл и возвращает ошибку "Circular dependency detected"

#### Scenario: Независимые задачи
- **WHEN** задачи A и B не зависят друг от друга
- **THEN** orchestrator помечает их как параллельно выполняемые

### Requirement: Топологическая сортировка для параллельного выполнения
Orchestrator ДОЛЖЕН использовать топологическую сортировку для определения порядка выполнения.

#### Scenario: Определение уровней выполнения
- **WHEN** граф задач построен
- **THEN** orchestrator группирует задачи по уровням где задачи одного уровня могут выполняться параллельно

#### Scenario: Максимальный параллелизм
- **WHEN** граф содержит независимые задачи
- **THEN** orchestrator планирует их выполнение одновременно с учетом concurrency_limit (max 3 агента)

#### Scenario: Последовательное выполнение при зависимостях
- **WHEN** все задачи зависят друг от друга последовательно
- **THEN** orchestrator планирует их выполнение по одной

#### Scenario: Оптимизация порядка
- **WHEN** существует несколько валидных порядков выполнения
- **THEN** orchestrator выбирает порядок минимизирующий общее время выполнения

### Requirement: Оценка стоимости выполнения
Orchestrator ДОЛЖЕН оценивать стоимость выполнения плана в $ API calls.

#### Scenario: Оценка стоимости LLM вызовов
- **WHEN** план создан
- **THEN** orchestrator оценивает количество LLM API calls и их стоимость на основе моделей агентов

#### Scenario: Оценка стоимости embeddings
- **WHEN** план включает RAG поиск
- **THEN** orchestrator добавляет стоимость генерации embeddings к общей оценке

#### Scenario: Диапазон стоимости
- **WHEN** точная стоимость неизвестна
- **THEN** orchestrator предоставляет диапазон (min-max) стоимости

#### Scenario: Предупреждение о высокой стоимости
- **WHEN** оценочная стоимость превышает $1.00
- **THEN** orchestrator помечает план как "high_cost" и требует approval

### Requirement: Оценка времени выполнения
Orchestrator ДОЛЖЕН оценивать время выполнения плана.

#### Scenario: Оценка времени для простого плана
- **WHEN** план содержит одну задачу
- **THEN** orchestrator оценивает время как average_task_duration агента

#### Scenario: Оценка времени для последовательного плана
- **WHEN** план содержит последовательные задачи
- **THEN** orchestrator суммирует время выполнения всех задач

#### Scenario: Оценка времени для параллельного плана
- **WHEN** план содержит параллельные задачи
- **THEN** orchestrator оценивает время как максимум среди параллельных веток

#### Scenario: Диапазон времени
- **WHEN** время выполнения неопределенно
- **THEN** orchestrator предоставляет диапазон (min-max) в секундах

### Requirement: Интеграция с Approval Manager
Orchestrator ДОЛЖЕН интегрироваться с Approval Manager для получения подтверждения сложных планов.

**Требование**: Все планы, которые содержат 3+ задачи или стоимость > $0.10, ДОЛЖНЫ быть подтверждены пользователем перед выполнением.

#### Scenario: Автоматическое выполнение простого плана
- **WHEN** план содержит 1-2 задачи и стоимость < $0.10
- **THEN** orchestrator выполняет план без approval

#### Scenario: Запрос approval для сложного плана
- **WHEN** план содержит 3+ задачи или стоимость > $0.10
- **THEN** orchestrator отправляет план в Approval Manager и ждет подтверждения от пользователя с деталями:
  - Список всех задач в плане
  - Граф зависимостей задач
  - Назначенные агенты для каждой задачи
  - Оценочная стоимость в долларах
  - Оценочное время выполнения

#### Scenario: Отображение плана пользователю
- **WHEN** план требует approval
- **THEN** пользователь видит в UI полный план с визуальным представлением:
  - Диаграмма потока задач
  - Риск-оценка (low/medium/high)
  - Стоимость и время выполнения
  - Кнопки "Approve" и "Reject"

#### Scenario: Выполнение после approval
- **WHEN** пользователь одобряет план
- **THEN** orchestrator начинает выполнение согласно графу задач и отправляет SSE события о прогрессе

#### Scenario: Отмена при reject
- **WHEN** пользователь отклоняет план
- **THEN** orchestrator отменяет выполнение и возвращает сообщение об отмене

#### Scenario: Timeout approval
- **WHEN** пользователь не отвечает на approval request в течение 300 секунд
- **THEN** orchestrator автоматически отклоняет план

#### Scenario: Частичное выполнение при ошибке
- **WHEN** одна из задач в одобренном плане завершается с ошибкой
- **THEN** orchestrator обрабатывает ошибку согласно зависимостям и отправляет обновление статуса

### Requirement: Выбор агентов для задач
Orchestrator ДОЛЖЕН выбирать подходящих агентов для каждой задачи на основе их capabilities.

#### Scenario: Выбор по типу задачи
- **WHEN** задача требует написания кода
- **THEN** orchestrator назначает задачу агенту с capability "coding"

#### Scenario: Выбор по доступности
- **WHEN** несколько агентов подходят для задачи
- **THEN** orchestrator выбирает агента со статусом "ready" и наименьшей загрузкой

#### Scenario: Отсутствие подходящего агента
- **WHEN** ни один агент не может выполнить задачу
- **THEN** orchestrator возвращает ошибку "No suitable agent available for task"

#### Scenario: Учет concurrency limit
- **WHEN** агент уже выполняет максимальное количество задач
- **THEN** orchestrator ставит новую задачу в очередь или выбирает другого агента

### Requirement: Мониторинг выполнения плана
Orchestrator ДОЛЖЕН отслеживать прогресс выполнения плана и отправлять обновления.

#### Scenario: Отправка SSE событий о прогрессе
- **WHEN** задача в плане начинается, выполняется или завершается
- **THEN** orchestrator отправляет SSE события: task_started, task_progress, task_completed

#### Scenario: Обработка успешного завершения задачи
- **WHEN** задача успешно завершена
- **THEN** orchestrator передает результат зависимым задачам и запускает их

#### Scenario: Обработка ошибки в задаче
- **WHEN** задача завершается с ошибкой
- **THEN** orchestrator останавливает зависимые задачи и помечает план как failed

#### Scenario: Частичный успех
- **WHEN** некоторые задачи успешны, но одна failed
- **THEN** orchestrator завершает успешные задачи и возвращает partial_success с деталями

### Requirement: Кеширование планов
Orchestrator ДОЛЖЕН кешировать похожие планы для ускорения планирования.

#### Scenario: Сохранение плана в cache
- **WHEN** план успешно создан и выполнен
- **THEN** orchestrator сохраняет план в Redis с ключом на основе hash запроса

#### Scenario: Использование закешированного плана
- **WHEN** пользователь отправляет похожий запрос
- **THEN** orchestrator находит план в cache и использует его вместо создания нового

#### Scenario: Инвалидация cache
- **WHEN** конфигурация агентов изменяется
- **THEN** orchestrator инвалидирует все планы в cache связанные с этими агентами

#### Scenario: TTL cache
- **WHEN** план сохраняется в cache
- **THEN** TTL устанавливается на 24 часа

### Requirement: Производительность планирования
Orchestrator ДОЛЖЕН создавать планы с минимальной задержкой.

#### Scenario: Планирование простых запросов
- **WHEN** запрос требует 1-2 задачи
- **THEN** планирование завершается менее чем за 2 секунды

#### Scenario: Планирование сложных запросов
- **WHEN** запрос требует 3+ задачи с зависимостями
- **THEN** планирование завершается менее чем за 5 секунд

#### Scenario: Timeout планирования
- **WHEN** планирование занимает более 5 секунд
- **THEN** orchestrator возвращает fallback план с последовательным выполнением

### Requirement: Хранение планов в PostgreSQL
Orchestrator ДОЛЖЕН сохранять полное состояние планов в PostgreSQL для восстановления после перезагрузки сервиса.

#### Scenario: Сохранение плана при создании
- **WHEN** план создан
- **THEN** план сохраняется в БД с таблицей task_plans (id, user_id, session_id, original_request, status, total_cost, total_duration, requires_approval, created_at)

#### Scenario: Сохранение задач плана
- **WHEN** план создан
- **THEN** каждая задача сохраняется в таблице task_plan_tasks (id, plan_id, task_id, description, agent_id, dependencies, estimated_cost, estimated_duration, risk_level, status, result, created_at)

#### Scenario: Восстановление после перезагрузки
- **WHEN** сервис перезагружается во время выполнения плана
- **THEN** orchestrator может восстановить полное состояние плана из БД и продолжить выполнение

#### Scenario: Индексы для оптимизации
- **WHEN** запрашиваются планы
- **THEN** используются индексы по (user_id, session_id), (plan_id), (status, created_at) для быстрого поиска

#### Scenario: Промежуточные результаты
- **WHEN** задача завершена
- **THEN** результат сохраняется в БД (task_plan_tasks.result) для использования зависимыми задачами

#### Scenario: Полное состояние выполнения
- **WHEN** план выполняется
- **THEN** все этапы (pending, executing, partial_success, completed, failed) сохраняются в БД для аудита

#### Scenario: TTL в Redis для кеша
- **WHEN** план сохранен в БД
- **THEN** план также кешируется в Redis (TTL 24 часа) для быстрого доступа к похожим запросам
