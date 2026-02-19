# Спецификация: User Worker Space

## Обзор

User Worker Space - это компонент backend, который управляет персональным рабочим пространством пользователя для каждого проекта. Он обеспечивает:
- Инициализацию и управление lifecycle backend ресурсов (agent_cache, Agent Bus, Qdrant collections)
- Координацию между режимами выполнения (direct/orchestrated)
- Доступ к персональному RAG контексту агентов через Qdrant
- Полную изоляцию между пользователями и проектами

**Ключевое архитектурное разделение:**
- **Workspace** (файловая система пользователя) находится на стороне пользователя (локально на клиентском компьютере)
- **Backend ресурсы** (agent_cache, Agent Bus, Qdrant) управляются User Worker Space backend компонентой на сервере
- **Агенты** (выполняются на backend сервере) получают доступ к workspace пользователя исключительно через tools с передачей контекста
- **Валидация путей** происходит на стороне пользователя (client), где находится локальная файловая система

---

## Workspace Access Architecture

### Архитектурный поток доступа

```
User/Client (локальная файловая система пользователя)
        ↓
Agent (выполняется на backend сервере)
        ↓
Tool (выполняется на backend сервере, например tool_read_file)
        ↓
Tool передает запрос на CLIENT для валидации и выполнения операции
        ↓
CLIENT валидирует путь (проверяет что находится в workspace границах)
        ↓
CLIENT выполняет операцию с локальной файловой системой
        ↓
CLIENT возвращает результат на backend
        ↓
Agent получает результат
```

### Sequence Diagram: Доступ к файлам workspace

```
Backend Agent/Tool     CLIENT (User FS)    Validation
        |                   |                   |
        |--tool_read_file   |                   |
        |  (path="src/main.py")--request------->|
        |                   |            validate
        |                   |            path in
        |                   |            workspace
        |                   |<--is_valid--|
        |<--read local file-|              
        |                   |--read FS--->|
        |                   |<-content----|
        |<--file content----|              |
        |                   |              |
```

**Ключевые моменты:**
1. Файлы находятся на локальной файловой системе пользователя (client side)
2. Backend Agent получает запрос и вызывает tool (например, tool_read_file)
3. Tool получает путь к файлу и отправляет запрос на CLIENT
4. CLIENT валидирует путь (проверяет что находится в пределах workspace границ)
5. CLIENT выполняет операцию с локальной файловой системой (read/write/list)
6. CLIENT возвращает результат обратно на backend tool
7. Agent получает результат

### Ключевые принципы

1. **Инициализация на backend**
   - User Worker Space создается для КАЖДОГО проекта при первом запросе
   - Backend создает и управляет: agent_cache, Agent Bus регистрацию, Qdrant collections
   - Workspace пользователя (файловая система) управляется пользователем и существует независимо на client стороне

2. **Доступ только через Tools**
   - Агенты (на backend) НЕ имеют прямого доступа к файловой системе пользователя
   - Все операции с файлами проходят через tools (tool_read_file, tool_write_file, tool_list_directory)
   - Tools получают workspace context (путь, user_id) как параметры и отправляют запрос на CLIENT

3. **Валидация на CLIENT стороне**
   - CLIENT валидирует пути (проверяет что находятся в пределах workspace границ)
   - CLIENT имеет доступ к локальной файловой системе пользователя
   - CLIENT предотвращает path traversal атаки через нормализацию пути
   - Backend не может обойти контроль доступа, т.к. все операции проходят через CLIENT

4. **Lifecycle management backend ресурсов**
   - Backend управляет lifecycle ТОЛЬКО backend ресурсов (agent_cache, Agent Bus, Qdrant)
   - Workspace пользователя (файловая система) НЕ управляется backend
   - Cleanup backend ресурсов НЕ удаляет файлы пользователя

---

## Tool Signatures с Workspace Context

### Примеры tool signatures для работы с файлами

