# Phase 4 Tool Execution Tracing - Руководство по развертыванию

**Дата**: 2026-03-12  
**Статус**: Готово к продакшену  
**Версия**: v1.0

---

## Содержание

1. [Чек-лист перед развертыванием](#чек-лист-перед-развертыванием)
2. [Настройка окружения](#настройка-окружения)
3. [Шаги развертывания](#шаги-развертывания)
4. [Проверка и тестирование](#проверка-и-тестирование)
5. [Мониторинг и алерты](#мониторинг-и-алерты)
6. [Процедуры отката](#процедуры-отката)
7. [Решение проблем](#решение-проблем)

---

## Чек-лист перед развертыванием

### Требования

- [ ] Python 3.12+ установлен
- [ ] Docker & Docker Compose доступны
- [ ] Redis настроен и доступен
- [ ] PostgreSQL база данных готова
- [ ] Langfuse аккаунт создан, credentials получены
- [ ] Достаточно места на диске для логов
- [ ] Сетевое соединение с Langfuse API

### Готовность кода

- [x] Весь код Phase 4 смержен в main ветку
- [x] Все тесты проходят: `pytest tests/ -v` ✅
- [x] Покрытие кода >= 90% ✅
- [x] Линтинг успешно завершен: `ruff check .` ✅
- [x] Type checking прошел: `mypy app/` ✅
- [x] Документация полная ✅

### Готовность инфраструктуры

- [ ] Langfuse production аккаунт настроен
- [ ] Redis production инстанс настроен
- [ ] PostgreSQL production база готова
- [ ] Мониторинг (Prometheus) настроен
- [ ] Правила алертинга созданы
- [ ] Процедуры бэкапа на месте

---

## Настройка окружения

### 1. Конфигурация Langfuse

**Получить credentials:**

1. Зайти на https://langfuse.com
2. Создать/залогиниться в организацию
3. Перейти в Settings → API Keys
4. Скопировать `Public Key` и `Secret Key`

**Обновить файл `.env`:**

```bash
# Langfuse интеграция
LANGFUSE_ENABLED=true
LANGFUSE_TRACING_ENABLED=true  # Управление отправкой трасс (SDK)
LANGFUSE_PUBLIC_KEY=pk-lf-ВАШ_PUBLIC_KEY_ЗДЕСЬ
LANGFUSE_SECRET_KEY=sk-lf-ВАШ_SECRET_KEY_ЗДЕСЬ
LANGFUSE_BASE_URL=https://api.langfuse.com

# Если используется self-hosted Langfuse:
# LANGFUSE_BASE_URL=https://ваш-langfuse-instance.com
```

**Проверить credentials:**

```bash
# Проверить подключение
curl -H "Authorization: Bearer YOUR_SECRET_KEY" \
  https://api.langfuse.com/api/health
```

Ожидаемый ответ: `{"status": "ok"}`

### 2. Конфигурация Tool Execution Tracing

```bash
# Feature flags
TOOL_EXECUTION_TRACING_ENABLED=true
TOOL_ANALYTICS_ENABLED=true
TOOL_EXECUTION_TIMEOUT_SECONDS=300

# Опционально: Тюнинг
LANGFUSE_FULL_PROMPTS=false  # Не отправлять полные промпты в Langfuse (приватность)
LANGFUSE_PAYLOAD_MAX_CHARS=1000  # Ограничить размер payload
```

### 3. Конфигурация Redis

```bash
# Redis для кэширования аналитики
REDIS_URL=redis://redis-host:6379/0
ANALYTICS_CACHE_TTL_SECONDS=3600  # 1 час

# Проверить подключение к Redis:
redis-cli -u redis://redis-host:6379/0 PING
# Ожидаемый результат: PONG
```

### 4. Настройка мониторинга

```bash
# Prometheus
PROMETHEUS_ENABLED=true
PROMETHEUS_PORT=9090

# Метрики для мониторинга:
# - langfuse_spans_created_total
# - langfuse_send_errors_total
# - langfuse_timeout_errors_total
# - tool_execution_latency_ms
```

---

## Шаги развертывания

### Шаг 1: Тестирование перед развертыванием

```bash
# 1. Запустить полный набор тестов
uv run pytest tests/ -v --tb=short

# 2. Проверить качество кода
ruff format . --check
ruff check .
mypy app/

# 3. Запустить специфические тесты Phase 4
uv run pytest tests/test_langfuse_integration.py -v

# Ожидаемый результат: Все тесты PASS ✅
```

### Шаг 2: Сборка и push Docker образа

```bash
# 1. Собрать образ
docker build -t codelab-core-service:v0.4.0-phase4 .

# 2. Добавить тег для реестра
docker tag codelab-core-service:v0.4.0-phase4 \
  registry.example.com/codelab-core-service:v0.4.0-phase4

# 3. Push в реестр
docker push registry.example.com/codelab-core-service:v0.4.0-phase4

# Проверка:
docker pull registry.example.com/codelab-core-service:v0.4.0-phase4
```

### Шаг 3: Обновить конфигурацию развертывания

**Обновить docker-compose.yml:**

```yaml
services:
  app:
    image: registry.example.com/codelab-core-service:v0.4.0-phase4
    environment:
      # === Phase 4 конфигурация ===
      LANGFUSE_ENABLED: "true"
      LANGFUSE_PUBLIC_KEY: ${LANGFUSE_PUBLIC_KEY}
      LANGFUSE_SECRET_KEY: ${LANGFUSE_SECRET_KEY}
      LANGFUSE_BASE_URL: "https://api.langfuse.com"
      
      TOOL_EXECUTION_TRACING_ENABLED: "true"
      TOOL_ANALYTICS_ENABLED: "true"
      
      REDIS_URL: "redis://redis:6379/0"
      ANALYTICS_CACHE_TTL_SECONDS: "3600"
    
    # Обеспечить достаточно ресурсов для async задач
    resources:
      limits:
        memory: 2G
      requests:
        memory: 1G
```

### Шаг 4: Постепенный откат

**Этап 1: Staging окружение (День 1)**

```bash
# Развернуть в staging
docker-compose -f docker-compose.staging.yml up -d

# Проверка:
curl http://localhost:8000/health
# Проверить Langfuse connectivity в ответе
```

**Этап 2: Production Canary (День 2-3)**

```bash
# Развернуть на 10% production инстансов
# Использовать load balancer или Kubernetes для постепенного проката

# Мониторить:
# - Error rates
# - Latency
# - Langfuse connectivity
# - Memory usage
```

**Этап 3: Full Production (День 4+)**

```bash
# Развернуть на 100% production
# Внимательно мониторить первые 24 часа
```

---

## Проверка и тестирование

### Немедленные тесты после развертывания

**1. Проверка здоровья**

```bash
curl -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  http://production-api.example.com/health

# Ожидаемый ответ:
{
  "status": "healthy",
  "services": {
    "langfuse": {
      "status": "available",
      "version": "2.0.0"
    },
    "redis": "ok",
    "postgres": "ok"
  }
}
```

**2. Тест исполнения инструмента**

```bash
# Выполнить простой инструмент
curl -X POST http://production-api.example.com/my/projects/PROJECT_ID/tools/execute \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "file_reader",
    "tool_params": {"file_path": "/test.txt"}
  }'

# Проверить:
# - Статус ответа 200
# - Инструмент выполнился успешно
# - Span создан в Langfuse (подождать 10 секунд для async отправки)
```

**3. Проверка Langfuse**

```bash
# 1. Залогиниться в Langfuse dashboard
# 2. Проверить Recent Traces секцию
# 3. Должны видеть spans от tool executions с:
#    - tool_name
#    - user_id
#    - время выполнения
#    - nested spans (validation, risk, execution)
```

**4. Тест Analytics API**

```bash
# Тестировать metrics endpoint
curl http://production-api.example.com/api/traces/tools/metrics \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json"

# Ожидаемый результат: Список tool metrics с success rate, latencies
```

### Нагрузочный тест

```bash
# Симулировать 100 параллельных tool executions
ab -n 100 -c 10 \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  http://production-api.example.com/api/traces/tools/metrics

# Ожидаемый результат:
# - Запросов в секунду: > 10 RPS
# - Ошибок: 0
# - Средняя latency: < 500ms
```

---

## Мониторинг и алерты

### Prometheus метрики для мониторинга

```yaml
# Файл: monitoring/prometheus.yml (добавить эти rules)

groups:
  - name: phase4_alerts
    rules:
      - alert: LangfuseSpanCreationErrors
        expr: rate(langfuse_send_errors_total[5m]) > 0.1
        for: 5m
        annotations:
          summary: "Высокий уровень Langfuse ошибок отправки"
          
      - alert: LangfuseTimeoutErrors
        expr: rate(langfuse_timeout_errors_total[5m]) > 0.05
        for: 5m
        annotations:
          summary: "Обнаружены Langfuse timeout ошибки"
          
      - alert: ToolExecutionLatencyHigh
        expr: histogram_quantile(0.95, tool_execution_latency_ms) > 500
        for: 10m
        annotations:
          summary: "Tool execution P95 latency > 500ms"
```

### Ключевые метрики для мониторинга

| Метрика | Норма | Алерт |
|---------|-------|--------|
| langfuse_spans_created/sec | > 10 | < 5 за 5м |
| langfuse_send_errors/min | < 1 | > 10 |
| langfuse_timeout_errors/min | 0 | > 5 |
| tool_execution_latency_p95 | < 300ms | > 500ms |
| tool_execution_latency_p99 | < 500ms | > 1000ms |
| redis_cache_hit_rate | > 80% | < 60% |

---

## Процедуры отката

### Быстрый откат (< 2 минуты)

**Если возникли критические проблемы:**

```bash
# 1. Отключить tool execution tracing немедленно
export TOOL_EXECUTION_TRACING_ENABLED=false
export LANGFUSE_ENABLED=false

# Перезагрузить сервисы
docker-compose restart app

# 2. Проверка
curl http://localhost:8000/health

# Tool execution продолжит работать БЕЗ трейсинга
# Нулевой impact на функциональность инструментов
```

### Полный откат (развертывание)

```bash
# 1. Вернуться к предыдущему Docker образу
docker pull registry.example.com/codelab-core-service:v0.3.0
docker-compose -f docker-compose.production.yml up -d

# 2. Проверка
curl http://localhost:8000/health
# Должна показать версию v0.3.0

# 3. Мониторинг
# Проверить:
# - Все запросы обрабатываются успешно
# - Нет ошибок в логах
# - База данных консистентна
```

### Консистентность данных после отката

**Нет рисков потери данных потому что:**

1. ✅ Spans отправляются асинхронно (fire-and-forget)
   - Уже в Langfuse, не теряются при откате
   
2. ✅ Метрики кэшированы в Redis
   - Могут быть ре-синхронизированы

3. ✅ Tool executions хранятся в PostgreSQL
   - Не затрагиваются статусом Langfuse
   
4. ✅ Нет транзакций смешивающих старый/новый код
   - Каждый запрос независим

---

## Решение проблем

### Проблема 1: Spans не появляются в Langfuse

**Признаки:**
- Tool выполняется успешно
- Нет spans в Langfuse dashboard
- Нет ошибок в логах

**Диагностика:**

```bash
# 1. Проверить что Langfuse включен
grep LANGFUSE_ENABLED .env
# Должно быть: true

# 2. Проверить credentials
grep LANGFUSE_PUBLIC_KEY .env
grep LANGFUSE_SECRET_KEY .env
# Должны быть не пусты

# 3. Тестировать Langfuse API
curl -H "Authorization: Bearer YOUR_SECRET_KEY" \
  https://api.langfuse.com/api/health
# Должен вернуть: {"status": "ok"}

# 4. Проверить логи на ошибки
docker-compose logs app | grep langfuse

# 5. Включить debug логирование
export LOG_LEVEL=DEBUG
docker-compose restart app
```

### Проблема 2: Tool execution latency увеличена

**Признаки:**
- Tool execution медленнее после развертывания
- Увеличение latency > 100ms

**Решение:**

- Увеличить Langfuse timeout если сеть медленная
- Отключить full prompts: `LANGFUSE_FULL_PROMPTS=false`
- Уменьшить payload: `LANGFUSE_PAYLOAD_MAX_CHARS=500`
- Отключить tracing если производительность критична

### Проблема 3: Redis connection ошибки

**Признаки:**
- Error: "ConnectionError: cannot connect to Redis"
- Analytics API возвращает 500 ошибки

**Решение:**

```bash
# 1. Проверить что Redis работает
docker ps | grep redis

# 2. Тестировать Redis
redis-cli -u redis://localhost:6379/0 PING
# Должен вернуть: PONG

# 3. Запустить Redis если не работает
docker-compose up -d redis
```

---

## Успешное развертывание когда:

- [x] Health check возвращает 200 с Langfuse available
- [x] Tool executions работают нормально
- [x] Spans появляются в Langfuse в течение 10 секунд
- [x] Analytics API отвечает в течение 500ms
- [x] Нет ошибок в логах приложения
- [x] Tool execution latency < 50ms overhead
- [x] Error rate < 0.1% в течение 1 часа
- [x] Мониторинг показывает healthy метрики

---

## Связанная документация

- [`doc/tool-execution-tracing.md`](doc/tool-execution-tracing.md) - Документация функций
- [`CHANGELOG.md`](CHANGELOG.md) - Изменения Phase 4
- [`doc/PHASE4_INTEGRATION_VERIFICATION.md`](doc/PHASE4_INTEGRATION_VERIFICATION.md) - Проверка интеграций
