# Спецификация: User Worker Space

## Обзор

User Worker Space - это компонент backend, который управляет персональным рабочим пространством пользователя для каждого проекта. Он обеспечивает:
- Инициализацию и управление lifecycle backend ресурсов (agent_cache, Agent Bus, Qdrant collections)
- Координацию между режимами выполнения (direct/orchestrated)
- Доступ к персональному RAG контексту агентов через Qdrant
- Полную изоляцию между пользователями и проектами
- Per-project архитектуру (отдельный Worker Space для каждого проекта пользователя)
- Default Starter Pack инициализацию с 4 default агентами

**Ключевое архитектурное разделение:**
- **Workspace** (файловая система пользователя) находится на стороне пользователя (локально на клиентском компьютере)
- **Backend ресурсы** (agent_cache, Agent Bus, Qdrant) управляются User Worker Space backend компонентой на сервере
- **Агенты** (выполняются на backend сервере) получают доступ к workspace пользователя исключительно через tools с передачей контекста
- **Валидация путей** происходит на стороне пользователя (client), где находится локальная файловая система

---

## 1. Workspace Access Architecture

### 1.1 Архитектурный поток доступа

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

### 1.2 Sequence Diagram: Доступ к файлам workspace

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

### 1.3 Полный Tool Execution Workflow

```
┌────────────────────────────────────────────────────────────────────────────────┐
│ USER SENDS TASK                                                                │
└────────────────────────┬─────────────────────────────────────────────────────┘
                         ↓
┌────────────────────────────────────────────────────────────────────────────────┐
│ SERVER RECEIVES                                                                │
└────────────────────────┬─────────────────────────────────────────────────────┘
                         ↓
┌────────────────────────────────────────────────────────────────────────────────┐
│ AGENT ANALYZES & SELECTS TOOL                                                 │
└────────────────────────┬─────────────────────────────────────────────────────┘
                         ↓
┌────────────────────────────────────────────────────────────────────────────────┐
│ TOOL EXECUTOR VALIDATES PARAMETERS                                             │
│ - PathValidator: проверяет пути в workspace границах                          │
│ - CommandValidator: валидирует команды                                        │
│ - SizeLimiter: проверяет размер данных                                       │
└────────────────────────┬──────────────────┬──────────────────────────────────┘
                         │                  │
                    ✓ OK │                  │ ❌ Error
                         ↓                  ↓
         ┌─────────────────────────┐  ┌─────────────────────┐
         │ RISK ASSESSMENT         │  │ RETURN ERROR TO     │
         │ RiskAssessor оценивает  │  │ AGENT               │
         │ риск операции           │  └────────┬────────────┘
         └────────────┬────────────┘           │
                      ↓                        │
         ┌────────────────────────┐            │
         │ Risk Level: LOW?        │            │
         └────┬─────────────┬──────┘            │
        YES ↓              ↓ NO                 │
          ┌────────┐    ┌─────────────────────┐│
          │ AUTO   │    │ REQUEST APPROVAL    ││
          │APPROVE │    │ via SSE             ││
          └───┬────┘    └────────┬────────────┘│
              │                  ↓             │
              │         ┌─────────────────────┐│
              │         │ CLIENT gets event   ││
              │         │ TOOL_APPROVAL_      ││
              │         │ REQUEST             ││
              │         └────────┬────────────┘│
              │                  ↓             │
              │         ┌─────────────────────┐│
              │         │ USER sees dialog    ││
              │         └────────┬────────────┘│
              │                  ↓             │
              │         ┌──────────────────────┐
              │         │ User decides?       │
              │         └─┬────────────────┬──┘
              │      ✓ YES│            NO ✓
              │           ↓              ↓
              │      ┌──────────┐  ┌──────────┐
              │      │ /approve │  │/reject   │
              │      │ REST     │  │REST      │
              │      └────┬─────┘  └────┬─────┘
              │           │             ↓
              └─────┬─────┘        ┌────────────┐
                    ↓              │ Return err │
        ┌─────────────────────────┐│ to Agent   │
        │ SEND TOOL_EXECUTION_    │└────┬───────┘
        │ SIGNAL via SSE          │     │
        └────────────┬────────────┘     │
                     ↓                  │
        ┌─────────────────────────┐    │
        │ CLIENT gets signal      │    │
        │ TOOL_EXECUTION_SIGNAL   │    │
        └────────────┬────────────┘    │
                     ↓                  │
        ┌─────────────────────────┐    │
        │ CLIENT executes tool    │    │
        │ LOCALLY on workspace    │    │
        │ (file operations)       │    │
        └────────────┬────────────┘    │
                     ↓                  │
        ┌─────────────────────────┐    │
        │ CLIENT sends result     │    │
        │ REST: /tools/{id}/      │    │
        │       result            │    │
        └────────────┬────────────┘    │
                     ↓                  │
        ┌─────────────────────────┐    │
        │ SERVER saves result     │    │
        │ in DB                   │    │
        └────────────┬────────────┘    │
                     ↓                  │
        ┌─────────────────────────┐    │
        │ AGENT unblocked         │    │
        └────────────┬────────────┘    │
                     ↓                  │
        ┌─────────────────────────┐    │
        │ AGENT processes result  │    │
        └────────────┬────────────┘    │
                     ↓                  │
        ┌─────────────────────────┐    │
        │ AGENT generates answer  │    │
        └────────────┬────────────┘    │
                     ↓                  │
        ┌─────────────────────────────┬┘
        │ USER gets final answer      │
        └─────────────────────────────┘
```

