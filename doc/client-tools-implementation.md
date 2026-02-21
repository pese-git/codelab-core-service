# VS Code Plugin - Agent Tools System Client Implementation

**Документ по доработкам для реализации client-side Tool Handler**

---

## 📋 Обзор

Этот документ описывает требования к реализации **Client-Side Tool Handler** для VS Code Plugin, необходимые для завершения Agent Tools System. 

**Backend статус**: ✅ COMPLETE (85 unit tests, production-ready)
**Client статус**: 🚧 TODO (требует реализации 5 компонентов)

---

## 1. Архитектура Client-Side Tool Handler

### 1.1 Общая схема

```
┌─────────────────────────────────────────────────────┐
│ VS Code Extension (UI Layer)                        │
├─────────────────────────────────────────────────────┤
│  - TreeView для файлов                              │
│  - Status Bar для Tool статуса                       │
│  - Dialog для Approval                              │
└──────────────┬──────────────────────────────────────┘
               │
┌──────────────▼──────────────────────────────────────┐
│ ToolHandler Service (Business Logic)                │
├─────────────────────────────────────────────────────┤
│  - Execute tool locally                             │
│  - Validate paths                                   │
│  - Collect results                                  │
└──────────────┬──────────────────────────────────────┘
               │
┌──────────────▼──────────────────────────────────────┐
│ File System & Command APIs                          │
├─────────────────────────────────────────────────────┤
│  - fs.readFile/writeFile                            │
│  - child_process.exec                               │
│  - path resolution                                  │
└─────────────────────────────────────────────────────┘
               │
┌──────────────▼──────────────────────────────────────┐
│ Network Layer (HTTP + SSE)                          │
├─────────────────────────────────────────────────────┤
│  - SSE: /my/projects/{id}/chat/events              │
│  - REST: /tools/{id}/result                        │
│  - REST: /approvals/{id}/approve                   │
└─────────────────────────────────────────────────────┘
```

### 1.2 Модули для реализации

```
src/
├── tools/
│   ├── ToolHandler.ts          # Main orchestrator (NEW)
│   ├── FileSystemExecutor.ts   # File operations (NEW)
│   ├── CommandExecutor.ts      # Command execution (NEW)
│   ├── PathValidator.ts        # Path validation (NEW)
│   ├── ToolResultCollector.ts  # Result handling (NEW)
│   └── types.ts                # Types/Interfaces (UPDATE)
├── ui/
│   ├── ApprovalDialog.ts       # Approval UI (NEW)
│   ├── ToolProgressBar.ts      # Progress indicator (NEW)
│   └── ToolStatusView.ts       # Status panel (NEW)
├── network/
│   ├── SSEListener.ts          # SSE events (UPDATE)
│   ├── ToolApiClient.ts        # REST API client (NEW)
│   └── ApprovalClient.ts       # Approval API (UPDATE)
└── config/
    └── toolConfig.ts           # Configuration (NEW)
```

---

## 2. ToolHandler - Main Orchestrator

### 2.1 Interface Definition

```typescript
// src/tools/ToolHandler.ts

export interface IToolHandler {
  // Main execution method
  executeToolLocally(
    toolId: string,
    toolName: string,
    toolParams: Record<string, any>,
    sessionId?: string
  ): Promise<ToolExecutionResult>;

  // Tool-specific methods
  readFile(path: string): Promise<FileReadResult>;
  writeFile(path: string, content: string, mode?: 'write' | 'append'): Promise<FileWriteResult>;
  executeCommand(command: string, args?: string[], timeout?: number): Promise<CommandResult>;
  listDirectory(path: string, recursive?: boolean, pattern?: string): Promise<FileListResult>;

  // Cleanup
  cancel(toolId: string): void;
  cleanup(): Promise<void>;
}

export interface ToolExecutionResult {
  toolId: string;
  toolName: string;
  status: 'success' | 'error' | 'cancelled';
  result?: Record<string, any>;
  error?: string;
  executionTime: number;
}
```

