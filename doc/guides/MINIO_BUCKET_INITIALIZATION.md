# MinIO Bucket Initialization - Решение проблемы автоматического создания bucket

## Проблема

При развертывании Langfuse с MinIO storage backend ошибка возникала:

```
Failed to upload JSON to S3 events/otel/default-project/.../...json
The specified bucket does not exist
```

**Причина:** MinIO не создавал buckets автоматически при запуске. Langfuse ожидает существования bucket с именем `langfuse` (и `langfuse-otel`), но без явного создания они не появлялись.

## Решение

Реализовано с использованием **отдельного init контейнера** (мини-контейнера инициализации), который:

1. Ждет готовности MinIO сервера
2. Подключается к MinIO через MinIO Client (`mc`)
3. Создает необходимые buckets
4. Включает versioning для защиты данных

### Архитектура решения

```
docker-compose up
    ↓
┌─────────────────────┐
│   minio service     │ ← основной сервер S3
│ (RELEASE.2025...)   │
└──────────┬──────────┘
           │ (service_healthy)
           ↓
┌─────────────────────────────────┐
│   minio-init container          │
│   (MinIO Client - mc)           │
│   - Создает buckets             │
│   - Включает versioning         │
│   - Завершается (restart: no)   │
└─────────────────────────────────┘
           │
           ↓
      Buckets ready:
      - langfuse
      - langfuse-otel
           │
           ↓
┌──────────────────────────┐
│ langfuse-worker service  │
│ langfuse-web service     │
│ (могут использовать S3)  │
└──────────────────────────┘
```

## Компоненты решения

### 1. Сервис `minio-init` в docker-compose.yml

```yaml
minio-init:
  image: minio/mc:RELEASE.2025-04-22T22-12-26Z
  container_name: codelab-minio-init
  restart: no
  depends_on:
    minio:
      condition: service_healthy
  environment:
    MINIO_HOST: ${MINIO_HOST:-minio}
    MINIO_PORT: ${MINIO_PORT:-9000}
    MINIO_ROOT_USER: ${MINIO_ROOT_USER:-minio}
    MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD:-miniosecret}
    MINIO_BUCKET: ${MINIO_BUCKET:-langfuse}
  volumes:
    - ./scripts/init-minio.sh:/scripts/init-minio.sh
  entrypoint: sh /scripts/init-minio.sh
  networks:
    - codelab-network
```

**Ключевые параметры:**
- `image: minio/mc` — MinIO Client для управления bucket
- `depends_on: minio (service_healthy)` — ждет готовности MinIO сервера
- `restart: no` — контейнер не перезапускается, только запускается один раз
- Все параметры настраиваются через переменные окружения

### 2. Скрипт инициализации: scripts/init-minio.sh

```bash
#!/bin/bash
set -e

# Поддерживает переменные окружения с дефолтными значениями
MINIO_HOST="${MINIO_HOST:-minio}"
MINIO_PORT="${MINIO_PORT:-9000}"
MINIO_ROOT_USER="${MINIO_ROOT_USER:-minio}"
MINIO_ROOT_PASSWORD="${MINIO_ROOT_PASSWORD:-miniosecret}"
MINIO_BUCKET="${MINIO_BUCKET:-langfuse}"

MINIO_ENDPOINT="http://${MINIO_HOST}:${MINIO_PORT}"

# Повторный подсчет подключения с таймаутом (30 попыток x 2 сек = 60 сек)
max_retries=30
retry_count=0
while ! mc alias set local "$MINIO_ENDPOINT" "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" 2>/dev/null; do
  retry_count=$((retry_count + 1))
  if [ $retry_count -ge $max_retries ]; then
    echo "Failed to connect to MinIO after $max_retries attempts"
    exit 1
  fi
  echo "Attempt $retry_count/$max_retries: Waiting for MinIO..."
  sleep 2
done

# Создает основной bucket
mc mb "local/$MINIO_BUCKET" 2>&1 || {
  if ! mc ls "local/$MINIO_BUCKET" >/dev/null 2>&1; then
    echo "✗ Failed to create bucket"
    exit 1
  fi
}

# Создает дополнительный bucket для OTEL данных
MINIO_BUCKET_OTEL="${MINIO_BUCKET}-otel"
mc mb "local/$MINIO_BUCKET_OTEL" 2>&1 || {
  if ! mc ls "local/$MINIO_BUCKET_OTEL" >/dev/null 2>&1; then
    echo "✗ Failed to create bucket"
    exit 1
  fi
}

# Включает versioning для защиты данных
mc version enable "local/$MINIO_BUCKET" 2>/dev/null || true
mc version enable "local/$MINIO_BUCKET_OTEL" 2>/dev/null || true

echo "✓ MinIO initialization completed successfully"
```

