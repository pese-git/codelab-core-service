# Тестирование LLM Tools через Docker Logs

## Запуск сервиса

### 1. Стартовать все сервисы
```bash
docker-compose up -d
```

Это запустит:
- **postgres:5432** - основная БД
- **redis:6379** - кэш
- **qdrant:6333** - векторная БД
- **prometheus:9090** - мониторинг
- **grafana:3000** - дашборды
- **app:8000** - основной сервис

### 2. Проверить статус контейнеров
```bash
docker-compose ps
```

Ожидаемый результат:
```
NAME                    STATUS
codelab-postgres        Up (healthy)
codelab-redis           Up (healthy)
codelab-qdrant          Up (healthy)
codelab-prometheus      Up
codelab-grafana         Up
codelab-core-service    Up
```

### 3. Убедиться, что приложение запустилось
```bash
curl http://localhost:8000/health
```

Ответ должен быть:
```json
{"status": "healthy"}
```

## Просмотр логов

### Все логи приложения
```bash
docker-compose logs -f app
```

Флаг `-f` = follow (реальное время)

### Логи конкретного сервиса
```bash
# Только postgresql
docker-compose logs -f postgres

# Только redis
docker-compose logs -f redis

# Только qdrant
docker-compose logs -f qdrant
```

### Логи последних N строк
```bash
docker-compose logs --tail=100 app
```

### Логи за последние N времени
```bash
docker-compose logs --since=10m app
```

## Ожидаемые логи при выполнении Tools

### 1. При инициализации агента
```
INFO: available_tools_retrieved
  agent_id: ...
  tools_count: 4
```

### 2. Когда LLM решает использовать tool
```
INFO: processing_tool_calls
  agent_id: ...
  tool_calls_count: 1
  task_id: ...
```

### 3. Когда агент выполняет tool
```
INFO: executing_tool_from_llm
  agent_id: ...
  tool_call_id: ...
  tool_name: read_file
```

### 4. Tool запрошен в ToolExecutor
```
DEBUG: tool_execution_requested
  agent_id: ...
  tool_call_id: ...
  tool_execution_id: ...
  status: approved
```

### 5. Tool выполнен
```
DEBUG: tool_execution_completed
  agent_id: ...
  tool_execution_id: ...
  status: completed
```

### 6. Результаты отправлены в LLM
```
INFO: tool_calls_processed
  agent_id: ...
  tool_calls_count: 1
  final_response_received: true
```

### 7. Финальный агент результат
```
INFO: agent_executed
  agent_id: ...
  agent_name: ...
  task_id: ...
  context_used: 2
  tools_used: 1
```

## Тестовый сценарий через Docker

### Шаг 1: Запустить сервис и посмотреть логи
```bash
# Терминал 1: Запустить сервис с логами
docker-compose up app

# Терминал 2: В отдельном окне выполнять curl'ы
```

### Шаг 2: Создать проект
```bash
# Нужен токен - пример предполагает, что токен уже есть
curl -X POST http://localhost:8000/my/projects \
  -H "Authorization: Bearer {YOUR_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "TestProject",
    "workspace_path": "/tmp/test_workspace"
  }'

# Сохранить project_id из ответа
export PROJECT_ID="..."
```

### Шаг 3: Создать агент с tools
```bash
curl -X POST http://localhost:8000/my/projects/${PROJECT_ID}/agents \
  -H "Authorization: Bearer {YOUR_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "FileAgent",
    "config": {
      "model": "gpt-4",
      "system_prompt": "You are helpful file assistant that can read files.",
      "temperature": 0.7,
      "max_tokens": 2000
    }
  }'

# Сохранить agent_id из ответа
export AGENT_ID="..."
```

### Шаг 4: Отправить запрос к файлу

```bash
curl -X POST http://localhost:8000/my/projects/${PROJECT_ID}/chat/messages \
  -H "Authorization: Bearer {YOUR_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Read file /tmp/test_workspace/README.md and tell me about it",
    "agent_id": "'${AGENT_ID}'"
  }'
```

### Шаг 5: Смотреть логи в Терминал 1

Должны появиться логи:
```
DEBUG: available_tools_retrieved (agent инициализирован)
↓
INFO: processing_tool_calls (LLM вызывает tool)
↓
INFO: executing_tool_from_llm (агент отправляет tool)
↓
DEBUG: tool_execution_requested (tool зарегистрирован)
↓
DEBUG: tool_execution_completed (tool выполнен)
↓
INFO: tool_calls_processed (результат отправлен в LLM)
↓
INFO: agent_executed (с tools_used: 1)
```

