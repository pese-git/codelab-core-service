# Agent Tools System - Детальный План Реализации

## 📊 Обзор архитектуры

```
┌─────────────────────────────────────────────────────────────────────┐
│                       VS Code Extension                             │
│                                                                     │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │  React WebView (Chat Interface)                            │   │
│  │  - Отправляет tool request через postMessage              │   │
│  │  - Отображает progress/results                            │   │
│  └────────────┬───────────────────────────────────────────────┘   │
│               │ postMessage("EXECUTE_TOOL", {tool, params})       │
│               │                                                    │
│  ┌────────────▼───────────────────────────────────────────────┐   │
│  │  Extension.ts (Main Process)                              │   │
│  │  - Получает tool request                                  │   │
│  │  - Валидирует параметры                                   │   │
│  │  - Отправляет в ToolHandler                               │   │
│  └────────────┬───────────────────────────────────────────────┘   │
│               │ IPC / Native API                                   │
│               │                                                    │
│  ┌────────────▼───────────────────────────────────────────────┐   │
│  │  ToolHandler.ts                                            │   │
│  │  - tool_read_file (fs.readFile)                            │   │
│  │  - tool_write_file (fs.writeFile)                          │   │
│  │  - tool_execute_command (child_process.exec)              │   │
│  │  - tool_list_directory (fs.readdir)                        │   │
│  │  - Workspace boundary validation                           │   │
│  └────────────┬───────────────────────────────────────────────┘   │
│               │ Results → Backend API                             │
│               │                                                    │
└───────────────┼────────────────────────────────────────────────────┘
                │
                │ HTTP POST /tool/execute + results
                │
        ┌───────▼────────────────────────────┐
        │     Backend (FastAPI)              │
        │                                    │
        │  ┌──────────────────────────────┐ │
        │  │  Tool Manager                │ │
        │  │  - Risk Assessment           │ │
        │  │  - Validation Schemas        │ │
        │  └──────────────────────────────┘ │
        │                                    │
        │  ┌──────────────────────────────┐ │
        │  │  Approval Manager            │ │
        │  │  - request_tool_approval()   │ │
        │  │  - confirm_approval()        │ │
        │  │  - Auto-approve LOW risk     │ │
        │  └──────────────────────────────┘ │
        │                                    │
        │  ┌──────────────────────────────┐ │
        │  │  REST API Endpoints          │ │
        │  │  POST /my/tools/execute      │ │
        │  │  POST /my/approvals/{id}/... │ │
        │  └──────────────────────────────┘ │
        │                                    │
        └────────────────────────────────────┘
```

## 🎯 Фазы реализации

### Фаза 1: Backend Infrastructure (Tasks 8.1 - 8.3)
**Цель**: Создать Backend layer для управления tools, валидации и оценки рисков

#### 8.1 Tool Signatures & Definitions
- **8.1.1** Создать `app/core/tools/definitions.py` с определениями всех tools
  - Структура: name, description, parameters, risk_level, requires_approval
  - Tools: read_file, write_file, execute_command, list_directory

- **8.1.2** Создать `app/schemas/tool.py` с Pydantic схемами
  - ToolReadFileRequest, ToolWriteFileRequest, ToolExecuteCommandRequest, ToolListDirectoryRequest
  - ToolExecutionResult schema

- **8.1.3** Создать `app/core/tools/models.py` для Database models (если требуется логирование)

#### 8.2 Security & Validation Layer
- **8.2.1** Создать `app/core/tools/validator.py` - ToolValidator класс
  - `validate_file_path(path, user_id)` - проверка workspace boundaries
  - `validate_read_params(path, max_size=100MB)`
  - `validate_write_params(path, content, mode)`
  - Валидация расширений (.exe, .bin, .so запрещены для write)

