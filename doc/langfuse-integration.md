# Langfuse Integration Documentation

## Обзор архитектуры

Langfuse интеграция обеспечивает полный LLM observability stack для отслеживания и анализа всех LLM вызовов в системе.

### Компоненты системы

```
┌─────────────────────────────────────────────────────┐
│           Application Layer (FastAPI)               │
├─────────────────────────────────────────────────────┤
│  Health Check │ Traces API │ Feedback API │ Analytics│
│   Endpoints   │ Endpoints  │  Endpoints   │Endpoints │
├─────────────────────────────────────────────────────┤
│       Services Layer (LLM Observability)            │
├──────────────────┬──────────────────┬───────────────┤
│ LangfuseIntegration │ TracesService  │ RetentionPolicy│
│  (SDK wrapper)      │  (Query/Filter) │ (Cleanup)     │
├──────────────────┬──────────────────┬───────────────┤
│       Metrics Layer (Prometheus)    │               │
├─────────────────────────────────────┤───────────────┤
│ Counters, Histograms, Gauges        │ Performance   │
└─────────────────────────────────────┴───────────────┘
         │                                     │
         └────────┬─────────────────────────────┘
                  │
         ┌────────▼──────────┐
         │  Langfuse Cloud   │
         │   (or Self-hosted)│
         └───────────────────┘
```

### Архитектурные слои

#### 1. SDK Wrapper (LangfuseIntegration)
- Graceful degradation при ошибках
- Context propagation (user_id, workspace_id)
- Unified API для trace/span/score управления

#### 2. REST API Layer (LangfuseRestClient)
- HTTP Basic Auth
- Async operations (httpx)
- Фильтрация и pagination
- Analytics queries

#### 3. Data Access Layer (TracesService)
- Query building
- Permission checks (user isolation)
- Result aggregation
- Caching (optional)

#### 4. Metrics Layer
- Prometheus exposition format
- Real-time monitoring
- Latency histograms
- Error counters

#### 5. Retention Layer
- Automatic cleanup of old traces
- S3 archival support
- Configurable policies
- Scheduled tasks

## Компоненты

### app/services/langfuse_integration.py

Основной сервис для взаимодействия с Langfuse SDK.

**Ключевые методы:**

```python
class LangfuseIntegration:
    def create_trace(
        name: str,
        user_id: Optional[UUID] = None,
        workspace_id: Optional[UUID] = None,
        metadata: Optional[dict] = None,
    ) -> Optional[Trace]
    
    def create_span(
        trace: Any,
        name: str,
        input_data: Optional[Any] = None,
        output_data: Optional[Any] = None,
        metadata: Optional[dict] = None,
        status: str = "success",
    ) -> Optional[Span]
    
    def record_score(
        trace_id: str,
        name: str,
        value: float,
        comment: Optional[str] = None,
    ) -> bool
    
    def get_trace(trace_id: str) -> Optional[dict]
```

### app/services/langfuse_rest_client.py

REST API клиент для получения traces и analytics.

**Ключевые методы:**

```python
class LangfuseRestClient:
    async def get_traces(
        user_id: UUID,
        workspace_id: Optional[UUID] = None,
        agent_name: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict
    
    async def get_trace(trace_id: str) -> Optional[dict]
    
    async def get_spans(
        trace_id: str,
        limit: int = 100,
    ) -> list[dict]
    
    async def record_score(
        trace_id: str,
        score_name: str,
        score_value: float,
        comment: Optional[str] = None,
    ) -> bool
    
    async def check_health() -> bool
```

### app/services/traces_service.py

Service для работы с traces на уровне приложения.

### app/routes/health.py

Health check endpoints для мониторинга.

### app/routes/traces.py

REST API endpoints для управления traces.

### app/routes/feedback.py

REST API endpoints для записи scores и feedback.

### app/metrics/langfuse_metrics.py

Prometheus метрики для мониторинга.