### 2.2 Implementation Requirements

```typescript
class ToolHandler implements IToolHandler {
  private workspacePath: string;
  private activeExecutions: Map<string, AbortController>;
  private fileSystemExecutor: FileSystemExecutor;
  private commandExecutor: CommandExecutor;
  private pathValidator: PathValidator;

  constructor(
    workspacePath: string,
    private apiClient: ToolApiClient,
    private outputChannel: vscode.OutputChannel
  ) {
    this.workspacePath = workspacePath;
    this.activeExecutions = new Map();
    this.fileSystemExecutor = new FileSystemExecutor(workspacePath);
    this.commandExecutor = new CommandExecutor(workspacePath);
    this.pathValidator = new PathValidator(workspacePath);
  }

  async executeToolLocally(
    toolId: string,
    toolName: string,
    toolParams: Record<string, any>,
    sessionId?: string
  ): Promise<ToolExecutionResult> {
    const startTime = Date.now();
    const abortController = new AbortController();
    this.activeExecutions.set(toolId, abortController);

    try {
      let result: any;

      switch (toolName) {
        case 'read_file':
          result = await this.readFile(toolParams.path);
          break;
        case 'write_file':
          result = await this.writeFile(
            toolParams.path,
            toolParams.content,
            toolParams.mode
          );
          break;
        case 'execute_command':
          result = await this.executeCommand(
            toolParams.command,
            toolParams.args,
            toolParams.timeout
          );
          break;
        case 'list_directory':
          result = await this.listDirectory(
            toolParams.path,
            toolParams.recursive,
            toolParams.pattern
          );
          break;
        default:
          throw new Error(`Unknown tool: ${toolName}`);
      }

      const executionTime = Date.now() - startTime;
      return {
        toolId,
        toolName,
        status: 'success',
        result,
        executionTime
      };
    } catch (error) {
      return {
        toolId,
        toolName,
        status: 'error',
        error: error instanceof Error ? error.message : String(error),
        executionTime: Date.now() - startTime
      };
    } finally {
      this.activeExecutions.delete(toolId);
    }
  }

  async readFile(path: string): Promise<FileReadResult> {
    // Validate path
    const validatedPath = await this.pathValidator.validateReadPath(path);
    if (!validatedPath.success) {
      throw new Error(validatedPath.error);
    }

    // Read file
    return this.fileSystemExecutor.readFile(validatedPath.path);
  }

  async writeFile(
    path: string,
    content: string,
    mode: 'write' | 'append' = 'write'
  ): Promise<FileWriteResult> {
    // Validate path
    const validatedPath = await this.pathValidator.validateWritePath(path);
    if (!validatedPath.success) {
      throw new Error(validatedPath.error);
    }

    // Validate content size
    if (Buffer.byteLength(content, 'utf8') > 100 * 1024 * 1024) {
      throw new Error('File content exceeds 100MB limit');
    }

    // Write file
    return this.fileSystemExecutor.writeFile(validatedPath.path, content, mode);
  }

  async executeCommand(
    command: string,
    args: string[] = [],
    timeout: number = 30000
  ): Promise<CommandResult> {
    // Note: Command validation should be done by backend
    // Client-side execution is trusted if approved
    return this.commandExecutor.executeCommand(command, args, timeout);
  }

  async listDirectory(
    path: string,
    recursive: boolean = false,
    pattern: string = '*'
  ): Promise<FileListResult> {
    // Validate path
    const validatedPath = await this.pathValidator.validateDirectoryPath(path);
    if (!validatedPath.success) {
      throw new Error(validatedPath.error);
    }

    // List files
    return this.fileSystemExecutor.listDirectory(validatedPath.path, recursive, pattern);
  }

  cancel(toolId: string): void {
    const abortController = this.activeExecutions.get(toolId);
    if (abortController) {
      abortController.abort();
      this.activeExecutions.delete(toolId);
    }
  }

  async cleanup(): Promise<void> {
    // Cancel all active executions
    for (const [toolId, controller] of this.activeExecutions) {
      controller.abort();
    }
    this.activeExecutions.clear();
  }
}
```

