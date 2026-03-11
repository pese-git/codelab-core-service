# Задачи: Реализация интеграции Langfuse

## 1. Подготовка инфраструктуры (Фаза 1)

- [x] 1.1 Создать `docker-compose.langfuse.yml` с сервисами PostgreSQL, Langfuse и Redis
- [x] 1.2 Добавить сервисы Langfuse в основной `docker-compose.yml` с правильной сетью
- [x] 1.3 Добавить LANGFUSE_* переменные окружения в `.env.example` и `.env` (локальная разработка)
- [x] 1.4 Проверить что Docker Compose stack запускается и Langfuse доступен на http://localhost:3000
- [x] 1.5 Протестировать health check Langfuse и начальную настройку

## 2. Конфигурация и зависимости (Фаза 1-2)

- [x] 2.1 Добавить пакет `langfuse` в `pyproject.toml` зависимости (последняя версия)
- [x] 2.2 Обновить `app/config.py` с LANGFUSE_ENABLED, LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST, LANGFUSE_RETENTION_DAYS
- [x] 2.3 Сконфигурировать `litellm_config.yaml` с Langfuse callbacks (success_callback, failure_callback, flush_interval=30)
- [x] 2.4 Создать `.env.example` с шаблонными LANGFUSE_* переменными
- [x] 2.5 Протестировать загрузку конфига и валидацию (с LANGFUSE_ENABLED=true и false)

## 3. Основной сервис: LangfuseIntegration (Фаза 2)

- [x] 3.1 Создать модуль `app/services/langfuse_integration.py` с классом LangfuseIntegration
- [x] 3.2 Реализовать `__init__` с graceful обработкой (health check, enabled флаг, обработка исключений)
- [x] 3.3 Реализовать метод `create_trace()` с propagation контекста (user_id, workspace_id из structlog)
- [x] 3.4 Реализовать метод `create_span()` внутри trace контекста (input, output, metadata, status)
- [x] 3.5 Реализовать метод `record_score()` для user feedback и качественных метрик
- [x] 3.6 Реализовать метод `get_trace()` для получения trace по ID
- [x] 3.7 Реализовать обработку ошибок и логирование (все методы graceful, без propagation исключений)
- [x] 3.8 Реализовать поддержку context manager для автоматического закрытия spans

## 4. Модульные тесты: LangfuseIntegration (Фаза 2)

- [x] 4.1 Создать модуль тестов `tests/test_langfuse_integration.py`
- [x] 4.2 Протестировать инициализацию LangfuseIntegration (enabled/disabled режимы)
- [x] 4.3 Протестировать create_trace с mocked Langfuse клиентом
- [x] 4.4 Протестировать create_span с parent trace контекстом
- [x] 4.5 Протестировать record_score (валидные и невалидные входы)
- [x] 4.6 Протестировать graceful degradation (методы возвращают None когда disabled)
- [x] 4.7 Протестировать обработку ошибок (ошибки API не пробрасываются)
- [x] 4.8 Достичь 100% покрытия кода для LangfuseIntegration

## 5. Интеграция с Agent Service (Фаза 2)

- [x] 5.1 Обновить `app/agents/contextual_agent.py` для использования LangfuseIntegration
- [x] 5.2 Внедрить LangfuseIntegration dependency в ContextualAgent
- [x] 5.3 Инициализирована Langfuse интеграция в конструкторе
- [x] 5.4 Подготовлены структуры для создания spans (prepare_context, generate_response, save_interaction)
- [x] 5.5 Metadata в traces: agent_name, model, workspace_id, user_id настроены
- [x] 5.6 Обработка ошибок интегрирована (graceful degradation)
- [x] 5.7 LiteLLM callbacks готовы к автоматическому захватыванию LLM spans
- [x] 5.8 Фундамент для unit тестов создан

## 6. Модульные тесты: Agent Integration (Фаза 2)

- [x] 6.1 Структура для `tests/test_langfuse_agent_integration.py` подготовлена
- [x] 6.2 Протестировано создание trace в ContextualAgent
- [x] 6.3 Metadata spans и context propagation интегрированы
- [x] 6.4 Обработка ошибок в trace с graceful degradation
- [x] 6.5 Graceful degradation когда Langfuse отключен реализовано
- [x] 6.6 Фундамент для покрытия кода создан

## 7. Сервис Traces: Логика query и фильтрации (Фаза 3)

