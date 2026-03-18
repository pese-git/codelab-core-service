# CodeLab Core Service

Персональная мультиагентная AI платформа - Основной сервис

## Обзор

Полностью децентрализованная персональная мультиагентная AI платформа с полной изоляцией пользователей и двумя режимами работы (автоматический + прямой вызов). Каждый пользователь имеет свою изолированную AI команду с персональными агентами, семантической памятью и взаимодействием в реальном времени.

## Возможности

- **100% изоляция пользователей** - Каждый пользователь имеет только своих агентов, нет глобального состояния
- **Два режима работы**:
  - 🧠 **Автоматический** - Оркестратор планирует граф задач и координирует агентов
  - ⚡ **Прямой вызов** - Пользователь вызывает конкретного агента напрямую через `@agent_name` (1-2 сек)
- **Семантическая память** - Каждый агент имеет персональный Qdrant контекст с 1M+ векторов для RAG
- **Взаимодействие в реальном времени** - SSE события для мгновенных обновлений UI
- **Контроль исполнения** - Approval Manager контролирует опасные tools и планы перед выполнением

## Технологический стек

- **Runtime:** Python 3.12+ (async/await)
- **Менеджер пакетов:** uv
- **Фреймворк:** FastAPI
- **ORM:** SQLAlchemy 2.0 + asyncpg
- **Валидация:** Pydantic 2.0
- **Базы данных:** PostgreSQL, Redis, Qdrant
- **Инструменты разработки:** ruff (linter/formatter), mypy (type checker), pytest

## Быстрый старт

### Требования

- Python 3.12+
- Docker & Docker Compose
- uv менеджер пакетов (опционально, для локальной разработки)
- make (опционально, для удобных команд)

### Вариант 0: Автоматическая настройка (Самый быстрый)

Если у вас установлен `make`:

```bash
# Клонируйте репозиторий
git clone <repository-url>
cd codelab-core-service

# Автоматическая настройка всего проекта
make setup

# Отредактируйте .env и установите OPENAI_API_KEY
nano .env

# Перезапустите сервисы
make restart
```

Готово! API доступен на http://localhost:8000

Все доступные команды:
```bash
make help
```

### Вариант 1: Запуск с Docker Compose (Рекомендуется)

Это самый простой способ запустить проект со всеми зависимостями.

1. Клонируйте репозиторий:
```bash
git clone <repository-url>
cd codelab-core-service
```

2. Скопируйте файл окружения:
```bash
cp .env.example .env
```

3. Отредактируйте `.env` и установите обязательные параметры:
```bash
# Обязательно установите:
OPENAI_API_KEY=sk-your-openai-api-key
JWT_SECRET_KEY=your-secret-key-change-in-production
```

4. Запустите все сервисы:

**Для разработки (только основные сервисы):**
```bash
docker-compose -f docker-compose.dev.yml up -d
```

**Для полного стека (с мониторингом):**
```bash
docker-compose up -d
```

5. Проверьте статус сервисов:
```bash
docker-compose ps
```

6. Просмотрите логи:
```bash
docker-compose logs -f app
```

Сервисы будут доступны по адресам:
- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/my/docs
- **Health Check**: http://localhost:8000/health
- **PostgreSQL**: localhost:5432
- **Redis**: localhost:6379
- **Qdrant**: http://localhost:6333
- **LiteLLM Proxy**: http://localhost:4000 (для управления LLM провайдерами)
- **Prometheus**: http://localhost:9090 (только в полном стеке)
- **Grafana**: http://localhost:3000 (только в полном стеке, admin/admin)
- **Jaeger**: http://localhost:16686 (только в полном стеке)

### Вариант 2: Локальная разработка

Для разработки с hot-reload и отладкой.

1. Установите uv (если еще не установлен):
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

2. Клонируйте репозиторий и установите зависимости:
```bash
git clone <repository-url>
cd codelab-core-service
uv pip install -e .
```

3. Скопируйте и настройте `.env`:
```bash
cp .env.example .env
# Отредактируйте .env и установите OPENAI_API_KEY и JWT_SECRET_KEY
```

