# Анализ логов Docker Compose - Отчет об ошибках

**Дата анализа:** 10 Марта 2026 г., 08:03 UTC
**Статус контейнеров:** 
- ✅ app (codelab-core-service) - healthy
- ✅ postgres - healthy  
- ✅ redis - healthy
- ✅ qdrant - healthy
- ✅ prometheus - healthy
- ✅ grafana - healthy
- ❌ jaeger - **unhealthy**
- ❌ litellm - **unhealthy**

---

## 🔴 КРИТИЧЕСКИЕ ОШИБКИ

### 1. SQLAlchemy DetachedInstanceError (App)
**Файл:** `app/services/llm_provider_service.py` или обработчик сообщений
**Проблема:** `DetachedInstanceError: Instance <UserLLMProvider> is not bound to a Session`
**Причина:** Объект `UserLLMProvider` был отсоединен от SQLAlchemy сессии и позже попыталась обновить его атрибуты.
**Последствие:** 500 Internal Server Error при обработке сообщений в чате
**Примеры:**
- POST `/my/projects/.../chat/.../message/` возвращает 500 ошибку
- Ошибка происходит в `direct_execution_error` обработчике

```python
sqlalchemy.orm.exc.DetachedInstanceError: Instance <UserLLMProvider at 0xffff8ccb6870> is not bound to a Session; 
attribute refresh operation cannot proceed
```

**Решение:** Необходимо:
1. Загружать объект `UserLLMProvider` в контексте активной сессии
2. Или использовать `merge()` для переприсоединения отсоединённого объекта
3. Или загружать только нужные атрибуты в текущей сессии перед её закрытием

---

### 2. Redis Security Attack Logs (Redis)
**Проблема:** Redis регулярно получает HTTP POST запросы вместо Redis протокола
**Сообщение:** `Possible SECURITY ATTACK detected. It looks like somebody is sending POST or Host: commands to Redis`
**Частота:** Каждые ~75 секунд (8 случаев в последние 9 минут)
**Источник:** `172.25.0.4:XXXXX` (это app контейнер)
**Причина:** Клиент неправильно пытается подключиться к Redis, возможно:
- Health check отправляет HTTP запрос вместо PING команды
- Некорректная конфигурация Redis клиента в приложении
- Proxy или middleware неправильно форматирует запросы

**Решение:**
1. Проверить health check конфигурацию для Redis
2. Убедиться что Redis клиент использует правильный протокол (не HTTP)
3. Проверить логику подключения в `app/redis_client.py`

---

### 3. Duplicate Project Creation Error (App & PostgreSQL)
**Проблема:** Попытка создать проект с именем `cherrypick` в пути `/Users/sergey/Projects/Flutter/Pets/cherrypick`
**Ошибка:** `IntegrityError: duplicate key value violates unique constraint "uq_user_projects_name_workspace_path"`
**Статус:** 500 Internal Server Error на `POST /my/projects/`
**Причина:** Ограничение уникальности проекта по (name, workspace_path) уже нарушено

**Решение:**
1. Реализовать проверку существования проекта перед созданием
2. Возвращать более информативную ошибку (400 Bad Request)
3. Обновлять существующий проект вместо попытки создания нового (idempotency)

---

## 🟠 СЕРЬЁЗНЫЕ ПРОБЛЕМЫ

### 4. PostgreSQL Missing LiteLLM Tables
**Проблема:** LiteLLM ищет таблицу `Last30dTopEndUsersSpend` которой не существует
**Ошибка:** `ERROR: relation "Last30dTopEndUsersSpend" does not exist`
**Источник:** LiteLLM контейнер при инициализации или health check
**Последствие:** Может вызвать проблемы с аналитикой в LiteLLM

**Решение:**
1. Проверить миграции LiteLLM базы данных
2. Убедиться что все таблицы созданы при инициализации контейнера
3. Или отключить запросы к этой таблице если она не используется

---

