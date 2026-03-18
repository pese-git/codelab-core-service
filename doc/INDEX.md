# 📚 Полный индекс документации CodeLab Core Service

Справочник всех документов в проекте, организованный по категориям.

---

## 🚀 Getting Started (Начало работы)

| Документ | Описание | Целевая аудитория |
|----------|---------|-------------------|
| [Quick Start](./getting-started/quickstart.md) | Быстрый старт за 5 минут | Новичок |
| [Setup Guide](./getting-started/setup-guide.md) | Детальная установка | Разработчик |
| [Infrastructure Setup](./getting-started/infrastructure-setup.md) | Настройка инфраструктуры | DevOps |

---

## 🏗️ Architecture (Архитектура)

### Обзор и основы
| Документ | Описание |
|----------|---------|
| [System Overview](./architecture/system-overview.md) | Полный обзор архитектуры системы с диаграммами |
| [Component Details](./architecture/component-details.md) | Детальное описание всех компонентов |
| [Architecture README](./architecture/README.md) | Обзор архитектурной документации |

### Специализированные архитектуры
| Документ | Описание |
|----------|---------|
| [Workspace Lifecycle](./architecture/workspace-lifecycle.md) | Жизненный цикл workspace |
| [Event Log Outbox Architecture](./architecture/event-log-outbox-architecture.md) | Архитектура event logging |
| [Diagrams](./architecture/diagrams.md) | Диаграммы системы |

---

## 🔌 API (API документация)

### REST API
| Документ | Описание |
|----------|---------|
| [REST API](./api/rest-api.md) | Полная спецификация REST API |
| [API Specification](./api/api-specification.md) | Детальная спецификация |
| [API README](./api/README.md) | Обзор API документации |

### Real-time API
| Документ | Описание |
|----------|---------|
| [SSE Event Streaming](./api/sse-event-streaming.md) | Server-Sent Events для real-time |
| [Streaming Fetch API](./api/streaming-fetch-api.md) | Streaming API с fetch |
| [Project Management Endpoints](./api/project-management-endpoints.md) | Endpoints управления проектами |

---

## 📖 Guides (Руководства)

| Документ | Описание | Для кого |
|----------|---------|----------|
| [Developer Guide](./guides/developer-guide.md) | Руководство для разработчиков | Разработчик |
| [Integration Guide](./guides/integration-guide.md) | Как интегрировать с системой | Разработчик |
| [LLM Error Handling](./guides/llm-error-handling.md) | Обработка ошибок LLM | Разработчик |
| [Tool Risk Assessment](./guides/tool-risk-assessment.md) | Оценка рисков инструментов | Архитектор |
| [Technical Requirements](./guides/technical-requirements.md) | Технические требования | DevOps |
| [Guides README](./guides/README.md) | Обзор руководств | - |

---

## 🚀 Deployment (Развёртывание)

| Документ | Описание | Для кого |
|----------|---------|----------|
| [Deployment Guide](./deployment/deployment-guide.md) | Полное руководство по развертыванию | DevOps |
| [Production Checklist](./deployment/production-checklist.md) | Чеклист перед production | DevOps |

---

## 🔗 Integrations (Внешние интеграции)

### LiteLLM
| Документ | Описание |
|----------|---------|
| [LiteLLM Integration](./integrations/litellm-integration.md) | Основная интеграция LiteLLM |
| [LiteLLM Docker Integration](./integrations/litellm-docker-integration.md) | Docker интеграция |
| [LiteLLM Providers Management](./integrations/litellm-providers-management.md) | Управление провайдерами |

### Other LLMs
| Документ | Описание |
|----------|---------|
| [Langfuse v4 Integration](./integrations/langfuse-v4-integration-summary.md) | Интеграция с Langfuse v4 |
| [LLM Providers API](./integrations/llm-providers-api.md) | API для управления LLM провайдерами |
| [Integrations README](./integrations/README.md) | Обзор интеграций |

---

## ✨ Features (Функциональность)

### Agent System
| Документ | Описание |
|----------|---------|
| [Agent Tools](./features/agent-tools.md) | Система инструментов для агентов |
| [Agent Context](./features/agent-context.md) | Контекстное хранилище агентов |
| [Agent Tools Workflow](./features/agent-tools-workflow.md) | Workflow использования инструментов |

