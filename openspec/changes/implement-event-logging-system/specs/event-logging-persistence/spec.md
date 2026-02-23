# Specification: Event Logging Persistence

## ADDED Requirements

### Requirement: EventLog model for persistent storage
Система ДОЛЖНА сохранять все события взаимодействия пользователя с агентами в таблице PostgreSQL event_logs с полным контекстом для последующего анализа и аудита.

#### Scenario: Event структура в БД
- **WHEN** событие генерируется в системе
- **THEN** система сохраняет событие с полями: id (UUID), session_id, user_id, project_id, agent_id, event_type, payload (JSONB), created_at, error_code, tool_name, approval_status

#### Scenario: EventLog модель наследует от Base
- **WHEN** код использует EventLog модель
- **THEN** модель наследует от app.database.Base и имеет аннотирующиеся типы (Mapped)

#### Scenario: Индексирование для оптимизации запросов
- **WHEN** пользователь выполняет поиск событий по session_id или user_id с сортировкой по времени
- **THEN** система использует индекс ix_event_logs_session_id_created_at или ix_event_logs_user_id_created_at для быстрого поиска

#### Scenario: JSONB payload для гибкости структуры
- **WHEN** различные типы событий имеют разные структуры payload
- **THEN** payload хранится как JSONB для поддержки любой JSON структуры без изменения схемы

#### Scenario: Денормализованные поля для частых фильтров
- **WHEN** пользователь фильтрует события по error_code, tool_name или approval_status
- **THEN** система использует денормализованные колонки вместо парсинга JSONB, что обеспечивает эффективность запросов

### Requirement: Foreign key relationships с сохранением целостности
Таблица event_logs ДОЛЖНА иметь foreign key связи с таблицами chat_sessions, users, user_projects и user_agents для обеспечения целостности данных.

#### Scenario: Каскадное удаление при удалении сессии
- **WHEN** пользователь удаляет chat session
- **THEN** все связанные события удаляются автоматически (ON DELETE CASCADE)

#### Scenario: SET NULL при удалении агента
- **WHEN** агент удаляется из проекта
- **THEN** event_logs.agent_id устанавливается в NULL для событий, которые ссылались на этого агента (ON DELETE SET NULL)

### Requirement: Миграция БД для создания event_logs таблицы
Система ДОЛЖНА иметь Alembic миграцию, которая создает таблицу event_logs с правильной схемой, индексами и constraints.

#### Scenario: Миграция успешно применяется
- **WHEN** выполнялась команда `alembic upgrade head`
- **THEN** таблица event_logs создается с правильной схемой и индексами

#### Scenario: Обратная миграция удаляет таблицу
- **WHEN** выполняется откат миграции `alembic downgrade -1`
- **THEN** таблица event_logs удаляется и все индексы очищаются

### Requirement: Представление EventLog в ORM
Модель EventLog доступна в app.models и может быть импортирована как: `from app.models import EventLog`

#### Scenario: EventLog доступна в __all__
- **WHEN** код выполняет `from app.models import EventLog`
- **THEN** экспорт успешен и EventLog доступна как класс ORM модели

#### Scenario: EventLog имеет корректные типы полей
- **WHEN** код создает новый EventLog экземпляр
- **THEN** все поля имеют правильные типы (UUID, datetime, str, dict, и т.д.) согласно аннотациям типов
