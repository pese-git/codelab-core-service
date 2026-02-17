# Тесты REST API

## 🚀 Быстрый старт

### Запуск всех тестов
```bash
uv run pytest tests/ -v
```

### Запуск конкретного файла
```bash
uv run pytest tests/test_chat_api.py -v
```

### Запуск с покрытием кода
```bash
uv run pytest tests/ --cov=app --cov-report=html
```

### Запуск без coverage (быстрее)
```bash
uv run pytest tests/ -v --no-cov
```

## 📁 Структура тестов

```
tests/
├── __init__.py              # Инициализация пакета
├── conftest.py              # Фикстуры и конфигурация pytest
├── test_chat_api.py         # Тесты для Chat Session API
├── TEST_REPORT.md           # Детальный отчет о тестировании
└── README.md                # Этот файл
```

## 🧪 Тестовые наборы

### 1. TestChatSessionAPI
Тесты CRUD операций для chat sessions:
- Создание сессии
- Список сессий
- Удаление сессии
- User isolation

### 2. TestChatMessagesAPI
Тесты для работы с сообщениями:
- Получение истории сообщений
- Отправка сообщений
- Пагинация
- Валидация

### 3. TestChatAPIIntegration
Интеграционные тесты полных сценариев:
- Полный workflow чата
- Изоляция между сессиями

## 📊 Текущий статус

**Последний запуск:** 2026-02-12

- ✅ **11 тестов пройдено** (61%)
- ❌ **7 тестов провалено** (39%)
- 📝 **Детали:** См. [`TEST_REPORT.md`](TEST_REPORT.md)

### Основные проблемы
1. ✅ ~~SQLAlchemy lazy loading в async context~~ - ИСПРАВЛЕНО (используются подзапросы)
2. ✅ ~~Требуется исправление в [`app/routes/chat.py`](../app/routes/chat.py)~~ - УЖЕ ИСПРАВЛЕНО

## 🔧 Фикстуры

### Базовые фикстуры (conftest.py)

- `test_engine` - Тестовая база данных (SQLite in-memory)
- `db_session` - Асинхронная сессия БД
- `test_user` - Тестовый пользователь
- `test_agent` - Тестовый агент
- `test_jwt_token` - JWT токен для аутентификации
- `auth_headers` - HTTP заголовки с авторизацией
- `client` - Асинхронный HTTP клиент

### Использование фикстур

```python
@pytest.mark.asyncio
async def test_example(
    client: AsyncClient,
    auth_headers: dict,
    test_user: User,
):
    response = await client.get(
        "/my/chat/sessions/",
        headers=auth_headers,
    )
    assert response.status_code == 200
```

## 📝 Написание новых тестов

### Шаблон теста

```python
import pytest
from httpx import AsyncClient

class TestMyFeature:
    """Test my feature."""
    
    @pytest.mark.asyncio
    async def test_something(
        self,
        client: AsyncClient,
        auth_headers: dict,
    ):
        """Test something specific."""
        # Arrange
        data = {"key": "value"}
        
        # Act
        response = await client.post(
            "/my/endpoint/",
            headers=auth_headers,
            json=data,
        )
        
        # Assert
        assert response.status_code == 200
        assert response.json()["key"] == "value"
```

## 🎯 Best Practices

1. **Используйте async/await** для всех тестов API
2. **Изолируйте тесты** - каждый тест должен быть независимым
3. **Используйте фикстуры** для переиспользования кода
4. **Тестируйте edge cases** - не только happy path
5. **Проверяйте статус коды** и структуру ответов
6. **Документируйте тесты** - используйте docstrings

## 🐛 Отладка тестов

### Запуск одного теста
```bash
uv run pytest tests/test_chat_api.py::TestChatSessionAPI::test_create_session_success -v
```

### Показать print statements
```bash
uv run pytest tests/ -v -s
```

### Остановиться на первой ошибке
```bash
uv run pytest tests/ -v -x
```

### Показать полный traceback
```bash
uv run pytest tests/ -v --tb=long
```

### Запустить только проваленные тесты
```bash
uv run pytest tests/ --lf
```

## 📚 Дополнительные ресурсы

- [Pytest Documentation](https://docs.pytest.org/)
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io/)
- [HTTPX Testing](https://www.python-httpx.org/advanced/#calling-into-python-web-apps)
- [FastAPI Testing](https://fastapi.tiangolo.com/tutorial/testing/)

## 🔗 Связанные файлы

- API Routes: [`app/routes/chat.py`](../app/routes/chat.py)
- Schemas: [`app/schemas/chat.py`](../app/schemas/chat.py)
- Models: [`app/models/chat_session.py`](../app/models/chat_session.py)
- Config: [`pyproject.toml`](../pyproject.toml) (секция `[tool.pytest.ini_options]`)
