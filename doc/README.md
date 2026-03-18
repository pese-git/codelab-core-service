# 📚 Документация CodeLab Core Service

Добро пожаловать в полную документацию **CodeLab Core Service** - персональной мультиагентной AI платформы с полной изоляцией пользователей.

## 🚀 Быстрый доступ

### Для новых пользователей
1. 📖 [Quick Start](./getting-started/quickstart.md) - Быстрый запуск за 5 минут
2. 🔧 [Setup Guide](./getting-started/setup-guide.md) - Детальная установка
3. 🏗️ [System Architecture](./architecture/system-overview.md) - Обзор архитектуры

### Для разработчиков
1. 👨‍💻 [Developer Guide](./guides/developer-guide.md) - Руководство разработчика
2. 📐 [Integration Guide](./guides/integration-guide.md) - Интеграция
3. 🧪 [REST API Documentation](./api/rest-api.md) - API спецификация

### Для DevOps / Операций
1. 🚀 [Deployment Guide](./deployment/deployment-guide.md) - Полное развертывание
2. 📊 [Infrastructure Setup](./getting-started/infrastructure-setup.md) - Инфраструктура
3. ✅ [Production Checklist](./deployment/production-checklist.md) - Pre-production проверка

### Для интеграций
1. 🧠 [LiteLLM Integration](./integrations/litellm-integration.md) - LiteLLM провайдеры
2. 📍 [Langfuse v4 Integration](./integrations/langfuse-v4-integration-summary.md) - Мониторинг
3. 🔌 [LLM Providers Management](./integrations/litellm-providers-management.md) - Управление провайдерами

---

## 📂 Структура документации

```
doc/
├── README.md                           # 👈 Главный обзор (вы здесь)
├── INDEX.md                            # Полный индекс документации
│
├── getting-started/                    # 🚀 Начало работы
│   ├── README.md                       # Обзор для новичков
│   ├── quickstart.md                   # Быстрый старт за 5 минут
│   ├── setup-guide.md                  # Детальная установка
│   └── infrastructure-setup.md         # Настройка инфраструктуры
│
├── architecture/                       # 🏗️ Архитектурная документация
│   ├── README.md                       # Навигация по архитектуре
│   ├── system-overview.md              # Обзор архитектуры системы
│   ├── component-details.md            # Детали компонентов
│   ├── workspace-lifecycle.md          # Жизненный цикл workspace
│   ├── event-log-outbox-architecture.md # Event Outbox архитектура
│   └── diagrams.md                     # Диаграммы системы
│
├── api/                                # 🔌 API документация
│   ├── README.md                       # Обзор API
│   ├── rest-api.md                     # REST API спецификация
│   ├── streaming-fetch-api.md          # Streaming API
│   ├── sse-event-streaming.md          # SSE события
│   └── api-specification.md            # Полная спецификация
│
├── guides/                             # 📖 Практические руководства
│   ├── README.md                       # Обзор руководств
│   ├── developer-guide.md              # Для разработчиков
│   ├── integration-guide.md            # Интеграция
│   ├── llm-error-handling.md           # Обработка ошибок LLM
│   ├── tool-risk-assessment.md         # Оценка рисков инструментов
│   └── technical-requirements.md       # Технические требования
│
├── deployment/                         # 🚀 Развёртывание
│   ├── deployment-guide.md             # Полное руководство
│   └── production-checklist.md         # Чеклист для production
│
├── integrations/                       # 🔗 Внешние интеграции
│   ├── README.md                       # Обзор интеграций
│   ├── litellm-integration.md          # LiteLLM
│   ├── litellm-docker-integration.md   # Docker интеграция
│   ├── litellm-providers-management.md # Управление провайдерами
│   ├── langfuse-v4-integration-summary.md # Langfuse v4
│   └── llm-providers-api.md            # LLM провайдеры API
│
├── features/                           # ✨ Описание функциональности
│   ├── README.md                       # Обзор функций
│   ├── agent-tools.md                  # Инструменты агентов
│   ├── agent-context.md                # Контекст агентов
│   ├── workspace-architecture.md       # Архитектура workspace
│   ├── session-id-propagation.md       # Session ID пропагация
│   ├── tool-execution-tracing.md       # Tracing инструментов
│   ├── idempotency.md                  # Идемпотентность
│   ├── project-initialization.md       # Инициализация проектов
│   └── llm-tools-integration.md        # Интеграция LLM инструментов
│
├── changelogs/                         # 📜 История изменений
│   ├── CHANGELOG.md                    # Главный changelog
│   ├── CHANGELOG_V0.2.0.md
│   ├── CHANGELOG_WORKSPACE_ARCHITECTURE.md
│   ├── CHANGELOG_LLM_PROVIDERS_MANAGEMENT.md
│   └── ... (остальные CHANGELOG_*.md)
│
├── implementation/                     # 📋 Отчёты о реализации
│   ├── implementation-summary.md       # Сводка реализации
│   ├── tool-execution-trace-design.md  # Design trace инструментов
│   ├── client-tools-implementation.md  # Реализация client tools
│   └── release-specification-v0.2.0.md # Спецификация v0.2.0
│
├── reports/                            # 📊 Технические отчёты
│   ├── code-analysis-report.md         # Анализ кода
│   ├── specification-consistency-report.md # Согласованность спец.
│   ├── infrastructure-complete.md      # Инфраструктура завершена
│   ├── session-id-propagation-report.md # Session ID отчёт
│   ├── span-lifecycle-fix-report.md    # Span lifecycle отчёт
│   ├── sqlalchemy-lazy-loading-fix.md  # SQLAlchemy отчёт
│   └── database-analysis.md            # Анализ БД
│
├── bugfixes/                           # 🐛 Исправления ошибок
│   ├── README.md                       # Обзор исправлений
│   ├── detached-instance-error-fix.md  # Detached instance ошибка
│   ├── duplicate-events-fix.md         # Дублирующиеся события
│   ├── message-events-fix.md           # Message events ошибка
│   ├── litellm-request-fix.md          # LiteLLM запрос ошибка
│   └── pathvalidator-fix.md            # PathValidator ошибка
│
├── migrations/                         # 🔄 Миграционные руководства
│   ├── sse-to-streaming-migration.md   # SSE → Streaming
│   ├── v0.2.0-migration.md             # Миграция на v0.2.0
│   └── workspace-architecture-clarification.md # Clarification
│
├── samples/                            # 💡 Примеры кода
│   ├── samples.md                      # Основные примеры
│   └── gradio-ui-guide.md              # Gradio UI примеры
│
└── archive/                            # 📦 Архив (устаревшие документы)
    ├── README.md                       # Индекс архива
    ├── langfuse-opentelemetry-removal/ # Deprecated feature
    ├── docker-logs-analysis/           # Анализ логов (obsolete)
    └── phase4-deployment/              # Phase 4 documentation
```

