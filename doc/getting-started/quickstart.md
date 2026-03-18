# 🚀 Быстрый старт CodeLab Core Service

## Самый быстрый способ (с Make)

```bash
# 1. Клонируйте репозиторий
git clone <repository-url>
cd codelab-core-service

# 2. Автоматическая настройка
make setup

# 3. Отредактируйте .env
nano .env
# Установите: OPENAI_API_KEY=sk-your-key

# 4. Перезапустите
make restart

# 5. Проверьте
make health
```

✅ Готово! API работает на http://localhost:8000

---

## Без Make (вручную)

```bash
# 1. Клонируйте репозиторий
git clone <repository-url>
cd codelab-core-service

# 2. Создайте .env
cp .env.example .env
nano .env  # Установите OPENAI_API_KEY

# 3. Запустите сервисы
docker-compose -f docker-compose.dev.yml up -d

# 4. Дождитесь запуска (30-40 секунд)
docker-compose logs -f app

# 5. Проверьте
curl http://localhost:8000/health
```

---

## Полезные команды

### С Make:
```bash
make dev          # Запустить dev окружение
make up           # Запустить полный стек (с мониторингом)
make down         # Остановить сервисы
make logs         # Показать логи
make health       # Проверить health
make migrate      # Применить миграции
make seed         # Добавить тестовые данные
make test         # Запустить тесты
make help         # Показать все команды
```

### Без Make:
```bash
# Запуск
docker-compose -f docker-compose.dev.yml up -d

# Остановка
docker-compose down

# Логи
docker-compose logs -f app

# Миграции
docker-compose exec app alembic upgrade head

# Seed data
docker-compose exec app python scripts/init_db.py seed
```

---

## Первые шаги после запуска

### 1. Проверьте API документацию
Откройте в браузере: http://localhost:8000/my/docs

### 2. Получите тестовый JWT токен
```bash
# Seed data создает тестового пользователя
# Найдите user_id в логах или используйте скрипт
docker-compose exec app python scripts/generate_test_jwt.py <user_id>
```

### 3. Создайте своего первого агента
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

### 4. Создайте чат-сессию
```bash
curl -X POST http://localhost:8000/my/chat/sessions/ \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### 5. Отправьте сообщение
```bash
curl -X POST http://localhost:8000/my/chat/{session_id}/message/ \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Hello! Can you help me?",
    "target_agent": "assistant"
  }'
```

---

## Доступные сервисы

После запуска доступны:

| Сервис | URL | Описание |
|--------|-----|----------|
| **API** | http://localhost:8000 | Основной API |
| **API Docs** | http://localhost:8000/my/docs | Swagger UI |
| **Health** | http://localhost:8000/health | Health check |
| **PostgreSQL** | localhost:5432 | База данных |
| **Redis** | localhost:6379 | Кэш и очереди |
| **Qdrant** | http://localhost:6333 | Векторная БД |
| **Prometheus** | http://localhost:9090 | Метрики (полный стек) |
| **Grafana** | http://localhost:3000 | Дашборды (полный стек) |

---

## Решение проблем

### Сервисы не запускаются
```bash
# Проверьте статус
docker-compose ps

# Проверьте логи
docker-compose logs

# Пересоздайте контейнеры
docker-compose down -v
docker-compose up -d
```

### Ошибка подключения к базе данных
```bash
# Проверьте, что PostgreSQL запущен
docker-compose ps postgres

# Проверьте логи PostgreSQL
docker-compose logs postgres

# Пересоздайте volume
docker-compose down -v
docker-compose up -d
```

### Миграции не применяются
```bash
# Примените миграции вручную
docker-compose exec app alembic upgrade head

# Или через make
make migrate
```

### Нет seed data
```bash
# Добавьте seed data
docker-compose exec app python scripts/init_db.py seed

# Или через make
make seed
```

---

## Следующие шаги

1. ✅ Прочитайте [README.md](../../README.md) для полной документации
2. ✅ Изучите [API документацию](../api/rest-api.md)
3. ✅ Посмотрите [примеры использования](../samples/samples.md)
4. ✅ Настройте мониторинг (если используете полный стек)
5. ✅ Начните разработку!

---

## Нужна помощь?

- 📖 Полная документация: [README.md](README.md)
- 🐛 Проблемы: Создайте issue на GitHub
- 💬 Вопросы: Обсудите в Discussions