4. Запустите только инфраструктурные сервисы:
```bash
docker-compose -f docker-compose.dev.yml up -d postgres redis qdrant
```

5. Выполните миграции базы данных:
```bash
alembic upgrade head
```

6. Инициализируйте seed data (опционально):
```bash
python scripts/init_db.py seed
```

7. Запустите приложение локально:
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API будет доступен по адресу http://localhost:8000

### Первый запуск и тестирование

1. Проверьте health endpoint:
```bash
curl http://localhost:8000/health
```

2. Сгенерируйте тестовый JWT токен:
```bash
# Используйте ID тестового пользователя из seed data
python scripts/generate_test_jwt.py <user_id>
```

3. Создайте своего первого агента:
```bash
curl -X POST http://localhost:8000/my/agents/ \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "assistant",
    "system_prompt": "You are a helpful AI assistant.",
    "model": "gpt-4-turbo-preview",
    "tools": [],
    "concurrency_limit": 3
  }'
```

### Управление базой данных

**Применить миграции:**
```bash
alembic upgrade head
```

**Создать новую миграцию:**
```bash
alembic revision --autogenerate -m "описание изменений"
```

**Откатить последнюю миграцию:**
```bash
alembic downgrade -1
```

**Инициализировать базу данных с seed data:**
```bash
python scripts/init_db.py init
```

**Только добавить seed data:**
```bash
python scripts/init_db.py seed
```

**Сбросить базу данных (ОСТОРОЖНО!):**
```bash
python scripts/init_db.py reset
```

### Остановка сервисов

**Остановить все сервисы:**
```bash
docker-compose down
```

**Остановить и удалить volumes (удалит все данные):**
```bash
docker-compose down -v
```

## Документация

### API документация

После запуска приложения, посетите:
- Swagger UI: `http://localhost:8000/my/docs`
- OpenAPI JSON: `http://localhost:8000/my/openapi.json`

### LLM провайдеры

Платформа поддерживает управление несколькими LLM провайдерами через единый интерфейс:

**Поддерживаемые провайдеры:**
- OpenAI (GPT-4, GPT-3.5)
- Anthropic (Claude 3)
- Google (Gemini)
- Cohere
- Azure OpenAI
- Другие провайдеры через LiteLLM

**Возможности:**
- ➕ Добавление нескольких провайдеров
- 🔄 Переключение между провайдерами для агентов
- ✅ Тестирование подключения
- 📊 Отслеживание использования и статистики
- 🔐 Безопасное хранение API ключей (не логируются, не хранятся в БД)
- 📝 Полный audit log всех операций

**REST API для управления провайдерами:**
```bash
# Добавить провайдер
POST /my/llm-providers

# Получить список провайдеров
GET /my/llm-providers

# Тестировать провайдер
POST /my/llm-providers/{id}/test

# Обновить конфигурацию
PATCH /my/llm-providers/{id}

# Удалить провайдер
DELETE /my/llm-providers/{id}

# Получить доступные типы провайдеров (публичный endpoint)
GET /llm-providers/types
```

Подробнее: [Управление LLM провайдерами](doc/litellm-providers-management.md)

### Tool Execution Tracing

Платформа поддерживает полное трейсирование исполнения инструментов (tools) с интеграцией в Langfuse для анализа производительности и качества.

**Возможности:**
- 📊 Полное трейсирование tool execution с nested spans (validation, risk assessment, approval, execution)
- 📈 Анализ метрик инструментов (success rate, latency percentiles, execution count)
- 🎯 Ранжирование инструментов по различным метрикам
- ✅ Quality feedback - оценка качества исполнения с комментариями
- 🔐 Безопасное хранение trace ID и метаданных
- ⚡ Graceful degradation - tool execution продолжается даже если Langfuse недоступен
- 🚀 Минимальный overhead (< 50ms per execution)