#### tool_read_file
```python
async def tool_read_file(
    path: str,           # Путь к файлу в workspace пользователя (на client стороне)
    user_id: int         # user_id из JWT токена
) -> dict[str, Any]:
    """
    Прочитать содержимое файла из workspace пользователя (локальной FS).
    
    Parameters:
    - path: Путь к файлу относительно workspace пользователя (например, "src/main.py")
    - user_id: ID пользователя из JWT токена
    
    Returns:
    {
        "success": bool,
        "content": str,  # Содержимое файла
        "size": int,     # Размер файла в байтах
        "error": Optional[str]  # Ошибка при чтении
    }
    
    Процесс:
    1. Backend tool получает запрос с путем к файлу
    2. Tool отправляет запрос на CLIENT с path и user_id
    3. CLIENT валидирует:
       - Путь находится в пределах workspace границ
       - user_id совпадает с текущим пользователем
       - Файл существует и доступен для чтения
    4. CLIENT читает содержимое файла из локальной FS
    5. CLIENT возвращает результат на backend
    6. Tool передает результат агенту
    """
```

#### tool_write_file
```python
async def tool_write_file(
    path: str,           # Путь к файлу в workspace пользователя (на client стороне)
    content: str,        # Новое содержимое файла
    user_id: int,        # user_id из JWT токена
    create_dirs: bool = False  # Создавать ли родительские директории
) -> dict[str, Any]:
    """
    Записать содержимое в файл в workspace пользователя (локальную FS).
    
    Parameters:
    - path: Путь к файлу относительно workspace пользователя
    - content: Новое содержимое
    - user_id: ID пользователя из JWT токена
    
    Returns:
    {
        "success": bool,
        "size": int,       # Размер записанного содержимого
        "timestamp": str,  # ISO timestamp записи
        "error": Optional[str]
    }
    
    Процесс:
    1. Backend tool получает запрос с путем и содержимым
    2. Tool отправляет запрос на CLIENT с path, content, user_id
    3. CLIENT валидирует:
       - Путь находится в пределах workspace границ
       - user_id совпадает с текущим пользователем
       - У пользователя есть разрешения на запись
       - Если create_dirs=False и родители отсутствуют - вернуть ошибку
    4. CLIENT записывает содержимое в файл локальной FS
    5. CLIENT возвращает результат на backend
    6. Tool передает результат агенту
    """
```

#### tool_list_directory
```python
async def tool_list_directory(
    path: str,           # Путь к директории в workspace пользователя (на client стороне)
    user_id: int,        # user_id из JWT токена
    recursive: bool = False,
    pattern: Optional[str] = None
) -> dict[str, Any]:
    """
    Получить список файлов и директорий в workspace пользователя (локальную FS).
    
    Parameters:
    - path: Путь к директории относительно workspace пользователя
    - user_id: ID пользователя из JWT токена
    - recursive: Включить подпапки
    - pattern: Фильтр по шаблону (например, "*.py")
    
    Returns:
    {
        "success": bool,
        "files": [
            {
                "path": str,
                "type": "file" | "directory",
                "size": int,
                "modified": str  # ISO timestamp
            },
            ...
        ],
        "error": Optional[str]
    }
    
    Процесс:
    1. Backend tool получает запрос с путем к директории
    2. Tool отправляет запрос на CLIENT с path, user_id, recursive, pattern
    3. CLIENT валидирует:
       - Путь находится в пределах workspace границ
       - user_id совпадает с текущим пользователем
       - Директория существует и доступна для чтения
       - Если recursive=True - проверить доступ ко всем подпапкам
    4. CLIENT получает список файлов из локальной FS
    5. CLIENT фильтрует по pattern если задан
    6. CLIENT возвращает результат на backend
    7. Tool передает результат агенту
    """
```

### Паттерн валидации доступа (CLIENT SIDE)

