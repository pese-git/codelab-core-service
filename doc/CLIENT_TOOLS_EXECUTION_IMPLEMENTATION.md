# VS Code Plugin: Реализация Tools Execution на клиенте

Инструкция по реализации поддержки выполнения tools (read_file, write_file, execute_command, list_directory) на стороне VS Code Plugin.

---

## 1. Архитектура

### 1.1 Workflow выполнения

```
┌─────────────────────────────────────────────────────┐
│ Backend (Python/FastAPI)                            │
├─────────────────────────────────────────────────────┤
│                                                     │
│  1. Agent запрашивает tool (read_file, write_file) │
│  2. PathValidator валидирует синтаксис пути        │
│  3. RiskAssessor оценивает риск                    │
│  4. ApprovalManager создаёт/auto-approves          │
│  5. TOOL_EXECUTION_REQUEST отправляется на клиент │
│                                                     │
└──────────────────────┬──────────────────────────────┘
                       │ SSE/Event
                       ↓
┌─────────────────────────────────────────────────────┐
│ VS Code Plugin (TypeScript/Node.js)                 │
├─────────────────────────────────────────────────────┤
│                                                     │
│  1. SSE слушатель получает TOOL_EXECUTION_REQUEST  │
│  2. PathValidator валидирует пути локально         │
│  3. Approval Dialog показывает пользователю        │
│  4. ToolHandler выполняет tool на локальной FS     │
│  5. Результат отправляется на сервер через REST   │
│                                                     │
└──────────────────────┬──────────────────────────────┘
                       │ HTTP POST /tools/{id}/result
                       ↓
┌─────────────────────────────────────────────────────┐
│ Backend: обработка результата                       │
├─────────────────────────────────────────────────────┤
│  - Сохранение результата в ToolExecution           │
│  - Отправка результата в LLM                       │
│  - Генерация финального ответа                     │
└─────────────────────────────────────────────────────┘
```

### 1.2 Основные компоненты

```typescript
// src/tools/
├── ToolExecutionManager.ts    // Основной орхестратор (NEW)
├── SSEToolListener.ts          // Слушатель SSE событий (NEW)
├── PathValidator.ts            // Клиентская валидация путей (NEW)
├── FileSystemTools.ts          // Операции с файлами (NEW)
├── CommandExecutor.ts          // Выполнение команд (NEW)
├── ToolResultSender.ts         // Отправка результатов (NEW)
└── types.ts                    // TypeScript interfaces (UPDATE)

// src/ui/
├── ApprovalDialog.ts           // Dialog для одобрения (NEW)
├── ToolProgressIndicator.ts    // Индикатор прогресса (NEW)
└── ToolStatusPanel.ts          // Панель статуса tools (NEW)
```

---

## 2. PathValidator на клиенте

### 2.1 Реализация