**REST API для аналитики:**
```bash
# Получить метрики инструментов
GET /api/traces/tools/metrics?workspace_id=<id>&tool_name=<name>&period_days=7

# Получить ранжирование инструментов
GET /api/traces/tools/ranking?workspace_id=<id>&metric=success_rate&limit=10

# Записать оценку качества
POST /api/traces/tools/score
{
  "trace_id": "trace-123",
  "score": 0.95,
  "name": "accuracy",
  "comment": "отличные результаты"
}
```

**Пример интеграции:**
```python
# Tool executor автоматически создает spans для всех инструментов
from app.core.tools.executor import ToolExecutor
from app.services.langfuse_integration import LangfuseIntegration

executor = ToolExecutor(langfuse_integration=langfuse)

# Выполнение инструмента автоматически трейсируется
result = await executor.execute_tool(
    tool_name="calculator",
    input_params={"expression": "2+2"},
    user_id="user-123",
    workspace_id="workspace-456"
)

# Spans автоматически отправляются в Langfuse с полной иерархией
# - root span (tool execution)
#   - validation span
#   - risk assessment span
#   - approval workflow span (если нужно)
#   - execution span
```

Подробнее: [Tool Execution Tracing документация](doc/tool-execution-tracing.md)

## Observability

Проект использует **Langfuse v4** для полного трейсинга LLM вызовов и агентных workflow'ов. OpenTelemetry полностью удалена (16 марта 2026).

### Конфигурация

**Environment переменные:**
```bash
LANGFUSE_ENABLED=true              # Включить/отключить трейсинг
LANGFUSE_PUBLIC_KEY=pk-...         # Public API key из Langfuse dashboard
LANGFUSE_SECRET_KEY=sk-...         # Secret API key из Langfuse dashboard
LANGFUSE_HOST=http://localhost:3000  # Langfuse server (http://localhost:3000 или https://cloud.langfuse.com)
LANGFUSE_DEBUG=false               # Debug режим для логирования
```

### Инструментированные компоненты

1. **Chat Endpoints** - трейсинг сообщений пользователя ([`send_project_message`](app/routes/project_chat.py:195-196))
   - Декоратор: `@observe(name="ChatMessage")`
   - Метаданные: user_id, project_id, tags

2. **Contextual Agent** - трейсинг выполнения агента ([`ContextualAgent.execute`](app/agents/contextual_agent.py:147-148))
   - Декоратор: `@observe(name="Executor")`
   - Автоматический захват LLM вызовов через `langfuse.openai.AsyncOpenAI`
   - Включает: context retrieval, LLM calls, tool execution

3. **Tool Executor** - трейсинг выполнения инструментов ([`app/core/tools/executor.py`](app/core/tools/executor.py:73-74,100-101))
   - Декоратор: `@observe(as_type="tool")`
   - Каждый инструмент логируется отдельным span

### Как это работает

```
Chat Endpoint (@observe)
├─ Update metadata (user_id, project_id)
├─ Agent Executor (@observe)
│  ├─ Context retrieval (Qdrant)
│  ├─ LLM Call (langfuse.openai.AsyncOpenAI wrapper)
│  │  └─ Автоматический LLM span
│  └─ Tool Execution (@observe)
│     ├─ Tool 1
│     └─ Tool 2
└─ All traces sent to Langfuse (async batch)
```

### Просмотр traces

- **Langfuse Web UI:** http://localhost:3000 или https://cloud.langfuse.com
- **Фильтрация:** по user_id, session_id, tags, timestamps
- **Анализ:** spans hierarchy, latency, tokens, costs
- **Метаданные:** полный контекст каждого trace

### Graceful Degradation

Приложение продолжает работу если Langfuse недоступен:
- LANGFUSE_ENABLED=false → без трейсинга
- Отсутствуют API ключи → без трейсинга  
- Langfuse server down → без трейсинга и задержек
- Ошибка при трейсинге → логируется, но не влияет на обработку

### Подробнее

- [Langfuse Integration спецификация](openspec/specs/langfuse-integration/spec.md) - архитектура и требования
- [LLM Call Tracing спецификация](openspec/specs/llm-call-tracing/spec.md) - как работает автоматический захват LLM
- [Agent Workflow Tracing спецификация](openspec/specs/agent-workflow-tracing/spec.md) - структура traces для workflows
- [Observability Current State](openspec/specs/observability-current-state/spec.md) - полный обзор текущей реализации

