# Интеграция Langfuse v4 SDK - Сводка реализации

## ✅ Завершено: Полная интеграция Langfuse v4 (сервер 3.158.0)

Дата: 16 марта 2026 г.

---

## Реализованные компоненты

### 1. **Конфигурация** ✅

#### `pyproject.toml`
- ✅ Добавлена зависимость `langfuse>=4.0.0`

#### `app/config.py`
- ✅ `langfuse_enabled` (bool): включение/отключение интеграции
- ✅ `langfuse_public_key` (str): публичный ключ Langfuse
- ✅ `langfuse_secret_key` (str): секретный ключ Langfuse
- ✅ `langfuse_host` (str): URL сервера Langfuse (default: http://localhost:3000)
- ✅ `langfuse_debug` (bool): включение отладки (default: False)

#### `.env.example`
- ✅ Добавлены переменные окружения:
  - `LANGFUSE_ENABLED=true`
  - `LANGFUSE_PUBLIC_KEY=pk_lf_...`
  - `LANGFUSE_SECRET_KEY=sk_lf_...`
  - `LANGFUSE_HOST=http://langfuse-web:3000`
  - `LANGFUSE_DEBUG=false`

### 2. **Сервис инициализации** ✅

#### `app/services/langfuse_client.py` (новый файл)

Включает:

```python
class LangfuseClient:
    """Manages Langfuse SDK initialization and tracing context."""
    
    def __init__(self) -> None:
        """Initialize Langfuse client based on settings."""
        # Инициализирует Langfuse если включен и конфиг полный

    def set_trace_metadata(
        self,
        user_id: UUID,
        project_id: UUID,
        tags: Optional[list[str]] = None,
    ) -> None:
        """Update current trace with metadata."""
        # Добавляет user_id, project_id и теги к текущей трассе
    
    def flush(self) -> None:
        """Flush all pending traces to Langfuse server."""
        # Отправляет оставшиеся трассы

def get_langfuse_client() -> LangfuseClient:
    """Get or create the global Langfuse client instance."""
    # Singleton для глобального доступа к клиенту
```

### 3. **Интеграция в приложение** ✅

#### `app/main.py`

**Startup:**
```python
# Инициализация Langfuse клиента
langfuse_client = get_langfuse_client()
app.state.langfuse_client = langfuse_client
```

**Shutdown:**
```python
# Flush оставшихся трас перед завершением
langfuse_client.flush()
```

### 4. **Трекинг бизнес-логики** ✅

#### `app/agents/contextual_agent.py`

```python
# Импорты
from langfuse import observe

# Декоратор на основной метод
@observe(name="Executor")
async def execute(self, user_message: str, ...):
    """Execute agent with context retrieval."""
    # Метод будет трейсен как операция "Executor"
    # OpenAI вызовы будут автоматически трейсены через observe_openai()
```

#### `app/routes/project_chat.py`

```python
# Импорты
from langfuse import observe, langfuse_context

# На endpoint отправки сообщения
@router.post("/{session_id}/message/")
@observe(name="ChatMessage")
async def send_project_message(...):
    """Send message to chat session in project."""
    user_id = get_current_user_id(request)
    
    # Добавить метаданные трассировки
    langfuse_context.update_current_trace(
        user_id=str(user_id),
        project_id=str(project_id),
    )
    # Остальная логика...
```

#### `app/core/tools/executor.py`

```python
# Импорты
from langfuse import observe

# На основной метод выполнения инструмента
@observe(as_type="tool", name="ExecuteTool")
async def execute_tool(self, tool_name: str, tool_params: dict, ...):
    """Execute tool with full validation and approval workflow."""
    # Метод будет трейсен как инструмент (tool)

# На метод валидации
@observe(as_type="tool", name="ValidateTool")
async def _validate_tool_params(self, tool_name: str, params: dict, ...):
    """Validate tool parameters."""
    # Трейсинг валидации инструмента
```

---

## Архитектура трассировки

### Поток данных

```
HTTP Request
    ↓
@observe(name="ChatMessage") [project_chat.py]
├─ langfuse_context.update_current_trace(user_id, project_id)
│  └─ Теги: ["v0.2.0"]
├─ Запуск workspace.handle_message()
│
└─ ContextualAgent.execute()
   ├─ @observe(name="Executor") [contextual_agent.py]
   ├─ OpenAI вызов (автоматически трейсен через observe_openai)
   │  └─ Model: gpt-4, tokens, cost
   ├─ Qdrant поиск контекста (RAG)
   │
   └─ ToolExecutor.execute_tool()
      ├─ @observe(as_type="tool", name="ExecuteTool")
      ├─ @observe(as_type="tool", name="ValidateTool")
      │  └─ Валидация параметров
      └─ OpenAI вызов для обработки результата
         └─ Model, tokens, cost

    ↓
Langfuse Server (фоновая отправка)

    ↓
Интерфейс Langfuse (3.158.0):
├─ Trace Tree: иерархия вызовов
├─ Cost Tracking: суммарная стоимость
├─ Latency: время каждой операции
├─ Input/Output: полные логи
└─ Metadata Filter: поиск по user_id, project_id
```

---

## Ключевые особенности

### Автоматический трекинг OpenAI

```python
# Все вызовы OpenAI автоматически трейсены
observe_openai(openai_client)

# После этого каждый вызов:
response = await openai_client.chat.completions.create(...)
# → автоматически становится span в Langfuse с:
#   - моделью (gpt-4, gpt-3.5, и т.д.)
#   - количеством токенов
#   - стоимостью вызова
```

### Иерархия трас

```
ChatMessage (корневая спан)
├─ user_id: "uuid..."
├─ project_id: "uuid..."
├─ tags: ["v0.2.0"]
└─ children:
   ├─ Executor (ContextualAgent.execute)
   │  ├─ OpenAI Generation (chat.completions.create)
   │  │  └─ model: gpt-4
   │  │     tokens: 150
   │  │     cost: $0.003
   │  └─ RAG Search
   │
   └─ ExecuteTool (tool execution)
      ├─ ValidateTool
      │  └─ result: valid
      └─ OpenAI Generation (if needed)
```

### Отладка

**Development (.env):**
```env
LANGFUSE_DEBUG=true
# В консоли будет видно:
# [Langfuse] Sending trace...
# [Langfuse] Trace sent successfully
```

**Production (.env.production):**
```env
LANGFUSE_DEBUG=false
# Тихая отправка в фоне без логов
```

---

## Переменные окружения

### Обязательные

- `LANGFUSE_ENABLED`: `true/false` (default: true)
- `LANGFUSE_PUBLIC_KEY`: ключ от Langfuse (если ENABLED)
- `LANGFUSE_SECRET_KEY`: секретный ключ (если ENABLED)

### Опциональные

- `LANGFUSE_HOST`: URL сервера (default: http://localhost:3000)
- `LANGFUSE_DEBUG`: логирование запросов (default: false)

---

## Проверка интеграции

### 1. Логи приложения

При запуске должны увидеть:
```
[INFO] langfuse_client_initialized host=http://localhost:3000 debug=false
[INFO] openai_client_wrapped_with_langfuse
```

При завершении:
```
[INFO] langfuse_traces_flushed
```

### 2. В интерфейсе Langfuse

После отправки сообщения в чат:
1. Откройте интерфейс Langfuse (http://localhost:3001)
2. Перейдите в Traces
3. Найдите трассу с именем "ChatMessage"
4. Проверьте иерархию с "Executor" и "OpenAI" вызовами

### 3. Метрики

В каждой трассе должны быть:
- **Input/Output**: сообщения пользователя и ответы
- **Metadata**: user_id, project_id, tags
- **Timing**: длительность каждой операции
- **Tokens**: количество токенов для OpenAI вызовов
- **Cost**: стоимость вызовов

---

## Следующие шаги

### Опционально: Расширенный трекинг

1. **RAG операции** - добавить `@observe(name="RAGSearch")` на методы поиска контекста
2. **Более детальные операции** - трейсить отдельные шаги обработки
3. **Кастомные метрики** - добавить дополнительные данные в traces

### Мониторинг в production

1. **Экспорт трас** - убедитесь, что Langfuse может отправлять трассы на ваш сервер 3.158.0
2. **Настройка фильтров** - создайте фильтры по user_id и project_id в Langfuse UI
3. **Alerting** - настройте alert если cost или latency превышают пороги

### Интеграция с другими компонентами

- Добавить трекинг для других асинхронных операций (если есть)
- Интегрировать с системой логирования для корреляции трас

---

## Файлы, которые были изменены

1. `pyproject.toml` - добавлена зависимость
2. `app/config.py` - добавлены параметры конфигурации
3. `.env.example` - добавлены переменные окружения
4. `app/main.py` - инициализация и shutdown
5. `app/services/langfuse_client.py` - **новый файл**
6. `app/agents/contextual_agent.py` - оборачивание OpenAI и декоратор
7. `app/routes/project_chat.py` - декоратор и метаданные
8. `app/core/tools/executor.py` - декораторы на методы

---

## Версии

- **Langfuse SDK**: v4.x (>=4.0.0)
- **Langfuse Server**: v3.158.0+
- **Python**: >=3.12
- **OpenAI SDK**: >=1.50.0

---

## Документация

- 📚 [Langfuse v4 SDK Documentation](https://langfuse.com/docs)
- 📚 [План интеграции](./langfuse-v4-integration-plan.md)
- 📊 [API Reference](https://api.langfuse.com)