```typescript
// src/tools/PathValidator.ts

import * as path from 'path';
import * as fs from 'fs';

export interface ValidationResult {
    success: boolean;
    path?: string;
    error?: string;
}

export class PathValidator {
    private readonly forbiddenExtensions = new Set([
        '.exe', '.bin', '.so', '.dll', '.dylib',
        '.sh', '.bat', '.cmd', '.scr', '.msi',
        '.app', '.deb', '.rpm'
    ]);

    constructor(private workspacePath: string) {
        // Убедимся что workspacePath абсолютный
        this.workspacePath = path.resolve(workspacePath);
    }

    /**
     * Валидирует путь для чтения файла
     */
    validateReadPath(relativePath: string): ValidationResult {
        try {
            // Валидировать синтаксис
            const result = this.validatePathSyntax(relativePath, 'file');
            if (!result.success) {
                return result;
            }

            const absolutePath = result.path!;

            // Проверить существование файла
            if (!fs.existsSync(absolutePath)) {
                return { success: false, error: `File not found: ${relativePath}` };
            }

            // Проверить что это файл (не директория)
            const stats = fs.statSync(absolutePath);
            if (!stats.isFile()) {
                return { success: false, error: `Path is not a file: ${relativePath}` };
            }

            // Проверить размер файла (100MB max)
            const MAX_FILE_SIZE = 100 * 1024 * 1024;
            if (stats.size > MAX_FILE_SIZE) {
                return {
                    success: false,
                    error: `File too large: ${stats.size} bytes (max ${MAX_FILE_SIZE})`
                };
            }

            // Проверить что это не symlink или что symlink указывает в workspace
            if (stats.isSymbolicLink()) {
                const target = fs.readlinkSync(absolutePath);
                const resolvedTarget = path.resolve(path.dirname(absolutePath), target);
                if (!resolvedTarget.startsWith(this.workspacePath)) {
                    return {
                        success: false,
                        error: `Symlink points outside workspace: ${target}`
                    };
                }
            }

            return { success: true, path: absolutePath };
        } catch (error) {
            return {
                success: false,
                error: `Error validating read path: ${error instanceof Error ? error.message : String(error)}`
            };
        }
    }

    /**
     * Валидирует путь для записи файла
     */
    validateWritePath(relativePath: string): ValidationResult {
        try {
            // Валидировать синтаксис
            const result = this.validatePathSyntax(relativePath, 'file');
            if (!result.success) {
                return result;
            }

            const absolutePath = result.path!;

            // Проверить расширение файла
            const ext = path.extname(absolutePath).toLowerCase();
            if (this.forbiddenExtensions.has(ext)) {
                return { success: false, error: `Writing to ${ext} files is not allowed` };
            }

            // Проверить что родительская директория существует или может быть создана
            const parentDir = path.dirname(absolutePath);
            if (!fs.existsSync(parentDir)) {
                try {
                    fs.mkdirSync(parentDir, { recursive: true });
                } catch (error) {
                    return {
                        success: false,
                        error: `Cannot create parent directory: ${error instanceof Error ? error.message : String(error)}`
                    };
                }
            }

            return { success: true, path: absolutePath };
        } catch (error) {
            return {
                success: false,
                error: `Error validating write path: ${error instanceof Error ? error.message : String(error)}`
            };
        }
    }

    /**
     * Валидирует путь для листинга директории
     */
    validateDirectoryPath(relativePath: string): ValidationResult {
        try {
            // Валидировать синтаксис
            const result = this.validatePathSyntax(relativePath, 'directory');
            if (!result.success) {
                return result;
            }

            const absolutePath = result.path!;

            // Проверить существование директории
            if (!fs.existsSync(absolutePath)) {
                return { success: false, error: `Directory not found: ${relativePath}` };
            }

            // Проверить что это директория
            const stats = fs.statSync(absolutePath);
            if (!stats.isDirectory()) {
                return { success: false, error: `Path is not a directory: ${relativePath}` };
            }

            return { success: true, path: absolutePath };
        } catch (error) {
            return {
                success: false,
                error: `Error validating directory path: ${error instanceof Error ? error.message : String(error)}`
            };
        }
    }

    /**
     * Валидирует синтаксис пути (защита от path traversal)
     */
    private validatePathSyntax(relativePath: string, type: 'file' | 'directory'): ValidationResult {
        if (!relativePath || !relativePath.trim()) {
            return { success: false, error: 'Path cannot be empty' };
        }

        // Блокировать null characters
        if (relativePath.includes('\0')) {
            return { success: false, error: 'Path contains null character' };
        }

        // Блокировать абсолютные пути
        if (path.isAbsolute(relativePath)) {
            return { success: false, error: `Absolute paths are not allowed: ${relativePath}` };
        }

        // Нормализировать и проверить границы workspace
        try {
            const absolutePath = path.resolve(this.workspacePath, relativePath);

            // Проверить что resolved path в границах workspace
            const relativeTo = path.relative(this.workspacePath, absolutePath);
            if (relativeTo.startsWith('..')) {
                return { success: false, error: `Path ${relativePath} is outside workspace boundary` };
            }

            return { success: true, path: absolutePath };
        } catch (error) {
            return {
                success: false,
                error: `Invalid path syntax: ${relativePath}`
            };
        }
    }
}
```

### 2.2 Использование

```typescript
const validator = new PathValidator('/workspace/my-project');

// Чтение файла
const result = validator.validateReadPath('src/main.ts');
if (result.success) {
    console.log('Файл валиден:', result.path);
} else {
    console.error('Ошибка:', result.error);
}

// Запись файла
const writeResult = validator.validateWritePath('output/results.json');

// Листинг директории
const dirResult = validator.validateDirectoryPath('src');
```

---

## 3. SSE Listener для Tool Events

### 3.1 Слушатель событий