### app/tasks/langfuse_retention.py

Scheduled task для управления retention policy.

## REST API Endpoints

### Health Check

```
GET /health/langfuse
```

Проверяет доступность Langfuse сервиса.

**Responses:**
- 200: `{"status": "healthy"}` - Langfuse доступен
- 200: `{"status": "disabled"}` - Langfuse отключен в конфигурации
- 503: `{"status": "unhealthy", "error": "..."}` - Langfuse недоступен

### Traces Endpoints

```
GET /traces?user_id=...&workspace_id=...&limit=10&offset=0
```

Получить список traces с фильтрацией.

**Query Parameters:**
- `user_id`: User ID (требуется)
- `workspace_id`: Workspace ID (опционально)
- `agent_name`: Имя агента для фильтрации (опционально)
- `limit`: Количество результатов (default: 100)
- `offset`: Offset для pagination (default: 0)

```
GET /traces/{trace_id}
```

Получить детали конкретного trace.

### Scores Endpoints

```
POST /traces/{trace_id}/scores
```

Записать score для trace.

**Request Body:**
```json
{
  "name": "user_satisfaction",
  "value": 0.85,
  "comment": "Good response"
}
```

### Analytics Endpoints

```
GET /analytics/traces/summary?period=7d
```

Получить summary analytics за период.

**Query Parameters:**
- `period`: `7d` | `30d` | `all`

```
GET /analytics/agents
```

Получить analytics по агентам.

```
GET /analytics/cost
```

Получить cost analysis.

## Конфигурация

### Environment Variables

```bash
# Langfuse основная конфигурация
LANGFUSE_ENABLED=true
LANGFUSE_PUBLIC_KEY=your_public_key
LANGFUSE_SECRET_KEY=your_secret_key
LANGFUSE_HOST=https://cloud.langfuse.com  # или http://localhost:3000

# Retention policy
LANGFUSE_RETENTION_DAYS=30  # Удалять traces старше 30 дней

# Optional: S3 archival
LANGFUSE_ARCHIVE_TO_S3=false
AWS_S3_BUCKET=langfuse-archives
AWS_S3_REGION=us-east-1
```

### app/config.py

```python
class Settings(BaseSettings):
    langfuse_enabled: bool = Field(
        default=False,
        description="Enable Langfuse integration"
    )
    langfuse_public_key: str = Field(
        default="",
        description="Langfuse public key"
    )
    langfuse_secret_key: str = Field(
        default="",
        description="Langfuse secret key"
    )
    langfuse_host: str = Field(
        default="http://localhost:3000",
        description="Langfuse host URL"
    )
    langfuse_retention_days: int = Field(
        default=30,
        description="Days to retain traces"
    )
```

## Примеры использования

### Создание trace и span

```python
from app.services.langfuse_integration import LangfuseIntegration
from uuid import UUID

langfuse = LangfuseIntegration()

# Создать trace
trace = langfuse.create_trace(
    name="agent_process_message",
    user_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
    workspace_id=UUID("223e4567-e89b-12d3-a456-426614174000"),
    metadata={"model": "gpt-4", "temperature": 0.7}
)

if trace:
    # Создать span
    span = langfuse.create_span(
        trace=trace,
        name="prepare_context",
        input_data={"context_size": 2000},
        output_data={"formatted_context": "..."},
        status="success"
    )
    
    # Записать score
    langfuse.record_score(
        trace_id=trace.id,
        name="user_satisfaction",
        value=0.95,
        comment="Good response quality"
    )
```

### API Usage

```bash
# Get traces
curl -X GET "http://localhost:8000/traces?user_id=123e4567&limit=10" \
  -H "Authorization: Bearer $TOKEN"

# Record score
curl -X POST "http://localhost:8000/traces/trace-123/scores" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "user_satisfaction",
    "value": 0.85,
    "comment": "Good response"
  }'

# Get analytics
curl -X GET "http://localhost:8000/analytics/traces/summary?period=7d" \
  -H "Authorization: Bearer $TOKEN"

# Check health
curl -X GET "http://localhost:8000/health/langfuse"
```