---

## 🎯 По ролям

### 🆕 Новичок в CodeLab?
1. Начните с [Quick Start](./getting-started/quickstart.md) - 5 минут
2. Прочитайте [System Overview](./architecture/system-overview.md) - понимание архитектуры
3. Изучите [REST API](./api/rest-api.md) - как использовать API
4. Посмотрите [Samples](./samples/samples.md) - примеры кода

### 👨‍💻 Разработчик
1. [Developer Guide](./guides/developer-guide.md) - Setup и best practices
2. [Architecture Details](./architecture/system-overview.md) - компоненты системы
3. [Component Details](./architecture/component-details.md) - API каждого компонента
4. [Integration Guide](./guides/integration-guide.md) - как расширять систему

### 🏗️ DevOps / Архитектор
1. [Deployment Guide](./deployment/deployment-guide.md) - полный процесс
2. [Production Checklist](./deployment/production-checklist.md) - before going live
3. [Infrastructure Setup](./getting-started/infrastructure-setup.md) - инфраструктура
4. [System Architecture](./architecture/system-overview.md) - понимание нагрузки

### 🤖 Интеграции LLM
1. [LLM Providers Management](./integrations/litellm-providers-management.md) - управление
2. [LiteLLM Integration](./integrations/litellm-integration.md) - детали
3. [LLM Error Handling](./guides/llm-error-handling.md) - обработка ошибок
4. [Langfuse Integration](./integrations/langfuse-v4-integration-summary.md) - мониторинг

---

## 📖 Категории по темам

### 🏗️ Архитектура и дизайн
- [System Overview](./architecture/system-overview.md) - полный обзор
- [Component Details](./architecture/component-details.md) - компоненты
- [Workspace Lifecycle](./architecture/workspace-lifecycle.md) - жизненный цикл
- [Event Log Outbox Architecture](./architecture/event-log-outbox-architecture.md) - события

### 🔌 API и интеграции
- [REST API](./api/rest-api.md) - полная спецификация
- [Streaming API](./api/streaming-fetch-api.md) - streaming
- [SSE Events](./api/sse-event-streaming.md) - real-time события
- [Integration Guide](./guides/integration-guide.md) - как интегрировать

### 🚀 Развертывание и операции
- [Deployment Guide](./deployment/deployment-guide.md) - local, Docker, K8s
- [Production Checklist](./deployment/production-checklist.md) - перед production
- [Infrastructure Setup](./getting-started/infrastructure-setup.md) - требования

### 🤖 Агенты и инструменты
- [Agent Tools](./features/agent-tools.md) - система инструментов
- [Agent Context](./features/agent-context.md) - контекстное хранилище
- [Tool Execution Tracing](./features/tool-execution-tracing.md) - отслеживание
- [Tool Risk Assessment](./guides/tool-risk-assessment.md) - оценка рисков

### 🧠 LLM интеграции
- [LiteLLM Integration](./integrations/litellm-integration.md) - основы
- [Providers Management](./integrations/litellm-providers-management.md) - управление
- [LLM Error Handling](./guides/llm-error-handling.md) - обработка ошибок
- [LLM Providers API](./integrations/llm-providers-api.md) - API

### 📊 Мониторинг и отчёты
- [Langfuse Integration](./integrations/langfuse-v4-integration-summary.md) - мониторинг
- [Code Analysis Reports](./reports/code-analysis-report.md) - анализ
- [Infrastructure Report](./reports/infrastructure-complete.md) - состояние

---

## 📋 Быстрые ссылки

| Документ | Описание |
|----------|---------|
| [CHANGELOG.md](./changelogs/CHANGELOG.md) | История изменений |
| [INDEX.md](./INDEX.md) | Полный индекс всех документов |
| [Samples](./samples/samples.md) | Примеры кода и использования |
| [Technical Requirements](./guides/technical-requirements.md) | Технические требования |

---

## 🆘 Помощь

- 📖 Не знаете где начать? → [Getting Started](./getting-started/)
- 🔍 Ищете документ? → [INDEX.md](./INDEX.md)
- 🐛 Нашли баг? → [Bugfixes](./bugfixes/)
- 📦 Обновление версии? → [Migrations](./migrations/)

---

**Последнее обновление**: Март 2026  
**Версия**: 0.2.0  
**Статус**: Production Ready
