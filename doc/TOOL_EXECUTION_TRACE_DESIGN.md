# Архитектурный дизайн системы трассировки Tool Execution Flow с OpenTelemetry

## 1. Обзор и контекст

### 1.1 Проблема
Текущая система отслеживает выполнение инструментов (ToolExecution), но не имеет полной видимости всего flow от запроса пользователя до ответа агента, включая:
- Связь между пользовательским сообщением и вызовами инструментов
- Иерархия вложенных вызовов инструментов (distributed tracing)
- Состояние валидации, risk assessment, одобрения на каждом этапе
- Временные метрики для каждого этапа
- Связь между LLM обработкой и tool execution

### 1.2 Цели
1. **Full Tracing** - полная видимость flow от запроса до ответа
2. **Distributed Tracing** - иерархия с parent-child spans для вложенных вызовов
3. **Structured Logging** - структурированное логирование на каждом этапе
4. **Performance Monitoring** - метрики и latency для каждого компонента
5. **Minimal Overhead** - минимальное влияние на производительность
6. **Industry Standard** - использование OpenTelemetry (OTEL) - стандартной library
7. **Persistence & Analytics** - сохранение важных traces в БД для анализа

### 1.3 Сравнение подходов

| Параметр | OpenTelemetry Only | Гибридный (OTEL + DB) | Minimal MVP |
|----------|-------------------|----------------------|------------|
| **Реализация** | 1-2 дня | 3-4 дня | 0.5 дня |
| **Dependencies** | otel + jaeger | + sqlalchemy | logging |
| **Real-time UI** | Jaeger ✅ | Jaeger + REST API ✅ | нет ❌ |
| **Persistence** | Jaeger only (временно) | PostgreSQL ✅ | нет |
| **REST API** | нет | да ✅ | нет |
| **Исторические данные** | нет | да ✅ | нет |
| **Production Ready** | нет | да ✅ | нет |
| **Масштабируемость** | до 1K spans/sec | до 10K spans/sec | ❌ |

### 1.4 Рекомендация для первой фазы

**Рекомендуем: OpenTelemetry Only (Phase 1) + планируемое расширение на Phase 2**

**Обоснование:**
- ✅ Быстрое внедрение без блокирования других работ
- ✅ Стандартный инструмент (легче найти разработчиков)
- ✅ Полная видимость в Jaeger UI для отладки
- ✅ Zero ломающих изменений в коде
- ✅ Архитектура позволяет добавить DB persistence позже
- ⏳ Phase 2: добавить DB tables + REST API для аналитики

**Для Phase 1 достаточно:**
- Инициализация OpenTelemetry с JaegerExporter
- Добавить spans в contextual_agent.py и executor.py
- Запустить Jaeger контейнер локально
- Документация по использованию Jaeger UI

---

## 2. Architecture Flow с OpenTelemetry

### 2.1 High-level Flow

```
User sends message
    ↓
[SPAN: message_processing]
  ├─ [EVENT: message_received]
  │
  ├─ [SPAN: agent_execution]
  │  ├─ [SPAN: llm_call]
  │  │  ├─ [ATTRIBUTE: model=gpt-4]
  │  │  ├─ [ATTRIBUTE: tokens=1250]
  │  │  └─ [EVENT: llm_response_received]
  │  │
  │  └─ [SPAN: tool_execution] (for each tool call)
  │     ├─ [SPAN: tool_validation]
  │     │  └─ [EVENT: validation_passed/failed]
  │     │
  │     ├─ [SPAN: risk_assessment]
  │     │  └─ [ATTRIBUTE: risk_level=medium]
  │     │
  │     ├─ [SPAN: approval_workflow]
  │     │  └─ [EVENT: approval_requested/approved/rejected]
  │     │
  │     └─ [SPAN: tool_execution_on_client]
  │        ├─ [ATTRIBUTE: tool_name=read_file]
  │        ├─ [ATTRIBUTE: duration_ms=250]
  │        └─ [EVENT: execution_completed]
  │
  └─ [EVENT: response_generated]
     └─ [ATTRIBUTE: final_status=success]
```