---

## 3. FileSystemExecutor - File Operations

### 3.1 Interface & Implementation

```typescript
// src/tools/FileSystemExecutor.ts

export interface FileReadResult {
  success: boolean;
  content?: string;
  encoding?: string;
  size?: number;
  error?: string;
}

export interface FileWriteResult {
  success: boolean;
  path?: string;
  size?: number;
  error?: string;
}

export interface FileListResult {
  success: boolean;
  files?: Array<{
    name: string;
    path: string;
    type: 'file' | 'directory';
    size?: number;
    modified?: string;
  }>;
  totalCount?: number;
  error?: string;
}

class FileSystemExecutor {
  constructor(private workspacePath: string) {}

  async readFile(absolutePath: string): Promise<FileReadResult> {
    try {
      const data = await fs.promises.readFile(absolutePath, 'utf-8');
      const stats = await fs.promises.stat(absolutePath);

      return {
        success: true,
        content: data,
        encoding: 'utf-8',
        size: stats.size
      };
    } catch (error) {
      return {
        success: false,
        error: `Failed to read file: ${error instanceof Error ? error.message : String(error)}`
      };
    }
  }

  async writeFile(
    absolutePath: string,
    content: string,
    mode: 'write' | 'append' = 'write'
  ): Promise<FileWriteResult> {
    try {
      // Ensure directory exists
      const directory = path.dirname(absolutePath);
      await fs.promises.mkdir(directory, { recursive: true });

      // Write file
      if (mode === 'append') {
        await fs.promises.appendFile(absolutePath, content, 'utf-8');
      } else {
        await fs.promises.writeFile(absolutePath, content, 'utf-8');
      }

      const stats = await fs.promises.stat(absolutePath);
      return {
        success: true,
        path: absolutePath,
        size: stats.size
      };
    } catch (error) {
      return {
        success: false,
        error: `Failed to write file: ${error instanceof Error ? error.message : String(error)}`
      };
    }
  }

  async listDirectory(
    absolutePath: string,
    recursive: boolean = false,
    pattern: string = '*'
  ): Promise<FileListResult> {
    try {
      const files: FileListResult['files'] = [];
      const visited = new Set<string>();

      const traverse = async (dir: string, depth: number = 0) => {
        if (recursive && depth > 10) return; // Limit recursion depth
        if (visited.has(dir)) return;
        visited.add(dir);

        try {
          const entries = await fs.promises.readdir(dir, { withFileTypes: true });

          for (const entry of entries) {
            // Skip hidden files
            if (entry.name.startsWith('.')) continue;

            const fullPath = path.join(dir, entry.name);
            const relativePath = path.relative(this.workspacePath, fullPath);
            const stats = await fs.promises.stat(fullPath);

            files.push({
              name: entry.name,
              path: relativePath,
              type: entry.isDirectory() ? 'directory' : 'file',
              size: stats.size,
              modified: stats.mtime.toISOString()
            });

            // Recurse into directories if requested
            if (recursive && entry.isDirectory() && depth < 5) {
              await traverse(fullPath, depth + 1);
            }
          }
        } catch (error) {
          // Log but continue traversal
          console.error(`Error reading directory ${dir}:`, error);
        }
      };

      await traverse(absolutePath);

      // Sort files by name
      files.sort((a, b) => a.name.localeCompare(b.name));

      // Limit results
      const limitedFiles = files.slice(0, 1000);

      return {
        success: true,
        files: limitedFiles,
        totalCount: files.length
      };
    } catch (error) {
      return {
        success: false,
        error: `Failed to list directory: ${error instanceof Error ? error.message : String(error)}`
      };
    }
  }
}
```