```python
# Валидация происходит на CLIENT стороне, где находится локальная FS
async def validate_workspace_access(
    path: str,
    user_id: int,
    workspace_root: str,
    action: str = "read"  # "read", "write", "delete"
) -> tuple[bool, Optional[str]]:
    """
    Валидировать что пользователь имеет доступ к пути в workspace.
    ЭТА ФУНКЦИЯ ВЫПОЛНЯЕТСЯ НА CLIENT СТОРОНЕ!
    
    Returns:
    (is_valid, error_message)
    """
    # 1. Нормализировать путь (на client стороне)
    normalized_path = os.path.normpath(path)
    normalized_root = os.path.normpath(workspace_root)
    
    # 2. Проверить что путь находится ВНУТРИ workspace_root (prevent path traversal)
    # Это критично и делается на client стороне
    if not normalized_path.startswith(normalized_root):
        return False, f"Path {path} is outside workspace bounds"
    
    # 3. Проверить что файл/директория существует (для read операций)
    if action == "read" and not os.path.exists(normalized_path):
        return False, f"Path {path} does not exist"
    
    # 4. Проверить разрешения (на client стороне, где находится FS)
    if action == "read" and not os.access(normalized_path, os.R_OK):
        return False, f"Permission denied to read {path}"
    
    if action == "write" and not os.access(os.path.dirname(normalized_path), os.W_OK):
        return False, f"Permission denied to write to {path}"
    
    return True, None
```

---

## Граничные условия безопасности

### Что агент НЕ может делать

1. **Прямой доступ к файловой системе пользователя**
   - ❌ Агент не может вызвать `open()`, `os.listdir()` напрямую на backend
   - ✅ Агент ДОЛЖЕН использовать tools (tool_read_file, tool_list_directory), которые обращаются к CLIENT

2. **Доступ к workspace других пользователей**
   - ❌ Tool не может прочитать файлы User456 если вызывается от User123
   - ✅ CLIENT валидирует что user_id совпадает и отказывает в доступе к чужим файлам

3. **Обход путем через ".." (path traversal)**
   - ❌ Tool получит path="/workspace/../../../etc/passwd" - НЕ разрешено
   - ✅ CLIENT нормализирует путь и проверяет что результат находится в workspace границах

4. **Управление workspace директориями**
   - ❌ Агент не может создать, переместить или удалить основные директории workspace
   - ✅ Пользователь управляет структурой workspace через client приложение

5. **Доступ к backend ресурсам напрямую**
   - ❌ Агент не может работать с Redis, Qdrant, Agent Bus напрямую
   - ✅ Агент может работать через User Worker Space методы (search_context, add_context)

### Примеры попыток нарушения и защиты

```python
# Попытка 1: Path traversal
# Агент попытается: tool_read_file("/workspace/../../etc/passwd")
# Защита: CLIENT нормализирует путь и проверяет boundaries
# Результат: ❌ Error: "Path is outside workspace bounds"

# Попытка 2: Доступ к другому пользователю
# User123 пытается: tool_read_file("/workspace/user456/secret.txt", user_id=123)
# Защита: CLIENT проверяет что user_id совпадает с текущим пользователем
# Результат: ❌ Error: "User 123 is not authorized to access this path"

# Попытка 3: Прямой доступ к файловой системе
# Агент пытается: import os; os.listdir("/workspace")
# Защита: Агент выполняется на backend и не имеет доступа к локальной FS
# Результат: ❌ Execution blocked (no direct file system access)

# Попытка 4: Удаление важных файлов
# Агент пытается: tool_write_file("/workspace/.gitignore", content="")
# Защита: CLIENT выполняет операцию в контексте пользователя
# Результат: ⚠️ File will be modified (user controls local FS)
```

---

## ADDED Requirements

### Requirement: Per-Project Architecture
User Worker Space ДОЛЖЕН быть создан для КАЖДОГО проекта пользователя (не per-user).