### 2.2 Key Components

```
┌──────────────────────────────────────┐
│     OpenTelemetry Setup              │
├──────────────────────────────────────┤
│                                      │
│  ┌─ TracerProvider (global)          │
│  │  └─ ServiceName: codelab-core    │
│  │                                   │
│  ├─ Tracer (per module)              │
│  │  ├─ app.agents.contextual_agent  │
│  │  ├─ app.core.tools.executor      │
│  │  ├─ app.routes.project_chat      │
│  │  └─ app.core.tools.validator     │
│  │                                   │
│  └─ SpanExporter                     │
│     └─ JaegerExporter (local dev)   │
│        (+ OTLPExporter на Phase 2)   │
│                                      │
└──────────────────────────────────────┘
```

---

## 3. OpenTelemetry Setup (Phase 1)

### 3.1 Инициализация и конфигурация

```python
# app/tracing.py

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

from app.config import settings

def initialize_tracing():
    """Initialize OpenTelemetry tracing infrastructure."""
    
    if not settings.enable_tracing:
        return
    
    # Resource описывает сервис
    resource = Resource.create({
        SERVICE_NAME: "codelab-core-service",
        "environment": settings.environment,
        "version": settings.app_version,
    })
    
    # JaegerExporter для локальной разработки
    jaeger_exporter = JaegerExporter(
        agent_host_name=settings.jaeger_host,  # "localhost"
        agent_port=settings.jaeger_port,  # 6831
    )
    
    # TracerProvider - глобальный провайдер для всех трейсов
    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(BatchSpanProcessor(jaeger_exporter))
    
    # Установить как global
    trace.set_tracer_provider(tracer_provider)
    
    # Автоматическое инструментирование
    FastAPIInstrumentor.instrument_app(app)
    SQLAlchemyInstrumentor().instrument()
    
    print(f"✅ OpenTelemetry initialized (Jaeger: {settings.jaeger_host}:{settings.jaeger_port})")

def get_tracer(module_name: str) -> trace.Tracer:
    """Get tracer for a specific module."""
    return trace.get_tracer(module_name)
```

### 3.2 Инициализация в main.py

```python
# app/main.py

from fastapi import FastAPI
from app.tracing import initialize_tracing

app = FastAPI()

# Initialize tracing before starting app
initialize_tracing()

# ... rest of the app setup
```

### 3.3 Использование в коде (contextual_agent.py)