### Workspace & Sessions
| Документ | Описание |
|----------|---------|
| [Workspace Architecture](./features/workspace-architecture.md) | Архитектура рабочего пространства |
| [Project Initialization](./features/project-initialization.md) | Инициализация проектов |
| [Session ID Propagation](./features/session-id-propagation.md) | Пропагация ID сессии |

### Technical Features
| Документ | Описание |
|----------|---------|
| [Tool Execution Tracing](./features/tool-execution-tracing.md) | Отслеживание выполнения инструментов |
| [Idempotency](./features/idempotency.md) | Идемпотентность операций |
| [LLM Tools Integration](./features/llm-tools-integration.md) | Интеграция инструментов LLM |
| [Features README](./features/README.md) | Обзор функциональности |

---

## 📜 Changelogs (История изменений)

| Документ | Описание |
|----------|---------|
| [CHANGELOG.md](./changelogs/CHANGELOG.md) | Главный changelog всех версий |
| [CHANGELOG_V0.2.0.md](./changelogs/CHANGELOG_V0.2.0.md) | Changelog для v0.2.0 |
| [CHANGELOG_WORKSPACE_ARCHITECTURE.md](./changelogs/CHANGELOG_WORKSPACE_ARCHITECTURE.md) | Изменения в workspace архитектуре |
| [CHANGELOG_LLM_PROVIDERS_MANAGEMENT.md](./changelogs/CHANGELOG_LLM_PROVIDERS_MANAGEMENT.md) | Изменения в управлении провайдерами |
| [CHANGELOG_SPECIFICATION_ACTUALIZATION.md](./changelogs/CHANGELOG_SPECIFICATION_ACTUALIZATION.md) | Обновления спецификации |
| [CHANGELOG_TOOL_EXECUTION_TRACE_DESIGN.md](./changelogs/CHANGELOG_TOOL_EXECUTION_TRACE_DESIGN.md) | Design tool execution trace |
| [CHANGELOG_WORKSPACE_ARCHITECTURE_CLARIFICATION.md](./changelogs/CHANGELOG_WORKSPACE_ARCHITECTURE_CLARIFICATION.md) | Clarification workspace |

---

## 📋 Implementation (Отчёты о реализации)

| Документ | Описание |
|----------|---------|
| [Implementation Summary](./implementation/implementation-summary.md) | Сводка реализации |
| [Tool Execution Trace Design](./implementation/tool-execution-trace-design.md) | Design trace инструментов |
| [Client Tools Implementation](./implementation/client-tools-implementation.md) | Реализация client tools |
| [Release Specification v0.2.0](./implementation/release-specification-v0.2.0.md) | Спецификация релиза v0.2.0 |
| [Verification Orchestrator Implementation](./implementation/verification-orchestrator-implementation.md) | Верификация оркестратора |

---

## 📊 Reports (Технические отчёты)

### Code & Architecture Analysis
| Документ | Описание |
|----------|---------|
| [Code Analysis Report](./reports/code-analysis-report.md) | Анализ кода проекта |
| [Specification Consistency Report](./reports/specification-consistency-report.md) | Согласованность спецификации |
| [Database Analysis](./reports/database-analysis.md) | Анализ базы данных |

### Implementation Reports
| Документ | Описание |
|----------|---------|
| [Infrastructure Complete](./reports/infrastructure-complete.md) | Инфраструктура завершена |
| [Session ID Propagation Report](./reports/session-id-propagation-report.md) | Отчёт о пропагации ID |
| [Span Lifecycle Fix Report](./reports/span-lifecycle-fix-report.md) | Отчёт о span lifecycle |
| [SQLAlchemy Lazy Loading Fix](./reports/sqlalchemy-lazy-loading-fix.md) | Отчёт о lazy loading |

### Verification Reports
| Документ | Описание |
|----------|---------|
| [Docker Logs Testing](./reports/docker-logs-testing.md) | Тестирование логов Docker |
| [Tools Integration Verification](./reports/tools-integration-verification.md) | Верификация интеграции инструментов |
| [Tools Verification Status](./reports/tools-verification-status.md) | Статус верификации инструментов |
| [LLM Providers Verification Report](./reports/verification-report-llm-providers-management.md) | Верификация LLM провайдеров |

### Analysis & Audits
| Документ | Описание |
|----------|---------|
| [OpenSpec Verification Report](./reports/openspec-verification-report.md) | Верификация OpenSpec |
| [OpenSpec Update Requirements](./reports/openspec-update-requirements.md) | Требования обновления OpenSpec |
| [Tool Execution Signal Fix](./reports/tool-execution-signal-fix.md) | Отчёт о signal fix |
| [Specification Actualization Analysis](./reports/specification-actualization-analysis.md) | Анализ актуализации спец. |

