# Интеграция LLM Tools в ContextualAgent

## Описание

Реализована полная интеграция OpenAI Function Calling в ContextualAgent для поддержки динамического выполнения tools (инструментов) через LLM.

## Архитектура

```
User Request
    ↓
ContextualAgent.execute()
    ↓
    ├─ Получить tools: _get_available_tools()
    │
    ├─ Запрос к LLM с tools (OpenAI Function Calling)
    │
    ├─ LLM решает использовать tool → tool_calls
    │
    ├─ Выполнить tools: _execute_tools()
    │   └─ ToolExecutor.execute_tool() → ToolExecution создана
    │
    ├─ Ожидать результат: _wait_for_tool_results()
    │   └─ Polling ToolExecution из БД с timeout 600 сек
    │
    ├─ Форматировать результаты: _format_tool_result()
    │
    ├─ Отправить результаты обратно в LLM
    │
    └─ LLM генерирует финальный ответ
        ↓
    Response с tools_used > 0
```

## Изменённые файлы

### 1. [`app/agents/contextual_agent.py`](../app/agents/contextual_agent.py)
- Добавлены методы для работы с tools
- Модифицирован конструктор: параметр `tool_executor`
- Модифицирован метод `execute()`: поддержка OpenAI Function Calling

**Ключевые методы:**
- `_get_available_tools()` - получить tools в формате OpenAI
- `_execute_tools(tool_calls)` - выполнить tool calls через ToolExecutor
- `_wait_for_tool_results(tool_execution_ids)` - polling результатов
- `_format_tool_result(tool_call_id, tool_name, tool_result)` - форматировать для LLM

### 2. [`app/agents/manager.py`](../app/agents/manager.py)
- Добавлен параметр `tool_executor` в конструктор
- Передача `tool_executor` при создании ContextualAgent

### 3. [`app/core/user_worker_space.py`](../app/core/user_worker_space.py)
- Передача `tool_executor=self.executor` в AgentManager и ContextualAgent

### 4. [`app/routes/project_agents.py`](../app/routes/project_agents.py)
- Обновлена зависимость `get_agent_manager()` для передачи executor

### 5. [`app/routes/project_chat.py`](../app/routes/project_chat.py)
- Передача `tool_executor=workspace.executor` при создании AgentManager

## Как проверить выполнение LLM Tools

### Способ 1: Логи (Рекомендуется)

Смотреть логи приложения на следующие события:

```
✓ available_tools_retrieved (DEBUG)
  → tools доступны для LLM

✓ processing_tool_calls (INFO)
  → LLM решил использовать tool

✓ executing_tool_from_llm (INFO)
  → агент отправляет tool на выполнение

✓ tool_execution_requested (DEBUG)
  → tool зарегистрирован в ToolExecutor

✓ tool_execution_completed (DEBUG)
  → tool выполнен успешно

✓ tool_calls_processed (INFO)
  → результаты отправлены в LLM

✓ agent_executed (INFO)
  → с полем "tools_used": 1
```

### Способ 2: Response структура

```json
{
  "success": true,
  "response": "Содержание файла...",
  "context_used": 2,
  "tokens_used": 1250,
  "tools_used": 1  // ← главный индикатор
}
```

**Проверить:** `tools_used > 0`

### Способ 3: БД (tool_executions таблица)

```sql
SELECT id, tool_name, status, result, error, created_at, completed_at
FROM tool_executions
WHERE user_id = '{user_id}'
ORDER BY created_at DESC
LIMIT 5;
```

**Ожидаемое:**
- `status = 'completed'`
- `result` заполнено JSON'ом
- `error IS NULL`

### Способ 4: curl тест

```bash
# 1. Создать агент
curl -X POST http://localhost:8000/my/projects/{project_id}/agents \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "TestAgent",
    "config": {
      "model": "gpt-4",
      "system_prompt": "Help with file operations.",
      "temperature": 0.7,
      "max_tokens": 2000
    }
  }'

# 2. Отправить запрос с tool'ом
curl -X POST http://localhost:8000/my/projects/{project_id}/chat/messages \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Read file README.md and tell me what it contains",
    "agent_id": "{agent_id}"
  }'

# 3. Проверить response
# "tools_used": 1 означает успех
```

## Конфигурация для работы

### Требования

1. **LLM Model**: `gpt-4` или совместимая
   - gpt-3.5-turbo НЕ поддерживает функции calling в полной мере
   
2. **ToolExecutor**: должен быть передан
   ```python
   agent = ContextualAgent(
       ...
       tool_executor=executor,  # ВАЖНО: не None
   )
   ```