```python
# app/agents/contextual_agent.py

from opentelemetry import trace
from app.tracing import get_tracer

tracer = get_tracer(__name__)

async def execute(
    self,
    user_message: str,
    session_history: list[dict[str, str]] | None = None,
    task_id: str | None = None,
):
    """Execute agent with tracing."""
    
    with tracer.start_as_current_span("agent_execution") as span:
        span.set_attribute("agent.id", str(self.agent_id))
        span.set_attribute("agent.name", self.agent_name)
        span.set_attribute("model", self.config.model)
        
        try:
            # ====== LLM Call ======
            with tracer.start_as_current_span("llm_call") as llm_span:
                llm_span.set_attribute("model", self.config.model)
                llm_span.set_attribute("temperature", self.config.temperature)
                llm_span.set_attribute("provider", "openai")
                
                start_time = time.time()
                
                response = await self.openai_client.chat.completions.create(
                    model=self.config.model,
                    messages=messages,
                    temperature=self.config.temperature,
                    max_tokens=self.config.max_tokens,
                )
                
                latency_ms = int((time.time() - start_time) * 1000)
                llm_span.set_attribute("latency_ms", latency_ms)
                llm_span.set_attribute("tokens_prompt", response.usage.prompt_tokens)
                llm_span.set_attribute("tokens_completion", response.usage.completion_tokens)
                llm_span.set_attribute("tokens_total", response.usage.total_tokens)
                
                llm_span.add_event("llm_response_received", {
                    "model": self.config.model,
                    "tokens": response.usage.total_tokens,
                })
                
                assistant_message = response.choices[0].message.content or ""
            
            # Check for tool calls
            tool_calls = response.choices[0].message.tool_calls
            
            if tool_calls:
                span.add_event("tool_calls_detected", {"count": len(tool_calls)})
                
                # ====== Tool Execution ======
                for tool_call in tool_calls:
                    with tracer.start_as_current_span("tool_execution") as tool_span:
                        tool_name = tool_call.function.name
                        tool_span.set_attribute("tool.name", tool_name)
                        
                        # Валидация
                        with tracer.start_as_current_span("tool_validation") as val_span:
                            is_valid, error = await self.tool_executor._validate_tool_params(
                                tool_name, tool_params
                            )
                            val_span.set_attribute("validation_status", "passed" if is_valid else "failed")
                            if error:
                                val_span.add_event("validation_error", {"error": error})
                        
                        if not is_valid:
                            tool_span.set_attribute("status", "failed")
                            continue
                        
                        # Risk Assessment
                        with tracer.start_as_current_span("risk_assessment") as risk_span:
                            risk_level = self.tool_executor.risk_assessor.assess_tool_risk(
                                tool_name, tool_params
                            )
                            risk_span.set_attribute("risk_level", risk_level.value)
                        
                        # Execute tool
                        try:
                            result = await self.tool_executor.execute_tool(
                                tool_name=tool_name,
                                tool_params=tool_params,
                                session_id=session_id,
                            )
                            tool_span.set_attribute("execution_status", result.get("status", "unknown"))
                            
                            span.add_event("tool_executed", {
                                "tool_name": tool_name,
                                "status": result.get("status", "unknown"),
                            })
                        except Exception as e:
                            tool_span.record_exception(e)
                            tool_span.set_attribute("status", "error")
            
            # Finalize
            span.set_attribute("status", "success")
            span.add_event("response_generated", {
                "response_length": len(assistant_message),
            })
            
            return {
                "success": True,
                "response": assistant_message,
                "context_used": len(context_results),
                "tokens_used": total_tokens,
            }
            
        except Exception as e:
            span.record_exception(e)
            span.set_attribute("status", "error")
            raise
```

### 3.4 Трассировка в ToolExecutor

```python
# app/core/tools/executor.py

from opentelemetry import trace
from app.tracing import get_tracer

tracer = get_tracer(__name__)

async def execute_tool(
    self,
    tool_name: str,
    tool_params: dict,
    session_id: Optional[UUID] = None,
):
    """Execute tool with tracing."""
    
    with tracer.start_as_current_span("tool_execution") as span:
        span.set_attribute("tool.name", tool_name)
        
        tool_execution = None
        
        try:
            # ====== Validation ======
            with tracer.start_as_current_span("tool_validation") as val_span:
                is_valid, error = await self._validate_tool_params(tool_name, tool_params)
                val_span.set_attribute("validation_passed", is_valid)
                
                if not is_valid:
                    span.set_attribute("status", "validation_failed")
                    val_span.add_event("validation_failed", {"error": error})
                    return ToolExecutionResponse(
                        tool_id=str(tool_id),
                        tool_name=tool_name,
                        status="failed",
                        error=error,
                    )
            
            # ====== Risk Assessment ======
            with tracer.start_as_current_span("risk_assessment") as risk_span:
                risk_level = self.risk_assessor.assess_tool_risk(tool_name, tool_params)
                risk_span.set_attribute("risk_level", risk_level.value)
            
            # Create execution record
            execution = await self._create_tool_execution(...)
            span.set_attribute("execution_record_id", str(execution.id))
            
            # ====== Approval Workflow ======
            if await self.approval_manager.auto_approve_tool_if_low_risk(risk_level.value):
                span.add_event("auto_approved", {"risk_level": risk_level.value})
                execution.status = "approved"
            else:
                with tracer.start_as_current_span("approval_workflow") as approval_span:
                    approval = await self.approval_manager.request_tool_execution_approval(...)
                    approval_span.set_attribute("approval_id", str(approval.id))
                    
                    approved, reason = await self.approval_manager.wait_for_tool_approval(...)
                    
                    if approved:
                        approval_span.set_attribute("status", "approved")
                        execution.status = "approved"
                    else:
                        approval_span.set_attribute("status", "rejected")
                        execution.status = "rejected"
                        execution.error = f"Rejected: {reason}"
                        span.set_attribute("status", "rejected")
                        return ToolExecutionResponse(...)
            
            await self.db.flush()
            
            # ====== Send to Client ======
            with tracer.start_as_current_span("client_execution") as client_span:
                await self._send_tool_execution_request(...)
                client_span.set_attribute("request_sent", True)
            
            span.set_attribute("status", "pending")
            return ToolExecutionResponse(...)
            
        except Exception as e:
            span.record_exception(e)
            span.set_attribute("status", "error")
            if execution:
                execution.status = "failed"
                execution.error = str(e)
            raise
```

