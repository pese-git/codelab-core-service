# Гайд проверки выполнения LLM Tools

## Способ 1: Проверка через логи

Когда агент выполняет tools, в логах появляются следующие события:

### 1. Инициализация tools (DEBUG)
```
event: "available_tools_retrieved"
agent_id: "..."
tools_count: 4  // количество доступных tools
```
✓ Означает, что `tool_executor` успешно передан и tools доступны

### 2. LLM решил использовать tool (INFO)
```
event: "processing_tool_calls"
agent_id: "..."
tool_calls_count: 1  // количество tool calls от LLM
task_id: "..."
```
✓ Означает, что LLM выбрал использовать tool

### 3. Выполнение tool (INFO)
```
event: "executing_tool_from_llm"
agent_id: "..."
tool_call_id: "..."
tool_name: "read_file"  // имя tool'а
```
✓ Означает, что агент отправил tool на ToolExecutor

### 4. Tool запущен (DEBUG)
```
event: "tool_execution_requested"
agent_id: "..."
tool_call_id: "..."
tool_execution_id: "..."
status: "approved|pending"  // статус выполнения
```
✓ Означает, что ToolExecutor получил запрос

### 5. Результат получен (DEBUG)
```
event: "tool_execution_completed"
agent_id: "..."
tool_execution_id: "..."
status: "completed"
```
✓ Означает, что tool выполнен и результат доступен

### 6. Финальный ответ (INFO)
```
event: "tool_calls_processed"
agent_id: "..."
tool_calls_count: 1
final_response_received: true
task_id: "..."
```
✓ Означает, что LLM обработал результаты и дал финальный ответ

## Способ 2: Проверка Response структуры

Ответ от endpoint'а `/chat/messages` содержит:

```json
{
  "success": true,
  "response": "Вот содержание файла: ...",
  "context_used": 2,
  "tokens_used": 1250,
  "tools_used": 1
}
```

**Проверять:**
- `tools_used > 0` - агент использовал tools
- `response` не пустой - LLM вернул результат

## Способ 3: Проверка БД

Таблица `tool_executions` содержит запись о каждом выполнении:

```sql
SELECT 
  id,
  tool_name,
  status,
  result,
  error,
  created_at,
  completed_at
FROM tool_executions
WHERE user_id = '{user_id}'
  AND created_at > NOW() - INTERVAL '5 minutes'
ORDER BY created_at DESC;
```

**Ожидаемое:**
- `status = 'completed'` - tool успешно выполнен
- `result` содержит JSON с результатом
- `completed_at` заполнено
- `error` пуст

## Способ 4: Тестирование через curl

### Создать агент
```bash
curl -X POST http://localhost:8000/my/projects/{project_id}/agents \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer {token}" \
  -d '{
    "name": "FileAgent",
    "config": {
      "model": "gpt-4",
      "system_prompt": "You are a helpful assistant that can work with files.",
      "temperature": 0.7,
      "max_tokens": 2000
    }
  }'
```

### Отправить сообщение с запросом к файлу
```bash
curl -X POST http://localhost:8000/my/projects/{project_id}/chat/messages \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer {token}" \
  -d '{
    "content": "Читай файл README.md и расскажи что там",
    "agent_id": "{agent_id}"
  }'
```

**Проверять:**
- Ответ `success: true`
- `tools_used: 1`
- В ответе есть содержание файла

## Способ 5: Проверка через SSE (если включен StreamManager)

Если настроен StreamManager, events отправляются через SSE:

```javascript
const eventSource = new EventSource(
  '/api/stream?user_id={user_id}',
  { headers: { Authorization: 'Bearer ' + token } }
);

// Событие: tool запрошен
eventSource.addEventListener('tool_execution_request', (event) => {
  const data = JSON.parse(event.data);
  console.log('Tool requested:', data.tool_name);
});

// Событие: tool выполнен
eventSource.addEventListener('tool_execution_completed', (event) => {
  const data = JSON.parse(event.data);
  console.log('Tool completed:', data.status);
});
```

## Способ 6: Интеграционный тест

```python
import asyncio
from uuid import uuid4
from app.agents.contextual_agent import ContextualAgent
from app.schemas.agent import AgentConfig

async def test_tools_integration():
    """Проверить, что tools работают в ContextualAgent"""
    
    # ВАЖНО: tool_executor должен быть передан!
    agent = ContextualAgent(
        agent_id=uuid4(),
        user_id=uuid4(),
        agent_name="TestAgent",
        config=AgentConfig(
            model="gpt-4",
            system_prompt="You are helpful file assistant.",
            temperature=0.7,
            max_tokens=2000
        ),
        qdrant_client=None,
        tool_executor=tool_executor,  # <- Это главное!
    )
    
    # Выполнить с request к файлу
    result = await agent.execute(
        user_message="Read file test.txt",
        session_id=uuid4(),
    )
    
    # Проверки
    assert result["success"], "Execution failed"
    assert result["tools_used"] >= 1, "No tools were used"
    assert "test.txt" in result["response"], "File content not in response"
    
    print("✓ Tools integration test PASSED!")

asyncio.run(test_tools_integration())
```

## Checklist для проверки

- [ ] В логах есть `available_tools_retrieved` с `tools_count > 0`
- [ ] При запросе к файлу появляется `processing_tool_calls`
- [ ] Видно `executing_tool_from_llm` с названием tool'а
- [ ] Видно `tool_execution_completed` со статусом `completed`
- [ ] Response содержит `tools_used > 0`
- [ ] В БД таблица `tool_executions` содержит запись со статусом `completed`
- [ ] Финальный ответ содержит результат выполнения tool'а

## Частые проблемы

### Tools не вызываются
**Проверить:**
- Модель: используется ли `gpt-4` или совместимая? (gpt-3.5-turbo может не поддерживать function calling)
- В логах должно быть `available_tools_retrieved` с `tools_count > 0`
- `tool_executor` не `None`

### Tools долго выполняются
**Это нормально для:**
- Первого запроса (требуется approval от пользователя)
- Когда tool требует доступа к файловой системе

**Проверить:**
- Статус в БД - может быть `pending` или `approved`
- Логи polling'а - должны показывать попытки получить результат

### Результаты tools не в ответе
**Проверить:**
- Статус tool в БД - должен быть `completed`
- Поле `result` в `tool_executions` - содержит ли данные
- Логи - есть ли `tool_calls_processed`

## Пример успешного выполнения

```
2026-03-04 12:30:15 INFO available_tools_retrieved tools_count=4
2026-03-04 12:30:16 INFO processing_tool_calls tool_calls_count=1
2026-03-04 12:30:16 INFO executing_tool_from_llm tool_name=read_file
2026-03-04 12:30:16 DEBUG tool_execution_requested status=approved
2026-03-04 12:30:17 DEBUG tool_execution_completed status=completed
2026-03-04 12:30:17 INFO tool_calls_processed final_response_received=true

Response: {
  "success": true,
  "response": "File content: ... [file contents]",
  "tools_used": 1,
  "tokens_used": 1250
}

DB: tool_executions status=completed, result={...}
```

Если видишь эту последовательность - tools работают корректно! ✓
