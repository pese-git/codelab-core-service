# Спецификация: Agent Tools System

## Обзор

Агенты должны иметь возможность выполнять операции над файловой системой и командами на стороне пользователя (CLIENT side) через инструменты (tools). Все операции должны быть безопасными и могут требовать подтверждения пользователя для опасных операций.

## 1. Доступные Tools

### 1.1 Чтение файлов
**Tool**: `tool_read_file(path: str, user_id: UUID) -> dict`

```
Параметры:
  path (str): путь к файлу в workspace пользователя
  user_id (UUID): ID пользователя (для изоляции)

Возвращает:
  {
    "success": bool,
    "content": str (содержимое файла),
    "encoding": str (utf-8, binary, etc),
    "size": int (размер в байтах),
    "error": str (если ошибка)
  }

Граничные условия безопасности:
  - Валидация пути: должен быть внутри workspace директории пользователя
  - Не должен позволять выход за пределы workspace (..)
  - Не должен читать системные файлы
  - Максимальный размер файла: 100MB
  - Ограничение на типы: запрещены бинарные файлы (кроме белого списка: pdf, images)

Подтверждение пользователя: НЕ требуется (информационная операция)
```

### 1.2 Редактирование файлов
**Tool**: `tool_write_file(path: str, content: str, mode: str = "write", user_id: UUID) -> dict`

```
Параметры:
  path (str): путь к файлу в workspace пользователя
  content (str): содержимое для записи
  mode (str): "write" (замена), "append" (добавление)
  user_id (UUID): ID пользователя

Возвращает:
  {
    "success": bool,
    "path": str,
    "size": int (новый размер файла),
    "error": str
  }

Граничные условия безопасности:
  - Валидация пути: только в workspace пользователя
  - Не должен перезаписывать системные файлы
  - Максимальный размер записи: 100MB
  - Проверка прав доступа на файл
  - Валидация расширения файла (исключить .exe, .bin, .so)

Подтверждение пользователя: ДА, обязательно (могут быть изменения важных файлов)
Уровень риска: HIGH (изменение данных пользователя)
```

### 1.3 Выполнение команд
**Tool**: `tool_execute_command(command: str, args: list = [], timeout: int = 30, user_id: UUID) -> dict`

```
Параметры:
  command (str): команда для выполнения (ограниченный список)
  args (list): аргументы команды
  timeout (int): таймаут в секундах (макс 300)
  user_id (UUID): ID пользователя

Возвращает:
  {
    "success": bool,
    "stdout": str,
    "stderr": str,
    "exit_code": int,
    "execution_time": float (в секундах),
    "error": str
  }

Граничные условия безопасности:
  - Разрешенный список команд (белый список):
    * Утилиты поиска: grep, find, locate
    * Утилиты файлов: ls, cat, head, tail, wc
    * Компиляция: gcc, python, node, npm
    * Git операции: git clone, git pull, git commit
    * Утилиты архивирования: zip, unzip, tar
    * Системные утилиты: echo, date, pwd, whoami
  - ЗАПРЕЩЕННЫЕ команды:
    * rm -rf, dd, mkfs (разрушающие операции)
    * sudo, su (escalation)
    * curl с опасными флагами (RCE векторы)
    * wget с опасными параметрами
    * ssh-keygen, openssl (генерация ключей)
    * pacman, apt, yum (установка пакетов)
  - Таймаут выполнения: максимум 300 секунд
  - Изоляция окружения: собственный environment (без доступа к sensitive env vars)
  - Максимальный размер вывода: 1MB
  - Запуск только в контексте пользователя (user namespace isolation)

Подтверждение пользователя: Зависит от команды
  - LOW риск (информационные): grep, find, ls → без подтверждения
  - MEDIUM риск (модификация): git, npm, python scripts → требуется подтверждение
  - HIGH риск (системные): все остальные → требуется подтверждение
```

### 1.4 Получение списка файлов
**Tool**: `tool_list_directory(path: str, user_id: UUID, recursive: bool = False, pattern: str = "*") -> dict`