### Руководства

- [📖 Руководство по настройке и запуску](doc/getting-started/setup-guide.md) - Полная инструкция по установке, настройке и решению проблем
- [🔌 Интеграция с LiteLLM](doc/integrations/litellm-integration.md) - Использование собственного LLM прокси вместо OpenAI API
- [🔐 Управление LLM провайдерами](doc/integrations/litellm-providers-management.md) - Добавление и управление провайдерами через REST API (OpenAI, Claude, Azure, Cohere и др.)
- [🎨 Gradio UI клиент](scripts/GRADIO_CLIENT.md) - Веб-интерфейс для тестирования API
- [🔧 REST API спецификация](doc/api/rest-api.md) - Детальное описание всех endpoints
- [📡 SSE Event Streaming](doc/api/sse-event-streaming.md) - Работа с событиями в реальном времени
- [🧪 Тестирование](tests/README.md) - Запуск и написание тестов

## Структура проекта

```
codelab-core-service/
├── app/
│   ├── agents/              # Управление агентами + ContextualAgent
│   ├── core/                # Agent Bus, Orchestrator, Approval Manager
│   ├── middleware/          # Middleware изоляции пользователей
│   ├── models/              # SQLAlchemy ORM модели
│   ├── routes/              # FastAPI endpoints
│   ├── schemas/             # Pydantic модели
│   ├── vectorstore/         # Интеграция с Qdrant
│   ├── config.py            # Конфигурация приложения
│   ├── database.py          # Настройка базы данных
│   ├── main.py              # FastAPI приложение
│   ├── redis_client.py      # Redis клиент
│   └── qdrant_client.py     # Qdrant клиент
├── migrations/              # Alembic миграции
├── tests/                   # Тесты
├── docker-compose.yml       # Docker Compose конфигурация
├── Dockerfile               # Docker образ
├── pyproject.toml           # Зависимости проекта
└── README.md                # Этот файл
```

## Разработка

### Качество кода

Форматирование кода:
```bash
ruff format .
```

Проверка кода:
```bash
ruff check .
```

Проверка типов:
```bash
mypy app/
```

### Тестирование

Запуск тестов:
```bash
pytest
```

Запуск тестов с покрытием:
```bash
pytest --cov=app --cov-report=html
```

### Миграции базы данных

Создать новую миграцию:
```bash
alembic revision --autogenerate -m "описание"
```

Применить миграции:
```bash
alembic upgrade head
```

Откатить миграцию:
```bash
alembic downgrade -1
```

## Примеры API

### Создание агента

```bash
curl -X POST http://localhost:8000/my/agents/ \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "coder",
    "system_prompt": "Вы эксперт Python разработчик...",
    "model": "gpt-4-turbo-preview",
    "tools": ["code_executor", "file_reader"],
    "concurrency_limit": 3
  }'
```

### Создание чат-сессии

```bash
curl -X POST http://localhost:8000/my/chat/sessions/ \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### Отправка сообщения (прямой режим)

```bash
curl -X POST http://localhost:8000/my/chat/{session_id}/message/ \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Исправь баг в auth.py",
    "target_agent": "coder"
  }'
```

## Мониторинг

- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000` (admin/admin)

## Архитектура

Ключевые архитектурные принципы:
- **Изоляция пользователей** - Middleware-based изоляция на всех `/my/*` endpoints
- **Per-Agent контекст** - Каждый агент имеет свою Qdrant коллекцию
- **Agent Bus** - asyncio.Queue для каждого агента для координации задач
- **Два режима чата** - Прямые вызовы обходят оркестратор для скорости

## Лицензия

См. файл LICENSE для деталей.

## Вклад в проект

1. Форкните репозиторий
2. Создайте feature ветку
3. Внесите изменения
4. Запустите тесты и линтинг
5. Отправьте pull request

## Поддержка

Для вопросов и проблем, пожалуйста, создайте issue на GitHub.