```typescript
// src/tools/SSEToolListener.ts

import * as vscode from 'vscode';

export interface ToolExecutionRequest {
    tool_id: string;
    tool_name: 'read_file' | 'write_file' | 'execute_command' | 'list_directory';
    tool_params: Record<string, any>;
    session_id?: string;
}

export interface ToolApprovalRequest {
    approval_id: string;
    tool_name: string;
    risk_level: 'LOW' | 'MEDIUM' | 'HIGH';
    timeout_seconds: number;
}

export class SSEToolListener {
    private eventSource: EventSource | null = null;

    /**
     * Подписаться на tool execution события
     */
    subscribeToToolEvents(
        apiUrl: string,
        sessionId: string,
        authToken: string,
        handlers: {
            onToolRequest: (request: ToolExecutionRequest) => void;
            onApprovalRequest: (request: ToolApprovalRequest) => void;
            onError: (error: string) => void;
        }
    ): void {
        const eventUrl = `${apiUrl}/my/projects/{projectId}/chat/${sessionId}/events`;

        try {
            this.eventSource = new EventSource(eventUrl, {
                headers: {
                    'Authorization': `Bearer ${authToken}`
                }
            });

            // Слушаем TOOL_EXECUTION_REQUEST события
            this.eventSource.addEventListener('tool.execution_request', (event) => {
                try {
                    const data = JSON.parse(event.data) as ToolExecutionRequest;
                    handlers.onToolRequest(data);
                } catch (error) {
                    handlers.onError(`Failed to parse tool request: ${error}`);
                }
            });

            // Слушаем TOOL_APPROVAL_REQUEST события (для HIGH risk tools)
            this.eventSource.addEventListener('tool.approval_request', (event) => {
                try {
                    const data = JSON.parse(event.data) as ToolApprovalRequest;
                    handlers.onApprovalRequest(data);
                } catch (error) {
                    handlers.onError(`Failed to parse approval request: ${error}`);
                }
            });

            // Обработка ошибок соединения
            this.eventSource.onerror = () => {
                handlers.onError('SSE connection error');
                this.close();
            };

            vscode.window.showInformationMessage('Tool execution listener started');
        } catch (error) {
            handlers.onError(`Failed to create SSE connection: ${error}`);
        }
    }

    /**
     * Закрыть соединение
     */
    close(): void {
        if (this.eventSource) {
            this.eventSource.close();
            this.eventSource = null;
        }
    }
}
```

---

## 4. Tool Execution Manager

### 4.1 Основной орхестратор

