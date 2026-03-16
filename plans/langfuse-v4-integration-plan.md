# План интеграции Langfuse v4 SDK (версия сервера 3.158.0)

## Обзор

Интеграция Langfuse v4 SDK в codelab-core-service для полного трекинга мультиагентной логики, включая:
- Автоматический трекинг всех вызовов OpenAI
- Иерархия трассировки с именованными агентами и инструментами
- Сбор метаданных (user_id, project_id)
- Отладка в режиме разработки

---

## Архитектура интеграции

### Уровень 1: Конфигурация

#### 1.1 Добавить Langfuse параметры в `app/config.py`

```python
# Langfuse Configuration
langfuse_enabled: bool = Field(default=True)
langfuse_public_key: str | None = Field(default=None)
langfuse_secret_key: str | None = Field(default=None)
langfuse_host: str = Field(default="http://localhost:3000")
langfuse_debug: bool = Field(default=False)  # True в разработке
```

#### 1.2 Обновить `.env.example`

```env
# =============================================================================
# LANGFUSE CONFIGURATION (Observability)
# =============================================================================
LANGFUSE_ENABLED=true
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=https://your-langfuse-server:3000
LANGFUSE_DEBUG=false  # true для разработки
```

#### 1.3 Обновить `pyproject.toml`

Добавить в зависимости:
```toml
"langfuse>=2.0.0",
```

---

### Уровень 2: Сервис инициализации

#### 2.1 Создать `app/services/langfuse_client.py`

Включить:
- Инициализацию Langfuse клиента
- Функцию `observe_openai(client)` для оборачивания OpenAI
- Функции для управления контекстом трассировки
- Функцию `flush()` для явной отправки данных

```python
from langfuse import Langfuse
from langfuse import observe
from app.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)

class LangfuseClient:
    def __init__(self):
        if not settings.langfuse_enabled:
            self.client = None
            return
        
        self.client = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
            debug=settings.langfuse_debug,
        )
        logger.info("langfuse_client_initialized", host=settings.langfuse_host)
  
    def set_trace_metadata(self, user_id: UUID, project_id: UUID, tags: list[str] | None = None):
        if settings.langfuse_enabled:
            metadata = {
                "user_id": str(user_id),
                "project_id": str(project_id),
            }
            if tags:
                metadata["tags"] = tags
            langfuse_context.update_current_trace(**metadata)
    
    def flush(self):
        if self.client:
            self.client.flush()
```

---

### Уровень 3: Интеграция в приложение

#### 3.1 Обновить `app/main.py`

В функции `lifespan()`:

**Startup:**
```python
# Инициализировать Langfuse
langfuse_client = LangfuseClient()
app.state.langfuse_client = langfuse_client
logger.info("langfuse_client_initialized")
```

**Shutdown:**
```python
# Graceful shutdown of Langfuse (flush remaining traces)
if hasattr(app.state, 'langfuse_client'):
    app.state.langfuse_client.flush()
    logger.info("langfuse_flushed")
```

---

### Уровень 4: Трекинг бизнес-логики

#### 4.1 `app/routes/project_chat.py`

Оберните основной endpoint для чата в декоратор:

```python
from langfuse import observe, langfuse_context
from app.services.langfuse_client import LangfuseClient

@router.post("/sessions/{session_id}/messages")
@observe(name="ChatMessage")
async def send_message(
    project_id: UUID,
    session_id: UUID,
    request: Request,
    message: MessageRequest,
    db: AsyncSession = Depends(get_db),
    # ... остальные зависимости
) -> MessageResponse:
    user_id = get_current_user_id(request)
    
    # Добавить метаданные трассировки
    langfuse_context.update_current_trace(
        user_id=str(user_id),
        project_id=str(project_id),
    )
    
    # Ваша логика здесь
```

#### 4.2 `app/agents/contextual_agent.py`

Добавить несколько `@observe` декораторов для разных методов:

```python
from langfuse import observe

class ContextualAgent:

    @observe(name="Planner")
    async def plan_steps(self, user_input: str) -> list[str]:
        """Планирование шагов - как в примере Langfuse"""
        # Логика планирования
        pass
    
    @observe(name="RAGSearch")
    async def retrieve_context(self, query: str):
        """Поиск контекста через RAG"""
        # Логика поиска в векторной БД
        pass
    
    @observe(name="Executor")
    async def execute_step(self, step: str):
        """Выполнение шага"""
        # Логика выполнения
        pass
    
    async def chat(self, user_input: str):
        """Основной метод чата"""
        # Вызовет вложенные операции, которые будут автоматически трейсены
        steps = await self.plan_steps(user_input)
        
        for step in steps:
            context = await self.retrieve_context(step)
            result = await self.execute_step(step)
```

#### 4.3 `app/core/tools/executor.py`

Оберните основной метод выполнения инструмента:

```python
from langfuse import observe

class ToolExecutor:
    @observe(as_type="tool", name="ExecuteTool")
    async def execute_tool(
        self,
        tool_name: str,
        tool_params: dict,
        session_id: Optional[UUID] = None,
    ) -> ToolExecutionResponse:
        """Execute tool with full validation and approval workflow"""
        # Существующая логика
        pass
    
    @observe(as_type="tool", name="ValidateTool")
    async def _validate_tool_params(self, tool_name: str, tool_params: dict):
        """Validate tool parameters"""
        pass
    
    @observe(as_type="tool", name="AssessTool")
    async def _assess_tool_risk(self, tool_name: str, tool_params: dict):
        """Assess tool execution risk"""
        pass
```

