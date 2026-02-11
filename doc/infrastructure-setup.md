# Настройка инфраструктуры

Этот документ описывает инфраструктуру проекта и процесс её настройки.

## Обзор инфраструктуры

Проект использует следующие компоненты:

### Основные сервисы

1. **PostgreSQL 16** - Основная реляционная база данных
   - Хранит пользователей, агентов, сессии, сообщения, задачи
   - Порт: 5432
   - Credentials: postgres/postgres (dev)

2. **Redis 7** - Кэш и брокер сообщений
   - Agent Bus очереди
   - SSE event buffering
   - Rate limiting
   - Порт: 6379

3. **Qdrant** - Векторная база данных
   - Семантическая память агентов (RAG)
   - Персональные коллекции для каждого агента
   - Порты: 6333 (HTTP), 6334 (gRPC)

### Опциональные сервисы (мониторинг)

4. **Prometheus** - Сбор метрик
   - Порт: 9090

5. **Grafana** - Визуализация метрик
   - Порт: 3000
   - Credentials: admin/admin

## Схема базы данных

### Таблицы

```
users
├── id (UUID, PK)
├── email (String, unique)
└── created_at (DateTime)

user_agents
├── id (UUID, PK)
├── user_id (UUID, FK -> users.id)
├── name (String)
├── config (JSON)
├── status (String: ready, busy, error)
└── created_at (DateTime)

user_orchestrators
├── id (UUID, PK)
├── user_id (UUID, FK -> users.id, unique)
├── config (JSON)
└── created_at (DateTime)

chat_sessions
├── id (UUID, PK)
├── user_id (UUID, FK -> users.id)
└── created_at (DateTime)

messages
├── id (UUID, PK)
├── session_id (UUID, FK -> chat_sessions.id)
├── role (String: user, assistant, system)
├── content (Text)
├── agent_id (UUID, FK -> user_agents.id, nullable)
└── created_at (DateTime)

tasks
├── id (UUID, PK)
├── session_id (UUID, FK -> chat_sessions.id)
├── agent_id (UUID, FK -> user_agents.id)
├── status (String: queued, running, completed, failed)
├── result (JSON, nullable)
├── created_at (DateTime)
├── started_at (DateTime, nullable)
└── completed_at (DateTime, nullable)

approval_requests
├── id (UUID, PK)
├── user_id (UUID, FK -> users.id)
├── type (String: tool, plan)
├── payload (JSON)
├── status (String: pending, approved, rejected, timeout)
├── created_at (DateTime)
├── resolved_at (DateTime, nullable)
└── decision (Text, nullable)
```

### Индексы

Все таблицы имеют оптимизированные индексы для:
- Primary keys (id)
- Foreign keys (user_id, session_id, agent_id)
- Часто используемые фильтры (status, created_at)
- Композитные индексы для сложных запросов

## Миграции базы данных

### Структура миграций

```
migrations/
├── env.py                    # Alembic environment
├── script.py.mako           # Шаблон миграций
└── versions/
    └── 2026_02_11_2215-001_initial_schema.py
```

### Команды миграций

```bash
# Применить все миграции
alembic upgrade head

# Создать новую миграцию (автогенерация)
alembic revision --autogenerate -m "описание"

# Откатить последнюю миграцию
alembic downgrade -1

# Показать текущую версию
alembic current

# Показать историю миграций
alembic history
```

### Автогенерация миграций

Alembic настроен на автоматическое обнаружение изменений в моделях:

1. Измените модели в `app/models/`
2. Запустите: `alembic revision --autogenerate -m "описание"`
3. Проверьте сгенерированную миграцию в `migrations/versions/`
4. Примените: `alembic upgrade head`

## Docker Compose конфигурации

### docker-compose.dev.yml (Разработка)

Легкая конфигурация для разработки:
- PostgreSQL
- Redis
- Qdrant
- Core Service

```bash
docker-compose -f docker-compose.dev.yml up -d
```

### docker-compose.yml (Полный стек)

Полная конфигурация с мониторингом:
- Все сервисы из dev
- Prometheus
- Grafana

```bash
docker-compose up -d
```

## Volumes

Все данные хранятся в Docker volumes:

```bash
# Список volumes
docker volume ls | grep codelab

# Удалить все volumes (УДАЛИТ ВСЕ ДАННЫЕ!)
docker-compose down -v
```