### 3.5 Трассировка в project_chat.py

```python
# app/routes/project_chat.py

from opentelemetry import trace
from app.tracing import get_tracer

tracer = get_tracer(__name__)

@router.post("/{session_id}/message/")
async def send_project_message(
    project_id: UUID,
    session_id: UUID,
    message_data: MessageCreate,
    ...
):
    """Send message with full tracing."""
    
    with tracer.start_as_current_span("message_processing") as span:
        span.set_attribute("message.type", "user_message")
        span.set_attribute("session.id", str(session_id))
        span.set_attribute("user.id", str(user_id))
        span.set_attribute("project.id", str(project_id))
        
        span.add_event("message_received", {
            "content_length": len(message_data.content)
        })
        
        try:
            # Create message in DB
            message = Message(
                session_id=session_id,
                role="user",
                content=message_data.content,
            )
            db.add(message)
            await db.flush()
            
            # Get agent for this session
            agent = await get_agent_for_session(db, session_id)
            
            # Execute agent with tracing
            response = await agent.execute(
                user_message=message_data.content,
                session_history=session_history,
                task_id=task_id,
            )
            
            # Store response
            assistant_message = Message(
                session_id=session_id,
                role="assistant",
                content=response,
                agent_id=agent.id,
            )
            db.add(assistant_message)
            await db.commit()
            
            span.set_attribute("response.length", len(response))
            span.set_attribute("status", "success")
            
            return {
                "message_id": str(assistant_message.id),
                "content": response,
            }
            
        except Exception as e:
            span.record_exception(e)
            span.set_attribute("status", "error")
            raise
```

---

## 4. Docker Compose для Jaeger (локальная разработка)

```yaml
# docker-compose-dev.yml

services:
  jaeger:
    image: jaegertracing/all-in-one:latest
    ports:
      - "16686:16686"  # Jaeger UI (http://localhost:16686)
      - "6831:6831/udp"  # Jaeger agent (thrift compact)
    environment:
      COLLECTOR_ZIPKIN_HOST_PORT: ":9411"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:16686/api/services"]
      interval: 30s
      timeout: 10s
      retries: 3
    networks:
      - codelab

networks:
  codelab:
    driver: bridge
```

### Запуск:
```bash
docker-compose -f docker-compose-dev.yml up -d jaeger

# Проверить Jaeger UI
open http://localhost:16686
```

---

## 5. Конфигурация

```python
# app/config.py

from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # === Existing settings ===
    environment: str = "development"
    app_version: str = "0.3.0"
    
    # === New: OpenTelemetry ===
    enable_tracing: bool = True
    jaeger_host: str = "localhost"
    jaeger_port: int = 6831
    
    # Optional (Phase 2)
    enable_trace_db_persistence: bool = False
    trace_retention_days: int = 30
    
    class Config:
        env_file = ".env"
```

```env
# .env

ENABLE_TRACING=true
JAEGER_HOST=localhost
JAEGER_PORT=6831

# Phase 2:
# ENABLE_TRACE_DB_PERSISTENCE=true
```

---

## 6. Использование Jaeger UI

### 6.1 Поиск трейсов

1. Перейти на http://localhost:16686
2. **Service**: выбрать `codelab-core-service`
3. **Operation**: выбрать операцию:
   - `message_processing` - полное сообщение пользователя
   - `agent_execution` - выполнение агента
   - `tool_execution` - выполнение инструмента
   - `llm_call` - вызов LLM

