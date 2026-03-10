# Оценка интеграции Langfuse в codelab-core-service

## Executive Summary

Langfuse — это комплексная платформа для LLM observability с фокусом на отслеживание цепочек LLM запросов (chains), промптов, токенов и стоимости. 

### Ключевые выводы:

1. **Критическая необходимость**: Текущая система observability (OpenTelemetry, structured logging) не охватывает LLM-специфичные метрики (промпты, токены, стоимость, latency)

2. **Рекомендуемое решение**: Гибридная интеграция Langfuse (self-hosted) через LiteLLM callbacks с обогащением метаданных

3. **Преимущества**:
   - Полная видимость LLM операций (промпты, ответы, токены)
   - Отслеживание стоимости в реальном времени
   - Анализ производительности и отладка
   - Полный контроль над данными (self-hosted)

4. **Инвестиция**: 
   - Реализация: ~4-5 недель (с 3-фазным подходом)
   - Поддержка инфраструктуры: ~4-8 часов/месяц
   - Стоимость: ~$200-500/месяц (self-hosted на AWS)

5. **Минимальный MVP**: 2 недели (базовое логирование LLM вызовов через LiteLLM callbacks)

---

## 1. Текущее состояние системы observability

### 1.1 Компоненты observability

#### OpenTelemetry (Jaeger)
```
Статус: Активно используется
Файл: app/tracing.py
Экспортер: OTLPSpanExporter → Jaeger
Автоинструментация: FastAPI
```

**Возможности**:
- HTTP request/response трейсинг
- Service latency tracking
- Distributed tracing (если настроено)

**Ограничения**:
- Не трейсит LLM-специфичные операции
- Нет информации о промптах/ответах
- Нет отслеживания стоимости

#### Structured Logging (structlog)
```
Статус: Активно используется
Уровень: Service-wide
Формат: JSON (в production)
```

**Возможности**:
- Структурированное логирование с метаконтекстом
- User/workspace isolation tracking
- Request/session ID propagation

**Ограничения**:
- LLM операции логируются как текст (нет структурированных полей)
- Невозможно агрегировать метрики по промптам/моделям

#### LLMProviderAuditService
```
Статус: Реализовано
Файл: app/services/llm_provider_audit_service.py
Область: Provider management events
```

**Логируемые события**:
- `create` — создание провайдера
- `update` — изменение конфигурации
- `delete` — удаление провайдера
- `test` — тестирование подключения
- `use` — использование провайдером
- `provider_reassigned` — переназначение

**Ограничения**:
- Не трейсит сами LLM запросы
- Не содержит информацию о промптах/токенах
- Не отслеживает стоимость вызовов

### 1.2 Архитектура текущей observability

```mermaid
graph TB
    subgraph "Application Layer"
        FastAPI["FastAPI App"]
        LLMClient["LiteLLM Client"]
        AuditSvc["LLMProviderAuditService"]
    end
    
    subgraph "Observability Stack"
        Logger["structlog Logger"]
        OTel["OpenTelemetry Tracer"]
        AuditDB["PostgreSQL Audit Log"]
    end
    
    subgraph "External Systems"
        Jaeger["Jaeger UI"]
        Logs["Log Aggregation"]
    end
    
    FastAPI -->|auto-instrumented| OTel
    FastAPI -->|structured logging| Logger
    AuditSvc -->|SQL write| AuditDB
    
    OTel -->|OTLP export| Jaeger
    Logger -->|JSON logs| Logs
    AuditDB -->|query| Logs
    
    LLMClient -.->|no LLM tracing| OTel
```

### 1.3 Пробелы в observability

| Метрика | Текущее состояние | Необходимо |
|---------|-------------------|-----------|
| Request/Response tracing | ✅ (OpenTelemetry) | - |
| Service latency | ✅ | - |
| LLM prompt tracking | ❌ | ✅ Required |
| LLM completion tracking | ❌ | ✅ Required |
| Token counting | ❌ | ✅ Required |
| Cost tracking | ❌ | ✅ Required |
| Model usage analytics | ❌ | ✅ Required |
| Error debugging | ✅ (partial) | ✅ Enhanced |
| Performance analysis | ✅ (partial) | ✅ Enhanced |
| User behavior analytics | ❌ | ✅ Required |

---

## 2. Обзор Langfuse и его возможностей

### 2.1 Что такое Langfuse?

Langfuse — это **LLM-native observability платформа** для отслеживания, отладки и оптимизации LLM приложений.

**Основные компоненты**:

#### Tracing
```python
# Отслеживание цепочки LLM операций
from langfuse import Langfuse

langfuse = Langfuse()

with langfuse.trace(name="agent_interaction") as trace:
    # LLM вызов 1
    with trace.span(name="retrieve_context") as span:
        context = retrieve_documents(query)
        span.end()
    
    # LLM вызов 2
    with trace.span(name="generate_response") as span:
        response = llm.complete(prompt + context)
        span.update(
            output=response,
            tokens=count_tokens(response)
        )
        span.end()
```

**Возможности**:
- Иерархическое отслеживание операций
- Автоматический расчет latency
- Метаданные и tags
- Session/conversation tracking

#### Structured Logging
```python
langfuse.log(
    level="INFO",
    message="LLM request completed",
    metadata={
        "model": "gpt-4",
        "temperature": 0.7,
        "max_tokens": 2000,
        "user_id": user_id,
        "workspace_id": workspace_id
    }
)
```

#### Score/Feedback
```python
# Отслеживание качества ответов
trace.update(
    output="Generated response",
    scores={
        "relevance": 0.95,
        "accuracy": 0.88,
        "user_satisfaction": 1.0  # Если получен от пользователя
    }
)
```

#### Analytics & Reporting
- Dashboard с метриками
- Сравнение моделей и промптов
- Cost analysis
- Latency distribution
- Error rate tracking

### 2.2 LiteLLM + Langfuse интеграция

LiteLLM имеет встроенную поддержку Langfuse callbacks:

```yaml
# litellm_config.yaml
litellm_settings:
  success_callback: ["langfuse"]
  failure_callback: ["langfuse"]

environment_variables:
  LANGFUSE_PUBLIC_KEY: "pk-..."
  LANGFUSE_SECRET_KEY: "sk-..."
  LANGFUSE_HOST: "http://langfuse:3000"  # Self-hosted
```

**Автоматически захватывается**:
- Model name и version
- Prompt и completion
- Tokens (input + output)
- Latency
- Cost (основан на pricing)
- Errors и exceptions
- Custom metadata (если передано)