```typescript
// src/tools/ToolExecutionManager.ts

import * as vscode from 'vscode';
import * as fs from 'fs';
import { exec } from 'child_process';
import { promisify } from 'util';
import { PathValidator } from './PathValidator';
import { ToolResultSender } from './ToolResultSender';
import { ApprovalDialog } from '../ui/ApprovalDialog';

const execAsync = promisify(exec);

export interface ToolExecutionResult {
    tool_id: string;
    tool_name: string;
    status: 'success' | 'error' | 'cancelled';
    result?: Record<string, any>;
    error?: string;
    execution_time_ms: number;
}

export class ToolExecutionManager {
    private pathValidator: PathValidator;
    private resultSender: ToolResultSender;
    private approvalDialog: ApprovalDialog;
    private activeExecutions = new Map<string, AbortController>();

    constructor(
        private workspacePath: string,
        private apiUrl: string,
        private authToken: string,
        private outputChannel: vscode.OutputChannel
    ) {
        this.pathValidator = new PathValidator(workspacePath);
        this.resultSender = new ToolResultSender(apiUrl, authToken);
        this.approvalDialog = new ApprovalDialog();
    }

    /**
     * Выполнить инструмент
     */
    async executeTool(
        toolId: string,
        toolName: string,
        toolParams: Record<string, any>
    ): Promise<void> {
        const startTime = Date.now();
        const abortController = new AbortController();
        this.activeExecutions.set(toolId, abortController);

        try {
            this.outputChannel.appendLine(`[TOOL] Executing ${toolName} (${toolId})`);

            let result: ToolExecutionResult;

            switch (toolName) {
                case 'read_file':
                    result = await this.executeReadFile(toolId, toolParams, abortController);
                    break;

                case 'write_file':
                    result = await this.executeWriteFile(toolId, toolParams, abortController);
                    break;

                case 'execute_command':
                    result = await this.executeCommand(toolId, toolParams, abortController);
                    break;

                case 'list_directory':
                    result = await this.listDirectory(toolId, toolParams, abortController);
                    break;

                default:
                    result = {
                        tool_id: toolId,
                        tool_name: toolName,
                        status: 'error',
                        error: `Unknown tool: ${toolName}`,
                        execution_time_ms: Date.now() - startTime
                    };
            }

            // Отправить результат на сервер
            await this.resultSender.sendToolResult(toolId, result);

            this.outputChannel.appendLine(
                `[TOOL] ${toolName} completed: ${result.status} (${result.execution_time_ms}ms)`
            );
        } catch (error) {
            const result: ToolExecutionResult = {
                tool_id: toolId,
                tool_name: toolName,
                status: 'error',
                error: error instanceof Error ? error.message : String(error),
                execution_time_ms: Date.now() - startTime
            };

            await this.resultSender.sendToolResult(toolId, result);
            this.outputChannel.appendLine(`[TOOL ERROR] ${toolName}: ${result.error}`);
        } finally {
            this.activeExecutions.delete(toolId);
        }
    }

    /**
     * Выполнить read_file
     */
    private async executeReadFile(
        toolId: string,
        params: Record<string, any>,
        signal: AbortController
    ): Promise<ToolExecutionResult> {
        const startTime = Date.now();

        try {
            const { path: relativePath } = params;

            // Валидировать путь
            const validation = this.pathValidator.validateReadPath(relativePath);
            if (!validation.success) {
                return {
                    tool_id: toolId,
                    tool_name: 'read_file',
                    status: 'error',
                    error: validation.error,
                    execution_time_ms: Date.now() - startTime
                };
            }

            // Прочитать файл
            const content = fs.readFileSync(validation.path!, 'utf-8');

            return {
                tool_id: toolId,
                tool_name: 'read_file',
                status: 'success',
                result: {
                    content,
                    path: relativePath,
                    size: content.length
                },
                execution_time_ms: Date.now() - startTime
            };
        } catch (error) {
            return {
                tool_id: toolId,
                tool_name: 'read_file',
                status: 'error',
                error: error instanceof Error ? error.message : String(error),
                execution_time_ms: Date.now() - startTime
            };
        }
    }

    /**
     * Выполнить write_file
     */
    private async executeWriteFile(
        toolId: string,
        params: Record<string, any>,
        signal: AbortController
    ): Promise<ToolExecutionResult> {
        const startTime = Date.now();

        try {
            const { path: relativePath, content, mode = 'write' } = params;

            // Валидировать путь
            const validation = this.pathValidator.validateWritePath(relativePath);
            if (!validation.success) {
                return {
                    tool_id: toolId,
                    tool_name: 'write_file',
                    status: 'error',
                    error: validation.error,
                    execution_time_ms: Date.now() - startTime
                };
            }

            // Записать файл
            if (mode === 'append') {
                fs.appendFileSync(validation.path!, content, 'utf-8');
            } else {
                fs.writeFileSync(validation.path!, content, 'utf-8');
            }

            return {
                tool_id: toolId,
                tool_name: 'write_file',
                status: 'success',
                result: {
                    path: relativePath,
                    size: content.length,
                    mode
                },
                execution_time_ms: Date.now() - startTime
            };
        } catch (error) {
            return {
                tool_id: toolId,
                tool_name: 'write_file',
                status: 'error',
                error: error instanceof Error ? error.message : String(error),
                execution_time_ms: Date.now() - startTime
            };
        }
    }

    /**
     * Выполнить execute_command
     */
    private async executeCommand(
        toolId: string,
        params: Record<string, any>,
        signal: AbortController
    ): Promise<ToolExecutionResult> {
        const startTime = Date.now();

        try {
            const { command, args = [], timeout = 30000 } = params;

            // Показать dialog для подтверждения
            const approved = await this.approvalDialog.showApproval(
                `Execute command: ${command}`,
                'MEDIUM'
            );

            if (!approved) {
                return {
                    tool_id: toolId,
                    tool_name: 'execute_command',
                    status: 'cancelled',
                    error: 'User rejected command execution',
                    execution_time_ms: Date.now() - startTime
                };
            }

            // Выполнить команду
            const fullCommand = [command, ...args].join(' ');
            const { stdout, stderr } = await execAsync(fullCommand, {
                cwd: this.workspacePath,
                timeout: Math.min(timeout, 300000), // Max 5 minutes
                maxBuffer: 10 * 1024 * 1024 // 10MB
            });

            return {
                tool_id: toolId,
                tool_name: 'execute_command',
                status: 'success',
                result: {
                    stdout: stdout.toString(),
                    stderr: stderr.toString(),
                    command: fullCommand
                },
                execution_time_ms: Date.now() - startTime
            };
        } catch (error) {
            return {
                tool_id: toolId,
                tool_name: 'execute_command',
                status: 'error',
                error: error instanceof Error ? error.message : String(error),
                execution_time_ms: Date.now() - startTime
            };
        }
    }

    /**
     * Выполнить list_directory
     */
    private async listDirectory(
        toolId: string,
        params: Record<string, any>,
        signal: AbortController
    ): Promise<ToolExecutionResult> {
        const startTime = Date.now();

        try {
            const { path: relativePath, recursive = false, pattern = '*' } = params;

            // Валидировать путь
            const validation = this.pathValidator.validateDirectoryPath(relativePath);
            if (!validation.success) {
                return {
                    tool_id: toolId,
                    tool_name: 'list_directory',
                    status: 'error',
                    error: validation.error,
                    execution_time_ms: Date.now() - startTime
                };
            }

            // Листить директорию
            const files: Array<{
                name: string;
                path: string;
                type: 'file' | 'directory';
                size?: number;
            }> = [];

            const traverse = (dir: string, depth: number = 0) => {
                if (recursive && depth > 10) return; // Limit recursion

                const entries = fs.readdirSync(dir, { withFileTypes: true });

                for (const entry of entries) {
                    const fullPath = `${dir}/${entry.name}`;
                    const relativePath = fullPath.replace(this.workspacePath + '/', '');

                    files.push({
                        name: entry.name,
                        path: relativePath,
                        type: entry.isDirectory() ? 'directory' : 'file',
                        size: entry.isFile() ? fs.statSync(fullPath).size : undefined
                    });

                    if (recursive && entry.isDirectory() && depth < 5) {
                        traverse(fullPath, depth + 1);
                    }
                }
            };

            traverse(validation.path!);

            return {
                tool_id: toolId,
                tool_name: 'list_directory',
                status: 'success',
                result: {
                    files: files.slice(0, 1000), // Limit results
                    total: files.length
                },
                execution_time_ms: Date.now() - startTime
            };
        } catch (error) {
            return {
                tool_id: toolId,
                tool_name: 'list_directory',
                status: 'error',
                error: error instanceof Error ? error.message : String(error),
                execution_time_ms: Date.now() - startTime
            };
        }
    }

    /**
     * Отменить выполнение инструмента
     */
    cancel(toolId: string): void {
        const controller = this.activeExecutions.get(toolId);
        if (controller) {
            controller.abort();
            this.activeExecutions.delete(toolId);
        }
    }

    /**
     * Очистить все активные выполнения
     */
    async cleanup(): Promise<void> {
        for (const [toolId, controller] of this.activeExecutions) {
            controller.abort();
        }
        this.activeExecutions.clear();
    }
}
```

