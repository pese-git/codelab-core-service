# Анализ логов сервиса codelab-core-service

**Дата логов:** 2026-03-14 18:27:02 - 18:31:43  
**Версия сервиса:** 0.1.0  
**Окружение:** development

## 📊 Резюме

Сервис успешно запустился и функционирует, но имеет **8 критических проблем**, требующих исправления.

---

## 🔴 Критические проблемы

### 1. **FastAPI Deprecation Warnings - параметр `regex` устарел**

**Файл:** `/app/app/routes/traces.py`  
**Строки:** 34, 35, 215, 477

```
FastAPIDeprecationWarning: `regex` has been deprecated, please use `pattern` instead
```

**Что нужно сделать:**
- Заменить параметр `regex="..."` на `pattern="..."`в Query параметрах

**Пример:**
```python
# ❌ Текущий код
order_by: str = Query("created_at", regex="^(created_at|duration)$")

# ✅ Исправленный код
order_by: str = Query("created_at", pattern="^(created_at|duration)$")
```

**Затронутые параметры:**
- `order_by` (строка 34)
- `order_direction` (строка 35)
- `period` (строка 215)
- `metric` (строка 477)

---

### 2. **Redis Authentication Failed - "Authentication required"**

**Проявление:** Множественные ошибки при работе с Redis кэшем:
```
redis_cache_error agent_id=... error='Authentication required.'
Failed to buffer event: Authentication required.
Failed to retrieve buffered events: Authentication required.
```

**Причина:** 
- Redis требует аутентификацию, но приложение не передаёт пароль/токен
- Или Redis не запущен/недоступен

**Время первого возникновения:** 18:30:18.014

**Последствия:**
- Ошибки кэширования агентов
- Неудача буферизации событий (3 раза)
- Невозможность восстановления буферизированных событий

---

### 3. **Invalid Embedding Model Name**

**Ошибка:**
```
embedding_failed_using_fallback
error='Error code: 400 - {'error': {'message': "Invalid model name passed in model=openrouter/openai/text-embedding-3-small. Call `/v1/models` to view available models for your key.'"}}'
```

**Время первого возникновения:** 18:30:40.342

**Причины:**
- Модель `openrouter/openai/text-embedding-3-small` не доступна через LiteLLM
- API ключ OpenRouter не имеет доступа к этой модели
- Неправильная конфигурация провайдера LLM

**Следствие:** Поиск контекста (RAG) работает с резервной стратегией, что может снизить качество результатов

---

### 4. **Qdrant Insecure Connection Warning**

**Ошибка:**
```
UserWarning: Api key is used with an insecure connection.
_qdrant_client = AsyncQdrantClient(...)
```

**Время:** 18:30:17.956

**Проблема:** Используется API ключ без шифрования (HTTP вместо HTTPS)

**Решение:** Использовать HTTPS для подключения к Qdrant

---

### 5. **OpenTelemetry Export Timeouts**

**Ошибки:**
```
Transient error Internal Server Error encountered while exporting span batch, retrying in 1.10s
Failed to export span batch code: None, reason: HTTPConnectionPool(host='langfuse-web', port=3000): Read timed out. (read timeout=0.04837679...)
```

**Время первого возникновения:** 18:30:44.439

**Проблемы:**
- Langfuse веб-интерфейс медленный или перегруженный
- Timeout установлен слишком низко (0.048 сек)
- Сетевые задержки между сервисами

**Следствие:** Traces не экспортируются правильно в Langfuse

---

### 6. **OpenTelemetry Span Lifecycle Issues**

**Ошибки (в конце обработки сообщения):**
```
Setting attribute on ended span.
Tried calling _add_event on an ended span.
```

**Время:** 18:30:57.023

**Причина:** Попытка добавить данные на уже завершённый span

**Проблема:** Race condition в коде обработки сообщений - span завершается до того, как все данные добавлены

---

### 7. **Missing /metrics Endpoint**

**Ошибка:**
```
INFO:     172.18.0.7:53178 - "GET /metrics HTTP/1.1" 404 Not Found
```

**Время:** Повторяется каждые ~30 секунд (18:27:23, 18:27:53, 18:28:23...)

**Проблема:** 
- Prometheus попытатися собрать метрики с `/metrics`
- Endpoint не реализован или не зарегистрирован