- **8.2.2** Создать `app/core/tools/command_whitelist.py` - CommandValidator
  - Whitelist: grep, find, locate, ls, cat, head, tail, wc, git, npm, node, python, gcc, zip, unzip, tar, echo, date, pwd, whoami
  - Blacklist: rm -rf, dd, mkfs, sudo, su, curl [опасные флаги], wget [опасные], ssh-keygen, openssl, pacman, apt, yum
  - `is_command_allowed(command)` - проверка
  - `validate_command_safety(command, args)` - парсинг и проверка аргументов

- **8.2.3** Создать `app/core/tools/size_limiter.py`
  - MAX_FILE_SIZE = 100MB
  - MAX_OUTPUT_SIZE = 1MB
  - MAX_COMMAND_TIMEOUT = 300 сек
  - Функции проверки лимитов

#### 8.3 Risk Assessment System
- **8.3.1** Создать `app/core/tools/risk_assessor.py` - RiskAssessor класс
  - Risk levels: LOW, MEDIUM, HIGH (Enum)
  - Матрица рисков:
    ```
    LOW_RISK:
      - read_file (любые файлы)
      - list_directory
      - execute_command (grep, find, ls, cat, head, tail, wc)
    
    MEDIUM_RISK:
      - write_file (.txt, .md, .json, .py, .js, .ts, .jsx, .tsx)
      - execute_command (git, npm, node, python scripts)
    
    HIGH_RISK:
      - write_file (.exe, .bin, .sh, .conf, .sys, .dll)
      - execute_command (gcc, docker, sudo, системные команды)
    ```

- **8.3.2** Реализовать `get_risk_level(tool_name: str, params: dict) -> RiskLevel`
  - Анализирует параметры tool
  - Определяет уровень риска на основе команды, файла, расширения

- **8.3.3** Реализовать timeout management
  - LOW_RISK: no approval timeout
  - MEDIUM_RISK: 5 минут (300 сек)
  - HIGH_RISK: 10 минут (600 сек)
  - `get_timeout_for_risk_level(risk_level) -> int`

### Фаза 2: Approval Manager Integration (Tasks 8.4)
**Цель**: Интегрировать tool execution с ApprovalManager

- **8.4.1** Расширить `ApprovalManager` методом `request_tool_approval()`
  ```python
  async def request_tool_approval(
      self,
      tool_name: str,
      tool_params: dict,
      risk_level: RiskLevel,
      timeout_seconds: int,
      session_id: Optional[UUID] = None
  ) -> ApprovalRequest
  ```

- **8.4.2** Реализовать auto-approve для LOW_RISK tools
  - Пропустить approval процесс, сразу отправить на выполнение

- **8.4.3** Реализовать approval request workflow для MEDIUM/HIGH_RISK
  - Создать ApprovalRequest
  - Отправить APPROVAL_REQUIRED событие через SSE
  - Ждать user decision (confirm/reject)

- **8.4.4** Реализовать timeout handling
  - Если timeout истёк → auto-reject
  - Отправить сообщение об ошибке

- **8.4.5** Реализовать batch approval (опционально)
  - Пользователь может одобрить класс операций (e.g., все git команды)

### Фаза 3: Tool Execution Orchestrator (Tasks 8.5)
**Цель**: Создать оркестратор для управления flow: validation → approval → execution

- **8.5.1** Создать `app/core/tools/executor.py` - ToolExecutor класс
  ```python
  async def execute_tool(
      self,
      user_id: UUID,
      session_id: UUID,
      tool_name: str,
      tool_params: dict,
      approval_manager: ApprovalManager,
      stream_manager: StreamManager
  ) -> ToolExecutionResult
  ```

- **8.5.2** Реализовать flow:
  1. Валидация параметров (ToolValidator)
  2. Оценка риска (RiskAssessor)
  3. Запрос на approval (ApprovalManager)
  4. Отправка на выполнение в VS Code Extension
  5. Ожидание результата
  6. Логирование выполнения

- **8.5.3** Создать WebSocket/Event-based communication для запроса tool execution
  - Backend отправляет TOOL_EXECUTION_REQUEST событие
  - VS Code Extension получает, выполняет, отправляет результат обратно

