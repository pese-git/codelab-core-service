# Спецификация: User Worker Space

## ADDED Requirements

### Requirement: Инициализация рабочего пространства
Система ДОЛЖНА создавать персональное рабочее пространство для каждого пользователя при первом запросе.

#### Scenario: Первый запрос пользователя
- **WHEN** пользователь делает первый запрос после аутентификации
- **THEN** система создает User Worker Space с уникальным user_prefix и инициализирует agent_cache

#### Scenario: Повторный запрос пользователя
- **WHEN** пользователь делает запрос и Worker Space уже существует
- **THEN** система использует существующий Worker Space без повторной инициализации

#### Scenario: Параллельные запросы одного пользователя
- **WHEN** пользователь делает несколько параллельных запросов
- **THEN** все запросы используют один и тот же Worker Space без конфликтов

### Requirement: Управление кешем агентов
Worker Space ДОЛЖЕН управлять кешем агентов пользователя для быстрого доступа.

#### Scenario: Загрузка агента в кеш
- **WHEN** агент запрашивается впервые
- **THEN** Worker Space загружает конфигурацию агента из БД в agent_cache с TTL 5 минут

#### Scenario: Доступ к закешированному агенту
- **WHEN** агент запрашивается повторно в течение TTL
- **THEN** Worker Space возвращает агента из cache без обращения к БД

#### Scenario: Инвалидация кеша агента
- **WHEN** конфигурация агента обновляется через API
- **THEN** Worker Space немедленно инвалидирует соответствующую запись в agent_cache

#### Scenario: Очистка кеша при удалении агента
- **WHEN** агент удаляется пользователем
- **THEN** Worker Space удаляет агента из agent_cache и освобождает ресурсы

### Requirement: Интеграция с Personal Agent Bus
Worker Space ДОЛЖЕН интегрироваться с Personal Agent Bus для координации выполнения задач.

#### Scenario: Регистрация агента в Bus
- **WHEN** агент загружается в Worker Space
- **THEN** Worker Space автоматически регистрирует агента в Agent Bus с его concurrency_limit

#### Scenario: Отправка задачи агенту
- **WHEN** Worker Space получает задачу для агента
- **THEN** Worker Space отправляет задачу в очередь агента через Agent Bus

#### Scenario: Дерегистрация агента
- **WHEN** агент удаляется или Worker Space очищается
- **THEN** Worker Space дерегистрирует агента из Agent Bus и завершает его worker tasks

### Requirement: Интеграция с Qdrant контекстом
Worker Space ДОЛЖЕН обеспечивать доступ к персональному Qdrant контексту агентов.

#### Scenario: Инициализация Qdrant collections
- **WHEN** Worker Space инициализируется
- **THEN** система проверяет существование Qdrant collections для агентов пользователя

#### Scenario: Доступ к контексту агента
- **WHEN** агент запрашивает RAG контекст
- **THEN** Worker Space предоставляет доступ к соответствующей Qdrant collection (user{id}_{agent_name}_context)

#### Scenario: Создание новой collection
- **WHEN** создается новый агент
- **THEN** Worker Space инициирует создание новой Qdrant collection для агента

### Requirement: Координация между режимами выполнения
Worker Space ДОЛЖЕН координировать выполнение задач в direct и orchestrated режимах.

#### Scenario: Direct mode execution
- **WHEN** запрос содержит target_agent
- **THEN** Worker Space направляет задачу напрямую указанному агенту, обходя orchestrator

#### Scenario: Orchestrated mode execution
- **WHEN** запрос не содержит target_agent
- **THEN** Worker Space передает запрос orchestrator для планирования графа задач

#### Scenario: Переключение между режимами
- **WHEN** пользователь меняет режим в рамках одной сессии
- **THEN** Worker Space корректно обрабатывает оба типа запросов без конфликтов

### Requirement: Lifecycle management
Worker Space ДОЛЖЕН управлять жизненным циклом с операциями initialization, cleanup и reset.

#### Scenario: Graceful cleanup
- **WHEN** пользователь завершает сессию или истекает timeout неактивности
- **THEN** Worker Space выполняет cleanup: завершает активные задачи, очищает cache, дерегистрирует агентов

#### Scenario: Force reset
- **WHEN** администратор или система инициирует reset Worker Space
- **THEN** Worker Space немедленно останавливает все задачи, очищает все ресурсы и реинициализируется

#### Scenario: Crash recovery
- **WHEN** Worker Space падает во время выполнения задач
- **THEN** система автоматически восстанавливает Worker Space и помечает незавершенные задачи как failed

### Requirement: Изоляция между пользователями
Worker Space ДОЛЖЕН обеспечивать полную изоляцию между пользователями на уровне рабочего пространства.

#### Scenario: Независимые Worker Spaces
- **WHEN** User123 и User456 одновременно используют систему
- **THEN** их Worker Spaces полностью изолированы и не имеют общих ресурсов

#### Scenario: Предотвращение утечки данных
- **WHEN** Worker Space обрабатывает данные пользователя
- **THEN** данные никогда не попадают в Worker Space другого пользователя

### Requirement: Мониторинг и метрики
Worker Space ДОЛЖЕН предоставлять метрики для мониторинга состояния и производительности.

#### Scenario: Метрики использования
- **WHEN** Worker Space активен
- **THEN** система собирает метрики: количество активных агентов, размер cache, количество задач в очереди

#### Scenario: Health check
- **WHEN** система проверяет здоровье Worker Space
- **THEN** Worker Space возвращает статус: healthy, degraded или unhealthy с деталями

#### Scenario: Алерты при проблемах
- **WHEN** Worker Space обнаруживает проблему (переполнение cache, зависшие задачи)
- **THEN** система генерирует алерт для мониторинга