### 2.3 Типы observability в Langfuse

#### 1. Observation (базовая единица)
```
Observation = {
    name: string,
    type: "GENERATION" | "SPAN" | "EVENT",
    start_time: datetime,
    end_time: datetime,
    input: object,
    output: object,
    metadata: object,
    level: "DEBUG" | "DEFAULT" | "WARNING" | "ERROR"
}
```

#### 2. Trace (цепочка операций)
```
Trace = {
    trace_id: uuid,
    name: string,
    timestamp: datetime,
    observations: [Observation],
    metadata: object,
    tags: [string]
}
```

#### 3. Session (conversation)
```
Session = {
    session_id: uuid,
    user_id: string,
    traces: [Trace],
    created_at: datetime,
    updated_at: datetime
}
```

---

## 3. Преимущества интеграции

### 3.1 Полная видимость LLM операций

**Проблема**: Сейчас невозможно отследить, что именно было отправлено в LLM и что пришло обратно.

**Решение с Langfuse**:
```python
# app/services/langfuse_integration.py
from langfuse import Langfuse

langfuse = Langfuse(
    public_key=settings.langfuse_public_key,
    secret_key=settings.langfuse_secret_key,
    host=settings.langfuse_host  # Self-hosted
)

async def trace_llm_call(
    user_id: UUID,
    workspace_id: UUID,
    agent_name: str,
    prompt: str,
    model: str,
    response: str,
    tokens: dict
):
    with langfuse.trace(
        name=f"agent_{agent_name}",
        user_id=str(user_id),
        session_id=f"workspace_{workspace_id}",
        metadata={
            "agent": agent_name,
            "model": model,
            "workspace_id": str(workspace_id)
        }
    ) as trace:
        trace.span(
            name="llm_generation",
            input={"prompt": prompt},
            output={"completion": response},
            metadata={
                "input_tokens": tokens.get("prompt_tokens"),
                "output_tokens": tokens.get("completion_tokens"),
                "total_tokens": tokens.get("total_tokens"),
                "temperature": 0.7
            }
        )
```

**Результат**:
- ✅ Видимость каждого LLM запроса
- ✅ Полная история промптов и ответов
- ✅ Трассировка multi-step агента workflows
- ✅ Отладка failures в production

### 3.2 Отслеживание стоимости в реальном времени

**Проблема**: Нет понимания стоимости использования различных моделей.

**Решение**:
```python
# LiteLLM автоматически рассчитывает стоимость
# Langfuse агрегирует данные в dashboard

# В UI Langfuse:
# - Total cost: $1,234.56
# - Cost by model: {gpt-4: $800, claude-3: $434}
# - Cost by user: {user_1: $500, user_2: $734}
# - Cost trend: Daily/Weekly/Monthly
```

**Типичные цены (на 2026)**:
```
GPT-4 Turbo:     $0.03 / 1K input tokens, $0.06 / 1K output
Claude 3 Opus:   $0.015 / 1K input, $0.075 / 1K output
GPT-4o:          $0.005 / 1K input, $0.015 / 1K output
```

**Результат**:
- ✅ Budget tracking
- ✅ Cost optimization insights
- ✅ Per-user/workspace cost allocation
- ✅ Billing automation

### 3.3 Анализ производительности и отладка

**Проблема**: Невозможно понять, почему запрос к LLM был медленным или вернул неправильный результат.

**Решение**:
```python
# Langfuse предоставляет dashboard с:

# 1. Latency analysis
latencies = langfuse.get_traces(
    filters=[
        {"key": "metadata.agent", "value": "research_agent"}
    ]
).latencies
# Output: {p50: 2.3s, p75: 3.5s, p99: 8.2s}

# 2. Error tracking
errors = langfuse.get_traces(
    filters=[
        {"key": "status", "value": "error"}
    ]
)
for error in errors:
    print(f"Error: {error.error_message}")
    print(f"Input: {error.input}")
    print(f"Model: {error.metadata['model']}")

# 3. Quality scores
scores = langfuse.get_traces(
    filters=[
        {"key": "metadata.agent", "value": "qa_agent"}
    ]
).scores
# Output: {relevance: [0.92, 0.88, 0.95]}
```

**Результат**:
- ✅ Быстрая локализация проблем
- ✅ Понимание bottleneck'ов
- ✅ A/B тестирование промптов
- ✅ Performance optimization

### 3.4 Интеграция с существующей архитектурой

**Harmonious Integration**:
```
┌─────────────────────────────────────────┐
│  Existing Observability Stack           │
│  ├─ OpenTelemetry (request tracing)    │
│  ├─ structlog (structured logging)     │
│  └─ LLMProviderAuditService (audit)    │
└──────────┬──────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────┐
│  Langfuse Integration Layer             │
│  ├─ LiteLLM callbacks (auto capture)   │
│  ├─ Custom instrumentation (metadata) │
│  └─ Cost tracking (pricing rules)      │
└──────────┬──────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────┐
│  Self-hosted Langfuse                   │
│  ├─ PostgreSQL (data storage)          │
│  ├─ Redis (caching)                    │
│  └─ Web UI + API                       │
└─────────────────────────────────────────┘
```

### 3.5 Примеры использования в проекте

#### Пример 1: Агент с multi-step reasoning
```python
# app/services/agent_with_langfuse.py
from langfuse import Langfuse
from app.services.litellm_client import litellm_client

langfuse = Langfuse()

async def run_agent_with_tracing(
    agent: Agent,
    user_query: str,
    user_id: UUID,
    workspace_id: UUID
):
    with langfuse.trace(
        name=f"agent_{agent.name}",
        user_id=str(user_id),
        session_id=f"workspace_{workspace_id}"
    ) as trace:
        # Шаг 1: Retrieval
        with trace.span(name="retrieve_context") as span:
            context = await retrieve_context(user_query)
            span.update(output={"context_count": len(context)})
        
        # Шаг 2: Reasoning
        with trace.span(name="generate_reasoning") as span:
            reasoning_prompt = f"Query: {user_query}\nContext: {context}"
            reasoning = await litellm_client.completion(
                model=agent.model,
                messages=[
                    {"role": "system", "content": agent.system_prompt},
                    {"role": "user", "content": reasoning_prompt}
                ]
            )
            span.update(
                input={"prompt": reasoning_prompt},
                output={"reasoning": reasoning}
            )
        
        # Шаг 3: Response generation
        with trace.span(name="generate_response") as span:
            response_prompt = f"{reasoning}\n\nNow answer: {user_query}"
            response = await litellm_client.completion(
                model=agent.model,
                messages=[
                    {"role": "system", "content": agent.system_prompt},
                    {"role": "user", "content": response_prompt}
                ]
            )
            span.update(
                input={"prompt": response_prompt},
                output={"response": response}
            )
        
        return response
```

