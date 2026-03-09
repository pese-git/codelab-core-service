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

### Руководства

- [📖 Руководство по настройке и запуску](doc/setup-guide.md) - Полная инструкция по установке, настройке и решению проблем
- [🔌 Интеграция с LiteLLM](doc/litellm-integration.md) - Использование собственного LLM прокси вместо OpenAI API
- [🔐 Управление LLM провайдерами](doc/litellm-providers-management.md) - Добавление и управление провайдерами через REST API (OpenAI, Claude, Azure, Cohere и др.)
- [🎨 Gradio UI клиент](scripts/GRADIO_CLIENT.md) - Веб-интерфейс для тестирования API
- [🔧 REST API спецификация](doc/rest-api.md) - Детальное описание всех endpoints
- [📡 SSE Event Streaming](doc/sse-event-streaming.md) - Работа с событиями в реальном времени
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