---

## 4. CommandExecutor - Command Execution

### 4.1 Interface & Implementation

```typescript
// src/tools/CommandExecutor.ts

export interface CommandResult {
  success: boolean;
  stdout?: string;
  stderr?: string;
  exitCode?: number;
  executionTime?: number;
  error?: string;
}

class CommandExecutor {
  constructor(private workspacePath: string) {}

  async executeCommand(
    command: string,
    args: string[] = [],
    timeout: number = 30000
  ): Promise<CommandResult> {
    const startTime = Date.now();

    return new Promise((resolve) => {
      try {
        // Validate command (should already be validated by backend)
        if (!this.isCommandAllowed(command)) {
          resolve({
            success: false,
            error: `Command not allowed: ${command}`
          });
          return;
        }

        const child = exec(
          [command, ...args].join(' '),
          {
            cwd: this.workspacePath,
            timeout: Math.min(timeout, 300000), // Max 5 minutes
            maxBuffer: 1024 * 1024, // 1MB buffer
            env: {
              // Safe environment - exclude sensitive vars
              PATH: process.env.PATH,
              HOME: process.env.HOME,
              LANG: process.env.LANG,
              USER: process.env.USER
            }
          },
          (error, stdout, stderr) => {
            const executionTime = Date.now() - startTime;

            if (error && error.code === null) {
              // Timeout error
              resolve({
                success: false,
                error: `Command timeout after ${timeout}ms`,
                executionTime
              });
              return;
            }

            resolve({
              success: !error,
              stdout: stdout.toString(),
              stderr: stderr.toString(),
              exitCode: error?.code || 0,
              executionTime,
              error: error?.message
            });
          }
        );

        // Handle large output
        child.stdout?.on('data', (data) => {
          // Streaming would be needed for large outputs
        });

      } catch (error) {
        resolve({
          success: false,
          error: `Failed to execute command: ${error instanceof Error ? error.message : String(error)}`,
          executionTime: Date.now() - startTime
        });
      }
    });
  }

  private isCommandAllowed(command: string): boolean {
    // Whitelist of allowed commands (mirrors backend)
    const allowed = [
      'grep', 'find', 'locate', 'ls', 'cat', 'head', 'tail', 'wc',
      'gcc', 'python', 'node', 'npm', 'git', 'zip', 'unzip', 'tar',
      'echo', 'date', 'pwd', 'whoami', 'npm', 'yarn', 'rustc'
    ];

    const baseName = path.basename(command);
    return allowed.includes(baseName);
  }
}
```

---

## 5. PathValidator - Path Validation

### 5.1 Implementation

