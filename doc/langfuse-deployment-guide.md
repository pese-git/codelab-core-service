# Langfuse Integration - Руководство по развертыванию

## Оглавление
1. [Развертывание инфраструктуры](#развертывание-инфраструктуры)
2. [Проверка health check](#проверка-health-check)
3. [Включение на staging](#включение-на-staging)
4. [Логирование и мониторинг](#логирование-и-мониторинг)
5. [План production rollout](#план-production-rollout)
6. [Troubleshooting runbook](#troubleshooting-runbook)

---

## Развертывание инфраструктуры

### Требования
- Docker & Docker Compose 1.29+
- 8GB+ свободного места на диске
- Порты 3000, 5432, 6379, 9000, 9090 доступны
- Сетевая связь между контейнерами

### Docker Compose стек для Langfuse v3

Создайте файл `docker-compose.langfuse.yml`:

```yaml
# Langfuse v3 - Полный стек для production
# Внимание: обновить значения с # CHANGEME на собственные секретные ключи

services:
  langfuse-worker:
    image: docker.io/langfuse/langfuse-worker:3
    restart: always
    depends_on: &langfuse-depends-on
      postgres:
        condition: service_healthy
      minio:
        condition: service_healthy
      redis:
        condition: service_healthy
      clickhouse:
        condition: service_healthy
    ports:
      - 127.0.0.1:3030:3030
    environment: &langfuse-worker-env
      NEXTAUTH_URL: ${NEXTAUTH_URL:-http://localhost:3000}
      DATABASE_URL: ${DATABASE_URL:-postgresql://postgres:postgres@postgres:5432/postgres} # CHANGEME
      SALT: ${SALT:-mysalt} # CHANGEME: openssl rand -hex 16
      ENCRYPTION_KEY: ${ENCRYPTION_KEY:-0000000000000000000000000000000000000000000000000000000000000000} # CHANGEME: openssl rand -hex 32
      TELEMETRY_ENABLED: ${TELEMETRY_ENABLED:-true}
      CLICKHOUSE_MIGRATION_URL: ${CLICKHOUSE_MIGRATION_URL:-clickhouse://clickhouse:9000}
      CLICKHOUSE_URL: ${CLICKHOUSE_URL:-http://clickhouse:8123}
      CLICKHOUSE_USER: ${CLICKHOUSE_USER:-clickhouse}
      CLICKHOUSE_PASSWORD: ${CLICKHOUSE_PASSWORD:-clickhouse} # CHANGEME
      LANGFUSE_S3_EVENT_UPLOAD_BUCKET: ${LANGFUSE_S3_EVENT_UPLOAD_BUCKET:-langfuse}
      LANGFUSE_S3_EVENT_UPLOAD_REGION: ${LANGFUSE_S3_EVENT_UPLOAD_REGION:-auto}
      LANGFUSE_S3_EVENT_UPLOAD_ACCESS_KEY_ID: ${LANGFUSE_S3_EVENT_UPLOAD_ACCESS_KEY_ID:-minio}
      LANGFUSE_S3_EVENT_UPLOAD_SECRET_ACCESS_KEY: ${LANGFUSE_S3_EVENT_UPLOAD_SECRET_ACCESS_KEY:-miniosecret} # CHANGEME
      LANGFUSE_S3_EVENT_UPLOAD_ENDPOINT: ${LANGFUSE_S3_EVENT_UPLOAD_ENDPOINT:-http://minio:9000}
      LANGFUSE_S3_EVENT_UPLOAD_FORCE_PATH_STYLE: ${LANGFUSE_S3_EVENT_UPLOAD_FORCE_PATH_STYLE:-true}
      LANGFUSE_S3_MEDIA_UPLOAD_BUCKET: ${LANGFUSE_S3_MEDIA_UPLOAD_BUCKET:-langfuse}
      LANGFUSE_S3_MEDIA_UPLOAD_REGION: ${LANGFUSE_S3_MEDIA_UPLOAD_REGION:-auto}
      LANGFUSE_S3_MEDIA_UPLOAD_ACCESS_KEY_ID: ${LANGFUSE_S3_MEDIA_UPLOAD_ACCESS_KEY_ID:-minio}
      LANGFUSE_S3_MEDIA_UPLOAD_SECRET_ACCESS_KEY: ${LANGFUSE_S3_MEDIA_UPLOAD_SECRET_ACCESS_KEY:-miniosecret} # CHANGEME
      LANGFUSE_S3_MEDIA_UPLOAD_ENDPOINT: ${LANGFUSE_S3_MEDIA_UPLOAD_ENDPOINT:-http://localhost:9090}
      LANGFUSE_S3_MEDIA_UPLOAD_FORCE_PATH_STYLE: ${LANGFUSE_S3_MEDIA_UPLOAD_FORCE_PATH_STYLE:-true}
      REDIS_HOST: ${REDIS_HOST:-redis}
      REDIS_PORT: ${REDIS_PORT:-6379}
      REDIS_AUTH: ${REDIS_AUTH:-myredissecret} # CHANGEME

  langfuse-web:
    image: docker.io/langfuse/langfuse:3
    restart: always
    depends_on: *langfuse-depends-on
    ports:
      - 3000:3000
    environment:
      <<: *langfuse-worker-env
      NEXTAUTH_SECRET: ${NEXTAUTH_SECRET:-mysecret} # CHANGEME
      LANGFUSE_INIT_ORG_NAME: ${LANGFUSE_INIT_ORG_NAME:-}
      LANGFUSE_INIT_PROJECT_NAME: ${LANGFUSE_INIT_PROJECT_NAME:-}
      LANGFUSE_INIT_USER_EMAIL: ${LANGFUSE_INIT_USER_EMAIL:-}
      LANGFUSE_INIT_USER_NAME: ${LANGFUSE_INIT_USER_NAME:-}
      LANGFUSE_INIT_USER_PASSWORD: ${LANGFUSE_INIT_USER_PASSWORD:-}

  clickhouse:
    image: docker.io/clickhouse/clickhouse-server
    restart: always
    user: "101:101"
    environment:
      CLICKHOUSE_DB: default
      CLICKHOUSE_USER: ${CLICKHOUSE_USER:-clickhouse}
      CLICKHOUSE_PASSWORD: ${CLICKHOUSE_PASSWORD:-clickhouse} # CHANGEME
    volumes:
      - langfuse_clickhouse_data:/var/lib/clickhouse
      - langfuse_clickhouse_logs:/var/log/clickhouse-server
    ports:
      - 127.0.0.1:8123:8123
      - 127.0.0.1:9000:9000
    healthcheck:
      test: wget --no-verbose --tries=1 --spider http://localhost:8123/ping || exit 1
      interval: 5s
      timeout: 5s
      retries: 10
      start_period: 1s

  minio:
    image: cgr.dev/chainguard/minio
    restart: always
    entrypoint: sh
    command: -c 'mkdir -p /data/langfuse && minio server --address ":9000" --console-address ":9001" /data'
    environment:
      MINIO_ROOT_USER: ${MINIO_ROOT_USER:-minio}
      MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD:-miniosecret} # CHANGEME
    ports:
      - 9090:9000
      - 127.0.0.1:9091:9001
    volumes:
      - langfuse_minio_data:/data
    healthcheck:
      test: ["CMD", "mc", "ready", "local"]
      interval: 1s
      timeout: 5s
      retries: 5
      start_period: 1s

  redis:
    image: docker.io/redis:7
    restart: always
    command: >
      --requirepass ${REDIS_AUTH:-myredissecret}
      --maxmemory-policy noeviction
    ports:
      - 127.0.0.1:6379:6379
    volumes:
      - langfuse_redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 3s
      timeout: 10s
      retries: 10

  postgres:
    image: docker.io/postgres:17
    restart: always
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 3s
      timeout: 3s
      retries: 10
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-postgres}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-postgres} # CHANGEME
      POSTGRES_DB: ${POSTGRES_DB:-postgres}
      TZ: UTC
      PGTZ: UTC
    ports:
      - 127.0.0.1:5432:5432
    volumes:
      - langfuse_postgres_data:/var/lib/postgresql/data

volumes:
  langfuse_postgres_data:
    driver: local
  langfuse_clickhouse_data:
    driver: local
  langfuse_clickhouse_logs:
    driver: local
  langfuse_minio_data:
    driver: local
  langfuse_redis_data:
    driver: local

networks:
  default:
    name: codelab-network
```

### Файл конфигурации переменных окружения

Создайте `.env.langfuse` с безопасными credentials:

```bash
# ===== ГЕНЕРАЦИЯ БЕЗОПАСНЫХ ЗНАЧЕНИЙ =====
# Для ENCRYPTION_KEY: openssl rand -hex 32
# Для SALT: openssl rand -hex 16
# Для NEXTAUTH_SECRET: openssl rand -hex 32

# Основная конфигурация
NEXTAUTH_URL=http://localhost:3000
DATABASE_URL=postgresql://postgres:ВАШ-ПАРОЛЬ@postgres:5432/postgres
ENCRYPTION_KEY=ВАШ-32-БАЙТОВЫЙ-HEX-КЛЮЧ
SALT=ВАШ-16-БАЙТОВЫЙ-HEX-КЛЮЧ
NEXTAUTH_SECRET=ВАШ-32-БАЙТОВЫЙ-HEX-КЛЮЧ

# ClickHouse
CLICKHOUSE_USER=clickhouse
CLICKHOUSE_PASSWORD=ВАШ-БЕЗОПАСНЫЙ-ПАРОЛЬ
CLICKHOUSE_URL=http://clickhouse:8123

# MinIO (S3 хранилище)
MINIO_ROOT_USER=minio
MINIO_ROOT_PASSWORD=ВАШ-БЕЗОПАСНЫЙ-ПАРОЛЬ
LANGFUSE_S3_EVENT_UPLOAD_ACCESS_KEY_ID=minio
LANGFUSE_S3_EVENT_UPLOAD_SECRET_ACCESS_KEY=ВАШ-БЕЗОПАСНЫЙ-ПАРОЛЬ
LANGFUSE_S3_MEDIA_UPLOAD_ACCESS_KEY_ID=minio
LANGFUSE_S3_MEDIA_UPLOAD_SECRET_ACCESS_KEY=ВАШ-БЕЗОПАСНЫЙ-ПАРОЛЬ

# Redis
REDIS_AUTH=ВАШ-БЕЗОПАСНЫЙ-ПАРОЛЬ

# Postgres
POSTGRES_PASSWORD=ВАШ-БЕЗОПАСНЫЙ-ПАРОЛЬ

# Начальный пользователь (для первого входа)
LANGFUSE_INIT_ORG_NAME=Моя организация
LANGFUSE_INIT_PROJECT_NAME=Мой проект
LANGFUSE_INIT_USER_EMAIL=admin@example.com
LANGFUSE_INIT_USER_NAME=Admin
LANGFUSE_INIT_USER_PASSWORD=ВАШ-БЕЗОПАСНЫЙ-ПАРОЛЬ
```

### Шаги развертывания

**Шаг 1: Запуск стека Langfuse**
```bash
# Скопировать файл docker-compose
cp docker-compose.langfuse.yml docker-compose.override.yml

# Загрузить переменные окружения
export $(cat .env.langfuse | grep -v '#' | xargs)

# Запустить сервисы
docker-compose up -d langfuse-postgres langfuse-worker langfuse-web

# Проверить статус
docker-compose ps
# Все сервисы должны показывать статус "healthy"
```

**Шаг 2: Проверка всех сервисов**
```bash
# Статус контейнеров
docker-compose ps

# Проверка PostgreSQL
docker-compose exec postgres psql -U postgres -c "SELECT version();"

# Проверка ClickHouse
docker-compose exec clickhouse clickhouse-client -h clickhouse -u clickhouse -p clickhouse --query "SELECT 'ClickHouse OK'"

# Проверка MinIO
docker-compose exec minio mc ls local/

# Проверка Redis
docker-compose exec redis redis-cli -a myredissecret ping
```

**Шаг 3: Доступ к UI Langfuse**
```bash
# Открыть браузер
open http://localhost:3000

# Логин с начальными credentials
# Email: admin@example.com
# Пароль: (из LANGFUSE_INIT_USER_PASSWORD)
```

**Шаг 4: Создание API ключей**
```bash
# В Langfuse UI:
# 1. Settings → API Keys
# 2. Создать новый public key (для creation traces)
# 3. Создать новый secret key (для analytics queries)
# 4. Обновить .env в codelab-core-service
```

---

## Проверка health check

### Endpoint статус коды

```bash
# Langfuse health endpoint
curl -i http://localhost:3000/api/public/health

# Ожидаемый ответ (200 OK):
HTTP/1.1 200 OK

# codelab integration health check
curl -i http://localhost:8000/health/langfuse

# Ответы:
# 1. Healthy (200):
{ "status": "healthy" }

# 2. Unhealthy (503):
{ "status": "unhealthy", "error": "Connection refused" }

# 3. Disabled (200):
{ "status": "disabled" }
```

### Полная процедура проверки

```bash
#!/bin/bash

echo "=== Проверка Health Check ==="

# 1. Статус контейнеров
echo "1. Статус контейнеров:"
docker-compose ps

# 2. Web UI Langfuse
echo "2. Langfuse Web UI:"
curl -s http://localhost:3000 | grep -q "Langfuse" && echo "✓ UI доступен" || echo "✗ UI не доступен"

# 3. Langfuse API Health
echo "3. Langfuse API Health:"
curl -s http://localhost:3000/api/public/health | jq .

# 4. Database connectivity
echo "4. Database статус:"
docker-compose exec -T postgres psql -U postgres -c "SELECT now();" 2>/dev/null && echo "✓ Postgres OK" || echo "✗ Postgres failed"

# 5. ClickHouse connectivity
echo "5. ClickHouse статус:"
docker-compose exec -T clickhouse clickhouse-client -h localhost --query "SELECT 'OK'" && echo "✓ ClickHouse OK" || echo "✗ ClickHouse failed"

# 6. MinIO connectivity
echo "6. MinIO статус:"
curl -s http://localhost:9090/minio/health/live && echo "✓ MinIO OK" || echo "✗ MinIO failed"

# 7. Redis connectivity
echo "7. Redis статус:"
docker-compose exec -T redis redis-cli ping 2>/dev/null | grep -q "PONG" && echo "✓ Redis OK" || echo "✗ Redis failed"

# 8. Integration health check
echo "8. codelab Integration:"
curl -s http://localhost:8000/health/langfuse | jq .

echo "=== Проверка завершена ==="
```

---

## Включение на staging

### Предварительный checklist

- [x] Все unit тесты проходят (58/58)
- [x] LANGFUSE_ENABLED=false в production конфиге
- [x] Документация развертывания завершена
- [ ] Инфраструктура Langfuse развернута
- [ ] API ключи созданы и сохранены
- [ ] Мониторинг сконфигурирован

### Включение на staging (пошаговый процесс)

**Фаза 1: Развертывание инфраструктуры (30 минут)**
```bash
# Запуск стека Langfuse
docker-compose -f docker-compose.langfuse.yml up -d

# Проверка здоровья всех сервисов
sleep 10
docker-compose ps
```

**Фаза 2: Создание API ключей (5 минут)**
```bash
# Логин в Langfuse UI и создание ключей
# URL: http://localhost:3000

# Сохранение ключей в vault/secrets manager
export LANGFUSE_PUBLIC_KEY="pk-staging-xxxx"
export LANGFUSE_SECRET_KEY="sk-staging-xxxx"
```

**Фаза 3: Включение интеграции (5 минут)**
```bash
# Обновление переменной окружения
export LANGFUSE_ENABLED=true

# Перезапуск сервиса
docker-compose restart codelab-core-service

# Проверка
curl http://localhost:8000/health/langfuse
```

**Фаза 4: Smoke тесты (5 минут)**
```bash
# Базовые интеграционные тесты
pytest tests/test_langfuse_integration.py -v -k "test_create_trace"

# Health check тесты
pytest tests/test_health_endpoints.py::TestLangfuseHealthCheckEndpoint -v

# E2E тесты
pytest tests/test_langfuse_e2e.py::TestLangfuseE2E::test_full_flow_trace_creation -v
```

**Фаза 5: Мониторинг traces (постоянно)**
```bash
# Просмотр логов создания traces
docker-compose logs -f codelab-core-service | grep -i "trace_created"

# Проверка UI Langfuse для входящих traces
# Dashboard: http://localhost:3000/dashboard
```

### Тестовые сценарии

1. **Базовая trace**: Создание агента с простым промптом
   - Expected: Trace видна в UI в течение 5 секунд
   
2. **Иерархия spans**: Агент с вызовом инструментов
   - Expected: Правильные parent-child relationships
   
3. **Запись scores**: Добавление user feedback
   - Expected: Score отображается в analytics
   
4. **Graceful degradation**: Остановка Langfuse
   - Expected: Сервис продолжает работать, ошибки в логах, восстановление при перезагрузке
   
5. **Performance**: Измерение latency trace
   - Expected: < 100ms медиана, < 500ms p99

---

## Логирование и мониторинг

### Structured логирование

Все события Langfuse логируются с structlog:

```python
# Примеры:
logger.info("langfuse_initialized", host=host, enabled=True)
logger.info("trace_created", trace_id="t-123", duration_ms=45)
logger.warning("health_check_failed", status_code=503)
logger.error("trace_error", error="Invalid metadata")
```

### Агрегация логов

```bash
# Просмотр последних Langfuse логов
docker-compose logs codelab-core-service | grep -i langfuse | tail -50

# Фильтр по типу события
docker-compose logs codelab-core-service | grep "trace_created" | jq .

# Мониторинг ошибок
docker-compose logs codelab-core-service | grep -i "error\|exception" | grep -i langfuse
```

### Prometheus метрики

Мониторить эти метрики:

```prometheus
# Создание traces
langfuse_traces_total{workspace_id="w-123"} 1250
langfuse_spans_total{trace_id="t-456"} 8
langfuse_trace_creation_latency_seconds{le="0.1"} 0.045

# Ошибки
langfuse_callback_failures_total{error_type="timeout"} 3
```

---

## План production rollout

### Фаза 1: Подготовка (1 день)
- Все тесты проходят
- LANGFUSE_ENABLED=false в production
- Документация завершена, команда обучена
- Мониторинг готов

### Фаза 2: Canary (1 день)
- 1% workspaces (≈ 10 пользователей)
- Мониторинг 24 часа
- Нулевой expected production impact

### Фаза 3: Rollout (3 дня)
- День 1: 10% workspaces
- День 2: 25% workspaces
- День 3: 100% workspaces

### Фаза 4: Стабилизация (постоянно)
- Непрерывный мониторинг метрик
- Еженедельные health reviews
- Документирование learnings

### Rollback (если необходимо)

```bash
# 1. Немедленное отключение
export LANGFUSE_ENABLED=false
docker-compose restart codelab-core-service

# 2. Проверка восстановления
curl http://localhost:8000/health

# 3. Проверка логов на impact
docker-compose logs codelab-core-service | grep -i error | head -50

# 4. Post-incident review
# - Root cause analysis
# - Preventive measures
# - Communication to team
```

---

## Troubleshooting runbook

### Проблема 1: Connection Refused

**Симптомы**: `Failed to connect to Langfuse at http://localhost:3000`

**Решение**:
```bash
# Проверить статус контейнера
docker-compose ps langfuse-web
# Должен быть "Up" и "healthy"

# Проверить логи
docker-compose logs langfuse-web --tail 50

# Перезапустить
docker-compose restart langfuse-web

# Проверить
curl http://localhost:3000/api/public/health
```

### Проблема 2: Traces не появляются в UI

**Симптомы**: Health check OK, traces не видны в UI

**Решение**:
```bash
# Проверить API ключи корректны
echo $LANGFUSE_PUBLIC_KEY
echo $LANGFUSE_SECRET_KEY

# Тест создания trace напрямую
curl -X POST http://localhost:3000/api/public/ingestion \
  -H "X-API-Key: $LANGFUSE_PUBLIC_KEY" \
  -H "Content-Type: application/json" \
  -d '{"traceId":"test-123"}'

# Проверить базу данных
docker-compose exec postgres psql -U postgres -d postgres -c "SELECT COUNT(*) FROM traces;"

# Проверить flush происходит
grep "flush" logs/codelab.log
```

### Проблема 3: Высокая latency

**Симптомы**: Создание trace медленно (> 200ms)

**Решение**:
```bash
# Проверить использование ресурсов
docker-compose stats

# Проверить performance базы данных
docker-compose exec postgres psql -U postgres -d postgres -c "EXPLAIN ANALYZE SELECT * FROM traces LIMIT 1;"

# Увеличить ресурсы если необходимо
# Отредактировать docker-compose.yml и увеличить:
# - memory limits
# - CPU limits
# - connection pool size
```

### Проблема 4: Database connection errors

**Симптомы**: `QueuePool limit exceeded`

**Решение**:
```bash
# Проверить активные connections
docker-compose exec postgres psql -U postgres -d postgres -c "SELECT count(*) FROM pg_stat_activity;"

# Проверить Langfuse connection pool
echo $DATABASE_POOL_SIZE
# Увеличить если необходимо (default 10, try 50)

# Перезапустить сервисы
docker-compose restart langfuse-web langfuse-worker postgres
```

### Emergency контакты

**На дежурстве**: [Контакт вашей команды]
**Эскалация**: [Контакт менеджера]
**Runbook**: `/doc/langfuse-deployment-guide.md`

---

## Итоговый checklist

- [x] Docker Compose стек (v3 архитектура)
- [x] Генерация безопасных credentials
- [x] Процедуры health check
- [x] Процесс включения на staging
- [x] Настройка логирования и мониторинга
- [x] План production rollout
- [x] Troubleshooting runbook

**Следующие шаги**:
1. Генерировать безопасные credentials
2. Развернуть стек Langfuse
3. Запустить проверку health check
4. Включить на staging
5. Спланировать production rollout с командой