#### Пример 2: Качественная оценка ответов
```python
# app/services/llm_quality_feedback.py

async def save_user_feedback(
    trace_id: str,
    user_id: UUID,
    rating: int,  # 1-5
    feedback_text: str = None
):
    """Сохраняет feedback пользователя в Langfuse"""
    
    langfuse.trace(id=trace_id).update(
        scores={
            "user_satisfaction": rating / 5.0,
            "helpfulness": 1.0 if rating >= 4 else 0.0
        },
        metadata={
            "feedback": feedback_text,
            "feedback_timestamp": datetime.utcnow()
        }
    )
    
    # Теперь можно анализировать корреляцию:
    # rating vs. model, prompt_template, agent_type и т.д.
```

#### Пример 3: Cost allocation между пользователями
```python
# app/reports/cost_analytics.py

async def get_user_cost_breakdown(
    workspace_id: UUID,
    start_date: datetime,
    end_date: datetime
):
    """Получает breakdown стоимости для всех пользователей workspace"""
    
    traces = langfuse.get_traces(
        filters=[
            {"key": "session_id", "value": f"workspace_{workspace_id}"},
            {"key": "timestamp", "value": start_date, "operator": "gte"},
            {"key": "timestamp", "value": end_date, "operator": "lte"}
        ]
    )
    
    cost_by_user = {}
    for trace in traces:
        user_id = trace.user_id
        trace_cost = trace.calculate_cost()  # Автоматический расчет
        
        if user_id not in cost_by_user:
            cost_by_user[user_id] = {"traces": 0, "cost": 0}
        
        cost_by_user[user_id]["traces"] += 1
        cost_by_user[user_id]["cost"] += trace_cost
    
    return cost_by_user
```

---

## 4. Недостатки и риски интеграции

### 4.1 Недостатки

#### 1. Self-hosted infrastructure overhead
| Аспект | Effort | Примечание |
|--------|--------|-----------|
| Initial setup | 2-3 дня | Docker Compose + DB migration |
| Backups | 4 часа/месяц | PostgreSQL backups |
| Updates | 2-4 часа/месяц | Новые версии |
| Monitoring | 4 часа/месяц | Disk space, memory |
| **Итого** | **~20 часов/месяц** | |

**Миtigация**:
```yaml
# docker-compose.prod.yml с best practices
services:
  langfuse:
    image: ghcr.io/langfuse/langfuse:latest
    volumes:
      - langfuse_data:/app/data
    environment:
      - DATABASE_URL=postgresql://user:pass@postgres:5432/langfuse
      - NEXTAUTH_SECRET=${NEXTAUTH_SECRET}
    restart: always
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
  
  postgres:
    image: postgres:16-alpine
    volumes:
      - postgres_data:/var/lib/postgresql/data
    environment:
      - POSTGRES_DB=langfuse
      - POSTGRES_PASSWORD=${DB_PASSWORD}
    restart: always
    backup:
      - automated daily snapshots to S3
```

#### 2. Data privacy & compliance
**Проблема**: Все LLM промпты и ответы будут хранятся в базе данных.

**Решение**:
- ✅ Self-hosted (данные не уходят в облако)
- ✅ Database-level encryption (TLS, at-rest)
- ✅ GDPR compliance (delete/export capabilities)
- ✅ Access control (RBAC in Langfuse)
- ✅ Audit logging (who accessed what)

```sql
-- Encryption at rest in PostgreSQL
CREATE TABLE traces (
    id UUID PRIMARY KEY,
    name TEXT,
    input BYTEA,  -- Encrypted with pgcrypto
    output BYTEA,
    created_at TIMESTAMP,
    user_id UUID
);

-- Row-level security
ALTER TABLE traces ENABLE ROW LEVEL SECURITY;

CREATE POLICY workspace_isolation ON traces
  USING (workspace_id = current_setting('app.workspace_id')::UUID);
```

#### 3. Performance impact на LLM запросы
**Проблема**: Отправка данных в Langfuse может добавить latency.

**Миtigация**:
```python
# Async callbacks с batching
langfuse = Langfuse(
    flush_at_exit=True,
    flush_interval=30.0,  # Batch отправка каждые 30 сек
    max_retries=2
)

# Или использовать LiteLLM встроенный callback
# который работает асинхронно
litellm_settings:
  success_callback: ["langfuse"]  # Async by default
  timeout: 5  # Fail-open если Langfuse недоступен
```

**Результат**: <100ms overhead на большинстве операций.

#### 4. Storage growth
**Проблема**: Каждый LLM запрос = несколько KB в БД.

```
Типичный trace: ~2-5 KB
Среднее использование: 100-1000 запросов/день
Месячное потребление: ~1-50 GB (зависит от scale)
Годовое потребление: ~12-600 GB
```

**Миtigация**:
```python
# Retention policy
langfuse.set_retention_policy(
    days=90  # Автоматическое удаление старых traces
)

# Archival to cold storage
def archive_old_traces():
    """Архивирует traces старше 90 дней в S3"""
    old_traces = langfuse.get_traces(
        filters=[{"key": "created_at", "value": days_90_ago, "operator": "lt"}]
    )
    for trace in old_traces:
        s3.put_object(
            Bucket="langfuse-archive",
            Key=f"traces/{trace.id}.json",
            Body=json.dumps(trace.to_dict())
        )
        trace.delete()
```

### 4.2 Риски

#### Риск 1: Data breach в self-hosted Langfuse
**Вероятность**: LOW (если правильно настроено)
**Impact**: HIGH (раскрытие промптов/ответов)
**Миtigация**:
- VPC isolation (не доступно из интернета)
- IP whitelist (только из app servers)
- Database encryption
- Regular security audits
- Automated backups в encrypted S3

#### Риск 2: Storage overflow
**Вероятность**: MEDIUM (если не настроить retention)
**Impact**: MEDIUM (Langfuse недоступен, no traces)
**Миtigация**:
- Automatic retention policy (90 дней)
- Disk monitoring + alerts
- Regular archival to cold storage
- Capacity planning