```
Параметры:
  path (str): директория для просмотра
  user_id (UUID): ID пользователя
  recursive (bool): показать файлы рекурсивно
  pattern (str): glob pattern для фильтрации

Возвращает:
  {
    "success": bool,
    "files": [
      {
        "name": str,
        "path": str,
        "type": str ("file" | "directory"),
        "size": int,
        "modified": str (ISO 8601)
      }
    ],
    "total_count": int,
    "error": str
  }

Граничные условия безопасности:
  - Только директории внутри workspace
  - Максимум 1000 результатов (для производительности)
  - Скрытые файлы (.*) показываются только если явно в pattern

Подтверждение пользователя: НЕ требуется (информационная операция)
```

## 2. Механизм Подтверждения

### 2.1 Approval Flow

```
Agent запрашивает tool → Backend отправляет APPROVAL_REQUIRED событие →
Пользователь видит запрос в UI → 
Пользователь подтверждает/отклоняет →
Backend отправляет tool результат или ошибку →
Agent продолжает работу
```

### 2.2 Risk Assessment

Каждый tool должен иметь уровень риска:

```
LOW_RISK:
  - tool_read_file (любые файлы)
  - tool_list_directory
  - tool_execute_command с информационными командами (grep, ls, find)

MEDIUM_RISK:
  - tool_write_file (для определенных расширений: .txt, .md, .json, .py, .js)
  - tool_execute_command с модификацией (git, npm install, python script)

HIGH_RISK:
  - tool_write_file (для .exe, .bin, .sh, .conf, .sys)
  - tool_execute_command с системными командами
  - tool_execute_command с компилятором и опасными флагами
```

### 2.3 Timeout для Подтверждения

- LOW_RISK: без таймаута (не требуется подтверждение)
- MEDIUM_RISK: 5 минут (300 сек)
- HIGH_RISK: 10 минут (600 сек)

После истечения таймаута:
- Запрос отклоняется автоматически
- Agent получает ошибку "Approval timeout"
- Событие логируется

### 2.4 Batch Approval

Пользователь может одобрить:
1. Одну операцию (одноразовое)
2. Класс операций (например, все git команды в этой сессии)
3. Все операции агента в этой сессии (с предупреждением)

## 3. Integration с Approval Manager

Tool approval должен быть интегрирован с существующей `ApprovalManager`:

```python
class ApprovalManager:
    async def request_tool_approval(
        self,
        user_id: UUID,
        tool_name: str,
        tool_params: dict,
        risk_level: RiskLevel,  # LOW, MEDIUM, HIGH
        timeout_seconds: int,
        agent_id: Optional[UUID] = None,
        session_id: Optional[UUID] = None
    ) -> ApprovalRequest:
        """Создание запроса подтверждения для tool"""
        
    async def get_pending_approvals(
        self,
        user_id: UUID
    ) -> list[ApprovalRequest]:
        """Получить все ожидающие подтверждения"""
        
    async def approve_tool(
        self,
        approval_id: UUID,
        user_id: UUID
    ) -> bool:
        """Подтвердить выполнение tool"""
        
    async def reject_tool(
        self,
        approval_id: UUID,
        user_id: UUID,
        reason: Optional[str] = None
    ) -> bool:
        """Отклонить выполнение tool"""
```

## 4. Implementation Details

### 4.1 Tool Execution Context

Все tools должны выполняться в контексте пользователя:

```
Frontend User → Backend (gets user_id from JWT) → 
Tool validation (path check, command whitelist, risk level) →
Approval check (if needed) →
USER_SIDE execution (on client through tool handler) →
Result return to Backend →
Agent receives result
```

### 4.2 Tool Validation Pattern