Volumes:
- `postgres_data` - Данные PostgreSQL
- `redis_data` - Данные Redis
- `qdrant_data` - Данные Qdrant
- `prometheus_data` - Метрики Prometheus
- `grafana_data` - Конфигурация Grafana

## Health Checks

Все сервисы имеют health checks:

### PostgreSQL
```bash
pg_isready -U postgres
```

### Redis
```bash
redis-cli ping
```

### Qdrant
```bash
timeout 1 bash -c "cat < /dev/null > /dev/tcp/localhost/6333"
```

### Core Service
```bash
curl -f http://localhost:8000/health
```

## Seed Data

Скрипт `scripts/init_db.py` создает тестовые данные:

### Тестовый пользователь
- Email: test@example.com
- ID: генерируется автоматически

### Тестовые агенты
1. **CodeAssistant** - Помощник по программированию
2. **DataAnalyst** - Аналитик данных
3. **DocumentWriter** - Технический писатель

### Команды

```bash
# Инициализация (создать таблицы + seed data)
python scripts/init_db.py init

# Только seed data
python scripts/init_db.py seed

# Сброс базы данных (ОСТОРОЖНО!)
python scripts/init_db.py reset

# Удалить все таблицы
python scripts/init_db.py drop
```

## Переменные окружения

Все переменные окружения документированы в `.env.example`.

### Критичные переменные

```bash
# База данных
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/codelab

# Redis
REDIS_URL=redis://localhost:6379/0

# Qdrant
QDRANT_URL=http://localhost:6333

# OpenAI (обязательно!)
OPENAI_API_KEY=sk-your-key

# JWT (обязательно для production!)
JWT_SECRET_KEY=your-secret-key
```

## Мониторинг

### Prometheus

Метрики доступны на http://localhost:9090

Основные метрики:
- HTTP запросы (latency, throughput, errors)
- Database connections
- Redis operations
- Agent tasks (queued, running, completed, failed)

### Grafana

Дашборды доступны на http://localhost:3000 (admin/admin)

Предустановленные дашборды:
- Application Overview
- Database Performance
- Agent Performance
- Error Tracking

## Производственное развертывание

### Рекомендации

1. **Безопасность**
   - Измените все пароли по умолчанию
   - Используйте сильный JWT_SECRET_KEY
   - Настройте SSL/TLS для всех сервисов
   - Ограничьте доступ к портам через firewall

2. **Масштабирование**
   - Используйте managed PostgreSQL (AWS RDS, Google Cloud SQL)
   - Используйте managed Redis (AWS ElastiCache, Redis Cloud)
   - Разверните Qdrant в кластере
   - Используйте load balancer для Core Service

3. **Резервное копирование**
   - Настройте автоматические бэкапы PostgreSQL
   - Настройте репликацию Redis
   - Регулярно экспортируйте данные Qdrant

4. **Мониторинг**
   - Настройте алерты в Prometheus
   - Интегрируйте с внешними системами (PagerDuty, Slack)
   - Настройте логирование в централизованную систему (ELK, Loki)

### Docker Compose для production

Создайте `docker-compose.prod.yml`:

```yaml
services:
  app:
    image: your-registry/codelab-core-service:latest
    restart: always
    environment:
      APP_ENV: production
      DEBUG: false
    # ... остальная конфигурация
```

## Troubleshooting

### Проблема: Сервисы не запускаются

```bash
# Проверьте логи
docker-compose logs

# Проверьте статус
docker-compose ps

# Пересоздайте контейнеры
docker-compose down
docker-compose up -d
```

### Проблема: Ошибка подключения к базе данных

```bash
# Проверьте, что PostgreSQL запущен
docker-compose ps postgres

# Проверьте логи PostgreSQL
docker-compose logs postgres

# Проверьте подключение
docker-compose exec postgres psql -U postgres -d codelab -c "SELECT 1"
```

### Проблема: Миграции не применяются

```bash
# Проверьте текущую версию
alembic current

# Примените миграции вручную
alembic upgrade head

# Если ошибка, откатите и примените заново
alembic downgrade base
alembic upgrade head
```

### Проблема: Нет места на диске

```bash
# Очистите неиспользуемые Docker ресурсы
docker system prune -a --volumes

# Удалите старые образы
docker image prune -a
```

## Дополнительные ресурсы

- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [Redis Documentation](https://redis.io/documentation)
- [Qdrant Documentation](https://qdrant.tech/documentation/)