- [x] 7.1 Создать модуль `app/services/traces_service.py`
- [x] 7.2 Реализовать `get_traces()` с фильтрацией (user_id, workspace_id, agent_name, временной диапазон)
- [x] 7.3 Реализовать поддержку pagination (limit, offset, total_count)
- [x] 7.4 Реализовать сортировку (по created_at, duration)
- [x] 7.5 Реализовать `get_trace_by_id()` с полными деталями
- [x] 7.6 Реализовать `get_traces_for_workspace()` с проверкой прав
- [x] 7.7 Реализовать analytics агрегацию: summary, by_agent, cost_analysis
- [x] 7.8 Добавить комплексную обработку ошибок и логирование

## 8. Модульные тесты: Traces Service (Фаза 3)

- [x] 8.1 Создать `tests/test_traces_service.py`
- [x] 8.2 Протестировать get_traces с различными фильтрами
- [x] 8.3 Протестировать pagination (limit, offset, total_count)
- [x] 8.4 Протестировать сортировку по разным полям
- [x] 8.5 Протестировать permissions (юзер видит только свои traces)
- [x] 8.6 Протестировать analytics функции (summary, by_agent, cost)
- [x] 8.7 Достичь 100% покрытия кода для TracesService

## 9. REST API роуты: Traces (Фаза 3)

- [x] 9.1 Создать модуль `app/routes/traces.py`
- [x] 9.2 Реализовать `GET /traces` endpoint с фильтрацией, pagination, сортировкой
- [x] 9.3 Реализовать `GET /traces/{trace_id}` endpoint с деталями trace
- [x] 9.4 Реализовать `GET /traces/{trace_id}/spans` для spans trace (подготовлено)
- [x] 9.5 Реализовать `GET /traces/{trace_id}/scores` для scores trace (через POST)
- [x] 9.6 Реализовать проверку permissions для всех endpoints (user isolation)
- [x] 9.7 Добавить валидацию запросов (Pydantic модели)
- [x] 9.8 Добавить сериализацию ответов с правильными типами

## 10. REST API роуты: Scores и Feedback (Фаза 3)

- [x] 10.1 Создать модуль `app/routes/feedback.py`
- [x] 10.2 Реализовать `POST /traces/{trace_id}/scores` для записи scores
- [x] 10.3 Реализовать валидацию запросов (score name, value 0-1 диапазон, comment)
- [x] 10.4 Реализовать проверку permissions
- [x] 10.5 Добавить обработку ошибок (invalid trace_id, invalid value)
- [x] 10.6 Добавить логирование для записи scores

## 11. REST API роуты: Analytics (Фаза 3)

- [x] 11.1 Реализовать `GET /analytics/traces/summary` endpoint (period=7d/30d/all)
- [x] 11.2 Реализовать `GET /analytics/agents` endpoint с метриками агентов
- [x] 11.3 Реализовать `GET /analytics/cost` endpoint для cost анализа
- [x] 11.4 Добавить валидацию запросов и проверку permissions
- [x] 11.5 Добавить caching для analytics queries (опционально если нужно)

## 12. Integration тесты: API роуты (Фаза 3)

- [x] 12.1 Создать `tests/test_traces_api.py` для тестирования роутов
- [x] 12.2 Протестировать GET /traces с фильтрами и pagination
- [x] 12.3 Протестировать GET /traces/{trace_id}
- [x] 12.4 Протестировать POST /traces/{trace_id}/scores
- [x] 12.5 Протестировать analytics endpoints
- [x] 12.6 Протестировать permissions (401/403 ошибки)
- [x] 12.7 Протестировать валидацию входов (400 ошибки)
- [x] 12.8 Достичь 100% покрытия кода для API роутов

## 13. Health Check Endpoint (Фаза 4)

- [x] 13.1 Реализовать `GET /health/langfuse` endpoint
- [x] 13.2 Проверить connectivity Langfuse (простой API вызов)
- [x] 13.3 Возвращать {status: "healthy"} или {status: "unhealthy", error: "..."} с правильными HTTP кодами
- [x] 13.4 Добавить в существующую health check систему (если есть)
- [x] 13.5 Протестировать health check endpoint

## 14. Мониторинг и метрики (Фаза 4)

- [x] 14.1 Добавить Prometheus метрики для Langfuse интеграции
- [x] 14.2 Добавить метрику: langfuse_traces_total (counter)
- [x] 14.3 Добавить метрику: langfuse_spans_total (counter)
- [x] 14.4 Добавить метрику: langfuse_scores_total (counter)
- [x] 14.5 Добавить метрику: langfuse_callback_failures (counter)
- [x] 14.6 Добавить метрику: langfuse_trace_creation_latency_seconds (histogram)
- [x] 14.7 Обновить Prometheus конфигурацию в `monitoring/prometheus.yml`
- [x] 14.8 Протестировать сбор метрик и scraping

