# Langfuse Integration Fix Report

## Проблема

Сервис не отправлял данные в Langfuse при запуске в Docker Compose. Данные были «черной дырой» — инициализация происходила, но трейсы не попадали в систему observability.

## Причины

### 1. **Ленивая инициализация Langfuse (ГЛАВНАЯ ПРИЧИНА)**

В файле [`app/services/langfuse_integration.py`](app/services/langfuse_integration.py:419) Langfuse инициализировался лениво через глобальную переменную:

```python
def get_langfuse() -> LangfuseIntegration:
    global _langfuse_instance
    if _langfuse_instance is None:
        _langfuse_instance = LangfuseIntegration()
    return _langfuse_instance
```

Это означало, что инициализация происходила только при первом вызове, а не при запуске приложения. **Если никто не вызывал `get_langfuse()` при старте, интеграция вообще не инициализировалась.**

### 2. **Отсутствие инициализации при запуске приложения**

В файле [`app/main.py`](app/main.py:42) функция `lifespan()` не инициализировала Langfuse. Сравните с инициализацией других компонентов:

```python
# В lifespan() инициализировались:
- LiteLLMClient()  # ✓ явная инициализация
- init_db()        # ✓ явная инициализация  
- get_worker_space_manager()  # ✓ явная инициализация

# Но НЕ инициализировалась:
- get_langfuse()   # ✗ отсутствовало!
```

### 3. **Отсутствие flush данных при shutdown**

Langfuse работает асинхронно и буферизирует данные. При shutdown контейнера данные могли теряться, если не было явного `flush()`.

### 4. **Неполная конфигурация контейнера**

В `docker-compose.yml` контейнер `app` не имел явно установленных переменных окружения:
- `LANGFUSE_ENABLED` 
- `LANGFUSE_PUBLIC_KEY`
- `LANGFUSE_SECRET_KEY`

Хотя они были в `.env`, явная передача гарантирует, что значения будут доступны.

### 5. **Использование structlog вместо app logger**

В файле [`app/services/langfuse_integration.py`](app/services/langfuse_integration.py:22) использовался `structlog` напрямую:

```python
import structlog
struct_logger = structlog.get_logger(__name__)
```

Нужно было использовать унифицированный logger из [`app/logging_config.py`](app/logging_config.py:40).

## Решение

### 1. Добавлена инициализация Langfuse в `lifespan()` 

**Файл: [`app/main.py`](app/main.py:50-56)**

```python
# Initialize Langfuse integration (LLM observability)
langfuse = get_langfuse()
if langfuse.enabled:
    logger.info("langfuse_initialized", host=settings.langfuse_host)
else:
    logger.info("langfuse_disabled")
```

### 2. Добавлен graceful shutdown Langfuse

**Файл: [`app/main.py`](app/main.py:90-92)**

```python
# Flush Langfuse data before shutdown
langfuse.shutdown()
logger.info("langfuse_shutdown_completed")
```

Метод `shutdown()` в [`app/services/langfuse_integration.py`](app/services/langfuse_integration.py:349) гарантирует отправку всех буферизованных данных перед завершением.

### 3. Добавлены явные переменные окружения в docker-compose.yml

**Файл: [`docker-compose.yml`](docker-compose.yml:348-351)**

```yaml
environment:
  LANGFUSE_ENABLED: "true"
  LANGFUSE_HOST: http://langfuse-web:3000
  LANGFUSE_PUBLIC_KEY: pk_defaultkey
  LANGFUSE_SECRET_KEY: sk_defaultsecret
```

### 4. Заменен structlog на app logger

**Файл: [`app/services/langfuse_integration.py`](app/services/langfuse_integration.py:1-24)**

```python
from app.logging_config import get_logger  # ← добавлено

# Старый код:
# struct_logger = structlog.get_logger(__name__)

# Новый код:
struct_logger = get_logger(__name__)
```

## Результат

После исправлений при запуске контейнера в логах видно:

```
Startup: Langfuse tracer successfully initialized | public_key=pk_defaultkey | base_url=http://langfuse-web:3000 | environment=default | sample_rate=1.0 | media_threads=1
[info] langfuse_initialized host=http://langfuse-web:3000
```

✓ Langfuse инициализируется при запуске приложения  
✓ Данные буферизуются и отправляются асинхронно  
✓ При shutdown все буферизованные данные flush'ятся перед завершением  
✓ Сервис готов отправлять трейсы в Langfuse  

## Проверка

Для проверки что данные попадают в Langfuse:

1. **В браузере откройте:** http://localhost:3001
2. **Логин:** admin@langfuse.local / langfuse123
3. **Перейдите в:** Projects → Default Project → Traces
4. **Запустите запрос к сервису:**
   ```bash
   curl http://localhost:8000/my/projects/YOUR_PROJECT_ID/agents
   ```
5. **Проверьте что трейс появился в Langfuse UI**

## Рекомендации на продакшен

1. **Используйте отдельные ключи** вместо `pk_defaultkey` и `sk_defaultsecret`
2. **Установите правильный `LANGFUSE_HOST`** (URL вашего Langfuse сервера)
3. **Настройте Sample Rate** если нужно трассировать не все запросы:
   ```yaml
   # В docker-compose.yml для langfuse-web
   LANGFUSE_SAMPLE_RATE: "0.1"  # 10% запросов
   ```
4. **Включите retention policy** для очистки старых данных
5. **Мониторьте** размер базы ClickHouse для Langfuse

## Файлы которые были изменены

- [`app/main.py`](app/main.py) — инициализация и shutdown Langfuse
- [`docker-compose.yml`](docker-compose.yml) — явные переменные окружения
- [`app/services/langfuse_integration.py`](app/services/langfuse_integration.py) — замена logger