**Рекомендация:** Добавить обработчик `/metrics` с Prometheus-совместимым форматом

---

### 8. **Message Processing - Event Buffering Failures**

**Множественные ошибки при обработке сообщения:**
```
Failed to buffer event: Authentication required.  (x3)
Message processed successfully: ... (но с потерей событий)
```

**Время:** 18:30:57.018, 18:30:57.023, 18:31:02.004

**Проблема:** 
- События не сохраняются в буфер из-за Redis ошибок
- Утеря данных о потоке обработки сообщения
- Event streaming клиентам может не получить все события

---

## ⚠️ Предупреждения (non-critical)

1. **Trace Dropping** - спаны с именами `GET /health`, `GET /metrics` постоянно отбрасываются фильтром `should_export_span`
   - Нормально для health-checks, но может скрывать реальные проблемы

2. **Multiple Concurrent Sessions** 
   - Множество параллельных запросов от пользователя
   - Нормально, но показывает активное использование

---

## ✅ Что работает хорошо

1. ✅ Базовая инициализация приложения
2. ✅ Подключение к PostgreSQL и выполнение миграций
3. ✅ Инициализация интеграций (OpenTelemetry, Langfuse, Qdrant)
4. ✅ Регистрация агентов в workspace
5. ✅ Обработка HTTP запросов (возвращаются 200 OK)
6. ✅ Работа с chat sessions и messaging
7. ✅ Выполнение LLM запросов (успешно получены ответы)
8. ✅ SSE streaming для real-time событий

---

## 📋 План исправлений (по приоритету)

| № | Проблема | Приоритет | Файл | Действие |
|---|----------|-----------|------|----------|
| 1 | Redis auth | 🔴 CRITICAL | `.env` / `config.py` | Добавить пароль Redis в конфиг |
| 2 | FastAPI regex → pattern | 🔴 CRITICAL | `app/routes/traces.py` | Заменить 4 параметра |
| 3 | Embedding model | 🔴 CRITICAL | `.env` / `config.py` | Проверить конфиг LLM провайдера |
| 4 | OTEL timeout | 🟠 HIGH | `config.py` | Увеличить timeout экспорта span'ов |
| 5 | Qdrant HTTPS | 🟠 HIGH | `.env` / `config.py` | Использовать HTTPS для Qdrant |
| 6 | /metrics endpoint | 🟠 HIGH | `app/routes/` или `app/main.py` | Добавить Prometheus metrics |
| 7 | Span lifecycle race condition | 🟠 HIGH | `app/routes/project_chat.py` | Исправить порядок операций со span'ами |
| 8 | Event buffering | 🟠 HIGH | `app/services/streaming.py` | Добавить fallback без Redis |

---

## 🔍 Детальный анализ критичных функций

### Обработка сообщения (Working, но с потерей событий)

**Timeline:**
- 18:30:40.007 - POST сообщение: "привет"
- 18:30:40.026 - Trace создан
- 18:30:40.342 - Ошибка embedding (fallback used)
- 18:30:40.358 - Начало выполнения агента
- 18:30:51.953 - LLM generation завершён (~11.5 сек)
- 18:30:57.014 - 3 ошибки буферизации события
- 18:30:57.024 - Сообщение обработано (но события потеряны)

**Результат:** ✅ Ответ получен, ❌ События не сохранены

---

## 🎯 Рекомендации по немедленному исправлению

1. **Прямо сейчас:**
   ```bash
   # Проверить конфиг Redis
   grep -r "REDIS_PASSWORD" .env*
   
   # Проверить LLM конфиг
   grep -r "EMBEDDING_MODEL" .env*
   ```

2. **В app/routes/traces.py** - заменить все `regex=` на `pattern=`

3. **В docker-compose.yml** - убедиться, что Redis запущен с паролем или без требования auth

4. **Добавить monitoring** - мониторить Redis connection pool и embedding API

---

## 📊 Статистика из логов

| Метрика | Значение |
|---------|----------|
| Время запуска сервиса | ~11 сек (с 18:27:02 до 18:27:13) |
| Время обработки сообщения | ~11.6 сек |
| Количество health checks | 6+ за 4 минуты |
| Количество /metrics запросов (404) | 6+ за 4 минуты |
| Redis auth failures | 5+ |
| Embedding failures | 6+ |
| Event buffer failures | 3+ |