#### Риск 3: Langfuse instability
**Вероятность**: LOW (stable project)
**Impact**: LOW (graceful degradation)
**Миtigация**:
```python
# Fail-open design
async def trace_with_fallback(trace_fn):
    try:
        langfuse.trace(...)
    except Exception as e:
        logger.warning(f"Langfuse unavailable: {e}")
        # Продолжаем работу без трейса
```

#### Риск 4: Performance degradation
**Вероятность**: MEDIUM (если много traces)
**Impact**: MEDIUM (slower dashboard)
**Миtigация**:
- Database indexing on common queries
- Redis caching layer
- Async trace processing
- Dashboard query optimization

---

## 5. Сравнение с альтернативными решениями

### 5.1 Сравнительная таблица

| Критерий | Langfuse | Helicone | LangSmith | OpenLLMetry |
|----------|----------|----------|-----------|-------------|
| **Type** | LLM Observability | LLM Observability | LLM Development Platform | OTel-based |
| **Self-hosted** | ✅ Yes | ❌ Cloud only | ❌ Cloud only | ✅ Yes |
| **Pricing Model** | Usage-based (self-hosted: free) | Per-request | Subscription | Free |
| **LLM Tracing** | ✅ Native | ✅ Native | ✅ Native | ⚠️ Basic |
| **Cost Tracking** | ✅ Yes | ✅ Yes | ✅ Yes | ❌ No |
| **Prompt Management** | ⚠️ Manual | ✅ Versioning | ✅ Versioning | ❌ No |
| **A/B Testing** | ⚠️ Manual | ✅ Built-in | ✅ Built-in | ❌ No |
| **Analytics Dashboard** | ✅ Advanced | ✅ Good | ✅ Excellent | ⚠️ Minimal |
| **LiteLLM Integration** | ✅ Native callback | ✅ Native callback | ✅ LangChain only | ❌ No |
| **Data Privacy** | ✅ Full control | ❌ Third-party | ❌ Third-party | ✅ Full control |
| **Community** | Growing (OSS) | Established | Large | Large |
| **Maintenance Burden** | Medium | None | None | Medium |

### 5.2 Детальное сравнение

#### Langfuse
```
Плюсы:
✅ Self-hosted = полный контроль над данными
✅ Open Source (GitHub: langfuse/langfuse)
✅ Отличная LiteLLM интеграция
✅ Асинхронная архитектура (не замораживает LLM запросы)
✅ Простая развертка (Docker Compose)
✅ Low TCO для production использования

Минусы:
❌ Molодой проект (требует мониторинга)
❌ Нет встроенного prompt versioning
❌ Требует самостоятельного управления инфраструктурой
❌ Меньше интеграций с фреймворками (vs LangSmith)
```

**Best for**: Companies требующие data sovereignty + open-source

#### Helicone
```
Плюсы:
✅ Очень простая интеграция (один запрос)
✅ Отличный UI для анализа промптов
✅ Native cost tracking
✅ Кэширование + rate limiting

Минусы:
❌ Cloud-only (нет self-hosted)
❌ Третья сторона хранит все промпты
❌ Per-request pricing (дорого на scale)
❌ Нет долгосрочного архивирования
❌ Vendor lock-in
```

**Best for**: Startups / быстрого прототипирования

#### LangSmith
```
Плюсы:
✅ Integrated suite (LangChain + LangSmith)
✅ Excellent prompt management & versioning
✅ Advanced evaluation framework
✅ Large community (LangChain ecosystem)
✅ Managed service (no ops burden)

Минусы:
❌ Cloud-only (no self-hosted option)
❌ Дорогие (subscription-based)
❌ Зависит от LangChain (не universal)
❌ Третья сторона хранит все данные
❌ Нет API для custom integrations
```

**Best for**: LangChain-heavy projects с budget

#### OpenLLMetry (OpenTelemetry-based)
```
Плюсы:
✅ OpenTelemetry standard (compatible с существующей stack)
✅ Self-hosted (free)
✅ Decoupled (работает с любым backend)

Минусы:
❌ LLM-focused metrics не настроены по умолчанию
❌ Требует много manual instrumentation
❌ Нет специализированного UI для LLM операций
❌ Сложнее настраивать (особенно для LLM)
❌ Меньше готовых интеграций
```

**Best for**: Teams с existing OTel infrastructure

### 5.3 Рекомендация для codelab-core-service

**Выбор: Langfuse (self-hosted)**

**Причины**:
1. ✅ Self-hosted совместим с requirement на data control
2. ✅ LiteLLM integration уже в проекте (минимальные изменения)
3. ✅ Open Source (модифицируемо если нужно)
4. ✅ Low operational overhead (Docker Compose)
5. ✅ Отличные LLM-specific features
6. ✅ Growing community + active development
7. ✅ Может работать параллельно с OpenTelemetry (не конфликт)

---

## 6. Рекомендуемая архитектура интеграции

### 6.1 High-level архитектура

```mermaid
graph TB
    subgraph "Application Layer"
        FastAPI["FastAPI App"]
        Agent["Agent Service"]
        LLMClient["LiteLLM Client"]
    end
    
    subgraph "Instrumentation"
        LiteLLMCallback["LiteLLM Callback<br/>(auto capture)"]
        LangfuseSDK["Langfuse SDK<br/>(custom traces)"]
        StructLog["structlog<br/>(enrichment)"]
    end
    
    subgraph "Langfuse Stack (Self-Hosted)"
        LangfuseAPI["Langfuse API"]
        LangfuseDB["PostgreSQL"]
        LangfuseRedis["Redis Cache"]
        LangfuseUI["Web UI"]
    end
    
    subgraph "Existing Observability"
        OTel["OpenTelemetry"]
        Jaeger["Jaeger"]
    end
    
    FastAPI -->|FastAPI instrumentation| OTel
    Agent -->|create traces| LangfuseSDK
    LLMClient -->|async callback| LiteLLMCallback
    LiteLLMCallback -->|HTTP API| LangfuseAPI
    LangfuseSDK -->|HTTP API| LangfuseAPI
    StructLog -->|metadata enrichment| LiteLLMCallback
    LangfuseAPI -->|read/write| LangfuseDB
    LangfuseAPI -->|cache| LangfuseRedis
    LangfuseAPI -->|query| LangfuseUI
    OTel -->|OTLP export| Jaeger
```

### 6.2 Фиксированные компоненты