**Особенности:**
- **Retries с таймаутом:** корректно обрабатывает случаи, когда MinIO не сразу готов
- **Идемпотентность:** безопасно работает если buckets уже существуют
- **Поддержка переменных окружения:** легко настраивается для разных окружений
- **Versioning:** включается для защиты от случайного удаления данных

## Использование

### Локальное развертывание

```bash
# Пересоздать контейнеры (важно для чистой инициализации)
docker-compose down
docker-compose up -d

# Проверить логи инициализации
docker logs codelab-minio-init

# Проверить создание buckets
docker exec codelab-minio-init mc ls local/
```

### Переменные окружения

Все параметры инициализации можно переопределить через `.env`:

```env
# MinIO конфигурация
MINIO_HOST=minio                    # Хост MinIO (для init контейнера)
MINIO_PORT=9000                     # Порт MinIO (для init контейнера)
MINIO_ROOT_USER=minio               # Пользователь
MINIO_ROOT_PASSWORD=miniosecret     # Пароль
MINIO_BUCKET=langfuse               # Основной bucket
```

### Проверка в MinIO Console

1. Откройте MinIO Console: http://localhost:9001
2. Логин: `minio` / `miniosecret`
3. Перейдите в "Object Browser"
4. Проверьте наличие buckets: `langfuse`, `langfuse-otel`

## Почему init контейнер, а не встроенный скрипт?

### Проблема с `/docker-entrypoint-initdb.d/` в MinIO

MinIO **не поддерживает** стандартный механизм Docker для выполнения init скриптов (`/docker-entrypoint-initdb.d/`). Этот механизм есть только в:
- PostgreSQL
- MySQL
- MongoDB
- Некоторых других БД

MinIO сразу переходит в режим сервера без выполнения дополнительных скриптов.

### Преимущества init контейнера

1. **Надежная инициализация:** явно дождается готовности MinIO
2. **Отладка:** видны логи выполнения скрипта
3. **Переиспользование:** можно запустить в разных окружениях
4. **Чистота:** не смешивает инициализацию с основным сервисом
5. **Гибкость:** легко добавлять новые операции (permissions, policies, etc.)

## Возможные улучшения

### Добавление lifecycle policies
```bash
mc ilm import local/langfuse <<EOF
<LifecycleConfiguration>
  <Rule>
    <ID>delete-old-events</ID>
    <Filter><Prefix>events/</Prefix></Filter>
    <Expiration><Days>90</Days></Expiration>
    <Status>Enabled</Status>
  </Rule>
</LifecycleConfiguration>
EOF
```

### Установка public policy для читаемых buckets
```bash
mc policy set public local/langfuse-public
```

### Шифрование bucket
```bash
mc encrypt set sse-s3 local/langfuse
```

## Troubleshooting

### Контейнер мinio-init завершается с ошибкой

**Симптом:**
```
minio-init exited with code 1
Error: Failed to connect to MinIO
```

**Решение:**
1. Проверьте, что minio контейнер здоров: `docker ps | grep minio`
2. Увеличьте `start_period` в healthcheck MinIO (текущее значение: 30s)
3. Проверьте переменные окружения в `.env`
4. Посмотрите логи: `docker logs codelab-minio`

### Buckets не создаются

**Симптом:**
```
mc: <ERROR> Failed to make bucket 'local/langfuse'
The specified bucket does not exist
```

**Решение:**
1. Проверьте credentails (пользователь/пароль) совпадают между minio и minio-init
2. Убедитесь что bucket имя валидно (только lowercase, цифры, дефис)
3. Проверьте сетевое подключение: `docker exec codelab-minio-init ping minio`

### Langfuse по-прежнему не может писать в S3

**Проверки:**
1. Подтвердить что buckets созданы: `docker logs codelab-minio-init`
2. Проверить что Langfuse видит правильный endpoint: `docker logs codelab-langfuse-worker | grep S3`
3. Убедиться что credentails совпадают в Langfuse конфигурации

## Файлы, которые были изменены

- [`docker-compose.yml`](../docker-compose.yml) — добавлен сервис `minio-init`
- [`scripts/init-minio.sh`](../scripts/init-minio.sh) — скрипт инициализации

## Дополнительные ресурсы

- [MinIO Client Documentation](https://min.io/docs/minio/linux/reference/minio-mc.html)
- [MinIO Bucket Management](https://min.io/docs/minio/linux/administration/minio-console.html)
- [Langfuse S3 Configuration](https://langfuse.com/docs/deployment/self-host/storage)