#### Scenario: Каждый проект имеет отдельный Worker Space
- **WHEN** пользователь создает несколько проектов
- **THEN** каждый проект имеет свой изолированный User Worker Space
- **AND** данные одного проекта недоступны другому

#### Scenario: Параллельные Worker Spaces
- **WHEN** пользователь работает с несколькими проектами одновременно
- **THEN** все Worker Spaces работают независимо без конфликтов

### Requirement: Default Starter Pack
User Worker Space инициализируется с 4 default агентами при создании проекта.

#### Scenario: Automatic creation of default agents
- **WHEN** пользователь создает новый проект через POST /my/projects/
- **THEN** backend автоматически создает 4 default агента:
  - agent_coder (developer, gpt-4, temperature=0.3, max_tokens=4096)
  - agent_analyzer (analyst, gpt-4, temperature=0.5, max_tokens=2048)
  - agent_writer (writer, gpt-4, temperature=0.7, max_tokens=2048)
  - agent_researcher (researcher, gpt-4, temperature=0.6, max_tokens=3096)

#### Scenario: Zero-to-use initialization
- **WHEN** пользователь создает проект
- **THEN** User Worker Space полностью инициализирован и готов к использованию
- **AND** все агенты зарегистрированы в Agent Bus
- **AND** все Qdrant collections созданы
- **AND** система готова принять сообщения

#### Scenario: Custom agents addition
- **WHEN** пользователь хочет добавить своего агента
- **THEN** user может создать дополнительного агента через API
- **AND** новый агент добавляется в существующий Worker Space

### Requirement: Инициализация рабочего пространства
Система ДОЛЖНА создавать User Worker Space для проекта при первом запросе.

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
Worker Space ДОЛЖЕН управлять жизненным циклом backend ресурсов с операциями initialization, cleanup и reset. Workspace (файловая система пользователя) НЕ управляется backend и существует независимо от lifecycle backend ресурсов.

#### Scenario: Graceful cleanup
- **WHEN** пользователь завершает сессию или истекает timeout неактивности
- **THEN** Worker Space выполняет cleanup: завершает активные задачи, очищает cache, дерегистрирует агентов
- **AND** НЕ удаляет файлы из workspace пользователя

#### Scenario: Force reset
- **WHEN** администратор или система инициирует reset Worker Space
- **THEN** Worker Space немедленно останавливает все задачи, очищает все ресурсы и реинициализируется
- **AND** НЕ затрагивает workspace пользователя (файловую систему)

#### Scenario: Crash recovery
- **WHEN** Worker Space падает во время выполнения задач
- **THEN** система автоматически восстанавливает Worker Space и помечает незавершенные задачи как failed
- **AND** workspace пользователя остается неизменным

### Requirement: Изоляция между пользователями
Worker Space ДОЛЖЕН обеспечивать полную изоляцию между пользователями и проектами.

#### Scenario: Независимые Worker Spaces
- **WHEN** User123 и User456 одновременно используют систему
- **THEN** их Worker Spaces полностью изолированы и не имеют общих ресурсов

#### Scenario: Независимые Worker Spaces для разных проектов
- **WHEN** User123 работает с несколькими проектами одновременно
- **THEN** каждый проект имеет свой изолированный Worker Space с отдельными backend ресурсами

#### Scenario: Предотвращение утечки данных
- **WHEN** Worker Space обрабатывает данные пользователя
- **THEN** данные никогда не попадают в Worker Space другого пользователя или другого проекта

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

### Requirement: Инвалидация индивидуального кеша агента
Worker Space ДОЛЖЕН предоставлять метод invalidate_agent() для инвалидации кеша конкретного агента.

#### Scenario: Инвалидация после обновления конфигурации
- **WHEN** конфигурация агента обновляется через API
- **THEN** Worker Space может вызвать invalidate_agent(agent_id)
- **AND** кеш агента немедленно очищается (in-memory + Redis)
- **AND** агент будет переинициализирован при следующем использовании