### 1.4 Ключевые архитектурные принципы

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

5. **Approval Workflow для высокорисковых операций**
   - ToolExecutor валидирует параметры (PathValidator, CommandValidator, SizeLimiter)
   - RiskAssessor оценивает риск операции
   - LOW risk операции auto-approve и отправляются на client
   - HIGH risk операции требуют одобрения пользователя через SSE + диалог
   - Client получает сигнал выполнения после одобрения
   - Client выполняет tool локально и отправляет результат на server
   - Server сохраняет результат и разблокирует агента

---

## 2. Tool Signatures с Workspace Context

### 2.1 Примеры tool signatures для работы с файлами

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

### 2.2 Паттерн валидации доступа (CLIENT SIDE)

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

## 3. Граничные условия безопасности

### 3.1 Что агент НЕ может делать

1. **Прямой доступ к файловой системе пользователя**
   - ❌ Агент не может вызвать `open()`, `os.listdir()` напрямую на backend
   - ✅ Агент ДОЛЖЕН использовать tools (tool_read_file, tool_list_directory), которые обращаются к CLIENT

2. **Доступ к workspace других пользователей**
   - ❌ Tool не может прочитать файлы User456 если вызывается от User123
   - ✅ CLIENT валидирует что user_id совпадает и отказывает в доступе к чужим файлам

3. **Обход пути через ".." (path traversal)**
   - ❌ Tool получит path="/workspace/../../../etc/passwd" - НЕ разрешено
   - ✅ CLIENT нормализирует путь и проверяет что результат находится в workspace границах

4. **Управление workspace директориями**
   - ❌ Агент не может создать, переместить или удалить основные директории workspace
   - ✅ Пользователь управляет структурой workspace через client приложение

5. **Доступ к backend ресурсам напрямую**
   - ❌ Агент не может работать с Redis, Qdrant, Agent Bus напрямую
   - ✅ Агент может работать через User Worker Space методы (search_context, add_context)

### 3.2 Примеры попыток нарушения и защиты

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

## 4. Requirements

### 4.1 Per-Project Architecture
User Worker Space ДОЛЖЕН быть создан для КАЖДОГО проекта пользователя (не per-user).

#### Scenario: Каждый проект имеет отдельный Worker Space
- **WHEN** пользователь создает несколько проектов
- **THEN** каждый проект имеет свой изолированный User Worker Space
- **AND** данные одного проекта недоступны другому

#### Scenario: Параллельные Worker Spaces
- **WHEN** пользователь работает с несколькими проектами одновременно
- **THEN** все Worker Spaces работают независимо без конфликтов

### 4.2 Default Starter Pack
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

### 4.3 Инициализация рабочего пространства
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

### 4.4 Управление кешем агентов
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

### 4.5 Интеграция с Personal Agent Bus
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

### 4.6 Интеграция с Qdrant контекстом
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

### 4.7 Координация между режимами выполнения
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

### 4.8 Lifecycle management
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

### 4.9 Изоляция между пользователями
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

### 4.10 Мониторинг и метрики
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

### 4.11 Архитектура доступа к workspace
Система ДОЛЖНА обеспечивать четкое разделение ответственности в доступе к workspace: workspace (файловая система пользователя) уже существует на стороне пользователя, пользователь предоставляет доступ к workspace через tools, агенты НЕ имеют прямого доступа к файловой системе.

#### Scenario: Workspace существует на стороне пользователя
- **WHEN** пользователь работает с client приложением
- **THEN** workspace (файловая система пользователя с локальными файлами, проектами, директориями) уже существует и управляется пользователем