3. **Доступные tools**: read_file, write_file, execute_command, list_directory
   - Определены в [`app/core/tools/definitions.py`](../app/core/tools/definitions.py)

### Таймауты и параметры

- **Tool execution timeout**: 600 сек (10 минут)
- **Polling interval**: 1.0 сек
- **Max retries**: не ограничено (до timeout)

## Примеры использования

### Пример 1: Агент читает файл

```
User: "Прочитай файл README.md"
     ↓
LLM: Вызывает read_file(path="README.md")
     ↓
ToolExecutor: Создаёт ToolExecution, отправляет на клиент
     ↓
ContextualAgent: Polling статуса
     ↓
Результат: ToolExecution.status = "completed"
           ToolExecution.result = {"content": "...", ...}
     ↓
LLM: Получает результат, генерирует ответ
     ↓
Response: "Вот содержание README.md: ..."
          "tools_used": 1
```

### Пример 2: Агент выполняет команду

```
User: "Выполни ls -la в текущей директории"
     ↓
LLM: Вызывает execute_command(command="ls", args=["-la"])
     ↓
ToolExecutor: Требует approval (HIGH risk)
     ↓
ContextualAgent: Ждёт одобрения от пользователя
     ↓
После одобрения: Tool выполняется
     ↓
Response с результатом выполнения
```

## Статусы Tool Execution

| Статус | Описание |
|--------|----------|
| `pending` | Ожидание обработки |
| `approved` | Одобрено, готово к выполнению |
| `executing` | Выполняется на клиенте |
| `completed` | ✓ Успешно выполнено |
| `failed` | ✗ Ошибка выполнения |
| `rejected` | ✗ Отклонено пользователем |
| `not_found` | ✗ Запись не найдена |
| `invalid` | ✗ Невалидный ID |
| `timeout` | ✗ Истёк timeout ожидания |

## Логирование

### DEBUG уровень
- `available_tools_retrieved` - tools инициализированы
- `tool_execution_requested` - tool отправлен на выполнение
- `tool_execution_completed` - tool выполнен
- `failed_to_check_tool_status` - ошибка при проверке статуса

### INFO уровень
- `processing_tool_calls` - LLM вызывает tools
- `executing_tool_from_llm` - агент выполняет tool
- `tool_calls_processed` - результаты получены
- `agent_executed` - с `"tools_used": N`

### ERROR уровень
- `tool_execution_error` - ошибка при выполнении
- `invalid_tool_execution_id` - невалидный ID tool'а
- `agent_execution_failed` - ошибка выполнения агента

## Обработка ошибок

### Tool падает
- ToolExecutor ловит ошибку и сохраняет в `ToolExecution.error`
- ContextualAgent получает `status="failed"` с сообщением об ошибке
- LLM получает информацию об ошибке и может попробовать другой подход

### Timeout при ожидании
- ContextualAgent ждёт max 600 сек
- По истечении timeout возвращает `status="timeout"`
- LLM получает info о timeout и генерирует соответствующий ответ

### Tool требует approval
- ToolExecutor создаёт Approval запрос
- ContextualAgent ждёт решения пользователя
- После одобрения tool выполняется
- После отклонения возвращается `status="rejected"`

## Graceful degradation

Если `tool_executor=None`:
- `_get_available_tools()` возвращает пустой список
- LLM не видит доступные tools
- Agent работает как раньше (только текстовые ответы)
- Полная обратная совместимость

## Интеграция с другими компонентами

### ApprovalManager
- Управляет approval workflow'ом для tool'ов
- Определяет risk level (LOW/MEDIUM/HIGH)
- Автоматически одобряет LOW risk tools
- Требует approval для MEDIUM/HIGH

### StreamManager
- Отправляет события о выполнении tool'ов через SSE
- Events: `tool_execution_request`, `tool_execution_completed`
- Позволяет клиенту отслеживать выполнение

### OutboxRepository
- Логирует все tool execution events
- Обеспечивает гарантированную доставку
- Хранит историю выполнения

## Тестирование

См. [`tests/LLM_TOOLS_TEST_GUIDE.md`](../tests/LLM_TOOLS_TEST_GUIDE.md) для подробного гайда проверки.

## Заключение

Интеграция полностью завершена и готова к использованию. 

✅ ContextualAgent → ToolExecutor → Tools execution → Result → LLM → Final response

Для проверки смотрите логи на события `processing_tool_calls` и `tool_calls_processed`.