#### 1. LiteLLM Configuration
```yaml
# litellm_config.yaml (обновлено)
model_list:
  - model_name: gpt-4-turbo
    litellm_params:
      model: openai/gpt-4-turbo-preview
      api_key: ${OPENAI_API_KEY}
  
  - model_name: claude-3-opus
    litellm_params:
      model: anthropic/claude-3-opus-20240229
      api_key: ${ANTHROPIC_API_KEY}

litellm_settings:
  # Langfuse callbacks
  success_callback: ["langfuse"]
  failure_callback: ["langfuse"]
  
  # Async processing (не блокирует LLM запрос)
  flush_at_exit: true
  flush_interval: 30
  
  # Fail-open (если Langfuse down)
  timeout: 5
  max_retries: 1

environment_variables:
  LANGFUSE_PUBLIC_KEY: ${LANGFUSE_PUBLIC_KEY}
  LANGFUSE_SECRET_KEY: ${LANGFUSE_SECRET_KEY}
  LANGFUSE_HOST: "http://langfuse:3000"  # Self-hosted
```

#### 2. Langfuse Wrapper Service
```python
# app/services/langfuse_integration.py
from typing import Optional, Any
from uuid import UUID
from datetime import datetime
from langfuse import Langfuse
from app.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)

class LangfuseIntegration:
    """Wrapper вокруг Langfuse SDK для unified интеграции"""
    
    def __init__(self):
        """Initialize Langfuse client"""
        try:
            self.client = Langfuse(
                public_key=settings.langfuse_public_key,
                secret_key=settings.langfuse_secret_key,
                host=settings.langfuse_host,
                flush_at_exit=True,
                flush_interval=30,
                max_retries=2,
                timeout=5
            )
            self.enabled = True
            logger.info("Langfuse initialized successfully")
        except Exception as e:
            self.enabled = False
            logger.warning(f"Langfuse initialization failed: {e}")
    
    def create_trace(
        self,
        name: str,
        user_id: UUID,
        workspace_id: UUID,
        agent_name: Optional[str] = None,
        metadata: Optional[dict] = None
    ):
        """Create root trace для agent interaction"""
        if not self.enabled:
            return None
        
        try:
            return self.client.trace(
                name=name,
                user_id=str(user_id),
                session_id=f"workspace_{workspace_id}",
                metadata={
                    "agent": agent_name,
                    "workspace_id": str(workspace_id),
                    "timestamp": datetime.utcnow().isoformat(),
                    **(metadata or {})
                },
                tags=["agent", agent_name] if agent_name else []
            )
        except Exception as e:
            logger.error(f"Failed to create trace: {e}")
            return None
    
    def create_span(
        self,
        trace,
        name: str,
        input_data: Optional[dict] = None,
        output_data: Optional[dict] = None,
        metadata: Optional[dict] = None
    ):
        """Create span within trace"""
        if not trace or not self.enabled:
            return None
        
        try:
            return trace.span(
                name=name,
                input=input_data,
                output=output_data,
                metadata=metadata,
                end_time=datetime.utcnow()
            )
        except Exception as e:
            logger.error(f"Failed to create span: {e}")
            return None
    
    def record_score(
        self,
        trace_id: str,
        name: str,
        value: float,
        comment: Optional[str] = None
    ):
        """Record quality score for trace"""
        if not self.enabled:
            return
        
        try:
            self.client.trace(id=trace_id).update(
                scores={name: value},
                metadata={"score_comment": comment}
            )
        except Exception as e:
            logger.error(f"Failed to record score: {e}")
    
    def get_traces(
        self,
        user_id: Optional[UUID] = None,
        workspace_id: Optional[UUID] = None,
        limit: int = 100
    ) -> list:
        """Retrieve traces for analysis"""
        if not self.enabled:
            return []
        
        try:
            filters = []
            if user_id:
                filters.append({
                    "key": "user_id",
                    "value": str(user_id)
                })
            if workspace_id:
                filters.append({
                    "key": "session_id",
                    "value": f"workspace_{workspace_id}"
                })
            
            return self.client.get_traces(
                filters=filters,
                limit=limit
            ).data
        except Exception as e:
            logger.error(f"Failed to retrieve traces: {e}")
            return []

# Global instance
langfuse = LangfuseIntegration()
```

#### 3. Agent Service Integration
```python
# app/services/agent_service.py (updated)
from app.services.langfuse_integration import langfuse

async def process_agent_message(
    session_id: UUID,
    workspace_id: UUID,
    agent_id: UUID,
    user_id: UUID,
    message: str,
    target_agent: str
) -> str:
    """Process message with Langfuse tracing"""
    
    agent = await get_agent(agent_id)
    
    # Create root trace
    trace = langfuse.create_trace(
        name=f"agent_interaction_{agent.name}",
        user_id=user_id,
        workspace_id=workspace_id,
        agent_name=agent.name
    )
    
    try:
        # Step 1: Prepare context
        span1 = langfuse.create_span(
            trace=trace,
            name="prepare_context",
            input_data={"message": message, "agent_id": str(agent_id)}
        )
        context = await prepare_agent_context(agent, message)
        if span1:
            span1.update(
                output={"context_length": len(context)},
                end_time=datetime.utcnow()
            )
        
        # Step 2: Generate response (LiteLLM will auto-capture via callback)
        span2 = langfuse.create_span(
            trace=trace,
            name="generate_response",
            input_data={"prompt": agent.system_prompt + message}
        )
        
        response = await agent.generate_response(
            message=message,
            context=context
        )
        # Response metrics captured by LiteLLM callback
        
        if span2:
            span2.update(
                output={"response": response[:100] + "..."},
                end_time=datetime.utcnow()
            )
        
        # Step 3: Save interaction
        span3 = langfuse.create_span(
            trace=trace,
            name="save_interaction"
        )
        await save_interaction(
            session_id=session_id,
            agent_id=agent_id,
            message=message,
            response=response
        )
        if span3:
            span3.update(
                output={"saved": True},
                end_time=datetime.utcnow()
            )
        
        return response
    
    except Exception as e:
        logger.error(f"Agent processing failed: {e}", exc_info=True)
        if trace:
            langfuse.client.trace(id=trace.id).update(
                metadata={"error": str(e)},
                level="ERROR"
            )
        raise
```

### 6.3 Docker Compose для Langfuse