#### Scenario: Агент запрашивает доступ к файлам workspace
- **WHEN** агент выполняет задачу и требуется доступ к файлам workspace
- **THEN** агент вызывает соответствующий tool (например, `tool_read_file`, `tool_write_file`, `tool_list_directory`) с путем к файлу/директории, tool выполняет операцию в файловой системе пользователя и возвращает результат

#### Scenario: Прямой доступ агента к файловой системе запрещен
- **WHEN** агент пытается получить прямой доступ к файловой системе пользователя
- **THEN** система предотвращает такой доступ, агент может работать с файлами только через tools

#### Scenario: Backend управляет backend ресурсами для проекта
- **WHEN** поступает запрос от пользователя для конкретного проекта
- **THEN** User Worker Space backend компонента создает/использует backend ресурсы (agent_cache, Agent Bus регистрация, Qdrant collections) для обслуживания агентов этого проекта, которые работают с уже существующим workspace пользователя через tools

### 4.12 Tool signatures с workspace context
Все tools, работающие с файловой системой workspace, ДОЛЖНЫ явно принимать пути к файлам/директориям как параметры и выполнять операции в контексте workspace пользователя.

#### Scenario: Tool получает путь к файлу workspace
- **WHEN** tool вызывается агентом для работы с файлом
- **THEN** tool получает путь к файлу (например, `/path/to/project/file.py`) как параметр и выполняет операцию в файловой системе пользователя

#### Scenario: Tool валидирует доступ к workspace
- **WHEN** tool получает путь к файлу/директории
- **THEN** tool проверяет, что путь находится в пределах workspace пользователя и user_id из JWT токена соответствует владельцу workspace

#### Scenario: Tool выполняет операции в workspace пользователя
- **WHEN** tool выполняет операцию с файлом (чтение, запись, удаление)
- **THEN** tool выполняет операцию в файловой системе пользователя и возвращает результат агенту без утечки информации о структуре workspace других пользователей

### 4.13 Backend координация backend ресурсов
User Worker Space компонента backend ДОЛЖНА управлять backend ресурсами (agent_cache, Agent Bus, Qdrant collections) для обслуживания агентов, которые работают с workspace пользователя через tools.

#### Scenario: Backend создает backend ресурсы для проекта
- **WHEN** поступает первый запрос от пользователя для конкретного проекта
- **THEN** User Worker Space создает backend ресурсы для этого проекта: agent_cache для кеширования агентов, регистрирует агентов в Agent Bus, обеспечивает доступ к Qdrant collections

#### Scenario: Backend управляет lifecycle backend ресурсов проекта
- **WHEN** пользователь активно работает с проектом
- **THEN** User Worker Space управляет agent_cache TTL, координирует задачи через Agent Bus, обеспечивает доступ к Qdrant/Redis для этого проекта, но НЕ управляет файловой системой пользователя

#### Scenario: Backend выполняет cleanup backend ресурсов проекта
- **WHEN** пользователь завершает работу с проектом или истекает timeout неактивности
- **THEN** User Worker Space завершает активные задачи проекта, очищает cache, дерегистрирует агентов, освобождает backend ресурсы, но НЕ удаляет файлы из workspace пользователя

### 4.14 Разделение ответственности компонентов
Система ДОЛЖНА явно разделять ответственность между компонентами в управлении workspace и backend ресурсами.

#### Scenario: Пользователь управляет workspace (файловой системой)
- **WHEN** пользователь работает с client приложением
- **THEN** пользователь управляет своей файловой системой (создает проекты, редактирует файлы, организует директории), workspace существует независимо от backend системы

#### Scenario: Backend управляет backend ресурсами для проекта
- **WHEN** backend получает запрос от пользователя для конкретного проекта
- **THEN** backend создает и управляет backend ресурсами (agent_cache, Agent Bus, Qdrant collections) для обслуживания агентов этого проекта, но НЕ управляет файловой системой пользователя напрямую

#### Scenario: Агенты используют workspace через tools
- **WHEN** агент выполняет задачу, требующую работы с файлами
- **THEN** агент вызывает tools с путями к файлам, tools выполняют операции в файловой системе пользователя от имени агента, агент получает результаты, но НЕ имеет прямого доступа к файловой системе

#### Scenario: Tools как посредники доступа к workspace
- **WHEN** tool вызывается агентом
- **THEN** tool выступает посредником между агентом и файловой системой пользователя: получает путь к файлу, валидирует доступ через backend (user_id из JWT), выполняет операцию, возвращает результат агенту