#### Scenario: Инвалидация с переинициализацией
- **WHEN** invalidate_agent() вызывается для зарегистрированного агента
- **THEN** кеш очищается
- **AND** если агент зарегистрирован в Agent Bus - он дерегистрируется и переинициализируется
- **AND** система логирует операцию

### Requirement: Полная очистка кеша проекта
Worker Space ДОЛЖЕН предоставлять метод clear_agent_cache() для полной очистки кеша всех агентов.

#### Scenario: Очистка всего кеша
- **WHEN** вызывается worker_space.clear_agent_cache()
- **THEN** все агенты удаляются из in-memory cache
- **AND** все Redis ключи с pattern "{user_prefix}:agent:*" удаляются
- **AND** используется для recovery или debug операций

#### Scenario: Очистка без влияния на Agent Bus
- **WHEN** clear_agent_cache() выполняется
- **THEN** зарегистрированные в Agent Bus агенты остаются активными
- **AND** следующий запрос перезагружает агента из БД в кеш

### Requirement: Мониторинг статуса агента в Agent Bus
Worker Space ДОЛЖЕН предоставлять метод get_agent_status() для проверки статуса агента.

#### Scenario: Получение статуса активного агента
- **WHEN** вызывается worker_space.get_agent_status(agent_id)
- **THEN** возвращается статус: "idle", "processing", "error"
- **AND** данные берутся из Agent Bus

#### Scenario: Проверка перегруженного агента
- **WHEN** агент обрабатывает максимальное количество задач
- **THEN** статус = "busy" или "at_capacity"
- **AND** система может принять решение использовать другого агента

### Requirement: Получение метрик агента из Agent Bus
Worker Space ДОЛЖЕН предоставлять метод get_agent_metrics() для сбора метрик.

#### Scenario: Получение базовых метрик
- **WHEN** вызывается worker_space.get_agent_metrics(agent_id)
- **THEN** возвращается объект с метриками:
  - tasks_processed: количество обработанных задач
  - tasks_failed: количество ошибок
  - avg_processing_time: среднее время обработки
  - last_activity: последняя активность
  - error_rate: процент ошибок

#### Scenario: Использование метрик для анализа
- **WHEN** система анализирует метрики агента
- **THEN** может принять решение о переобучении или обновлении конфигурации
- **AND** эти данные используются для мониторинга и алертов

### Requirement: Публичная регистрация агента в Agent Bus
Worker Space ДОЛЖЕН предоставлять публичный метод register_agent() для явной регистрации.

#### Scenario: Ручная регистрация агента
- **WHEN** вызывается worker_space.register_agent(agent_id)
- **THEN** агент получается из кеша (или загружается из БД)
- **AND** регистрируется в Agent Bus с его concurrency_limit
- **AND** добавляется в registered_agents сет
- **AND** система логирует регистрацию

#### Scenario: Регистрация нового динамического агента
- **WHEN** новый агент создается после инициализации Worker Space
- **THEN** может быть явно зарегистрирован через register_agent()
- **AND** становится сразу же доступным для обработки задач

### Requirement: Публичная дерегистрация агента из Agent Bus
Worker Space ДОЛЖЕН предоставлять публичный метод deregister_agent() для явной дерегистрации.

#### Scenario: Ручная дерегистрация агента
- **WHEN** вызывается worker_space.deregister_agent(agent_id)
- **THEN** агент дерегистрируется из Agent Bus
- **AND** удаляется из registered_agents сета
- **AND** активные задачи агента завершаются gracefully
- **AND** система логирует дерегистрацию

#### Scenario: Дерегистрация перед удалением
- **WHEN** агент удаляется пользователем
- **THEN** deregister_agent() гарантирует что нет активных задач
- **AND** другие операции не стартуют

### Requirement: Получение контекстного хранилища агента
Worker Space ДОЛЖЕН предоставлять метод get_agent_context_store() для доступа к RAG памяти.

