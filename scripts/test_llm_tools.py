#!/usr/bin/env python
"""Test script for verifying LLM tools execution with ContextualAgent."""

import asyncio
import json
from uuid import uuid4

# Example of how tools are integrated into ContextualAgent execution

INTEGRATION_TEST_SCENARIO = """
## Проверка выполнения LLM Tools в ContextualAgent

### Способ 1: Прямое тестирование через API

```bash
# 1. Создать агент с поддержкой tools
curl -X POST http://localhost:8000/api/v1/core/my/projects/{project_id}/agents \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer {token}" \\
  -d '{
    "name": "FileAgent",
    "config": {
      "model": "gpt-4",
      "system_prompt": "You are a helpful file assistant. You can read and write files.",
      "temperature": 0.7,
      "max_tokens": 2000
    }
  }'

# 2. Отправить сообщение с запросом к файлу
curl -X POST http://localhost:8000/api/v1/core/my/projects/{project_id}/chat/messages \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer {token}" \\
  -d '{
    "content": "Прочитай файл README.md и суммаризируй его",
    "agent_id": "{agent_id}"
  }'

# 3. Мониторить логи для проверки:
#    - "processing_tool_calls" - LLM решил использовать tool
#    - "executing_tool_from_llm" - агент выполняет tool
#    - "tool_execution_completed" - tool успешно выполнен
#    - "tool_calls_processed" - получен финальный ответ из LLM
```

### Способ 2: Проверка логов

Логи содержат следующие события:

1. **processing_tool_calls** (уровень INFO)
   ```
   {
     "event": "processing_tool_calls",
     "agent_id": "...",
     "tool_calls_count": 1,
     "task_id": "..."
   }
   ```

2. **executing_tool_from_llm** (уровень INFO)
   ```
   {
     "event": "executing_tool_from_llm",
     "agent_id": "...",
     "tool_call_id": "...",
     "tool_name": "read_file"
   }
   ```

3. **tool_execution_requested** (уровень DEBUG)
   ```
   {
     "event": "tool_execution_requested",
     "agent_id": "...",
     "tool_call_id": "...",
     "tool_execution_id": "...",
     "status": "approved|pending"
   }
   ```

4. **tool_execution_completed** (уровень DEBUG)
   ```
   {
     "event": "tool_execution_completed",
     "agent_id": "...",
     "tool_execution_id": "...",
     "status": "completed"
   }
   ```

5. **tool_calls_processed** (уровень INFO)
   ```
   {
     "event": "tool_calls_processed",
     "agent_id": "...",
     "tool_calls_count": 1,
     "final_response_received": true,
     "task_id": "..."
   }
   ```

### Способ 3: Проверка БД

Проверить таблицу `tool_executions`:

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
ORDER BY created_at DESC
LIMIT 10;
```

Возможные статусы:
- `pending` - ожидание одобрения
- `approved` - одобрено, готово к выполнению
- `executing` - выполняется на клиенте
- `completed` - успешно выполнено
- `failed` - ошибка выполнения
- `rejected` - отклонено пользователем

### Способ 4: Проверка Response структуры

Ответ от `/chat/messages` содержит:

```json
{
  "success": true,
  "response": "Вот содержание README.md: ...",
  "context_used": 2,
  "tokens_used": 1250,
  "tools_used": 1
}
```

Поле `tools_used` показывает количество выполненных tools.

### Способ 5: SSE мониторинг (если включен StreamManager)

События о выполнении tools отправляются через SSE:

```javascript
const eventSource = new EventSource('/api/stream');

eventSource.addEventListener('tool_execution_request', (event) => {
  console.log('Tool requested:', JSON.parse(event.data));
});

eventSource.addEventListener('tool_execution_completed', (event) => {
  console.log('Tool completed:', JSON.parse(event.data));
});
```

## Пример интеграционного теста

```python
import asyncio
from uuid import uuid4
from app.agents.contextual_agent import ContextualAgent
from app.core.tools.executor import ToolExecutor
from app.schemas.agent import AgentConfig

async def test_tool_execution():
    # Setup
    agent_id = uuid4()
    user_id = uuid4()
    config = AgentConfig(
        model="gpt-4",
        system_prompt="You are a helpful assistant.",
        temperature=0.7,
        max_tokens=2000
    )
    
    # Создать agent с tool_executor
    agent = ContextualAgent(
        agent_id=agent_id,
        user_id=user_id,
        agent_name="TestAgent",
        config=config,
        qdrant_client=None,  # или actual qdrant client
        tool_executor=tool_executor,  # Important: передать executor
    )
    
    # Выполнить с запросом к файлу
    result = await agent.execute(
        user_message="Read file test.txt and summarize it",
        session_history=None,
        task_id="test_task_1",
        session_id=uuid4(),
    )
    
    # Проверить результат
    assert result["success"] == True
    assert result["tools_used"] >= 1  # Минимум один tool должен быть использован
    print(f"✓ Tool execution test passed!")
    print(f"  Response: {result['response'][:100]}...")
    print(f"  Tools used: {result['tools_used']}")

if __name__ == "__main__":
    asyncio.run(test_tool_execution())
```

## Общая схема проверки

1. **Проверить, что tools передаются в LLM** - логи должны показывать "available_tools_retrieved"
2. **Проверить, что LLM вызывает tools** - логи "processing_tool_calls"
3. **Проверить, что tools выполняются** - логи "tool_execution_requested"
4. **Проверить, что результаты возвращаются** - статус в БД "completed"
5. **Проверить финальный ответ** - LLM получает результаты и отвечает

## Возможные проблемы и решения

### Проблема: tools не вызываются LLM
- Проверить, что в конфигурации LLM используется "gpt-4" (gpt-3.5 может не поддерживать function calling)
- Проверить логи - должны быть "available_tools_retrieved" с количеством > 0
- Проверить, что tool_executor не None

### Проблема: tools выполняются долго
- Это нормально для первого запроса (требуется approval)
- Проверить статус ToolExecution в БД
- Проверить логи polling'а

### Проблема: результаты tools не в финальном ответе
- Проверить, что "_format_tool_result" логирует
- Проверить результаты tool_results в логах
- Проверить, что второй запрос к LLM успешен

"""

print(INTEGRATION_TEST_SCENARIO)

# Также сохранить сценарий
with open("tests/LLM_TOOLS_TEST_GUIDE.md", "w") as f:
    f.write(INTEGRATION_TEST_SCENARIO)
    print("\n✓ Guide saved to tests/LLM_TOOLS_TEST_GUIDE.md")