---

## 🐛 Bugfixes (Исправления ошибок)

| Документ | Описание |
|----------|---------|
| [Detached Instance Error Fix](./bugfixes/detached-instance-error-fix.md) | Исправление detached instance |
| [Duplicate Events Fix](./bugfixes/duplicate-events-fix.md) | Исправление дублирующихся событий |
| [Message Events Fix](./bugfixes/message-events-fix.md) | Исправление message events |
| [LiteLLM Request Fix](./bugfixes/litellm-request-fix.md) | Исправление LiteLLM запроса |
| [PathValidator Fix](./bugfixes/pathvalidator-fix.md) | Исправление PathValidator |
| [Bugfix Agent Config Validation](./bugfixes/bugfix-agent-config-validation.md) | Валидация конфига агента |
| [Bugfixes README](./bugfixes/README.md) | Обзор исправлений |

---

## 🔄 Migrations (Миграционные руководства)

| Документ | Описание |
|----------|---------|
| [SSE to Streaming Migration](./migrations/sse-to-streaming-migration.md) | Миграция SSE → Streaming |
| [v0.2.0 Migration](./migrations/v0.2.0-migration.md) | Миграция на v0.2.0 |
| [Workspace Architecture Clarification](./migrations/workspace-architecture-clarification.md) | Clarification архитектуры |

---

## 💡 Samples (Примеры кода)

| Документ | Описание |
|----------|---------|
| [Samples](./samples/samples.md) | Основные примеры использования |
| [Gradio UI Guide](./samples/gradio-ui-guide.md) | Примеры Gradio UI |

---

## 📦 Archive (Архивированные документы)

### Deprecated Features
| Документ | Описание | Статус |
|----------|---------|--------|
| [Langfuse OpenTelemetry Removal - Final Report](./archive/langfuse-opentelemetry-removal/final-report.md) | Финальный отчёт | ⚠️ Deprecated |
| [Langfuse OpenTelemetry Removal - Report](./archive/langfuse-opentelemetry-removal/report.md) | Основной отчёт | ⚠️ Deprecated |
| [Langfuse OpenTelemetry Removal - Verification](./archive/langfuse-opentelemetry-removal/verification.md) | Верификация | ⚠️ Deprecated |
| [LiteLLM OpenRouter Integration Issue](./archive/litellm-openrouter-integration-issue.md) | OpenRouter интеграция | ⚠️ Deprecated |

### Obsolete Analysis
| Документ | Описание | Статус |
|----------|---------|--------|
| [Docker Logs Analysis - 2026-03-13](./archive/docker-logs-analysis/2026-03-13-analysis.md) | Анализ логов | 📦 Архив |
| [Logs Analysis Initial Report](./archive/docker-logs-analysis/logs-analysis.md) | Первоначальный отчёт | 📦 Архив |
| [Logs Fix Summary](./archive/docker-logs-analysis/logs-fix-summary.md) | Сводка исправлений | 📦 Архив |

### Phase 4 Documentation
| Документ | Описание | Статус |
|----------|---------|--------|
| [Phase 4 Deployment Guide](./archive/phase4-deployment/phase4-deployment-guide.md) | Deployment guide | 📦 Архив |
| [Phase 4 Integration Verification](./archive/phase4-deployment/phase4-integration-verification.md) | Верификация интеграции | 📦 Архив |
| [Phase 4 Production Readiness](./archive/phase4-deployment/phase4-production-readiness.md) | Production readiness | 📦 Архив |

### Other Archived
| Документ | Описание | Статус |
|----------|---------|--------|
| [Orchestrator Architecture Audit](./archive/orchestrator-architecture-audit.md) | Audit архитектуры | 📦 Архив |
| [Orchestrator Model Design Analysis](./archive/orchestrator-model-design-analysis.md) | Design analysis | 📦 Архив |
| [Orchestrator Unified Agent Implementation Plan](./archive/orchestrator-unified-agent-implementation-plan.md) | Implementation plan | 📦 Архив |
| [Team Announcement Workspace Architecture](./archive/team-announcement-workspace-architecture.md) | Announcement | 📦 Архив |
| [User Worker Space Architecture Analysis](./archive/user-worker-space-architecture-analysis.md) | Analysis | 📦 Архив |
| [User Worker Space Implementation Plan](./archive/user-worker-space-implementation-plan.md) | Implementation plan | 📦 Архив |
| [Workspace Responsibility Separation](./archive/workspace-responsibility-separation.md) | Design document | 📦 Архив |
| [Documentation Audit 2026-02-18](./archive/documentation-audit.md) | Аудит документации | 📦 Архив |
| [Archive README](./archive/README.md) | Индекс архива | 📦 Архив |