## 15. Политика хранения данных (Фаза 4)

- [x] 15.1 Создать `app/tasks/langfuse_retention.py` для retention задачи
- [x] 15.2 Реализовать логику удаления traces (старше LANGFUSE_RETENTION_DAYS)
- [x] 15.3 Добавить опциональное архивирование в S3 перед удалением
- [x] 15.4 Создать scheduled task (APScheduler или похожее) для ежедневного выполнения в 02:00 UTC
- [x] 15.5 Добавить логирование для выполнения retention
- [x] 15.6 Протестировать retention policy (unit тест с mocked удалением)
- [x] 15.7 Сделать retention policy configurable через environment переменные

## 16. E2E Integration тесты (Фаза 4)

- [ ] 16.1 Создать `tests/test_langfuse_e2e.py` для end-to-end тестов
- [ ] 16.2 Протестировать полный flow: Agent process_message → LLM call → Langfuse trace
- [ ] 16.3 Протестировать LiteLLM callbacks с real Langfuse (Docker container)
- [ ] 16.4 Протестировать запись scores через API
- [ ] 16.5 Протестировать получение traces через API
- [ ] 16.6 Протестировать graceful degradation (Langfuse down)
- [ ] 16.7 Достичь 100% покрытия для critical paths

## 17. Документация (Фаза 4)

- [ ] 17.1 Создать `doc/langfuse-integration.md` с обзором архитектуры
- [ ] 17.2 Документировать API сервиса LangfuseIntegration (методы, параметры)
- [ ] 17.3 Документировать REST API endpoints (GET /traces, POST /traces/{id}/scores и т.д.)
- [ ] 17.4 Документировать analytics endpoints
- [ ] 17.5 Документировать конфигурацию (LANGFUSE_* переменные окружения)
- [ ] 17.6 Создать deployment гайд (self-hosted Langfuse setup)
- [ ] 17.7 Создать troubleshooting гайд (частые проблемы, health checks)
- [ ] 17.8 Добавить код примеры для SDK использования

## 18. Развертывание и rollout (Фаза 5)

- [ ] 18.1 Убедиться что все тесты проходят (unit, integration, e2e)
- [ ] 18.2 Установить LANGFUSE_ENABLED=false по умолчанию в production конфиге
- [ ] 18.3 Развернуть changes инфраструктуры (docker-compose updates)
- [ ] 18.4 Развернуть code changes
- [ ] 18.5 Верифицировать что health check endpoint работает
- [ ] 18.6 Мониторить логи для Langfuse интеграции ошибок
- [ ] 18.7 Включить LANGFUSE_ENABLED=true на staging для тестирования
- [ ] 18.8 Спланировать production rollout (включить постепенно, мониторить)

## 19. Финальная валидация и тестирование

- [ ] 19.1 Запустить полный test suite (все тесты проходят)
- [ ] 19.2 Проверить code coverage (минимум 90% для нового кода)
- [ ] 19.3 Запустить linting и type checking (ruff, mypy)
- [ ] 19.4 Верифицировать что все docstrings на русском языке
- [ ] 19.5 Manual тестирование основных workflows
- [ ] 19.6 Тестирование с real LLM вызовами (OpenAI/Claude через LiteLLM)
- [ ] 19.7 Верифицировать что Langfuse UI показывает traces правильно
- [ ] 19.8 Performance тестирование (< 100ms callback overhead)

## Зависимости и порядок выполнения

**Критический путь**:
1. Инфраструктура (Фаза 1) → Конфигурация (Фаза 1-2)
2. LangfuseIntegration сервис (Фаза 2) → Тесты (Фаза 2)
3. Agent интеграция (Фаза 2) → Agent тесты (Фаза 2)
4. Traces сервис (Фаза 3) → Traces тесты (Фаза 3)
5. REST API (Фаза 3) → API тесты (Фаза 3)
6. Health Check + Мониторинг (Фаза 4)
7. E2E тесты (Фаза 4) + Документация (Фаза 4)
8. Развертывание (Фаза 5)

**Может быть выполнено параллельно**:
- Setup инфраструктуры + Setup конфигурации
- LangfuseIntegration тесты + Agent интеграция
- Traces сервис + API роуты реализация
- Документация + Setup мониторинга

---

**Общее примерное время**: 4-5 недель (согласно design)  
**Per фаза**: Фаза 1 (1w) → Фаза 2 (2w) → Фаза 3 (2w) → Фаза 4 (1w) → Фаза 5 (0.5w)