---

## 5. Отправка результатов на сервер

### 5.1 Tool Result Sender

```typescript
// src/tools/ToolResultSender.ts

import { ToolExecutionResult } from './ToolExecutionManager';

export class ToolResultSender {
    constructor(
        private apiUrl: string,
        private authToken: string
    ) {}

    /**
     * Отправить результат tool на сервер
     */
    async sendToolResult(toolId: string, result: ToolExecutionResult): Promise<void> {
        const response = await fetch(
            `${this.apiUrl}/my/projects/{projectId}/tools/${toolId}/result`,
            {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${this.authToken}`
                },
                body: JSON.stringify(result)
            }
        );

        if (!response.ok) {
            throw new Error(`Failed to send tool result: ${response.statusText}`);
        }
    }
}
```

---

## 6. Approval Dialog

### 6.1 UI для одобрения

```typescript
// src/ui/ApprovalDialog.ts

import * as vscode from 'vscode';

export class ApprovalDialog {
    /**
     * Показать dialog одобрения
     */
    async showApproval(
        description: string,
        riskLevel: 'LOW' | 'MEDIUM' | 'HIGH'
    ): Promise<boolean> {
        const riskColors: Record<string, string> = {
            LOW: '🟢 LOW',
            MEDIUM: '🟡 MEDIUM',
            HIGH: '🔴 HIGH'
        };

        const action = await vscode.window.showInformationMessage(
            `${riskColors[riskLevel]} Risk: ${description}`,
            { modal: true },
            { title: '✅ Approve', id: 'approve' },
            { title: '❌ Reject', id: 'reject' }
        );

        return action?.id === 'approve';
    }
}
```

---

## 7. Integration в Extension

### 7.1 Активация и инициализация

```typescript
// src/extension.ts