```yaml
# docker-compose.prod.yml (новый сервис)
version: '3.8'

services:
  langfuse-postgres:
    image: postgres:16-alpine
    container_name: langfuse-postgres
    environment:
      POSTGRES_DB: langfuse
      POSTGRES_USER: langfuse
      POSTGRES_PASSWORD: ${LANGFUSE_DB_PASSWORD}
    volumes:
      - langfuse_postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U langfuse"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - codelab-network
    restart: always

  langfuse:
    image: ghcr.io/langfuse/langfuse:latest
    container_name: langfuse
    depends_on:
      langfuse-postgres:
        condition: service_healthy
    environment:
      DATABASE_URL: postgresql://langfuse:${LANGFUSE_DB_PASSWORD}@langfuse-postgres:5432/langfuse
      NEXTAUTH_SECRET: ${NEXTAUTH_SECRET}
      NEXTAUTH_URL: ${LANGFUSE_NEXTAUTH_URL}
      # Security
      NODE_ENV: production
      # Optional: SMTP for notifications
      SMTP_FROM_EMAIL: ${LANGFUSE_SMTP_FROM_EMAIL}
      SMTP_HOST: ${LANGFUSE_SMTP_HOST}
      SMTP_PORT: ${LANGFUSE_SMTP_PORT}
      SMTP_USERNAME: ${LANGFUSE_SMTP_USERNAME}
      SMTP_PASSWORD: ${LANGFUSE_SMTP_PASSWORD}
    ports:
      - "3000:3000"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3000/api/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    networks:
      - codelab-network
    restart: always
    volumes:
      - langfuse_data:/app/data

  codelab-core-service:
    # ... existing service ...
    depends_on:
      - langfuse
    environment:
      LANGFUSE_PUBLIC_KEY: ${LANGFUSE_PUBLIC_KEY}
      LANGFUSE_SECRET_KEY: ${LANGFUSE_SECRET_KEY}
      LANGFUSE_HOST: http://langfuse:3000
    networks:
      - codelab-network

volumes:
  langfuse_postgres_data:
  langfuse_data:

networks:
  codelab-network:
    driver: bridge
```

### 6.4 Environment variables

```bash
# .env.langfuse
# Langfuse Server
LANGFUSE_HOST=http://langfuse:3000
LANGFUSE_NEXTAUTH_URL=https://langfuse.yourdomain.com
NEXTAUTH_SECRET=$(openssl rand -base64 32)

# Database
LANGFUSE_DB_PASSWORD=$(openssl rand -base64 16)

# Langfuse API Keys (генерируются при первом запуске)
LANGFUSE_PUBLIC_KEY=pk-...
LANGFUSE_SECRET_KEY=sk-...

# Optional: Email notifications
LANGFUSE_SMTP_FROM_EMAIL=langfuse@yourdomain.com
LANGFUSE_SMTP_HOST=smtp.yourdomain.com
LANGFUSE_SMTP_PORT=587
LANGFUSE_SMTP_USERNAME=...
LANGFUSE_SMTP_PASSWORD=...
```

---

## 7. План внедрения (3 фазы)

### 7.1 Phase 1: Foundation (Недели 1-2)

**Цель**: Базовое логирование LLM вызовов через LiteLLM callbacks

**Задачи**:

1. **Развертка Langfuse (2-3 дня)**
   ```bash
   # 1. Prepare infrastructure
   - Выделить VM/server для self-hosted
   - Настроить PostgreSQL, Redis
   - Настроить backup strategy
   
   # 2. Deploy Langfuse
   docker-compose up -d langfuse
   
   # 3. Initial configuration
   - Create admin account
   - Generate API keys
   - Configure email notifications
   ```

2. **LiteLLM интеграция (2-3 дня)**
   ```python
   # Обновить litellm_config.yaml
   litellm_settings:
     success_callback: ["langfuse"]
     failure_callback: ["langfuse"]
   
   environment_variables:
     LANGFUSE_PUBLIC_KEY: pk-...
     LANGFUSE_SECRET_KEY: sk-...
     LANGFUSE_HOST: http://langfuse:3000
   ```

3. **Базовое тестирование (1-2 дня)**
   ```python
   # Простой e2e тест
   from litellm import completion
   
   response = completion(
       model="gpt-4",
       messages=[{"role": "user", "content": "Hello"}]
   )
   # LiteLLM автоматически отправит данные в Langfuse
   
   # Проверить в UI Langfuse: http://localhost:3000
   ```

**Output**:
- ✅ Langfuse running
- ✅ LiteLLM callbacks enabled
- ✅ Basic traces in Langfuse dashboard
- ✅ Team training на Langfuse UI

**Estimated effort**: 40 hours (4-5 days)

### 7.2 Phase 2: Deep Integration (Недели 3-4)

**Цель**: Полная интеграция с agent сервисом и custom instrumentation

**Задачи**:

1. **Langfuse SDK интеграция (3-4 дня)**
   ```python
   # Создать app/services/langfuse_integration.py
   - LangfuseIntegration class
   - Context management
   - Error handling
   - Fail-safe mechanisms
   
   # Unit tests
   - test_trace_creation
   - test_span_creation
   - test_score_recording
   - test_error_handling
   ```

2. **Agent Service instrumentation (3-4 дня)**
   ```python
   # Обновить agent processing pipeline
   app/services/agent_service.py:
   - Wrap main processing в trace
   - Create spans для каждого step
   - Capture input/output
   - Record performance metrics
   
   # Coverage:
   - prepare_context span
   - generate_response span
   - save_interaction span
   - error handling
   ```

3. **Quality feedback mechanism (2-3 дня)**
   ```python
   # app/routes/feedback.py
   POST /feedback/{trace_id}
   {
     "rating": 5,
     "feedback": "Excellent response"
   }
   
   # Saves to Langfuse trace scores
   ```

4. **Cost tracking dashboard (2-3 дня)**
   ```python
   # app/reports/cost_analytics.py
   - User cost breakdown
   - Model usage analytics
   - Daily/weekly/monthly trends
   - Budget alerts
   ```

**Output**:
- ✅ Full agent tracing
- ✅ Quality feedback integration
- ✅ Cost analytics
- ✅ Dashboard queries working
- ✅ Integration tests passing

**Estimated effort**: 60 hours (6-8 days)

### 7.3 Phase 3: Optimization & Production (Недели 5-6)

**Цель**: Performance optimization, monitoring, production hardening

**Задачи**:

1. **Performance optimization (2-3 дня)**
   ```python
   # Batch processing
   langfuse_settings:
     flush_interval: 30  # Batch every 30 sec
     max_batch_size: 100
   
   # Connection pooling
   PostgreSQL:
     - Configure pgBouncer for connection pooling
     - Monitor query performance
     - Add indexes on hot queries
   
   # Caching
   Redis:
     - Cache dashboard queries
     - Cache user metadata
   ```