#### Scenario: Получение store для чтения контекста
- **WHEN** вызывается worker_space.get_agent_context_store(agent_id)
- **THEN** возвращается AgentContextStore с правильной collection name
- **AND** collection name = "user{user_id}_project{project_id}_{agent_name}_context"
- **AND** store готов к операциям поиска и добавления

#### Scenario: Использование store для RAG
- **WHEN** агент нуждается в контексте для задачи
- **THEN** может получить store и выполнить search/add/clear операции
- **AND** все операции изолированы per-project

### Requirement: Проверка/создание Qdrant collection для агента
Worker Space ДОЛЖЕН предоставлять метод ensure_agent_collection() для инициализации.

#### Scenario: Создание collection при отсутствии
- **WHEN** вызывается worker_space.ensure_agent_collection(agent_id)
- **THEN** система проверяет существование Qdrant collection
- **AND** если collection отсутствует - создается с правильным naming и конфигурацией
- **AND** настраиваются индексы для поиска по metadata

#### Scenario: Проверка при инициализации Worker Space
- **WHEN** Worker Space инициализируется
- **THEN** вызывается ensure_agent_collection() для каждого агента
- **AND** гарантируется что все collections существуют перед использованием

### Requirement: Поиск контекста в памяти агента
Worker Space ДОЛЖЕН предоставлять метод search_context() для RAG поиска.

#### Scenario: Семантический поиск в контексте
- **WHEN** вызывается worker_space.search_context(agent_id, query)
- **THEN** выполняется семантический поиск в Qdrant collection агента
- **AND** возвращаются top-k релевантные взаимодействия с relevance scores
- **AND** поиск работает за < 50ms (P95)

#### Scenario: Фильтрованный поиск
- **WHEN** поиск выполняется с фильтрами (по типу, по успеху, по дате)
- **THEN** результаты фильтруются перед возвратом
- **AND** только релевантные и разрешенные результаты видны

### Requirement: Добавление взаимодействия в памяти агента
Worker Space ДОЛЖЕН предоставлять метод add_context() для сохранения взаимодействий.

#### Scenario: Сохранение успешного взаимодействия
- **WHEN** вызывается worker_space.add_context(agent_id, interaction_data)
- **THEN** взаимодействие сохраняется в Qdrant collection агента
- **AND** генерируется embedding и сохраняется с метаданными (task_id, timestamp, success, type)
- **AND** становится доступным для future RAG поисков

#### Scenario: Обогащение памяти проекта
- **WHEN** каждое взаимодействие добавляется
- **THEN** система строит Knowledge Base проекта
- **AND** будущие агенты могут учиться на истории

### Requirement: Очистка памяти агента
Worker Space ДОЛЖЕН предоставлять метод clear_context() для удаления контекста.

#### Scenario: Полная очистка памяти агента
- **WHEN** вызывается worker_space.clear_context(agent_id)
- **THEN** все vectors удаляются из Qdrant collection агента
- **AND** collection остается существовать для новых взаимодействий
- **AND** используется для reset или privacy операций

#### Scenario: Очистка перед удалением агента
- **WHEN** агент удаляется пользователем
- **THEN** его контекст может быть очищен или архивирован
- **AND** освобождаются ресурсы в Qdrant

### Requirement: Прямое выполнение задачи конкретным агентом
Worker Space ДОЛЖЕН предоставлять метод direct_execution() для синхронного выполнения.

#### Scenario: Синхронное выполнение в direct mode
- **WHEN** вызывается worker_space.direct_execution(agent_id, task_payload)
- **THEN** задача отправляется напрямую агенту через Agent Bus
- **AND** система ожидает результат (с timeout 30 сек)
- **AND** возвращается структурированный результат с response и metadata

#### Scenario: Обработка успешного выполнения
- **WHEN** агент успешно выполняет задачу
- **THEN** result содержит: success=true, response="...", context=["..."]
- **AND** результат автоматически сохраняется в контексте агента через add_context()

