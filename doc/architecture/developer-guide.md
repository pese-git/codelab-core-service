# Руководство разработчика

## Содержание
- [Начало работы](#начало-работы)
- [Структура проекта](#структура-проекта)
- [Стандарты кодирования](#стандарты-кодирования)
- [Тестирование](#тестирование)
- [Отладка](#отладка)
- [Добавление новых функций](#добавление-новых-функций)
- [Best Practices](#best-practices)

---

## Начало работы

### Настройка окружения разработки

```bash
# 1. Клонирование репозитория
git clone https://github.com/your-org/codelab-core-service.git
cd codelab-core-service

# 2. Установка uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 3. Установка зависимостей
uv pip install -e ".[dev]"

# 4. Настройка pre-commit hooks
pre-commit install

# 5. Копирование .env
cp .env.example .env
# Отредактируйте .env и установите OPENAI_API_KEY

# 6. Запуск инфраструктуры
docker-compose -f docker-compose.dev.yml up -d postgres redis qdrant

# 7. Применение миграций
alembic upgrade head

# 8. Создание тестовых данных
python scripts/init_db.py seed
```

### IDE Setup

#### VS Code

Рекомендуемые расширения (`.vscode/extensions.json`):
```json
{
  "recommendations": [
    "ms-python.python",
    "ms-python.vscode-pylance",
    "charliermarsh.ruff",
    "ms-python.mypy-type-checker",
    "tamasfe.even-better-toml",
    "redhat.vscode-yaml"
  ]
}
```

Настройки (`.vscode/settings.json`):
```json
{
  "python.defaultInterpreterPath": ".venv/bin/python",
  "python.linting.enabled": true,
  "python.linting.mypyEnabled": true,
  "python.formatting.provider": "none",
  "[python]": {
    "editor.defaultFormatter": "charliermarsh.ruff",
    "editor.formatOnSave": true,
    "editor.codeActionsOnSave": {
      "source.organizeImports": true
    }
  }
}
```

#### PyCharm

1. Открыть проект
2. Settings → Project → Python Interpreter → Add Interpreter
3. Выбрать существующий venv или создать новый
4. Settings → Tools → Python Integrated Tools → Testing → pytest
5. Settings → Editor → Code Style → Python → Set from... → PEP 8

---

## Структура проекта

```
codelab-core-service/
├── app/                          # Основной код приложения
│   ├── __init__.py
│   ├── main.py                   # FastAPI приложение
│   ├── config.py                 # Конфигурация
│   ├── database.py               # Database setup
│   ├── logging_config.py         # Logging setup
│   ├── redis_client.py           # Redis client
│   ├── qdrant_client.py          # Qdrant client
│   │
│   ├── agents/                   # Управление агентами
│   │   ├── __init__.py
│   │   ├── contextual_agent.py   # Агент с RAG
│   │   └── manager.py            # CRUD операции
│   │
│   ├── core/                     # Ядро системы
│   │   ├── __init__.py
│   │   ├── agent_bus.py          # Координация задач
│   │   └── sse_manager.py        # SSE события
│   │
│   ├── middleware/               # Middleware
│   │   ├── __init__.py
│   │   └── user_isolation.py     # Изоляция пользователей
│   │
│   ├── models/                   # SQLAlchemy модели
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── user_agent.py
│   │   ├── user_orchestrator.py
│   │   ├── chat_session.py
│   │   ├── message.py
│   │   ├── task.py
│   │   └── approval_request.py
│   │
│   ├── routes/                   # API endpoints
│   │   ├── __init__.py
│   │   ├── health.py
│   │   ├── agents.py
│   │   ├── chat.py
│   │   └── sse.py
│   │
│   ├── schemas/                  # Pydantic схемы
│   │   ├── __init__.py
│   │   ├── agent.py
│   │   ├── chat.py
│   │   ├── event.py
│   │   ├── task.py
│   │   ├── approval.py
│   │   └── error.py
│   │
│   └── vectorstore/              # Векторное хранилище
│       ├── __init__.py
│       └── agent_context_store.py
│
├── migrations/                   # Alembic миграции
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│
├── tests/                        # Тесты
│   ├── __init__.py
│   ├── conftest.py              # Pytest fixtures
│   ├── test_agents_api.py
│   ├── test_chat_api.py
│   └── test_sse.py
│
├── scripts/                      # Утилиты
│   ├── init_db.py               # Инициализация БД
│   ├── generate_test_jwt.py     # Генерация JWT
│   └── gradio_ui.py             # Тестовый UI
│
├── doc/                          # Документация
│   ├── architecture/            # Архитектурная документация
│   ├── rest-api.md
│   ├── sse-event-streaming.md
│   └── setup-guide.md
│
├── .env.example                  # Пример конфигурации
├── .gitignore
├── alembic.ini                   # Alembic конфигурация
├── docker-compose.yml            # Production stack
├── docker-compose.dev.yml        # Development stack
├── Dockerfile
├── Makefile                      # Команды разработки
├── pyproject.toml               # Зависимости и настройки
└── README.md
```

---

## Стандарты кодирования

### Python Style Guide

Проект следует **PEP 8** с некоторыми дополнениями:

#### Форматирование

Используется **Ruff** для форматирования и линтинга:

```bash
# Форматирование кода
ruff format .

# Проверка кода
ruff check .

# Автоисправление
ruff check --fix .
```

#### Настройки Ruff

```toml
[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = [
    "E",   # pycodestyle errors
    "W",   # pycodestyle warnings
    "F",   # pyflakes
    "I",   # isort
    "B",   # flake8-bugbear
    "C4",  # flake8-comprehensions
    "UP",  # pyupgrade
]
```

### Type Hints

Все функции должны иметь type hints:

```python
# ✅ Правильно
async def create_agent(
    config: AgentConfig,
    user_id: UUID,
    db: AsyncSession
) -> AgentResponse:
    ...

# ❌ Неправильно
async def create_agent(config, user_id, db):
    ...
```

### Docstrings

Используется Google style docstrings:

```python
def complex_function(param1: str, param2: int) -> dict[str, Any]:
    """
    Brief description of function.
    
    Longer description if needed. Can span multiple lines
    and include examples.
    
    Args:
        param1: Description of param1
        param2: Description of param2
        
    Returns:
        Dictionary containing result data
        
    Raises:
        ValueError: If param2 is negative
        
    Example:
        >>> result = complex_function("test", 42)
        >>> print(result["status"])
        "success"
    """
    ...
```

### Именование

```python
# Модули и пакеты: lowercase_with_underscores
import user_agent
from app.core import agent_bus

# Классы: PascalCase
class AgentManager:
    pass

# Функции и переменные: lowercase_with_underscores
def create_agent():
    user_id = get_user_id()

# Константы: UPPERCASE_WITH_UNDERSCORES
MAX_RETRIES = 3
DEFAULT_TIMEOUT = 30

# Приватные: _leading_underscore
def _internal_helper():
    pass

# Type aliases: PascalCase
AgentID = UUID
ConfigDict = dict[str, Any]
```

### Imports

Порядок импортов (автоматически через Ruff):

```python
# 1. Стандартная библиотека
import asyncio
from typing import Any
from uuid import UUID

# 2. Сторонние библиотеки
from fastapi import APIRouter, Depends
from sqlalchemy import select

# 3. Локальные импорты
from app.config import settings
from app.models.user_agent import UserAgent
```

---

## Тестирование

### Структура тестов

```python
# tests/test_agents_api.py
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_create_agent(client: AsyncClient, auth_headers: dict):
    """Test agent creation endpoint."""
    response = await client.post(
        "/my/agents/",
        headers=auth_headers,
        json={
            "name": "test_agent",
            "system_prompt": "You are a test agent",
            "model": "gpt-4-turbo-preview",
            "tools": [],
            "concurrency_limit": 3
        }
    )
    
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "test_agent"
    assert data["status"] == "ready"
```

### Fixtures

```python
# tests/conftest.py
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

@pytest.fixture
async def db_session() -> AsyncSession:
    """Provide database session for tests."""
    async with get_test_db() as session:
        yield session

@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncClient:
    """Provide HTTP client for API tests."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

@pytest.fixture
def auth_headers(test_user_id: UUID) -> dict:
    """Provide authentication headers."""
    token = generate_test_jwt(test_user_id)
    return {"Authorization": f"Bearer {token}"}
```

### Запуск тестов

```bash
# Все тесты
pytest

# С покрытием
pytest --cov=app --cov-report=html

# Конкретный файл
pytest tests/test_agents_api.py

# Конкретный тест
pytest tests/test_agents_api.py::test_create_agent

# С выводом print
pytest -s

# Параллельно (требует pytest-xdist)
pytest -n auto
```

### Моки

```python
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_agent_with_mock_llm():
    """Test agent with mocked LLM."""
    with patch("app.agents.contextual_agent.openai.AsyncOpenAI") as mock_openai:
        # Setup mock
        mock_client = AsyncMock()
        mock_client.chat.completions.create.return_value = AsyncMock(
            choices=[AsyncMock(message=AsyncMock(content="Mocked response"))]
        )
        mock_openai.return_value = mock_client
        
        # Test
        agent = ContextualAgent(...)
        result = await agent.execute("test message")
        
        assert result["success"] is True
        assert result["response"] == "Mocked response"
```

---

## Отладка

### Логирование

```python
from app.logging_config import get_logger

logger = get_logger(__name__)

# Структурированное логирование
logger.info(
    "agent_created",
    agent_id=str(agent.id),
    user_id=str(user_id),
    agent_name=agent.name
)

logger.error(
    "agent_execution_failed",
    agent_id=str(agent.id),
    error=str(e),
    exc_info=True  # Включить traceback
)
```

### Debugger

```python
# Встроенный debugger
import pdb; pdb.set_trace()

# Или ipdb (более удобный)
import ipdb; ipdb.set_trace()

# Или breakpoint() (Python 3.7+)
breakpoint()
```

### VS Code Debug Configuration

```json
// .vscode/launch.json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "FastAPI",
      "type": "python",
      "request": "launch",
      "module": "uvicorn",
      "args": [
        "app.main:app",
        "--reload",
        "--host", "0.0.0.0",
        "--port", "8000"
      ],
      "jinja": true,
      "justMyCode": false
    },
    {
      "name": "Pytest",
      "type": "python",
      "request": "launch",
      "module": "pytest",
      "args": ["-v"],
      "console": "integratedTerminal"
    }
  ]
}
```

### Профилирование

```python
# Memory profiling
from memory_profiler import profile

@profile
def memory_intensive_function():
    ...

# Time profiling
import cProfile
import pstats

profiler = cProfile.Profile()
profiler.enable()

# Your code here

profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats('cumulative')
stats.print_stats(10)
```

---

## Добавление новых функций

### Добавление нового endpoint

#### 1. Создать Pydantic схемы

```python
# app/schemas/feature.py
from pydantic import BaseModel, Field
from uuid import UUID

class FeatureRequest(BaseModel):
    """Request schema for feature."""
    name: str = Field(..., min_length=1, max_length=100)
    description: str = Field(..., min_length=1, max_length=1000)

class FeatureResponse(BaseModel):
    """Response schema for feature."""
    id: UUID
    name: str
    description: str
    created_at: datetime
```

#### 2. Создать SQLAlchemy модель

```python
# app/models/feature.py
from sqlalchemy import Column, String, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from app.models import Base

class Feature(Base):
    """Feature model."""
    __tablename__ = "features"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(String(1000), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Индексы
    __table_args__ = (
        Index("ix_features_user_id", "user_id"),
    )
```

#### 3. Создать миграцию

```bash
# Автогенерация миграции
alembic revision --autogenerate -m "add_features_table"

# Проверить сгенерированную миграцию
cat migrations/versions/xxx_add_features_table.py

# Применить миграцию
alembic upgrade head
```

#### 4. Создать route handler

```python
# app/routes/features.py
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.user_isolation import get_current_user_id
from app.models.feature import Feature
from app.schemas.feature import FeatureRequest, FeatureResponse

router = APIRouter(prefix="/my/features", tags=["features"])

@router.post("/", status_code=status.HTTP_201_CREATED, response_model=FeatureResponse)
async def create_feature(
    feature_request: FeatureRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> FeatureResponse:
    """Create new feature."""
    user_id = get_current_user_id(request)
    
    feature = Feature(
        user_id=user_id,
        name=feature_request.name,
        description=feature_request.description,
    )
    db.add(feature)
    await db.flush()
    
    return FeatureResponse(
        id=feature.id,
        name=feature.name,
        description=feature.description,
        created_at=feature.created_at,
    )

@router.get("/", response_model=list[FeatureResponse])
async def list_features(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> list[FeatureResponse]:
    """List all user features."""
    user_id = get_current_user_id(request)
    
    result = await db.execute(
        select(Feature).where(Feature.user_id == user_id)
    )
    features = result.scalars().all()
    
    return [
        FeatureResponse(
            id=f.id,
            name=f.name,
            description=f.description,
            created_at=f.created_at,
        )
        for f in features
    ]
```

#### 5. Зарегистрировать router

```python
# app/main.py
from app.routes import features

app.include_router(features.router)
```

#### 6. Написать тесты

```python
# tests/test_features_api.py
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_create_feature(client: AsyncClient, auth_headers: dict):
    """Test feature creation."""
    response = await client.post(
        "/my/features/",
        headers=auth_headers,
        json={
            "name": "Test Feature",
            "description": "Test description"
        }
    )
    
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Feature"

@pytest.mark.asyncio
async def test_list_features(client: AsyncClient, auth_headers: dict):
    """Test feature listing."""
    # Create feature first
    await client.post(
        "/my/features/",
        headers=auth_headers,
        json={"name": "Feature 1", "description": "Desc 1"}
    )
    
    # List features
    response = await client.get("/my/features/", headers=auth_headers)
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
```

### Добавление нового SSE события

```python
# 1. Добавить тип события в схему
# app/schemas/event.py
class SSEEventType(str, Enum):
    # ... существующие типы
    NEW_EVENT_TYPE = "new_event_type"

# 2. Отправить событие
from app.core.sse_manager import get_sse_manager

sse_manager = await get_sse_manager(redis)
await sse_manager.broadcast_event(
    session_id=session_id,
    event=SSEEvent(
        event_type=SSEEventType.NEW_EVENT_TYPE,
        payload={
            "key": "value",
            "data": "some data"
        },
        session_id=session_id,
    )
)
```

---

## Best Practices

### Асинхронное программирование

```python
# ✅ Правильно: использовать async/await
async def fetch_data():
    async with httpx.AsyncClient() as client:
        response = await client.get("https://api.example.com")
        return response.json()

# ❌ Неправильно: блокирующий вызов в async функции
async def fetch_data_bad():
    import requests
    response = requests.get("https://api.example.com")  # Блокирует!
    return response.json()
```

### Обработка ошибок

```python
# ✅ Правильно: специфичные исключения
try:
    agent = await get_agent(agent_id)
    if not agent:
        raise HTTPException(
            status_code=404,
            detail=f"Agent {agent_id} not found"
        )
except ValueError as e:
    logger.error("validation_error", error=str(e))
    raise HTTPException(status_code=422, detail=str(e))
except Exception as e:
    logger.error("unexpected_error", error=str(e), exc_info=True)
    raise HTTPException(status_code=500, detail="Internal server error")

# ❌ Неправильно: голый except
try:
    agent = await get_agent(agent_id)
except:  # Не делайте так!
    pass
```

### Database Sessions

```python
# ✅ Правильно: использовать dependency injection
@router.post("/agents/")
async def create_agent(
    config: AgentConfig,
    db: AsyncSession = Depends(get_db)  # DI
):
    agent = UserAgent(...)
    db.add(agent)
    await db.flush()  # Или commit
    return agent

# ✅ Правильно: явное управление транзакциями
async with get_db() as db:
    async with db.begin():
        # Операции с БД
        db.add(obj)
        # Автоматический commit при выходе
```

### Изоляция пользователей

```python
# ✅ Правильно: всегда фильтровать по user_id
result = await db.execute(
    select(UserAgent).where(
        UserAgent.id == agent_id,
        UserAgent.user_id == user_id  # Критично!
    )
)

# ❌ Неправильно: забыть фильтр user_id
result = await db.execute(
    select(UserAgent).where(UserAgent.id == agent_id)
)
```

### Валидация данных

```python
# ✅ Правильно: использовать Pydantic
class AgentConfig(BaseModel):
    name: str = Field(..., min_length=1, max_length=50, pattern=r"^[a-zA-Z0-9_]+$")
    concurrency_limit: int = Field(default=3, ge=1, le=10)
    
    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if v in RESERVED_NAMES:
            raise ValueError(f"Name '{v}' is reserved")
        return v
```

### Кэширование

```python
# ✅ Правильно: кэшировать часто используемые данные
async def get_agent_config(agent_id: UUID) -> AgentConfig:
    # Проверить кэш
    cache_key = f"agent:{agent_id}:config"
    cached = await redis.get(cache_key)
    if cached:
        return AgentConfig.model_validate_json(cached)
    
    # Загрузить из БД
    agent = await db.get(UserAgent, agent_id)
    config = AgentConfig(**agent.config)
    
    # Сохранить в кэш
    await redis.setex(cache_key, 300, config.model_dump_json())
    
    return config
```

### Логирование

```python
# ✅ Правильно: структурированное логирование
logger.info(
    "agent_created",
    agent_id=str(agent.id),
    user_id=str(user_id),
    agent_name=agent.name,
    model=agent.config.model
)

# ❌ Неправильно: строковое логирование
logger.info(f"Agent {agent.id} created for user {user_id}")
```

---

## Git Workflow

### Branching Strategy

```
main (production)
  ↑
develop (staging)
  ↑
feature/add-new-endpoint
feature/fix-bug-123
```

### Commit Messages

Следуем [Conventional Commits](https://www.conventionalcommits.org/):

```bash
# Формат
<type>(<scope>): <subject>

# Примеры
feat(agents): add agent deletion endpoint
fix(sse): fix memory leak in connection manager
docs(api): update API specification
test(chat): add tests for message sending
refactor(database): optimize query performance
chore(deps): update dependencies
```

### Pull Request Process

1. Создать feature branch
2. Написать код и тесты
3. Запустить линтеры и тесты
4. Создать PR с описанием изменений
5. Code review
6. Merge после approval

---

## Полезные команды

```bash
# Разработка
make dev              # Запустить dev сервер
make test             # Запустить тесты
make lint             # Проверить код
make format           # Форматировать код
make type-check       # Проверить типы

# База данных
make db-upgrade       # Применить миграции
make db-downgrade     # Откатить миграцию
make db-reset         # Сбросить БД
make db-seed          # Создать тестовые данные

# Docker
make docker-build     # Собрать образ
make docker-up        # Запустить контейнеры
make docker-down      # Остановить контейнеры
make docker-logs      # Просмотр логов

# Очистка
make clean            # Очистить временные файлы
make clean-all        # Полная очистка
```

---

## Дополнительные ресурсы

### Документация
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy 2.0 Documentation](https://docs.sqlalchemy.org/en/20/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [Pytest Documentation](https://docs.pytest.org/)

### Внутренние ресурсы
- [Architecture Overview](./system-overview.md)
- [Component Details](./component-details.md)
- [API Specification](./api-specification.md)
- [Deployment Guide](./deployment-guide.md)

### Контакты
- Tech Lead: techlead@company.com
- Team Chat: #codelab-dev on Slack
- Issues: GitHub Issues