2. **Monitoring & Alerts (2-3 дня)**
   ```yaml
   # Prometheus metrics
   - langfuse_database_size
   - langfuse_request_latency
   - langfuse_error_rate
   - langfuse_callback_failures
   
   # Alerts
   - Disk usage > 80%
   - Trace insert latency > 100ms
   - Callback success rate < 99%
   ```

3. **Data retention & archival (2-3 дня)**
   ```python
   # Retention policy
   LANGFUSE_RETENTION_DAYS=90
   
   # Archival script
   def archive_old_traces():
       old_traces = langfuse.get_traces(
           filters=[{"key": "created_at", "value": 90_days_ago, "operator": "lt"}]
       )
       # Archive to S3
       # Delete from DB
   
   # Scheduled: Daily at 02:00 UTC
   ```

4. **Documentation & runbooks (2-3 дня)**
   ```markdown
   - Deployment guide
   - Troubleshooting guide
   - Scaling guide
   - Backup/recovery procedures
   - On-call runbook
   ```

5. **Production hardening (2 дня)**
   ```yaml
   # Security
   - SSL/TLS for all connections
   - Database encryption at rest
   - Access control (RBAC)
   - Audit logging
   
   # High availability
   - Replicated PostgreSQL
   - Langfuse behind load balancer
   - Health checks configured
   ```

**Output**:
- ✅ Optimized performance
- ✅ Monitoring & alerting
- ✅ Retention policy configured
- ✅ Backup/recovery tested
- ✅ Complete documentation
- ✅ Production-ready

**Estimated effort**: 50 hours (5-6 days)

### 7.4 Timeline Summary

```
Week 1-2: Foundation (Phase 1)
├─ Mon-Wed: Langfuse deployment
├─ Thu-Fri: LiteLLM integration
└─ Fri: Testing & validation

Week 3-4: Deep Integration (Phase 2)
├─ Mon-Tue: SDK integration
├─ Wed-Thu: Agent instrumentation
├─ Thu-Fri: Quality feedback
└─ Fri: Cost tracking

Week 5-6: Optimization (Phase 3)
├─ Mon-Tue: Performance optimization
├─ Wed: Monitoring setup
├─ Thu: Data retention
└─ Fri: Documentation & hardening

Total: ~30 working days (6 weeks)
Effort: ~150-180 hours
```

---

## 8. Оценка трудозатрат и стоимости

### 8.1 Development Effort

| Phase | Component | Hours | FTE-Weeks | Notes |
|-------|-----------|-------|-----------|-------|
| **Phase 1** | | | | |
| | Langfuse deployment | 20 | 0.5 | Infrastructure |
| | LiteLLM config | 12 | 0.3 | Simple |
| | Testing | 8 | 0.2 | Smoke tests |
| **Phase 1 Total** | | **40** | **1.0** | |
| **Phase 2** | | | | |
| | SDK integration | 28 | 0.7 | Main integration |
| | Agent instrumentation | 24 | 0.6 | Testing intensive |
| | Feedback mechanism | 12 | 0.3 | Simple |
| | Cost analytics | 12 | 0.3 | Data analysis |
| **Phase 2 Total** | | **76** | **1.9** | |
| **Phase 3** | | | | |
| | Performance tuning | 16 | 0.4 | Optimization |
| | Monitoring setup | 12 | 0.3 | Prometheus |
| | Data retention | 8 | 0.2 | Archival logic |
| | Documentation | 12 | 0.3 | Runbooks |
| | Production hardening | 8 | 0.2 | Security |
| **Phase 3 Total** | | **56** | **1.4** | |
| **GRAND TOTAL** | | **172** | **4.3** | ~6 weeks |

### 8.2 Infrastructure Costs (Monthly)

#### Self-Hosted on AWS

| Component | Instance Type | Monthly Cost | Notes |
|-----------|--------------|--------------|-------|
| **Compute** | | | |
| Langfuse app | t3.medium | $30 | 2 vCPU, 4GB RAM |
| **Database** | | | |
| RDS PostgreSQL | db.t3.small | $45 | Multi-AZ for HA |
| PostgreSQL backups | S3 storage | $5 | 100GB/month |
| **Cache** | | | |
| ElastiCache Redis | cache.t3.micro | $15 | For dashboard caching |
| **Networking** | | | |
| NAT Gateway | - | $32 | Data transfer |
| ALB | - | $16 | Load balancer |
| **Storage** | | | |
| S3 archival | - | $25 | Old traces archival |
| **Monitoring** | | | |
| CloudWatch logs | - | $5 | Basic monitoring |
| **TOTAL MONTHLY** | | **$173** | ~$200/month |

#### Alternative: Managed Langfuse Cloud
- **Cost**: $500-2000/month (depending on usage)
- **Pros**: No ops burden
- **Cons**: Data in third-party cloud, higher cost

### 8.3 Operational Costs (Monthly)

| Task | Hours/Month | Cost @ $100/hr | Notes |
|------|------------|--------|-------|
| Database backups & monitoring | 4 | $400 | Automated mostly |
| Disk space management | 2 | $200 | Manual cleanup |
| Security patches | 2 | $200 | PostgreSQL updates |
| Performance monitoring | 2 | $200 | Dashboard queries |
| Incident response | 2 | $200 | If issues arise |
| Documentation updates | 2 | $200 | Maintenance |
| **TOTAL MONTHLY** | **14** | **$1,400** | ~$1,400/month |

### 8.4 Total Cost of Ownership (Year 1)

```
Development:
├─ Internal team: 172 hours × $150/hour = $25,800
└─ Subtotal: $25,800

Infrastructure (Annual):
├─ Monthly recurring: $173 × 12 = $2,076
└─ Subtotal: $2,076

Operations (Annual):
├─ Monthly recurring: $1,400 × 12 = $16,800
└─ Subtotal: $16,800

YEAR 1 TOTAL: $44,676
Annual per-seat: $44,676 / 100 users ≈ $450/user/year
Monthly per-user: ~$37/user/month
```

### 8.5 ROI Analysis

#### Value delivered:
1. **Reduced debugging time**: -30% from 10 hours/week → 7 hours/week
   - Annual savings: 156 hours × $150/hour = **$23,400**

2. **Cost optimization**: Identify expensive models/prompts
   - Typical savings: 15-25% of LLM spend
   - If annual LLM spend = $50K, savings = **$7,500-12,500**