#### Scenario: Обработка ошибок агента
- **WHEN** агент выбрасывает ошибку или timeout
- **THEN** result содержит: success=false, error="...", error_type="timeout|execution|..."
- **AND** ошибка логируется и может быть использована для анализа

### Requirement: Оркестрированное выполнение с планированием графа задач
Worker Space ДОЛЖЕН предоставлять метод orchestrated_execution() для multi-step workflows.

#### Scenario: Делегирование на Orchestrator
- **WHEN** вызывается worker_space.orchestrated_execution(task_payload)
- **THEN** задача передается на Personal Orchestrator для планирования
- **AND** Orchestrator создает граф задач с несколькими агентами
- **AND** возвращается ID workflow для отслеживания

#### Scenario: Параллельное выполнение нескольких агентов
- **WHEN** Orchestrator планирует граф с независимыми узлами
- **THEN** несколько агентов могут выполняться параллельно
- **AND** Worker Space координирует их работу через Agent Bus
- **AND** результаты объединяются в финальный ответ

#### Scenario: Зависимые задачи в workflow
- **WHEN** результат одного агента нужен другому
- **THEN** Orchestrator управляет порядком выполнения
- **AND** контекст передается между агентами
- **AND** система гарантирует консистентность данных

### Requirement: Обработка сообщения в контексте проекта
Worker Space ДОЛЖЕН предоставлять метод handle_message() для единого входного API.

#### Scenario: Direct mode - сообщение с target_agent
- **WHEN** вызывается worker_space.handle_message(message, target_agent_id)
- **THEN** выполняется direct_execution() для указанного агента
- **AND** результат оформляется в MessageResponse
- **AND** возвращается немедленно с full_response или streaming chunk

#### Scenario: Orchestrated mode - сообщение без target_agent
- **WHEN** вызывается worker_space.handle_message(message, target_agent=None)
- **THEN** выполняется orchestrated_execution() через Orchestrator
- **AND** система планирует оптимальный граф агентов
- **AND** результат объединяет ответы всех задействованных агентов

#### Scenario: Автоматическое сохранение в RAG контекст
- **WHEN** handle_message() завершается успешно
- **THEN** взаимодействие (user message + assistant response) сохраняется
- **AND** может быть позже использовано для поиска и контекста
- **AND** система строит Knowledge Base проекта на основе истории

#### Scenario: Переключение между режимами в сессии
- **WHEN** пользователь чередует direct и orchestrated запросы
- **THEN** handle_message() корректно обрабатывает оба типа
- **AND** контекст и состояние сохраняются между запросами
- **AND** нет конфликтов или потери данных

### Requirement: Полные метрики Worker Space
Worker Space ДОЛЖЕН предоставлять метод get_metrics() для полного мониторинга.

#### Scenario: Получение метрик использования
- **WHEN** вызывается worker_space.get_metrics()
- **THEN** возвращается объект с полными метриками:
  - user_id: идентификатор пользователя
  - project_id: идентификатор проекта
  - active_agents: количество зарегистрированных агентов (len(registered_agents))
  - cache_size: текущий размер кеша (len(agent_cache))
  - total_tasks_processed: счетчик задач (task_counter)
  - uptime: время работы worker space (time.time() - start_time)
  - is_healthy: boolean статус здоровья

#### Scenario: Использование метрик для мониторинга
- **WHEN** система периодически вызывает get_metrics()
- **THEN** можно видеть тренды: растет ли нагрузка, есть ли утечки памяти
- **AND** можно установить пороги для алертов (uptime too long = reset needed)
- **AND** dashboards показывают health различных projects

#### Scenario: Debug и troubleshooting
- **WHEN** возникает проблема с worker space
- **THEN** get_metrics() помогает диагностировать:
  - cache_size == 0? → инициализация не произошла
  - active_agents < expected? → какие агенты пропали
  - task_counter >> ожидания? → слишком много нагрузки