```typescript
// src/tools/PathValidator.ts

export interface ValidationResult {
  success: boolean;
  path?: string;
  error?: string;
}

class PathValidator {
  constructor(private workspacePath: string) {}

  async validateReadPath(relativePath: string): Promise<ValidationResult> {
    try {
      const absolutePath = path.resolve(this.workspacePath, relativePath);

      // Check workspace boundary
      if (!absolutePath.startsWith(this.workspacePath)) {
        return {
          success: false,
          error: 'Path is outside workspace boundary'
        };
      }

      // Check file exists
      const stats = await fs.promises.stat(absolutePath);
      if (!stats.isFile()) {
        return {
          success: false,
          error: 'Path is not a file'
        };
      }

      // Check file size (100MB max)
      if (stats.size > 100 * 1024 * 1024) {
        return {
          success: false,
          error: 'File exceeds 100MB size limit'
        };
      }

      return {
        success: true,
        path: absolutePath
      };
    } catch (error) {
      return {
        success: false,
        error: `Failed to validate path: ${error instanceof Error ? error.message : String(error)}`
      };
    }
  }

  async validateWritePath(relativePath: string): Promise<ValidationResult> {
    try {
      const absolutePath = path.resolve(this.workspacePath, relativePath);

      // Check workspace boundary
      if (!absolutePath.startsWith(this.workspacePath)) {
        return {
          success: false,
          error: 'Path is outside workspace boundary'
        };
      }

      // Check forbidden extensions
      const ext = path.extname(absolutePath).toLowerCase();
      const forbidden = ['.exe', '.dll', '.so', '.bin', '.dylib'];
      if (forbidden.includes(ext)) {
        return {
          success: false,
          error: `Writing to ${ext} files is not allowed`
        };
      }

      return {
        success: true,
        path: absolutePath
      };
    } catch (error) {
      return {
        success: false,
        error: `Failed to validate path: ${error instanceof Error ? error.message : String(error)}`
      };
    }
  }

  async validateDirectoryPath(relativePath: string): Promise<ValidationResult> {
    try {
      const absolutePath = path.resolve(this.workspacePath, relativePath);

      // Check workspace boundary
      if (!absolutePath.startsWith(this.workspacePath)) {
        return {
          success: false,
          error: 'Path is outside workspace boundary'
        };
      }

      // Check directory exists
      const stats = await fs.promises.stat(absolutePath);
      if (!stats.isDirectory()) {
        return {
          success: false,
          error: 'Path is not a directory'
        };
      }

      return {
        success: true,
        path: absolutePath
      };
    } catch (error) {
      return {
        success: false,
        error: `Failed to validate path: ${error instanceof Error ? error.message : String(error)}`
      };
    }
  }
}
```

---

## 6. SSE Listener Integration

### 6.1 Listen for Tool Execution Signals

```typescript
// src/network/SSEListener.ts - UPDATE EXISTING

export class SSEListener {
  private eventSource: EventSource;

  subscribeToToolEvents(sessionId: string, handlers: {
    onApprovalRequest: (data: ToolApprovalRequest) => void;
    onExecutionSignal: (data: ToolExecutionSignal) => void;
    onResultAck: (data: ToolResultAck) => void;
  }): void {
    // Subscribe to existing event stream
    this.eventSource.addEventListener('tool.approval_request', (event) => {
      const data = JSON.parse(event.data) as ToolApprovalRequest;
      handlers.onApprovalRequest(data);
    });

    this.eventSource.addEventListener('tool.execution_signal', (event) => {
      const data = JSON.parse(event.data) as ToolExecutionSignal;
      handlers.onExecutionSignal(data);
    });

    this.eventSource.addEventListener('tool.result_ack', (event) => {
      const data = JSON.parse(event.data) as ToolResultAck;
      handlers.onResultAck(data);
    });
  }
}

export interface ToolApprovalRequest {
  approval_id: string;
  tool_name: string;
  risk_level: 'LOW' | 'MEDIUM' | 'HIGH';
  timeout_seconds: number;
}

export interface ToolExecutionSignal {
  tool_id: string;
  tool_name: string;
  tool_params: Record<string, any>;
}

export interface ToolResultAck {
  tool_id: string;
  status: 'received' | 'error';
}
```

---

## 7. Tool API Client

### 7.1 Implementation