### Фаза 4: Backend REST API (Tasks 13.5)
**Цель**: Создать REST endpoints для управления tools

- **13.5.1** POST `/my/tools/execute` - запуск tool
  ```json
  {
    "tool_name": "read_file",
    "tool_params": {"path": "src/main.py"},
    "session_id": "uuid"
  }
  ```
  - Response: {tool_id, approval_id, status, result (если auto-approved)}

- **13.5.2** GET `/my/tools/{tool_id}` - статус выполнения tool

- **13.5.3** GET `/my/tools/history` - история выполненных tools

- **13.5.4** POST `/my/approvals/{id}/confirm` - интеграция с approval flow

### Фаза 5: VS Code Extension Enhancement (Tasks 8.5 Frontend)
**Цель**: Расширить VS Code плагин с ToolHandler для client-side execution

- **8.5.1** Создать `src/tools/ToolHandler.ts`
  ```typescript
  class ToolHandler {
    async executeReadFile(path: string, userId: string): Promise<Result>
    async executeWriteFile(path: string, content: string, mode: string, userId: string): Promise<Result>
    async executeCommand(command: string, args: string[], timeout: number, userId: string): Promise<Result>
    async listDirectory(path: string, userId: string, recursive: boolean, pattern: string): Promise<Result>
  }
  ```

- **8.5.2** Интегрировать в `src/extension.ts`
  - Слушать TOOL_EXECUTION_REQUEST события от backend
  - Выполнять tool через Node.js APIs
  - Отправлять результат обратно на backend

- **8.5.3** Реализовать workspace boundary validation
  - Получить workspace root из `vscode.workspace.workspaceFolders`
  - Проверить что path находится внутри workspace

- **8.5.4** Реализовать error handling и retry
  - Таймауты
  - Отсутствие файла
  - Permission denied

### Фаза 6: Testing (Tasks 8.6)
**Цель**: Полное покрытие тестами

- **8.6.1** Unit тесты для `ToolValidator`
  - Path traversal prevention (../, /etc/passwd)
  - File size limits
  - Extension validation

- **8.6.2** Unit тесты для `RiskAssessor`
  - Корректная классификация tools
  - Timeout values для каждого risk level

- **8.6.3** Unit тесты для `CommandValidator`
  - Whitelist/blacklist проверки
  - Command injection prevention

- **8.6.4** Integration тесты
  - Full flow: validation → approval → execution
  - LOW/MEDIUM/HIGH risk scenarios
  - Timeout scenarios

- **8.6.5** Security тесты
  - Path traversal attempts
  - Command injection attempts
  - Cross-user isolation violations

## 📁 Структура файлов

```
app/
├── core/
│   └── tools/
│       ├── __init__.py
│       ├── definitions.py          # Tool definitions
│       ├── validator.py            # ToolValidator class
│       ├── command_whitelist.py    # CommandValidator
│       ├── size_limiter.py         # Size limits
│       ├── risk_assessor.py        # RiskAssessor class
│       ├── executor.py             # ToolExecutor orchestrator
│       └── models.py               # Database models (optional)
├── schemas/
│   ├── tool.py                     # Tool Pydantic schemas
│   └── approval.py                 # Update with tool approval fields
├── routes/
│   └── project_tools.py            # REST API endpoints
└── approval_manager.py             # Update with tool approval methods

tests/
├── test_tool_validator.py
├── test_command_whitelist.py
├── test_risk_assessor.py
├── test_tool_executor.py
└── test_tool_execution_flow.py

VS Code Extension:
├── src/
│   └── tools/
│       ├── ToolHandler.ts          # Tool execution handler
│       └── __tests__/
│           └── ToolHandler.test.ts
└── webview/src/
    └── components/
        └── ToolApprovalModal.tsx   # UI для approval requests
```

## 🔄 Workflow примеры

