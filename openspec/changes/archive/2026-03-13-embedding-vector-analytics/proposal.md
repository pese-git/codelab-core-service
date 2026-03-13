# Phase 5: Advanced Tracing - Embedding & Vector Analytics - Proposal

## Проблема

Текущее трейсирование исполнения инструментов (Phase 4) обеспечивает видимость в вызовы инструментов, но не дает понимания операций в семантической памяти (RAG контекст) и векторных вычислениях. Это ограничивает нашу способность:

- Отладки качества RAG (почему поиск вернул неоптимальный контекст?)
- Оптимизации производительности семантической памяти (какие embeddings медленные? какие запросы дорогие?)
- Анализа стоимости и latency embeddings в масштабе
- Корреляции между качеством контекста и успехом исполнения инструментов

Phase 5 добавляет комплексное трейсирование для генерации embeddings, векторных поисков и операций извлечения контекста - делая RAG контекст таким же наблюдаемым, как исполнение инструментов.

## Что изменяется

- **Embedding Tracing**: Каждый вызов embedding (пользовательские запросы, документы, контекст) создает Langfuse spans с latency, количеством токенов и стоимостью
- **Vector Search Tracing**: Операции поиска в Qdrant трейсируются с:
  - Метриками embedding запроса (latency, размер вектора)
  - Параметрами поиска (top_k, threshold, метрика расстояния)
  - Статистикой результатов (найдено совпадений, min/max scores сходства)
  - Breakdown latency поиска (embedding + search + фильтрация)
- **Analytics API для контекста**: REST API для анализа качества RAG контекста:
  - Какие embeddings используются чаще всего
  - Средний latency извлечения по агентам
  - Метрики качества контекста (relevance scores если доступны)
  - Метрики эффективности использования токенов
- **Dashboard производительности**: SQL запросы для выявления:
  - Дорогостоящих embeddings (стоимость за запрос)
  - Медленных векторных поисков (latency outliers)
  - Hit rates embedding cache
  - Самых используемых vs малоиспользуемых chunk контекста
- **Cost Attribution**: Детальный breakdown:
  - Стоимость по агентам (по операциям семантической памяти)
  - Стоимость по embedding модели
  - Стоимость по пользовательскому workspace

## Capabilities

### Новые capabilities

- `embedding-trace-collection`: Автоматическое создание spans для вызовов embedding API (OpenAI, локальные модели) с трейсированием latency, количества токенов и стоимости
- `vector-similarity-tracing`: Операции поиска сходства в Qdrant трейсируются с метриками запроса, параметрами и статистикой результатов
- `context-retrieval-analytics-api`: REST endpoints для запросов производительности RAG контекста (latency, качество, стоимость)
- `semantic-memory-performance-metrics`: Агрегация spans из Langfuse для анализа производительности embeddings и поисков в масштабе
- `rag-context-quality-scoring`: Механизм feedback для записи relevance scores контекста и корреляции с успехом исполнения инструментов
- `embedding-cost-attribution`: Breakdown стоимости по агентам, по embedding моделям, по workspaces

### Модифицированные capabilities

- `llm-call-tracing`: Расширение для включения embedding spans в полную иерархию trace (embedding → LLM call → tool use)
- `tool-execution-trace`: Вложенный span для операций семантической памяти (стоимость извлечения контекста включена в tool execution span)

## Влияние

### Изменения кода

- [`app/services/langfuse_integration.py`](../../app/services/langfuse_integration.py) - Добавить методы для embedding spans, трейсирование векторного поиска, analytics контекста
- `app/services/vector_store_service.py` - Интеграция с Qdrant для создания trace spans до/после поиска
- `app/services/embedding_service.py` - Обертка вызовов embedding API с созданием Langfuse spans
- [`app/routes/traces.py`](../../app/routes/traces.py) - Новые endpoints для metrics embeddings, analytics векторного поиска, качества контекста
- `app/agent/agent_context_store.py` - Инструментирование операций извлечения контекста трейсированием

### База данных/Storage

- Нет новых таблиц - все данные хранятся в Langfuse (spans с custom атрибутами)
- Возможно: Добавить `embedding_trace_cache` Redis ключ для недавних embedding metrics

### Изменения API

- Новые REST endpoints:
  - `GET /api/traces/embeddings/metrics` - Метрики производительности embeddings
  - `GET /api/traces/embeddings/cost-breakdown` - Анализ стоимости по агентам/моделям
  - `GET /api/traces/vector-searches/analytics` - Производительность векторного поиска
  - `POST /api/traces/context/feedback` - Запись scores качества контекста
  - `GET /api/traces/semantic-memory/performance` - Общая производительность RAG

### Зависимости

- Нет новых external dependencies (использует существующий Langfuse SDK)
- Требует: Langfuse 2.60+ (поддержка custom span attributes и cost tracking)

### Performance

- Создание embedding span: < 5ms overhead за вызов
- Трейсирование векторного поиска: < 10ms overhead за поиск
- Общий overhead за tool execution: < 50ms (поддерживаем Phase 4 требование)
- Graceful degradation если Langfuse недоступна (инструменты продолжают работать, трейсирование отключено)

## Non-Goals

- Real-time мониторинг качества embeddings (только batch анализ)
- Автоматическая оптимизация embeddings (только рекомендации)
- Re-ranking результатов поиска по metrics трейса (только analysis layer)
- Кэширование embeddings на клиенте (только server-side, TBD для Phase 6)

## Timeline реализации

- **Design**: 3-4 часа (архитектура, API контракты, Langfuse схема)
- **Implementation**: 16-20 часов (4 компонента + integration тесты)
- **Testing**: 8-10 часов (unit, integration, E2E, performance)
- **Documentation**: 4-6 часов (guide, API docs, troubleshooting)

**Всего**: ~40-45 часов (~1 неделя с параллельными задачами)

## Зависимости

- ✅ Phase 4 Complete: Tool Execution Tracing (базовая инфраструктура)
- ✅ Langfuse Integration: LLM Call Tracing (существующая иерархия spans)
- ✅ Agent Context Store: Vector store реализация готова
- ✅ Embedding Service: Базовая инфраструктура embeddings на месте

Все зависимости удовлетворены - готовы переходить на design этап.