```typescript
// src/network/ToolApiClient.ts

export class ToolApiClient {
  constructor(
    private baseUrl: string,
    private projectId: string,
    private authToken: string
  ) {}

  async sendToolResult(
    toolId: string,
    result: ToolExecutionResult
  ): Promise<void> {
    const response = await fetch(
      `${this.baseUrl}/my/projects/${this.projectId}/tools/${toolId}/result`,
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

  async approveToolExecution(approvalId: string): Promise<void> {
    const response = await fetch(
      `${this.baseUrl}/my/projects/${this.projectId}/approvals/${approvalId}/approve`,
      {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${this.authToken}`
        }
      }
    );

    if (!response.ok) {
      throw new Error(`Failed to approve tool: ${response.statusText}`);
    }
  }

  async rejectToolExecution(
    approvalId: string,
    reason?: string
  ): Promise<void> {
    const response = await fetch(
      `${this.baseUrl}/my/projects/${this.projectId}/approvals/${approvalId}/reject`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${this.authToken}`
        },
        body: JSON.stringify({ reason })
      }
    );

    if (!response.ok) {
      throw new Error(`Failed to reject tool: ${response.statusText}`);
    }
  }

  async getAvailableTools(): Promise<ToolDefinition[]> {
    const response = await fetch(
      `${this.baseUrl}/my/projects/${this.projectId}/tools/available`,
      {
        headers: {
          'Authorization': `Bearer ${this.authToken}`
        }
      }
    );

    if (!response.ok) {
      throw new Error(`Failed to get available tools: ${response.statusText}`);
    }

    return response.json();
  }
}

export interface ToolDefinition {
  name: string;
  description: string;
  parameters: Record<string, ParameterDefinition>;
  riskLevel: 'LOW' | 'MEDIUM' | 'HIGH';
}

export interface ParameterDefinition {
  type: string;
  description: string;
  required: boolean;
}
```

---

## 8. Approval Dialog UI

### 8.1 Implementation

```typescript
// src/ui/ApprovalDialog.ts

export class ApprovalDialog {
  async showApproval(request: ToolApprovalRequest): Promise<boolean> {
    const riskColors = {
      LOW: new vscode.ThemeColor('testing.runAction'),
      MEDIUM: new vscode.ThemeColor('debugConsole.warningForeground'),
      HIGH: new vscode.ThemeColor('errorForeground')
    };

    const action = await vscode.window.showInformationMessage(
      `Agent wants to execute: ${request.tool_name} (${request.risk_level} risk)`,
      {
        modal: true,
        detail: `Timeout: ${request.timeout_seconds}s\n\nApprove this operation?`
      },
      { title: '✅ Approve', id: 'approve' },
      { title: '❌ Reject', id: 'reject' }
    );

    return action?.id === 'approve';
  }
}
```

---

## 9. Integration with Extension

### 9.1 Activation & Setup

```typescript
// src/extension.ts - UPDATE

export async function activate(context: vscode.ExtensionContext) {
  const workspaceFolders = vscode.workspace.workspaceFolders;
  if (!workspaceFolders || workspaceFolders.length === 0) {
    vscode.window.showErrorMessage('No workspace folder found');
    return;
  }

  const workspacePath = workspaceFolders[0].uri.fsPath;
  const config = vscode.workspace.getConfiguration('codelab');
  const baseUrl = config.get<string>('apiUrl') || 'http://localhost:8000';
  const authToken = await context.secrets.get('authToken');

  // Initialize components
  const toolApiClient = new ToolApiClient(baseUrl, projectId, authToken);
  const toolHandler = new ToolHandler(workspacePath, toolApiClient, outputChannel);
  const approvalDialog = new ApprovalDialog();
  const sseListener = new SSEListener();

  // Subscribe to SSE events
  sseListener.subscribeToToolEvents(sessionId, {
    onApprovalRequest: async (data) => {
      const approved = await approvalDialog.showApproval(data);
      if (approved) {
        await toolApiClient.approveToolExecution(data.approval_id);
      } else {
        await toolApiClient.rejectToolExecution(data.approval_id, 'User rejected');
      }
    },

    onExecutionSignal: async (data) => {
      try {
        const result = await toolHandler.executeToolLocally(
          data.tool_id,
          data.tool_name,
          data.tool_params,
          sessionId
        );
        await toolApiClient.sendToolResult(data.tool_id, result);
      } catch (error) {
        vscode.window.showErrorMessage(
          `Tool execution failed: ${error instanceof Error ? error.message : String(error)}`
        );
      }
    },

    onResultAck: (data) => {
      if (data.status === 'error') {
        vscode.window.showErrorMessage(`Failed to process tool result: ${data.tool_id}`);
      }
    }
  });

  // Cleanup on deactivation
  context.subscriptions.push({
    dispose: async () => {
      await toolHandler.cleanup();
    }
  });
}
```

---

## 10. Implementation Phases

### Phase 1: Core Infrastructure (Week 1)
- [ ] ToolHandler class
- [ ] FileSystemExecutor
- [ ] PathValidator
- [ ] Unit tests for path validation
- [ ] TypeScript types

### Phase 2: Execution Layer (Week 2)
- [ ] CommandExecutor
- [ ] ToolResultCollector
- [ ] Integration with existing extension
- [ ] Error handling & logging

### Phase 3: Network Integration (Week 3)
- [ ] SSE listener integration
- [ ] ToolApiClient
- [ ] ApprovalDialog UI
- [ ] Result sending via REST API

### Phase 4: Testing & Polish (Week 4)
- [ ] Integration tests (tool execution + network)
- [ ] Security tests (path traversal, command injection)
- [ ] E2E tests (full workflow)
- [ ] Performance optimization
- [ ] Documentation

### Phase 5: Deployment (Week 5)
- [ ] Production build
- [ ] Extension marketplace publishing
- [ ] User documentation
- [ ] Monitoring & logging

---

## 11. Testing Strategy

### 11.1 Unit Tests

```typescript
// src/tools/__tests__/PathValidator.test.ts

describe('PathValidator', () => {
  let validator: PathValidator;

  beforeEach(() => {
    validator = new PathValidator('/workspace');
  });

  test('should validate safe read path', async () => {
    const result = await validator.validateReadPath('src/file.ts');
    expect(result.success).toBe(true);
  });

  test('should block path traversal', async () => {
    const result = await validator.validateReadPath('../../../etc/passwd');
    expect(result.success).toBe(false);
  });

  test('should block oversized files', async () => {
    const result = await validator.validateReadPath('large-file.bin');
    expect(result.success).toBe(false);
  });
});
```

### 11.2 Integration Tests

```typescript
// src/__tests__/integration/ToolHandler.integration.test.ts

describe('ToolHandler Integration', () => {
  test('should handle complete read_file workflow', async () => {
    // 1. Create test file
    // 2. Call ToolHandler.readFile()
    // 3. Verify result
    // 4. Send via API
    // 5. Verify server acknowledgment
  });

  test('should handle write_file with approval', async () => {
    // 1. Mock SSE approval request
    // 2. Simulate user approval
    // 3. Execute writeFile
    // 4. Send result via API
    // 5. Verify file written
  });
});
```

### 11.3 Security Tests

```typescript
// src/__tests__/security/PathTraversal.test.ts

describe('Security: Path Traversal Prevention', () => {
  test('should block ../../ sequences', async () => {
    const paths = [
      '../../../etc/passwd',
      'src/../../etc/passwd',
      'src//../../etc/passwd'
    ];
    
    for (const p of paths) {
      const result = await validator.validateReadPath(p);
      expect(result.success).toBe(false);
    }
  });

  test('should resolve symlinks safely', async () => {
    // Create symlink to outside workspace
    // Verify it's rejected
  });
});
```

---

## 12. Configuration

### 12.1 Extension Settings

```json
{
  "codelab.tools.enabled": true,
  "codelab.tools.autoApprove": false,
  "codelab.tools.commandTimeout": 30000,
  "codelab.tools.maxFileSize": 104857600,
  "codelab.tools.logging.level": "info",
  "codelab.tools.logging.file": "${workspaceFolder}/.codelab/tools.log"
}
```

---

## 13. Error Handling

### 13.1 Error Recovery Strategy

```typescript
export enum ToolErrorCode {
  VALIDATION_ERROR = 'VALIDATION_ERROR',
  EXECUTION_TIMEOUT = 'EXECUTION_TIMEOUT',
  PERMISSION_DENIED = 'PERMISSION_DENIED',
  NETWORK_ERROR = 'NETWORK_ERROR',
  UNKNOWN_ERROR = 'UNKNOWN_ERROR'
}

export interface ToolError {
  code: ToolErrorCode;
  message: string;
  details?: Record<string, any>;
  recoverable: boolean;
}

// Retry logic
async function executeWithRetry<T>(
  fn: () => Promise<T>,
  maxRetries: number = 3,
  backoffMs: number = 1000
): Promise<T> {
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      return await fn();
    } catch (error) {
      if (attempt === maxRetries) throw error;
      await new Promise(resolve => setTimeout(resolve, backoffMs * attempt));
    }
  }
  throw new Error('Max retries exceeded');
}
```

---

## 14. Documentation & Examples

### 14.1 User Documentation

**File**: `doc/client-tools-usage.md`

```markdown
# Using Agent Tools in VS Code

## Enabling Tools

1. Install Codelab Extension
2. Configure API URL and authentication
3. Enable tools in extension settings

## Approval Workflow

When an agent wants to execute a tool:
1. You see approval dialog
2. Review tool name and risk level
3. Click "Approve" or "Reject"
4. Tool executes on your machine
5. Results sent back to agent

## Examples

### Example 1: Read File
Agent: "Show me the contents of package.json"
1. Agent requests: read_file("package.json")
2. Tool executes locally
3. Result displayed in chat

### Example 2: Execute Command
Agent: "Run npm test"
1. Agent requests: execute_command("npm", ["test"])
2. You approve (MEDIUM risk)
3. Command runs in your workspace
4. Output shown in chat
```

---

## 15. Success Criteria

- [ ] All 5 components implemented and tested
- [ ] 85+ unit tests (mirroring backend coverage)
- [ ] Integration tests for complete workflow
- [ ] Security tests for path traversal and command injection
- [ ] All tools working: read_file, write_file, execute_command, list_directory
- [ ] Approval dialog working correctly
- [ ] Error handling and recovery
- [ ] Performance: tool execution < 5 seconds (excluding network latency)
- [ ] Full documentation and examples
- [ ] Extension marketplace ready

---

## 16. Dependencies

```json
{
  "dependencies": {
    "vscode": "^1.85.0"
  },
  "devDependencies": {
    "typescript": "^5.0.0",
    "jest": "^29.0.0",
    "@types/jest": "^29.0.0",
    "@types/node": "^20.0.0"
  }
}
```

---

## 17. Timeline

| Phase | Duration | Tasks |
|-------|----------|-------|
| 1 | 1 week | Core infrastructure, path validation |
| 2 | 1 week | Command execution, result collection |
| 3 | 1 week | SSE integration, API client, UI |
| 4 | 1 week | Testing, security, optimization |
| 5 | 1 week | Deployment, documentation, release |

**Total**: 5 weeks (including buffer)

---

## Appendix A: File Structure

```
codelab-vscode-extension/
├── src/
│   ├── tools/
│   │   ├── ToolHandler.ts
│   │   ├── FileSystemExecutor.ts
│   │   ├── CommandExecutor.ts
│   │   ├── PathValidator.ts
│   │   ├── ToolResultCollector.ts
│   │   ├── types.ts
│   │   └── __tests__/
│   ├── ui/
│   │   ├── ApprovalDialog.ts
│   │   ├── ToolProgressBar.ts
│   │   └── ToolStatusView.ts
│   ├── network/
│   │   ├── SSEListener.ts
│   │   ├── ToolApiClient.ts
│   │   └── ApprovalClient.ts
│   ├── config/
│   │   └── toolConfig.ts
│   ├── extension.ts
│   └── __tests__/
│       ├── integration/
│       └── security/
├── doc/
│   ├── client-tools-implementation.md (this file)
│   ├── client-tools-usage.md
│   └── architecture.md
├── package.json
├── tsconfig.json
└── jest.config.js
```

---

**Document Version**: 1.0
**Last Updated**: 2026-02-21
**Status**: Ready for Implementation