---

### Уровень 5: Поток данных

```
User Request
    ↓
@observe(name="ChatMessage") in project_chat.py
    ↓ langfuse_context.update_current_trace(user_id, project_id)
    ↓
ContextualAgent.chat()
    ├─ @observe(name="Planner")
    │  └─ OpenAI call (автоматически трейсен через observe_openai)
    ├─ @observe(name="RAGSearch")
    │  └─ Qdrant search
    └─ @observe(name="Executor")
       ├─ ToolExecutor.execute_tool()
       │  ├─ @observe(as_type="tool", name="ValidateTool")
       │  ├─ @observe(as_type="tool", name="AssessTool")
       │  └─ OpenAI call (если нужно, например, для парсинга)
       └─ ToolExecution.create(...)
    ↓
Result
    ↓
Langfuse Server (автоматическая отправка в фоне)
    ↓
Интерфейс Langfuse: иерархия трас, метрики, логи
```

---

## Параметры конфигурации

### Переменные окружения

| Переменная | Тип | По умолчанию | Описание |
|---|---|---|---|
| LANGFUSE_ENABLED | bool | true | Включить Langfuse интеграцию |
| LANGFUSE_PUBLIC_KEY | str | None | Публичный ключ Langfuse (обязателен) |
| LANGFUSE_SECRET_KEY | str | None | Секретный ключ Langfuse (обязателен) |
| LANGFUSE_HOST | str | http://localhost:3000 | URL сервера Langfuse |
| LANGFUSE_DEBUG | bool | false | Включить отладку (логирование всех запросов) |

### Примеры использования

#### Development (.env)
```env
LANGFUSE_ENABLED=true
LANGFUSE_PUBLIC_KEY=pk-lf-dev-key
LANGFUSE_SECRET_KEY=sk-lf-dev-secret
LANGFUSE_HOST=http://localhost:3000
LANGFUSE_DEBUG=true
```

#### Production (.env.production)
```env
LANGFUSE_ENABLED=true
LANGFUSE_PUBLIC_KEY=pk-lf-prod-key
LANGFUSE_SECRET_KEY=sk-lf-prod-secret
LANGFUSE_HOST=https://your-langfuse-server:3000
LANGFUSE_DEBUG=false
```

---

## Ожидаемые результаты в интерфейсе Langfuse

### 1. Trace Tree (Дерево трасс)

```
ChatMessage
├─ user_id: "customer_007"
├─ project_id: "proj_123"
└─ children:
   ├─ Planner
   │  └─ OpenAI API call (gpt-4o)
   ├─ RAGSearch
   │  └─ Qdrant vector search
   └─ Executor
      ├─ ExecuteTool (as_type="tool")
      │  ├─ ValidateTool
      │  ├─ AssessTool
      │  └─ OpenAI API call (если есть)
      └─ ToolExecution record
```

### 2. Metrics

- **Cost Tracking**: Суммарная стоимость всех OpenAI вызовов
- **Latency**: Время каждого компонента (Planner, RAGSearch, Executor)
- **Token Count**: Количество токенов в каждом вызове
- **Error Rate**: Процент ошибок по компоненту

### 3. Поиск и фильтрация

Можно искать по:
- `user_id`
- `project_id`
- Имени операции (ChatMessage, Planner, ExecuteTool)
- Типу операции (Generation, Span, Tool)

---

## Отладка

### Включить debug mode

Если данные не появляются в интерфейсе:

```python
# В app/config.py
langfuse_debug: bool = Field(default=True)

# В консоли вы увидите:
# [Langfuse] Sending trace...
# [Langfuse] Trace sent successfully
```

### Проверить инициализацию

```bash
# В логах приложения должно быть:
# 2026-03-16T10:52:00 [INFO] langfuse_client_initialized host=http://localhost:3000
```

### Проверить отправку при завершении

```bash
# При останове приложения:
# 2026-03-16T10:53:00 [INFO] langfuse_flushed
```

---

## Зависимости и совместимость

- **Langfuse SDK**: v4.x (>=2.0.0)
- **Python**: >=3.12 (совместимо с проектом)
- **OpenAI SDK**: >=1.50.0 (уже в проекте)
- **Сервер Langfuse**: v3.158.0+

---

## Миграция (если была предыдущая версия)

Поскольку в проекте были найдены файлы вроде `LANGFUSE_OPENTELEMETRY_REMOVAL_*`, предполагается что была удалена интеграция OpenTelemetry. Эта интеграция Langfuse v4 более легковесна и не требует OpenTelemetry.

---

## Следующие шаги

1. ✅ Создать `app/services/langfuse_client.py`
2. ✅ Обновить `app/config.py`
3. ✅ Обновить `.env.example`
4. ✅ Обновить `pyproject.toml`
5. ✅ Обновить `app/main.py`
6. ✅ Добавить декораторы в `app/agents/contextual_agent.py`
7. ✅ Добавить декораторы в `app/routes/project_chat.py`
8. ✅ Добавить декораторы в `app/core/tools/executor.py`
9. ✅ Протестировать базовый сценарий