---

## 📊 Статистика

| Метрика | Значение |
|---------|----------|
| **Всего документов** | 101+ |
| **Категорий** | 12 |
| **Active документов** | ~90 |
| **Archived документов** | ~11 |
| **Статус** | Production Ready |

---

## 🎯 По целям

### Я новичок, где начать?
1. [Quick Start](./getting-started/quickstart.md) - 5 минут
2. [System Overview](./architecture/system-overview.md) - поймите архитектуру
3. [REST API](./api/rest-api.md) - начните использовать API
4. [Samples](./samples/samples.md) - примеры кода

### Я разработчик, как расширять?
1. [Developer Guide](./guides/developer-guide.md)
2. [Component Details](./architecture/component-details.md)
3. [Integration Guide](./guides/integration-guide.md)
4. [Tool Risk Assessment](./guides/tool-risk-assessment.md)

### Я DevOps, как развернуть?
1. [Deployment Guide](./deployment/deployment-guide.md) - полный гайд
2. [Infrastructure Setup](./getting-started/infrastructure-setup.md)
3. [Production Checklist](./deployment/production-checklist.md)
4. [System Architecture](./architecture/system-overview.md) - для понимания нагрузки

### Я интегрирую LLM
1. [LiteLLM Integration](./integrations/litellm-integration.md)
2. [Providers Management](./integrations/litellm-providers-management.md)
3. [LLM Error Handling](./guides/llm-error-handling.md)
4. [Langfuse Integration](./integrations/langfuse-v4-integration-summary.md) - для мониторинга

---

## 🔍 Поиск по темам

### Агенты и инструменты
- [Agent Tools](./features/agent-tools.md)
- [Agent Context](./features/agent-context.md)
- [Tool Execution Tracing](./features/tool-execution-tracing.md)
- [Tool Risk Assessment](./guides/tool-risk-assessment.md)

### Real-time и события
- [SSE Event Streaming](./api/sse-event-streaming.md)
- [Event Log Outbox Architecture](./architecture/event-log-outbox-architecture.md)
- [Duplicate Events Fix](./bugfixes/duplicate-events-fix.md)

### LLM интеграции
- [LiteLLM Integration](./integrations/litellm-integration.md)
- [Langfuse Integration](./integrations/langfuse-v4-integration-summary.md)
- [LLM Error Handling](./guides/llm-error-handling.md)
- [LLM Providers API](./integrations/llm-providers-api.md)

### Развертывание и операции
- [Deployment Guide](./deployment/deployment-guide.md)
- [Infrastructure Setup](./getting-started/infrastructure-setup.md)
- [Production Checklist](./deployment/production-checklist.md)

### Безопасность и валидация
- [Tool Risk Assessment](./guides/tool-risk-assessment.md)
- [PathValidator Fix](./bugfixes/pathvalidator-fix.md)
- [Workspace Architecture](./features/workspace-architecture.md)

---

## 📝 Документы по типам

### Руководства (How-To)
- [Quick Start](./getting-started/quickstart.md)
- [Setup Guide](./getting-started/setup-guide.md)
- [Deployment Guide](./deployment/deployment-guide.md)
- [Developer Guide](./guides/developer-guide.md)
- [Integration Guide](./guides/integration-guide.md)

### Спецификации (Specifications)
- [REST API](./api/rest-api.md)
- [API Specification](./api/api-specification.md)
- [System Architecture](./architecture/system-overview.md)
- [Technical Requirements](./guides/technical-requirements.md)

### Отчёты (Reports)
- [Code Analysis Report](./reports/code-analysis-report.md)
- [Infrastructure Complete](./reports/infrastructure-complete.md)
- [Implementation Summary](./implementation/implementation-summary.md)

### Changelog & History
- [CHANGELOG.md](./changelogs/CHANGELOG.md)
- [Migration Guides](./migrations/)

---

**Последнее обновление**: Март 2026  
**Версия**: 0.2.0  
**Статус**: Production Ready ✅