## Мониторинг

### Prometheus метрики

```
# Traces counter
langfuse_traces_total{workspace_id="..."} 150

# Spans counter
langfuse_spans_total{trace_id="..."} 450

# Scores counter
langfuse_scores_total{score_name="user_satisfaction"} 200

# Callback failures
langfuse_callback_failures{callback_type="trace_creation",error_type="TimeoutError"} 5

# Latency histogram
langfuse_trace_creation_latency_seconds_bucket{le="0.1"} 120
langfuse_trace_creation_latency_seconds_bucket{le="0.25"} 145
langfuse_trace_creation_latency_seconds_bucket{le="0.5"} 148
langfuse_trace_creation_latency_seconds_sum 42.5
langfuse_trace_creation_latency_seconds_count 150
```

### Grafana Dashboard

Рекомендуется создать Grafana dashboard с панелями:

1. **Trace Count** - График количества traces в времени
2. **Average Latency** - Graph для latency histogram
3. **Error Rate** - Ratio callback failures к total traces
4. **Cost Analysis** - Breakdown по типам моделей
5. **Health Status** - Current health check status

## Troubleshooting

### Langfuse не доступен

**Симптом:** `/health/langfuse` возвращает 503

**Решение:**
1. Проверить что Langfuse контейнер запущен: `docker-compose ps`
2. Проверить LANGFUSE_HOST переменную окружения
3. Проверить network connectivity: `curl http://localhost:3000`

### Traces не записываются

**Симптом:** Нет traces в Langfuse UI

**Решение:**
1. Проверить что LANGFUSE_ENABLED=true
2. Проверить что LangfuseIntegration.enabled=true
3. Проверить логи приложения для ошибок
4. Проверить credentials (public_key, secret_key)

### Retention очистка не работает

**Симптом:** Старые traces остаются в Langfuse

**Решение:**
1. Запустить retention вручную
2. Проверить LANGFUSE_RETENTION_DAYS (default 30 дней)
3. Проверить что scheduled task запущен

### Performance проблемы

**Симптом:** Медленные API запросы

**Решение:**
1. Проверить Prometheus метрики latency
2. Увеличить pagination limits
3. Добавить индексы в Langfuse database
4. Рассмотреть caching для analytics

## Deployment Guide

### Self-hosted Langfuse

```yaml
# docker-compose.yml
services:
  langfuse-postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: langfuse
      POSTGRES_PASSWORD: password
    volumes:
      - postgres_data:/var/lib/postgresql/data

  langfuse:
    image: langfuse/langfuse:latest
    ports:
      - "3000:3000"
    environment:
      DATABASE_URL: postgresql://postgres:password@langfuse-postgres:5432/langfuse
      NEXTAUTH_SECRET: your_secret
      NEXTAUTH_URL: http://localhost:3000
    depends_on:
      - langfuse-postgres

  langfuse-redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

volumes:
  postgres_data:
```

### Production Setup

1. Используйте managed Langfuse cloud (https://cloud.langfuse.com)
2. Или self-host с Kubernetes
3. Настроить backups
4. Настроить monitoring и alerts
5. Настроить retention policy согласно requirements

## Performance Considerations

- **Batch operations:** Langfuse автоматически батчит запросы для оптимизации
- **Async processing:** Все операции async для non-blocking performance
- **Graceful degradation:** Ошибки в Langfuse не影响основное приложение
- **Memory usage:** Lazy loading traces для больших datasets
- **Network:** HTTP Basic Auth для security

## Security

- Credentials хранятся в environment variables
- REST API используют HTTP Basic Auth
- User isolation через workspace_id
- All traces связаны с user_id для audit trail