import * as vscode from 'vscode';
import { ToolExecutionManager } from './tools/ToolExecutionManager';
import { SSEToolListener } from './tools/SSEToolListener';

let toolExecutionManager: ToolExecutionManager | null = null;
let sseListener: SSEToolListener | null = null;

export async function activate(context: vscode.ExtensionContext) {
    const workspaceFolders = vscode.workspace.workspaceFolders;
    if (!workspaceFolders || workspaceFolders.length === 0) {
        vscode.window.showErrorMessage('No workspace folder found');
        return;
    }

    const workspacePath = workspaceFolders[0].uri.fsPath;
    const outputChannel = vscode.window.createOutputChannel('Codelab Tools');

    // Получить конфигурацию
    const config = vscode.workspace.getConfiguration('codelab');
    const apiUrl = config.get<string>('apiUrl') || 'http://localhost:8000';
    const authToken = await context.secrets.get('authToken');

    if (!authToken) {
        vscode.window.showErrorMessage('No auth token found. Please configure Codelab extension.');
        return;
    }

    // Инициализировать Tool Execution Manager
    toolExecutionManager = new ToolExecutionManager(
        workspacePath,
        apiUrl,
        authToken,
        outputChannel
    );

    // Инициализировать SSE Listener
    sseListener = new SSEToolListener();
    const sessionId = 'current-session-id'; // Получить из контекста

    sseListener.subscribeToToolEvents(
        apiUrl,
        sessionId,
        authToken,
        {
            onToolRequest: async (request) => {
                outputChannel.appendLine(
                    `[SSE] Received tool request: ${request.tool_name} (${request.tool_id})`
                );
                if (toolExecutionManager) {
                    await toolExecutionManager.executeTool(
                        request.tool_id,
                        request.tool_name,
                        request.tool_params
                    );
                }
            },
            onApprovalRequest: async (request) => {
                outputChannel.appendLine(`[SSE] Approval request: ${request.tool_name}`);
                // Обработать в ApprovalManager
            },
            onError: (error) => {
                outputChannel.appendLine(`[SSE ERROR] ${error}`);
                vscode.window.showErrorMessage(`Tool execution error: ${error}`);
            }
        }
    );

    // Cleanup на деактивацию
    context.subscriptions.push({
        dispose: async () => {
            if (sseListener) {
                sseListener.close();
            }
            if (toolExecutionManager) {
                await toolExecutionManager.cleanup();
            }
        }
    });

    vscode.window.showInformationMessage('Codelab Tools extension activated');
}

export function deactivate() {
    // Cleanup
}
```

---

## 8. Тестирование

### 8.1 Unit тесты для PathValidator

```typescript
// src/tools/__tests__/PathValidator.test.ts

import * as assert from 'assert';
import { PathValidator } from '../PathValidator';
import * as fs from 'fs';
import * as path from 'path';