## Фильтрация логов

### Логи только о tools
```bash
docker-compose logs -f app | grep -i "tool"
```

### Логи только об ошибках
```bash
docker-compose logs -f app | grep -E "ERROR|CRITICAL"
```

### Логи конкретного агента
```bash
# Нужно знать agent_id
docker-compose logs -f app | grep "{AGENT_ID}"
```

### Логи за определённое время
```bash
# Только INFO и выше
docker-compose logs --since=2m app | grep "INFO:"
```

## Анализ логов - Checklist

Для успешного выполнения tools должны быть логи в этом порядке:

- [ ] `available_tools_retrieved` - tools инициализированы
- [ ] `processing_tool_calls` - LLM выбрал использовать tool
- [ ] `executing_tool_from_llm` - агент выполняет tool
- [ ] `tool_execution_requested` - ToolExecutor получил запрос
- [ ] `tool_execution_completed` - tool успешно выполнен
- [ ] `tool_calls_processed` - результаты обработаны
- [ ] `agent_executed` с `tools_used: >= 1` - финальный результат

Если видишь все эти логи в правильном порядке - **tools работают корректно** ✓

## Отладка проблем через логи

### Problem: Tools не вызываются

**Логи показывают:**
```
available_tools_retrieved ✓
processing_tool_calls ✗ (нет этого логи)
```

**Причины:**
1. Модель не `gpt-4` (используется несовместимая модель)
2. system_prompt не содержит информацию о tools
3. tool_executor не инициализирован

**Решение:** Проверить в логах ошибки при инициализации agentmanager

### Problem: Tool долго выполняется

**Логи показывают:**
```
tool_execution_requested ✓
tool_execution_completed ✗ (долго ждёт)
```

**Причины:**
1. Tool требует approval (есть statatus: pending/approved)
2. Клиент не выполняет tool
3. Timeout истёк

**Решение:** Проверить статус ToolExecution в БД:
```sql
SELECT status, error FROM tool_executions 
WHERE created_at > NOW() - INTERVAL '5 minutes'
ORDER BY created_at DESC LIMIT 1;
```

### Problem: Результаты tools не в ответе

**Логи показывают:**
```
tool_execution_completed ✓
tool_calls_processed ✗ (нет этого логи)
```

**Причины:**
1. Ошибка при форматировании результатов
2. Ошибка при отправке результатов в LLM
3. Ошибка при обработке ответа LLM

**Решение:** Посмотреть ERROR логи:
```bash
docker-compose logs app | grep "ERROR"
```

## Пример успешного лог-сессии

```
2026-03-04 13:30:15 INFO  UserWorkerSpace initialized for user: {user_id}
2026-03-04 13:30:16 DEBUG available_tools_retrieved agent_id={agent_id} tools_count=4
2026-03-04 13:30:17 INFO  Chat message received: "Read file README.md"
2026-03-04 13:30:18 INFO  processing_tool_calls agent_id={agent_id} tool_calls_count=1
2026-03-04 13:30:18 INFO  executing_tool_from_llm tool_name=read_file
2026-03-04 13:30:18 DEBUG tool_execution_requested status=approved
2026-03-04 13:30:19 DEBUG tool_execution_completed status=completed
2026-03-04 13:30:20 INFO  tool_calls_processed final_response_received=true
2026-03-04 13:30:21 INFO  agent_executed tools_used=1
2026-03-04 13:30:21 INFO  Response: {
  "success": true,
  "response": "File contents: ...",
  "tools_used": 1,
  "tokens_used": 1250
}
```

Если видишь такую последовательность - всё работает идеально! ✓

## Полезные команды

```bash
# Перезапустить сервис с логами
docker-compose restart app && docker-compose logs -f app

# Очистить старые контейнеры/логи
docker-compose down -v

# Заново собрать образ и запустить
docker-compose build app && docker-compose up -d app

# Войти в контейнер для отладки
docker-compose exec app bash

# Проверить ошибки при стартапе
docker-compose logs --tail=50 app | grep -E "ERROR|CRITICAL|Traceback"
```

## Заключение

Для проверки выполнения LLM tools:

1. Запустить: `docker-compose up app`
2. Посмотреть логи: `docker-compose logs -f app`
3. Отправить curl запрос с tool call'ом
4. Найти последовательность логов: available_tools → processing_tool_calls → executing → completed → processed
5. Проверить ответ: `tools_used: >= 1`

Если видишь все эти события в логах - **tools работают!** ✓