### Scenario 1: Чтение файла (LOW RISK)
```
1. User: "Прочитай файл src/main.py"
2. Agent: tool_read_file("src/main.py")
3. Backend:
   - Валидирует path (OK, внутри workspace)
   - Risk level = LOW
   - Auto-approve (без требования подтверждения)
4. Отправляет TOOL_EXECUTION_REQUEST в VS Code Extension
5. VS Code Extension:
   - Выполняет fs.readFile()
   - Отправляет результат обратно
6. Backend: Возвращает результат агенту
7. Agent: Анализирует содержимое файла
```

### Scenario 2: Изменение JSON файла (MEDIUM RISK)
```
1. User: "Обнови config.json значение api_url на http://new.api.com"
2. Agent: tool_write_file("config.json", new_content, mode="write")
3. Backend:
   - Валидирует path и content (OK)
   - Проверяет расширение (.json - MEDIUM RISK)
   - Risk level = MEDIUM (timeout 5 мин)
   - Создает ApprovalRequest
   - Отправляет APPROVAL_REQUIRED событие через SSE
4. Frontend (VS Code):
   - Отображает modal: "Agent хочет изменить config.json"
   - Пользователь кликает "Approve"
5. Backend:
   - Обновляет ApprovalRequest status = approved
   - Отправляет TOOL_EXECUTION_REQUEST в VS Code
6. VS Code Extension:
   - Выполняет fs.writeFile()
   - Отправляет результат (success)
7. Backend: Возвращает результат агенту
8. Agent: Продолжает работу
```

### Scenario 3: Выполнение npm install (MEDIUM RISK)
```
1. User: "Установи зависимости"
2. Agent: tool_execute_command("npm", ["install"], timeout=300)
3. Backend:
   - Валидирует команду (npm - в whitelist)
   - Проверяет аргументы (install - безопасно)
   - Risk level = MEDIUM
   - Создает ApprovalRequest
4. Frontend: Отображает approval modal
5. User: Кликает "Approve"
6. Backend: Отправляет TOOL_EXECUTION_REQUEST в VS Code
7. VS Code Extension:
   - Выполняет child_process.exec("npm install", {timeout: 300000})
   - Собирает stdout/stderr
   - Отправляет результат
8. Backend: Возвращает результат с output и exit code
```

### Scenario 4: Запрещённая операция (BLACKLIST)
```
1. Agent: tool_execute_command("rm", ["-rf", "/"], ...)
2. Backend:
   - Проверяет команду (rm - В BLACKLIST)
   - Отклоняет с ошибкой "Command not allowed: rm"
3. Agent: Получает ошибку, не может выполнить операцию
```

## 🎯 Метрики успеха

- ✅ Все 29 tasks в секции 8 реализованы
- ✅ Coverage > 90% для всех компонентов
- ✅ Security тесты пройдены (path traversal, command injection)
- ✅ Approval workflow работает для всех risk levels
- ✅ Performance: tool execution < 5 сек (в т.ч. approval)

## 📊 Зависимости

### Already Implemented
- ✅ ApprovalManager (request_tool_approval method)
- ✅ StreamManager (SSE events)
- ✅ UserIsolationMiddleware (user_id validation)
- ✅ VS Code Extension architecture

### To be Implemented
- Tool definitions and schemas
- ToolValidator, CommandValidator, RiskAssessor
- ToolExecutor orchestrator
- REST API endpoints
- VS Code ToolHandler
- Tests

## 🚀 Приоритет реализации

1. **Phase 1** (Priority: CRITICAL) - Backend Tool Infrastructure
   - Tools definitions
   - Validator classes
   - Risk assessment

2. **Phase 2** (Priority: CRITICAL) - Approval Integration
   - ApprovalManager methods
   - SSE notification flow

3. **Phase 3** (Priority: HIGH) - Orchestrator
   - ToolExecutor
   - Full workflow

4. **Phase 4** (Priority: HIGH) - Backend REST API
   - Tool execution endpoints

5. **Phase 5** (Priority: HIGH) - VS Code Extension
   - ToolHandler
   - Client-side execution

6. **Phase 6** (Priority: MEDIUM) - Testing
   - Complete test coverage