### 6.2 Фильтрация по тегам

```
Status: error
Tool: read_file
Risk level: high
Model: gpt-4
```

### 6.3 Примеры queries

**Все неудачные tool executions за час:**
```
Operation: tool_execution
Tags: status=error
```

**Все LLM calls модели gpt-4 с latency > 2000ms:**
```
Operation: llm_call
Tags: model=gpt-4, latency_ms>2000
```

**Все high-risk инструменты:**
```
Operation: tool_execution
Tags: risk_level=high
```

---

## 7. Примеры использования

### 7.1 Простой span с атрибутами

```python
from app.tracing import get_tracer

tracer = get_tracer(__name__)

def process_file(file_path: str):
    with tracer.start_as_current_span("process_file") as span:
        span.set_attribute("file.path", file_path)
        span.set_attribute("file.size", os.path.getsize(file_path))
        
        # ... processing ...
        
        span.set_attribute("status", "success")
```

### 7.2 Вложенные spans

```python
with tracer.start_as_current_span("parent_operation") as parent_span:
    parent_span.set_attribute("operation.type", "batch_processing")
    
    for item in items:
        with tracer.start_as_current_span("process_item") as child_span:
            child_span.set_attribute("item.id", item.id)
            # child_span automatically имеет parent_span как parent
            
            # ... processing ...
```

### 7.3 События (events)

```python
with tracer.start_as_current_span("api_call") as span:
    span.add_event("request_sent", {"url": "https://api.example.com"})
    
    # ... network call ...
    
    span.add_event("response_received", {
        "status_code": 200,
        "response_size": 1024
    })
```

### 7.4 Обработка исключений

```python
with tracer.start_as_current_span("risky_operation") as span:
    try:
        # ... risky code ...
    except Exception as e:
        span.record_exception(e)
        span.set_attribute("status", "error")
        raise
```

---

## 8. Requirements для Phase 1

```
# pyproject.toml или requirements.txt

opentelemetry-api==1.21.0
opentelemetry-sdk==1.21.0
opentelemetry-exporter-jaeger==1.21.0
opentelemetry-instrumentation-fastapi==0.42b0
opentelemetry-instrumentation-sqlalchemy==0.42b0
opentelemetry-instrumentation==0.42b0
```

---

## 9. Migration Path к Phase 2

Когда будет нужна персистентность и аналитика:

1. **Добавить DB tables** (ExecutionTrace, ToolExecutionTrace, LLMCallTrace)
2. **Реализовать TraceDBExporter** для сохранения spans в PostgreSQL
3. **Создать REST API endpoints** для аналитики
4. **Включить OTLP для Production** (Tempo, DataDog)

**Текущая архитектура позволяет легко добавить Phase 2 без изменения Phase 1 кода.**

---

## 10. Контрольный список для внедрения Phase 1

- [ ] Добавить dependencies в pyproject.toml
- [ ] Создать `app/tracing.py` с инициализацией OpenTelemetry
- [ ] Обновить `app/main.py` - вызвать `initialize_tracing()`
- [ ] Добавить `app/config.py` параметры для Jaeger
- [ ] Обновить `.env` с параметрами Jaeger
- [ ] Добавить spans в `app/agents/contextual_agent.py`
- [ ] Добавить spans в `app/core/tools/executor.py`
- [ ] Добавить spans в `app/routes/project_chat.py`
- [ ] Запустить `docker-compose -f docker-compose-dev.yml up -d jaeger`
- [ ] Протестировать Jaeger UI: http://localhost:16686
- [ ] Документировать использование в README

---

## Заключение

**Phase 1 (OpenTelemetry Only):**
- ✅ Быстро внедрить (1-2 дня)
- ✅ Zero breaking changes
- ✅ Полная видимость в Jaeger UI
- ✅ Стандартный инструмент индустрии
- ✅ Foundation для Phase 2

**Phase 2 (DB Persistence):**
- планируется добавить позже
- DB таблицы для долгосрочного хранения
- REST API для аналитики
- Production-ready с OTLP