describe('PathValidator', () => {
    let validator: PathValidator;
    let testDir: string;

    before(() => {
        testDir = '/tmp/test-workspace';
        fs.mkdirSync(testDir, { recursive: true });
        validator = new PathValidator(testDir);

        // Создать тестовые файлы
        fs.writeFileSync(path.join(testDir, 'test.txt'), 'content');
        fs.mkdirSync(path.join(testDir, 'subdir'), { recursive: true });
    });

    after(() => {
        // Cleanup
    });

    it('should validate safe read path', () => {
        const result = validator.validateReadPath('test.txt');
        assert.strictEqual(result.success, true);
    });

    it('should block path traversal', () => {
        const result = validator.validateReadPath('../../../etc/passwd');
        assert.strictEqual(result.success, false);
        assert(result.error?.includes('outside workspace'));
    });

    it('should block executable write', () => {
        const result = validator.validateWritePath('malware.exe');
        assert.strictEqual(result.success, false);
        assert(result.error?.includes('.exe'));
    });

    it('should validate directory path', () => {
        const result = validator.validateDirectoryPath('subdir');
        assert.strictEqual(result.success, true);
    });
});
```

---

## 9. Чеклист реализации

### Phase 1: Core Infrastructure (1-2 недели)
- [ ] PathValidator на клиенте (TypeScript/Node.js)
- [ ] Unit тесты для PathValidator
- [ ] SSEToolListener для получения событий
- [ ] ToolExecutionResult interface

### Phase 2: Tool Execution (1-2 недели)
- [ ] ToolExecutionManager (основной орхестратор)
- [ ] FileSystem operations (read_file, write_file, list_directory)
- [ ] CommandExecutor с безопасностью
- [ ] ToolResultSender для отправки результатов

### Phase 3: UI и Integration (1 неделя)
- [ ] ApprovalDialog компонент
- [ ] ToolProgressIndicator компонент
- [ ] Integration в extension.ts
- [ ] Error handling и recovery

### Phase 4: Тестирование (1 неделя)
- [ ] Unit тесты (все компоненты)
- [ ] Integration тесты (end-to-end workflow)
- [ ] Security тесты (path traversal, command injection)
- [ ] Performance тесты

### Phase 5: Полировка (1 неделя)
- [ ] Documentation
- [ ] Error messages улучшения
- [ ] Logging и diagnostics
- [ ] Production build и publishing

---

## 10. Конфигурация package.json

```json
{
  "name": "codelab-vscode-extension",
  "displayName": "Codelab",
  "description": "VS Code extension for Codelab AI",
  "version": "1.0.0",
  "engines": {
    "vscode": "^1.85.0"
  },
  "dependencies": {
    "vscode": "^1.85.0"
  },
  "devDependencies": {
    "@types/node": "^20.0.0",
    "typescript": "^5.0.0",
    "mocha": "^10.0.0",
    "ts-node": "^10.0.0"
  },
  "scripts": {
    "compile": "tsc -p ./",
    "test": "mocha --require ts-node/register src/**/__tests__/**/*.test.ts",
    "package": "vsce package"
  }
}
```

---

## 11. Точки интеграции с Backend

### API Endpoints для клиента

| Метод | Endpoint | Описание |
|-------|----------|---------|
| POST | `/my/projects/{id}/tools/{toolId}/result` | Отправить результат tool |
| POST | `/my/projects/{id}/approvals/{id}/approve` | Одобрить tool |
| POST | `/my/projects/{id}/approvals/{id}/reject` | Отклонить tool |
| GET | `/my/projects/{id}/chat/{sessionId}/events` | SSE events |

### SSE Event Types

| Event Type | Payload | Описание |
|-----------|---------|---------|
| `tool.execution_request` | `ToolExecutionRequest` | Запрос выполнить tool |
| `tool.approval_request` | `ToolApprovalRequest` | Запрос одобрения |
| `tool.result_ack` | `ToolResultAck` | Подтверждение результата |

---

## 12. Примеры использования

### Пример 1: Чтение файла

```typescript
// Backend запрашивает: read_file("README.md")

// Клиент получает SSE event:
// {
//   "tool_id": "123abc",
//   "tool_name": "read_file",
//   "tool_params": { "path": "README.md" }
// }

// Клиент выполняет:
const validator = new PathValidator(workspacePath);
const validation = validator.validateReadPath("README.md");
if (validation.success) {
    const content = fs.readFileSync(validation.path, 'utf-8');
    // Отправить результат на сервер
}
```

### Пример 2: Выполнение команды

```typescript
// Backend запрашивает: execute_command("npm", ["test"])

// Клиент получает SSE event и показывает Approval Dialog
const approved = await approvalDialog.showApproval("Execute: npm test", "MEDIUM");

if (approved) {
    // Выполнить команду
    const { stdout } = await execAsync("npm test", { cwd: workspacePath });
    // Отправить результат
}
```

---

## Заключение

Данная инструкция описывает полную реализацию поддержки execution tools на клиенте. Все компоненты готовы для разработки и могут быть реализованы параллельно.

Критически важно:
1. **PathValidator на клиенте** должен дублировать логику сервера
2. **SSE Listener** должен обрабатывать все tool events
3. **ToolExecutionManager** должен выполнять tools локально
4. **Результаты** должны отправляться на сервер через REST API

Вся коммуникация между клиентом и сервером должна быть асинхронной и должны быть обработаны все edge cases и ошибки.