3. **Improved user experience**: Better error handling & debugging
   - Reduced support tickets: -20%
   - Annual savings: 20 hours/month × $100/hour × 12 = **$24,000**

4. **Faster feature development**: Quick iteration on prompts
   - Faster deployment: -25% cycle time
   - Annual productivity gain: **$10,000**

**Total annual value**: $65K - $70K
**Payback period**: ~6-8 months

---

## 9. Заключение и рекомендации

### 9.1 Рекомендация

**✅ РЕКОМЕНДУЕТСЯ РЕАЛИЗОВАТЬ интеграцию Langfuse (self-hosted)**

**Ключевые причины**:

1. **Стратегическая необходимость**
   - LLM операции — core функциональность системы
   - Текущее отсутствие LLM observability = слепота в production
   - Competitive advantage: лучшее понимание своей система

2. **Хорошее ROI**
   - Development cost: ~$26K
   - Value delivered: $65-70K/year
   - Payback period: 6-8 месяцев

3. **Low risk**
   - Self-hosted = полный контроль над данными
   - Open source = может быть модифицировано если нужно
   - Graceful degradation = не повлияет на основной функционал

4. **Гибкость**
   - Начать с MVP (2 недели)
   - Масштабировать постепенно
   - Интегрируется с existing OpenTelemetry stack

### 9.2 Рекомендуемый путь реализации

#### Вариант A: Быстрый MVP (Рекомендуется для начала)
- **Timeline**: 2-3 недели
- **Effort**: 50-60 часов
- **Scope**: 
  - Langfuse deployment
  - LiteLLM callbacks integration
  - Basic dashboard
- **Value**: 80% функциональности с 20% effort

#### Вариант B: Полная реализация
- **Timeline**: 6 недель (как описано в Phase 1-3)
- **Effort**: 170-180 часов
- **Scope**: Все feature из документа
- **Value**: 100% функциональности

**Рекомендация**: Начать с Вариантом A, затем постепенно реализовать Вариант B

### 9.3 Next Steps

1. **Approve decision** (1 день)
   - Обсудить с stakeholders
   - Согласовать timeline и бюджет

2. **Setup development environment** (2-3 дня)
   - Выделить инфраструктуру для Langfuse
   - Подготовить dev/staging environment

3. **Phase 1 implementation** (4-5 дней)
   - Deploy Langfuse
   - Integrate LiteLLM callbacks
   - Smoke testing

4. **Validate MVP** (2 дня)
   - Demо stakeholders
   - Gather feedback
   - Plan Phase 2

5. **Phase 2-3 execution** (4-6 недель)
   - Полная интеграция
   - Production deployment
   - Team training

### 9.4 Критические успешные факторы

1. **Infrastructure readiness**
   - Self-hosted сервер ready
   - Backup strategy defined
   - Security policies in place

2. **Team commitment**
   - Developer привлечен для 6 недель
   - Ops team обучен на Langfuse
   - Clear ownership assigned

3. **Proper documentation**
   - Architecture diagrams
   - Deployment runbooks
   - Troubleshooting guides

4. **Monitoring & alerting**
   - Langfuse health checks
   - Database performance monitoring
   - Error rate tracking

### 9.5 Альтернативные scenario'ы

#### Если data sovereignty не требуется:
- Используйте **Helicone** (проще, быстрее)
- Effort: 1-2 недели
- Cost: $500-2000/месяц

#### Если уже используется LangChain:
- Попробуйте **LangSmith** (лучше интегрирует)
- Effort: 2-3 недели
- Cost: $2000-5000/месяц

#### Если нужна полная OpenTelemetry интеграция:
- Используйте **OpenLLMetry + Grafana**
- Effort: 3-4 недели
- Cost: Бесплатно (self-hosted)

---

## Приложение A: Ссылки на файлы проекта

### Текущая observability infrastructure:
- [`app/tracing.py`](app/tracing.py:1) — OpenTelemetry setup
- [`app/logging_config.py`](app/logging_config.py:1) — Structured logging
- [`app/services/llm_provider_audit_service.py`](app/services/llm_provider_audit_service.py:1) — Audit logging

### LLM интеграция:
- [`app/services/litellm_client.py`](app/services/litellm_client.py:1) — LiteLLM wrapper
- [`app/services/llm_provider_service.py`](app/services/llm_provider_service.py:1) — Provider management
- [`doc/litellm-integration.md`](doc/litellm-integration.md:1) — LiteLLM documentation

### Agent система:
- [`app/services/agent_service.py`](app/services/agent_service.py:1) — Agent processing
- [`app/routes/project_chat.py`](app/routes/project_chat.py:1) — Chat API

### Dependencies:
- [`pyproject.toml`](pyproject.toml:1) — Project dependencies

---

## Приложение B: Useful Resources

### Langfuse Documentation
- https://langfuse.com/docs
- https://github.com/langfuse/langfuse
- https://github.com/langfuse/langfuse-js (SDKs)

### LiteLLM + Langfuse
- https://docs.litellm.ai/docs/observability/langfuse_integration
- https://github.com/BerriAI/litellm

### OpenTelemetry
- https://opentelemetry.io/docs
- https://github.com/open-telemetry

### Deployment
- Self-hosted Langfuse: https://langfuse.com/docs/deployment/self-host
- Docker Compose: https://github.com/langfuse/langfuse/blob/main/docker-compose.yml
- Kubernetes: https://langfuse.com/docs/deployment/self-host#kubernetes

---

## Приложение C: Checklist для реализации

- [ ] Approve decision & allocate budget
- [ ] Выделить инфраструктуру (AWS EC2, RDS, etc.)
- [ ] Setup development environment
- [ ] Deploy Langfuse (Phase 1)
- [ ] Integrate LiteLLM callbacks (Phase 1)
- [ ] Smoke testing (Phase 1)
- [ ] Create LangfuseIntegration service (Phase 2)
- [ ] Instrument agent service (Phase 2)
- [ ] Implement quality feedback (Phase 2)
- [ ] Add cost analytics (Phase 2)
- [ ] Performance optimization (Phase 3)
- [ ] Setup monitoring & alerting (Phase 3)
- [ ] Configure data retention (Phase 3)
- [ ] Write documentation (Phase 3)
- [ ] Production hardening (Phase 3)
- [ ] Team training
- [ ] Go-live decision
- [ ] Post-launch review

---

**Document Version**: 1.0
**Last Updated**: 2026-03-10
**Author**: СodeLab Team
**Status**: Ready for Implementation