```python
async def validate_and_execute_tool(
    tool_name: str,
    tool_params: dict,
    user_id: UUID,
    session_id: UUID
) -> dict:
    # 1. Validate tool exists
    if tool_name not in AVAILABLE_TOOLS:
        return {"success": False, "error": "Tool not found"}
    
    # 2. Validate parameters (path, command, etc)
    try:
        validate_tool_params(tool_name, tool_params, user_id)
    except ValidationError as e:
        return {"success": False, "error": str(e)}
    
    # 3. Check risk level and request approval if needed
    risk_level = get_risk_level(tool_name, tool_params)
    if risk_level != RiskLevel.LOW:
        approval = await approval_manager.request_tool_approval(
            user_id=user_id,
            tool_name=tool_name,
            tool_params=tool_params,
            risk_level=risk_level,
            timeout_seconds=get_timeout(risk_level),
            session_id=session_id
        )
        
        # Wait for user approval
        result = await approval.wait_for_decision(timeout=get_timeout(risk_level))
        if not result.approved:
            return {"success": False, "error": "Approval denied"}
    
    # 4. Execute tool on CLIENT side
    result = await execute_tool_on_client(tool_name, tool_params, user_id)
    
    # 5. Log execution
    await log_tool_execution(user_id, tool_name, result, risk_level)
    
    return result
```

### 4.3 Client-Side Tool Handler

На CLIENT (frontend или desktop app) должен быть handler:

```javascript
// Pseudo-code
class ToolHandler {
  async executeReadFile(path, userId) {
    // Validate path is in workspace
    if (!isInWorkspace(path)) throw new Error("Path outside workspace");
    
    // Read file
    const content = await fs.readFile(path);
    return { success: true, content };
  }
  
  async executeWriteFile(path, content, userId) {
    // Validate path
    if (!isInWorkspace(path)) throw new Error("Path outside workspace");
    if (isDangerousExtension(path)) throw new Error("File type not allowed");
    
    // Write file
    await fs.writeFile(path, content);
    return { success: true, path };
  }
  
  async executeCommand(command, args, userId) {
    // Check command in whitelist
    if (!isWhitelisted(command)) throw new Error("Command not allowed");
    
    // Execute with timeout and isolation
    const result = await exec(command, args, { timeout: 30000 });
    return { success: true, stdout: result.stdout };
  }
  
  async listDirectory(path, userId, recursive, pattern) {
    // Validate path
    if (!isInWorkspace(path)) throw new Error("Path outside workspace");
    
    // List files
    const files = await fs.listDir(path, { recursive, pattern });
    return { success: true, files };
  }
}
```

## 5. Scenarios

### Scenario: Агент читает файл
1. Agent → tool_read_file("workspace/README.md")
2. Backend валидирует параметры
3. Backend отправляет в client execution
4. Client выполняет чтение файла
5. Результат возвращается Agent

### Scenario: Агент хочет изменить файл
1. Agent → tool_write_file("workspace/config.json", new_content)
2. Backend определяет risk_level = HIGH
3. Backend создает ApprovalRequest
4. Backend отправляет APPROVAL_REQUIRED событие пользователю
5. Пользователь видит в UI: "Agent хочет изменить config.json"
6. Пользователь кликает "Approve"
7. Backend отправляет tool execution в client
8. Client выполняет запись файла
9. Agent получает результат

### Scenario: Агент хочет выполнить команду
1. Agent → tool_execute_command("npm", ["install", "express"])
2. Backend определяет risk_level = MEDIUM
3. Backend проверит, что "npm" в whitelist
4. Backend создает ApprovalRequest с 5-минутным таймаутом
5. Пользователь подтверждает или отклоняет
6. Client выполняет команду с timeout=300
7. Agent получает stdout/stderr

### Scenario: Агент пытается опасную операцию
1. Agent → tool_execute_command("rm", ["-rf", "/"])
2. Backend проверяет: "rm" НЕ в whitelist
3. Backend отклоняет с ошибкой "Command not allowed"
4. Agent не может выполнить операцию

## 6. Security Boundaries

- ✅ Agents МОГУТ читать файлы в workspace пользователя
- ✅ Agents МОГУТ писать файлы в workspace пользователя (с подтверждением)
- ✅ Agents МОГУТ выполнять разрешенные команды (с подтверждением для модификации)
- ❌ Agents НЕ МОГУТ обойти validation checks
- ❌ Agents НЕ МОГУТ выполнять команды вне whitelist
- ❌ Agents НЕ МОГУТ выполнять операции вне workspace пользователя
- ❌ Agents НЕ МОГУТ одобрять свои собственные requests
- ❌ Agents НЕ МОГУТ видеть результаты tools других пользователей