### 5. Jaeger Unhealthy Status
**Проблема:** Контейнер `codelab-jaeger` имеет статус `unhealthy`
**Health Check:** Проверяет `http://localhost:16686/api/services`
**Логи:** Контейнер стартует корректно, но health check не проходит
**Возможные причины:**
- Health check endpoint недоступен
- Timeout в health check конфигурации
- OTEL collector не полностью инициализирован

**Решение:** Увеличить `start_period` в health check для Jaeger

---

### 6. LiteLLM Unhealthy Status  
**Проблема:** Контейнер `codelab-litellm` имеет статус `unhealthy`
**Логи:** Контейнер работает, обрабатывает запросы (HTTP 200), выполняет регулярные задачи
**Возможные причины:**
- Health check endpoint возвращает неправильный статус
- Проблема с инициализацией/подключением БД для LiteLLM
- Зависимость от отсутствующей таблицы `Last30dTopEndUsersSpend`

**Решение:** 
1. Проверить health check конфигурацию
2. Разрешить проблему с отсутствующей таблицей PostgreSQL
3. Убедиться что все зависимости готовы

---

## 🟡 ПРЕДУПРЕЖДЕНИЯ

### 7. PostgreSQL Invalid Startup Packets
**Проблема:** `LOG: invalid length of startup packet` каждые 15 секунд
**Количество:** 30+ ошибок в последние 9 минут
**Причина:** Неполные/повреждённые пакеты при попытках подключения
**Вероятная причина:** Health check или мониторинг отправляет некорректные пакеты

**Решение:**
1. Проверить health check конфигурацию PostgreSQL
2. Убедиться что мониторинг (Prometheus) использует правильный протокол подключения

---

### 8. App Metrics Endpoint Not Found
**Проблема:** Prometheus пытается достучаться до `/metrics` на app контейнере
**Ошибка:** `GET /metrics HTTP/1.1" 404 Not Found`
**Частота:** Каждые 10-15 секунд из Prometheus
**Причина:** Endpoint `/metrics` не реализован в FastAPI приложении

**Решение:**
1. Установить `prometheus-client` library
2. Реализовать `/metrics` endpoint или использовать middleware для Prometheus
3. Проверить конфигурацию Prometheus (`monitoring/prometheus.yml`)

---

## 📋 СВОДКА ДЕЙСТВИЙ

| Приоритет | Ошибка | Компонент | Статус |
|-----------|--------|-----------|--------|
| 🔴 CRITICAL | DetachedInstanceError на UserLLMProvider | app | Требует срочного исправления |
| 🔴 CRITICAL | Redis получает HTTP вместо Redis протокола | redis/app | Требует срочного исправления |
| 🟠 HIGH | Duplicate project constraint violation | app/postgres | Требует исправления |
| 🟠 HIGH | Missing LiteLLM table Last30dTopEndUsersSpend | litellm/postgres | Требует исправления |
| 🟠 HIGH | Jaeger unhealthy status | jaeger | Требует исправления |
| 🟠 HIGH | LiteLLM unhealthy status | litellm | Требует исправления |
| 🟡 MEDIUM | /metrics endpoint not found | app/prometheus | Улучшение мониторинга |
| 🟡 MEDIUM | PostgreSQL invalid startup packets | postgres | Оптимизация health check |

---

## 🔧 РЕКОМЕНДУЕМЫЙ ПОРЯДОК ИСПРАВЛЕНИЯ

1. **Немедленно:** Исправить `DetachedInstanceError` в обработчике LLM Provider сообщений
2. **Немедленно:** Исправить Redis security attack logs - проверить health check конфигурацию
3. **Срочно:** Добавить проверку дубликатов при создании проекта
4. **Срочно:** Исправить missing таблицу LiteLLM или отключить её использование
5. **Вскоре:** Реализовать `/metrics` endpoint для Prometheus
6. **Вскоре:** Оптимизировать health check конфигурации для Jaeger и LiteLLM
