# План реорганизации документации codelab-core-service

**Дата создания:** 17 марта 2026  
**Статус:** Подготовка к реализации  
**Автор:** Архитектурный анализ

---

## 📋 Оглавление

1. [Обзор проблемы](#обзор-проблемы)
2. [Целевая структура](#целевая-структура)
3. [Матрица перемещения файлов](#матрица-перемещения-файлов)
4. [План объединения дубликатов](#план-объединения-дубликатов)
5. [Фазы реорганизации](#фазы-реорганизации)
6. [Стратегия обновления ссылок](#стратегия-обновления-ссылок)
7. [Чеклист проверки](#чеклист-проверки)

---

## 🔍 Обзор проблемы

### Текущее состояние

| Метрика | Значение | Статус |
|---------|----------|--------|
| Файлов в корне | 29 | ❌ Требует перемещения |
| Файлов в doc/ | 45 | ⚠️ Требует реорганизации |
| Файлов спецификаций | 13 | ✅ В порядке |
| Дубликатов выявлено | 2 основных пары | ❌ Требует объединения |
| Устаревших документов | 4 | ⚠️ Требует архивирования |
| Опечаток в именах | 1 | ❌ Требует исправления |
| Тестовых файлов | 1 (test.md) | ❌ Требует удаления |

### Ключевые проблемы

1. **Загромождённый корневой каталог** - 29 файлов, которые должны быть в `doc/`
2. **Дублирование контента** - 2 пары файлов с похожим содержанием
3. **Отсутствие категоризации** - файлы в `doc/` хаотично расположены
4. **Неконсистентные имена** - смешивание UPPERCASE и lowercase, опечатка в `techincal-requrements.md`
5. **Устаревшая информация** - несколько отчетов об анализе логов из 2026-03-13

---

## 🎯 Целевая структура

### Рекомендуемая иерархия

```
doc/
├── README.md                           # Главный индекс документации
├── INDEX.md                            # Сохранить существующий индекс
│
├── getting-started/                    # Начало работы
│   ├── quickstart.md                   # Быстрый старт (из QUICKSTART.md)
│   ├── setup-guide.md                  # Настройка окружения
│   └── infrastructure-setup.md         # Инфраструктура
│
├── architecture/                       # Архитектурная документация (очистка)
│   ├── README.md                       # Навигация по архитектуре
│   ├── system-overview.md              # Обновленный (SYSTEM_ARCHITECTURE.md + system-overview.md)
│   ├── component-details.md
│   ├── workspace-lifecycle.md
│   ├── event-log-outbox-architecture.md
│   └── diagrams.md
│
├── api/                                # API документация
│   ├── README.md                       # Навигация по API
│   ├── rest-api.md                     # REST API
│   ├── streaming-fetch-api.md          # Streaming API
│   ├── sse-event-streaming.md          # SSE события
│   └── api-specification.md
│
├── guides/                             # Практические руководства
│   ├── developer-guide.md              # Для разработчиков
│   ├── integration-guide.md            # Интеграция
│   ├── llm-error-handling.md           # Обработка ошибок LLM
│   ├── tool-risk-assessment.md         # Оценка рисков инструментов
│   └── command-whitelist.md
│
├── deployment/                         # Развёртывание
│   ├── deployment-guide.md             # Объединённое (PRODUCTION_DEPLOYMENT_GUIDE.md + deployment-guide.md)
│   ├── production-checklist.md         # Production чеклист
│   └── docker-integration.md           # Docker интеграция
│
├── integrations/                       # Интеграции с внешними сервисами
│   ├── litellm-integration.md          # LiteLLM
│   ├── litellm-providers-management.md # Управление провайдерами
│   ├── langfuse-v4-integration.md      # Langfuse v4
│   └── llm-providers-api.md            # LLM провайдеры API
│
├── features/                           # Описание функциональности
│   ├── agent-tools.md                  # Инструменты агентов
│   ├── agent-context.md                # Контекст агентов
│   ├── workspace-architecture.md       # Архитектура workspace
│   ├── session-id-propagation.md       # Session ID пропагация
│   ├── tool-execution-tracing.md       # Tracing инструментов
│   ├── idempotency.md                  # Идемпотентность
│   └── agent-tools-workflow.md         # Workflow инструментов
│
├── changelogs/                         # История изменений
│   ├── CHANGELOG.md                    # Главный changelog
│   ├── CHANGELOG_V0.2.0.md
│   ├── CHANGELOG_WORKSPACE_ARCHITECTURE.md
│   ├── CHANGELOG_LLM_PROVIDERS_MANAGEMENT.md
│   └── ... (остальные CHANGELOG_*.md)
│
├── implementation/                     # Отчёты о реализации
│   ├── implementation-summary.md       # Сводка реализации
│   ├── implementation-priority-analysis.md
│   ├── tool-execution-trace-design.md
│   ├── client-tools-implementation.md
│   └── orchestrator-unified-plan.md
│
├── reports/                            # Технические отчёты
│   ├── code-analysis-report.md         # Анализ кода
│   ├── specification-consistency-report.md
│   ├── infrastructure-complete.md
│   ├── cleanup-completion-report.md
│   ├── session-id-propagation-report.md
│   ├── span-lifecycle-fix-report.md
│   └── sqlalchemy-lazy-loading-fix.md
│
├── bugfixes/                           # Исправления ошибок
│   ├── README.md                       # Навигация
│   ├── detached-instance-error-fix.md
│   ├── duplicate-events-fix.md
│   ├── message-events-fix.md
│   ├── litellm-request-fix.md
│   └── logs-analysis-fix.md
│
├── migrations/                         # Миграционные руководства
│   ├── sse-to-streaming-migration.md   # SSE → Streaming
│   ├── v0.2.0-migration.md             # Миграция на v0.2.0
│   └── workspace-architecture-clarification.md
│
├── samples/                            # Примеры кода и использования
│   ├── samples.md                      # Основной файл примеров
│   └── gradio-ui-guide.md              # Примеры Gradio UI
│
├── archive/                            # Архив (устаревшие документы)
│   ├── README.md                       # Индекс архива
│   ├── langfuse-opentelemetry-removal/
│   │   ├── final-report.md
│   │   ├── report.md
│   │   └── verification.md
│   ├── docker-logs-analysis/
│   │   ├── 2026-03-13-analysis.md
│   │   └── initial-report.md
│   └── deprecated-docs/
│       ├── phase4-deployment-guide.md
│       ├── orchestrator-architecture-audit.md
│       └── workspace-responsibility-separation.md
│
└── .cleanup/                           # Служебные файлы (не отслеживать)
    └── .gitkeep
```

---

## 📊 Матрица перемещения файлов

### Часть 1: Файлы из корня → doc/

| Текущий путь | Новый путь | Действие | Категория | Примечание |
|---|---|---|---|---|
| QUICKSTART.md | doc/getting-started/quickstart.md | move | getting-started | Базовое содержимое |
| PRODUCTION_DEPLOYMENT_GUIDE.md | doc/deployment/deployment-guide.md | merge | deployment | Объединить с deployment-guide.md |
| PRODUCTION_READINESS_CHECKLIST.md | doc/deployment/production-checklist.md | move | deployment | Rename + move |
| SESSION_ID_PROPAGATION_STRATEGY.md | doc/features/session-id-propagation.md | move | features | Основной документ |
| SESSION_ID_PROPAGATION_IMPLEMENTATION_PLAN.md | doc/implementation/ | delete | - | Дублирует content из strategy |
| SESSION_ID_PROPAGATION_COMPLETION_REPORT.md | doc/reports/session-id-propagation-report.md | move | reports | Rename + move |
| PROJECT_INITIALIZATION_FLOW.md | doc/features/project-initialization.md | move | features | Rename + move |
| PROJECT_MANAGEMENT_ENDPOINTS.md | doc/api/project-management-endpoints.md | move | api | Rename + move |
| PROJECT_MODEL_DATABASE_ANALYSIS.md | doc/reports/database-analysis.md | move | reports | Rename + move |
| SPAN_LIFECYCLE_FIX_REPORT.md | doc/reports/span-lifecycle-fix-report.md | move | reports | Move as-is |
| SQLALCHEMY_LAZY_LOADING_FIX_REPORT.md | doc/reports/sqlalchemy-lazy-loading-fix.md | move | reports | Move as-is |
| SPECIFICATION_CONSISTENCY_REPORT.md | doc/reports/specification-consistency-report.md | move | reports | Move as-is |
| CODE_ANALYSIS_REPORT.md | doc/reports/code-analysis-report.md | move | reports | Move as-is |
| CLEANUP_COMPLETION_REPORT.md | doc/reports/cleanup-completion-report.md | move | reports | Move as-is |
| INFRASTRUCTURE_COMPLETE.md | doc/reports/infrastructure-complete.md | move | reports | Move as-is |
| IMPLEMENTATION_SUMMARY.md | doc/implementation/implementation-summary.md | move | implementation | Move as-is |
| IMPLEMENTATION_PRIORITY_ANALYSIS.md | doc/implementation/implementation-priority-analysis.md | move | implementation | Move as-is |
| CHANGELOG_*.md (7 файлов) | doc/changelogs/CHANGELOG_*.md | move | changelogs | Bulk move |
| DETACHED_INSTANCE_ERROR_FIX_SUMMARY.md | doc/bugfixes/detached-instance-error-fix.md | move | bugfixes | Rename + move |
| LANGFUSE_OPENTELEMETRY_REMOVAL_*.md (3 файла) | doc/archive/langfuse-opentelemetry-removal/ | move | archive | Deprecated feature |
| DOCKER_LOGS_ANALYSIS_*.md (2 файла) | doc/archive/docker-logs-analysis/ | move | archive | Устаревшие отчёты |
| LITELLM_OPENROUTER_INTEGRATION_ISSUE.md | doc/reports/litellm-integration-issue.md | move | reports | Rename + move |
| LITELLM_REQUEST_FIX_SUMMARY.md | doc/bugfixes/litellm-request-fix.md | move | bugfixes | Rename + move |
| LOGS_*.md (2 файла) | doc/reports/logs-analysis.md | merge | reports | Consolidate |
| OPENSPEC_*.md (2 файла) | doc/reports/openspec-*.md | move | reports | Move as-is |
| RELEASE_SPECIFICATION_V0.2.0.md | doc/implementation/release-specification-v0.2.0.md | move | implementation | Move as-is |
| test.md | DELETE | delete | - | Удалить (тестовый файл) |

### Часть 2: Файлы внутри doc/ - переорганизация

| Текущий путь | Новый путь | Действие | Категория | Примечание |
|---|---|---|---|---|
| doc/architecture/README.md | Keep | - | architecture | Сохранить и обновить |
| doc/architecture/SYSTEM_ARCHITECTURE.md | doc/architecture/system-overview.md | merge | architecture | Объединить, удалить дубликат |
| doc/architecture/system-overview.md | doc/architecture/system-overview.md | merge | architecture | Новый консолидированный файл |
| doc/architecture/deployment-guide.md | doc/deployment/deployment-guide.md | move | deployment | Переместить в новую категорию |
| doc/architecture/developer-guide.md | doc/guides/developer-guide.md | move | guides | Переместить в новую категорию |
| doc/architecture/integration-guide.md | doc/guides/integration-guide.md | move | guides | Переместить в новую категорию |
| doc/architecture/api-specification.md | doc/api/api-specification.md | move | api | Переместить в новую категорию |
| doc/setup-guide.md | doc/getting-started/setup-guide.md | move | getting-started | Переместить в новую категорию |
| doc/infrastructure-setup.md | doc/getting-started/infrastructure-setup.md | move | getting-started | Переместить в новую категорию |
| doc/rest-api.md | doc/api/rest-api.md | move | api | Переместить в новую категорию |
| doc/sse-event-streaming.md | doc/api/sse-event-streaming.md | move | api | Переместить в новую категорию |
| doc/streaming-fetch-api.md | doc/api/streaming-fetch-api.md | move | api | Переместить в новую категорию |
| doc/llm-providers-api.md | doc/integrations/llm-providers-api.md | move | integrations | Переместить в новую категорию |
| doc/litellm-integration.md | doc/integrations/litellm-integration.md | move | integrations | Переместить в новую категорию |
| doc/litellm-docker-integration.md | doc/integrations/litellm-docker-integration.md | move | integrations | Переместить в новую категорию |
| doc/litellm-providers-management.md | doc/integrations/litellm-providers-management.md | move | integrations | Переместить в новую категорию |
| doc/langfuse-v4-integration-*.md (2 файла) | doc/integrations/langfuse-v4-integration/ | move | integrations | Consolidate в папку |
| doc/llm-error-handling.md | doc/guides/llm-error-handling.md | move | guides | Переместить в новую категорию |
| doc/agent-*.md (3 файла) | doc/features/ | move | features | Переместить в новую категорию |
| doc/tool-*.md (4 файла) | doc/features/ + doc/guides/ | move | features/guides | Переместить по типу |
| doc/workspace-*.md (3 файла) | doc/features/ + doc/archive/ | move | features/archive | Переместить по статусу |
| doc/client-tools-*.md (2 файла) | doc/features/client-tools/ | move | features | Consolidate в папку |
| doc/idempotency-*.md (1 файл) | doc/features/idempotency.md | move | features | Rename + move |
| doc/migration-*.md (2 файла) | doc/migrations/ | move | migrations | Move all migrations |
| doc/orchestrator-*.md (3 файла) | doc/implementation/ + doc/archive/ | move | - | Move по статусу (audit → archive) |
| doc/techincal-requrements.md | doc/guides/technical-requirements.md | move | guides | Fix typo + move |
| doc/INDEX.md | doc/INDEX.md | update | - | Обновить индекс |
| doc/samples.md | doc/samples/samples.md | move | samples | Move to category |
| doc/phase4-*.md (3 файла) | doc/archive/phase4-deployment/ | move | archive | Deprecated |
| doc/DOCUMENTATION_AUDIT_2026_02_18.md | doc/archive/documentation-audit.md | move | archive | Rename + archive |
| doc/bugfix-*.md (3 файла) | doc/bugfixes/ | move | bugfixes | Move all bugfixes |
| doc/PATHVALIDATOR_FIX.md | doc/bugfixes/pathvalidator-fix.md | move | bugfixes | Rename + move |
| doc/TOOLS_*.md (2 файла) | doc/reports/ + doc/implementation/ | move | - | Move по типу |

---

## 🔀 План объединения дубликатов

### Дубликат 1: Deployment Guide

**Конфликт:**
- `PRODUCTION_DEPLOYMENT_GUIDE.md` (461 строка, в корне)
- `doc/architecture/deployment-guide.md` (901 строка, в doc/)

**Анализ содержания:**

| Аспект | PRODUCTION_DEPLOYMENT_GUIDE.md | deployment-guide.md | Рекомендация |
|---|---|---|---|
| Требования | ✅ Production-специфичные требования | ✅ Общие требования | Объединить: сначала общие, потом production |
| Локальная разработка | ❌ Нет | ✅ Есть подробно | Взять из deployment-guide.md |
| Docker Compose | ❌ Краткий обзор | ✅ Подробно | Взять из deployment-guide.md |
| Kubernetes | ❌ Нет | ✅ Есть подробно | Взять из deployment-guide.md |
| Production специфика | ✅ Полный гайд | ⚠️ Частично | Взять из PRODUCTION_DEPLOYMENT_GUIDE.md |
| Мониторинг | ✅ Подробно | ✅ Подробно | Объединить, выбрать лучшее |
| Резервное копирование | ✅ Есть | ✅ Есть | Объединить |
| Troubleshooting | ✅ Подробно | ✅ Подробно | Объединить, удалить дубли |

**Стратегия объединения:**

1. **Основной файл:** `doc/deployment/deployment-guide.md` (крупнее, полнее)
2. **Источник дополнений:** `PRODUCTION_DEPLOYMENT_GUIDE.md`

**Структура нового файла:**

```markdown
# Руководство по развертыванию

## Содержание
- Требования (общие + production)
- Локальная разработка
- Docker Compose
- Kubernetes
- Мониторинг и оповещения
- Резервное копирование
- Production специфика (усиление безопасности, масштабирование)
- Troubleshooting

## Действия:

1. Основа: content из doc/architecture/deployment-guide.md (структура + Docker Compose + K8s)
2. Добавить раздел "## Production специфика" с content из PRODUCTION_DEPLOYMENT_GUIDE.md
3. Объединить требования (общие + production)
4. Объединить мониторинг и alerts
5. Удалить дубликаты в troubleshooting

## Итого:
- Новый файл: doc/deployment/deployment-guide.md (~1100 строк)
- Удалить: PRODUCTION_DEPLOYMENT_GUIDE.md
- Обновить: Все ссылки на PRODUCTION_DEPLOYMENT_GUIDE.md → doc/deployment/deployment-guide.md
```

### Дубликат 2: System Architecture

**Конфликт:**
- `doc/architecture/SYSTEM_ARCHITECTURE.md` (401 строка)
- `doc/architecture/system-overview.md` (595 строк)

**Анализ содержания:**

| Аспект | SYSTEM_ARCHITECTURE.md | system-overview.md | Рекомендация |
|---|---|---|---|
| Обзор архитектуры | ✅ Диаграмма и компоненты | ✅ Подробный обзор | Объединить |
| Принципы архитектуры | ⚠️ Кратко | ✅ Подробно (8 принципов) | Взять из system-overview.md |
| Изоляция пользователей | ✅ Есть диаграмма | ✅ Подробное объяснение | Объединить оба подхода |
| Компоненты системы | ✅ Mermaid диаграмма | ✅ Детальное описание | Объединить |
| Каналы связи | ❌ Нет | ✅ Есть | Взять из system-overview.md |
| Integration points | ⚠️ Кратко | ✅ Подробно | Взять из system-overview.md |
| Data models | ❌ Нет | ✅ Есть (Project, Agent, Message) | Взять из system-overview.md |

**Стратегия объединения:**

1. **Основной файл:** `doc/architecture/system-overview.md` (более полное описание)
2. **Источник дополнений:** `doc/architecture/SYSTEM_ARCHITECTURE.md` (диаграммы и компоненты)

**Структура нового файла:**

```markdown
# Обзор архитектуры системы CodeLab Core Service v0.2.0

## Введение
(из system-overview.md)

## Ключевые принципы архитектуры
(из system-overview.md - все 8 принципов)

## Общая архитектура системы
(диаграмма из SYSTEM_ARCHITECTURE.md)

## Компоненты системы
(объединённый обзор)
- Клиентский слой
- API маршруты
- Middleware
- Core Orchestrator
- Services и интеграции
- Data models (из system-overview.md)

## Каналы связи между компонентами
(из system-overview.md)

## Integration points
(из system-overview.md)

## Workflow примеры
(если есть в обоих)
```

**Действия:**

1. Основа: content из `doc/architecture/system-overview.md`
2. Добавить Mermaid диаграммы из `SYSTEM_ARCHITECTURE.md`
3. Объединить все компоненты и их описания
4. Сохранить новый файл как `doc/architecture/system-overview.md` (более короткое имя)
5. Удалить `doc/architecture/SYSTEM_ARCHITECTURE.md`
6. Обновить все ссылки

### Дополнительные дубликаты (мягкие)

| Файл 1 | Файл 2 | Статус | Действие |
|---|---|---|---|
| doc/litellm-integration.md | doc/litellm-docker-integration.md | ⚠️ Перекрытие | Объединить в одну иерархию integrations/ |
| doc/langfuse-v4-integration-completion-report.md | doc/langfuse-v4-integration-summary.md | ⚠️ Дублирование | Consolidate или выбрать основной |
| LOGS_ANALYSIS.md + LOGS_FIX_SUMMARY.md | doc/reports/ | ⚠️ Связанные | Объединить в один файл logs-analysis-and-fixes.md |

---

## 🚀 Фазы реорганизации

### Фаза 1: Подготовка и создание структуры (без изменений файлов)

**Цель:** Создать полную целевую структуру директорий

**Команды:**

```bash
# Создание основных категорий
mkdir -p doc/getting-started
mkdir -p doc/api
mkdir -p doc/guides
mkdir -p doc/deployment
mkdir -p doc/integrations
mkdir -p doc/features
mkdir -p doc/changelogs
mkdir -p doc/implementation
mkdir -p doc/reports
mkdir -p doc/bugfixes
mkdir -p doc/migrations
mkdir -p doc/samples
mkdir -p doc/archive
mkdir -p doc/archive/langfuse-opentelemetry-removal
mkdir -p doc/archive/docker-logs-analysis
mkdir -p doc/archive/phase4-deployment

# Создание служебной папки
mkdir -p doc/.cleanup
touch doc/.cleanup/.gitkeep
```

**Файлы, которые будут затронуты:** Только создание директорий (обратимо)

**Риски и меры предосторожности:**

- ✅ Низкий риск: только создание пустых директорий
- Проверить, что .gitignore не исключает созданные директории
- Убедиться, что нет конфликтов имён

**Критерии завершения:**

- [ ] Все 12 основных категорий созданы
- [ ] Все подкатегории созданы
- [ ] Существующие файлы в doc/ остаются на месте
- [ ] Файлы в корне не затронуты
- [ ] `git status` показывает только новые пустые директории

---

### Фаза 2: Перемещение файлов из корня в doc/

**Цель:** Очистить корневой каталог от документации, переместив её в doc/

**Команды перемещения по категориям:**

```bash
# getting-started/
mv QUICKSTART.md doc/getting-started/quickstart.md

# deployment/ (сначала только скопируем, потом объединим)
cp PRODUCTION_DEPLOYMENT_GUIDE.md doc/deployment/PRODUCTION_DEPLOYMENT_GUIDE.md.backup

# changelogs/ (bulk move)
mv CHANGELOG*.md doc/changelogs/

# reports/ (bulk move)
mv CODE_ANALYSIS_REPORT.md doc/reports/
mv SPECIFICATION_CONSISTENCY_REPORT.md doc/reports/
mv CLEANUP_COMPLETION_REPORT.md doc/reports/
mv INFRASTRUCTURE_COMPLETE.md doc/reports/
mv SPAN_LIFECYCLE_FIX_REPORT.md doc/reports/
mv SQLALCHEMY_LAZY_LOADING_FIX_REPORT.md doc/reports/
mv PROJECT_MODEL_DATABASE_ANALYSIS.md doc/reports/database-analysis.md
mv SESSION_ID_PROPAGATION_COMPLETION_REPORT.md doc/reports/session-id-propagation-report.md
mv SPECIFICATION_CONSISTENCY_REPORT.md doc/reports/
mv OPENSPEC_VERIFICATION_REPORT.md doc/reports/
mv OPENSPEC_UPDATE_REQUIREMENTS.md doc/reports/

# implementation/
mv IMPLEMENTATION_SUMMARY.md doc/implementation/
mv IMPLEMENTATION_PRIORITY_ANALYSIS.md doc/implementation/
mv RELEASE_SPECIFICATION_V0.2.0.md doc/implementation/

# features/
mv SESSION_ID_PROPAGATION_STRATEGY.md doc/features/session-id-propagation.md
mv PROJECT_INITIALIZATION_FLOW.md doc/features/project-initialization.md

# api/
mv PROJECT_MANAGEMENT_ENDPOINTS.md doc/api/project-management-endpoints.md

# bugfixes/
mv DETACHED_INSTANCE_ERROR_FIX_SUMMARY.md doc/bugfixes/detached-instance-error-fix.md
mv LITELLM_REQUEST_FIX_SUMMARY.md doc/bugfixes/litellm-request-fix.md

# archive/ (deprecated features)
mv LANGFUSE_OPENTELEMETRY_REMOVAL_*.md doc/archive/langfuse-opentelemetry-removal/
mv DOCKER_LOGS_ANALYSIS_*.md doc/archive/docker-logs-analysis/
mv LITELLM_OPENROUTER_INTEGRATION_ISSUE.md doc/archive/
mv LOGS_ANALYSIS.md doc/archive/
mv LOGS_FIX_SUMMARY.md doc/archive/

# Удаление дубликатов и тестовых файлов
rm test.md
rm SESSION_ID_PROPAGATION_IMPLEMENTATION_PLAN.md  # Дублирует strategy
```

**Файлы, которые будут затронуты:**

- Все 29 файлов из корня (по сути все CHANGELOG_*, отчёты и гайды)

**Риски и меры предосторожности:**

- ⚠️ **Риск 1:** Потеря ссылок в других файлах
  - Мера: Проверить все ссылки перед выполнением (Фаза 6)
  
- ⚠️ **Риск 2:** CI/CD может ломаться, если ищет файлы в корне
  - Мера: Проверить `.github/`, `Makefile`, скрипты на предмет hardcoded путей

- ⚠️ **Риск 3:** Историческое значение путей в git
  - Мера: Использовать `git mv` вместо обычного `mv` (сохраняет историю)

**Критерии завершения:**

- [ ] Все 29 файлов из корня перемещены (можно проверить: `ls *.md` должен быть пустой или только README.md, QUICKSTART.md оставлены)
- [ ] Каждый файл находится в правильной категории
- [ ] Не потеряны файлы (проверить контрольные суммы)
- [ ] `git status` показывает только перемещения и удаления
- [ ] Структура doc/ соответствует целевой структуре

---

### Фаза 3: Реорганизация внутри doc/

**Цель:** Переместить файлы внутри doc/ в правильные категории

**Команды перемещения:**

```bash
# Перемещение из doc/architecture/
mv doc/architecture/deployment-guide.md doc/deployment/
mv doc/architecture/developer-guide.md doc/guides/
mv doc/architecture/integration-guide.md doc/guides/
mv doc/architecture/api-specification.md doc/api/

# Перемещение из корня doc/
mv doc/setup-guide.md doc/getting-started/
mv doc/infrastructure-setup.md doc/getting-started/
mv doc/rest-api.md doc/api/
mv doc/sse-event-streaming.md doc/api/
mv doc/streaming-fetch-api.md doc/api/
mv doc/llm-providers-api.md doc/integrations/
mv doc/litellm-integration.md doc/integrations/
mv doc/litellm-docker-integration.md doc/integrations/
mv doc/litellm-providers-management.md doc/integrations/
mv doc/langfuse-v4-integration-completion-report.md doc/integrations/
mv doc/langfuse-v4-integration-summary.md doc/integrations/
mv doc/llm-error-handling.md doc/guides/
mv doc/techincal-requrements.md doc/guides/technical-requirements.md
mv doc/agent-tools-workflow.md doc/features/
mv doc/agent-context.md doc/features/
mv doc/tool-execution-tracing.md doc/features/
mv doc/tool-risk-assessment-matrix.md doc/guides/tool-risk-assessment.md
mv doc/client-tools-implementation.md doc/features/
mv doc/CLIENT_TOOLS_EXECUTION_IMPLEMENTATION.md doc/features/
mv doc/идемпотентность-надежность.md doc/features/idempotency.md
mv doc/MIGRATION_SSE_TO_STREAMING.md doc/migrations/sse-to-streaming-migration.md
mv doc/MIGRATION_V0.2.0.md doc/migrations/v0.2.0-migration.md
mv doc/workspace-*.md doc/features/ # или archive в зависимости от статуса

# Перемещение bugfixes
mv doc/bugfix-*.md doc/bugfixes/
mv doc/PATHVALIDATOR_FIX.md doc/bugfixes/pathvalidator-fix.md

# Перемещение в archive
mv doc/PHASE4_*.md doc/archive/phase4-deployment/
mv doc/ORCHESTRATOR_ARCHITECTURE_AUDIT.md doc/archive/
mv doc/DOCUMENTATION_AUDIT_2026_02_18.md doc/archive/documentation-audit.md

# Перемещение samples
mv doc/samples.md doc/samples/
mv doc/GRADIO_CLIENT.md doc/samples/gradio-ui-guide.md (если есть - смотрить scripts/)
```

**Файлы, которые будут затронуты:**

- 45 файлов в doc/ будут переорганизованы

**Риски и меры предосторожности:**

- ⚠️ **Риск 1:** doc/architecture/ станет неполным, но это нормально для переходного периода
  - Мера: Обновить doc/architecture/README.md после перемещений

- ⚠️ **Риск 2:** Возможны конфликты имён (например, несколько development guide'ов)
  - Мера: Проверить имена перед перемещением, объединить если нужно

**Критерии завершения:**

- [ ] Все файлы в doc/ находятся в правильных категориях
- [ ] doc/architecture/ содержит только архитектурные документы
- [ ] doc/getting-started/ содержит документы для начинающих
- [ ] Нет файлов в корне doc/ (кроме README.md, INDEX.md)
- [ ] Все файлы доступны и не потеряны

---

### Фаза 4: Объединение дубликатов

**Цель:** Объединить дублирующиеся документы, оставив одну версию

**Дубликат 1: Deployment Guide**

```bash
# 1. Создать новый объединённый файл (временно)
cat doc/deployment/deployment-guide.md > /tmp/deployment-combined.md
# Вручную добавить Production-специфичный контент из doc/deployment/PRODUCTION_DEPLOYMENT_GUIDE.md.backup

# 2. Проверить и валидировать новый файл
less /tmp/deployment-combined.md

# 3. Если всё хорошо, заменить
cp /tmp/deployment-combined.md doc/deployment/deployment-guide.md

# 4. Удалить оригиналы
rm doc/deployment/PRODUCTION_DEPLOYMENT_GUIDE.md.backup
rm PRODUCTION_DEPLOYMENT_GUIDE.md
```

**Дубликат 2: System Architecture**

```bash
# 1. Создать новый файл (основа system-overview.md + диаграммы из SYSTEM_ARCHITECTURE.md)
cat doc/architecture/system-overview.md > /tmp/system-overview-combined.md
# Вручную добавить Mermaid диаграммы из SYSTEM_ARCHITECTURE.md

# 2. Проверить и валидировать
less /tmp/system-overview-combined.md

# 3. Если всё хорошо, заменить
cp /tmp/system-overview-combined.md doc/architecture/system-overview.md

# 4. Удалить старый дубликат
rm doc/architecture/SYSTEM_ARCHITECTURE.md
```

**Дополнительное объединение (по возможности):**

```bash
# Langfuse интеграция (если содержимое существенно отличается)
# langfuse-v4-integration-completion-report.md + langfuse-v4-integration-summary.md
# Рекомендация: оставить summary как основной, использовать report как бэкап в archive/

# Logs анализ
# LOGS_ANALYSIS.md + LOGS_FIX_SUMMARY.md → объединить или оставить оба?
```

**Файлы, которые будут затронуты:**

- PRODUCTION_DEPLOYMENT_GUIDE.md (удалить)
- doc/architecture/SYSTEM_ARCHITECTURE.md (удалить)
- doc/deployment/deployment-guide.md (объединить, обновить)
- doc/architecture/system-overview.md (объединить, обновить)

**Риски и меры предосторожности:**

- ⚠️ **Риск 1:** Потеря информации при объединении
  - Мера: Создать бэкапы обоих файлов перед объединением

- ⚠️ **Риск 2:** Структура нового файла может быть неoptimal
  - Мера: Тщательно планировать структуру перед объединением, просмотреть результат

**Критерии завершения:**

- [ ] Объединённые файлы содержат контент из обоих источников
- [ ] Удалены все дубликаты
- [ ] Структура объединённых файлов логична и читаема
- [ ] Нет потери информации

---

### Фаза 5: Очистка и исправления

**Цель:** Исправить опечатки, удалить устаревшие файлы, обновить индексы

**Действия:**

```bash
# 1. Исправление опечатки (уже сделано в Фазе 3)
# doc/techincal-requrements.md → doc/guides/technical-requirements.md

# 2. Удаление тестовых файлов
# (уже сделано в Фазе 2)
# rm test.md

# 3. Удаление дубликатов в archive
# Убедиться, что старые версии архивированы правильно

# 4. Проверка целостности файлов
find doc -type f -name "*.md" | wc -l  # Должно быть ~73 файла

# 5. Обновление main индекса
# doc/INDEX.md - должен отражать новую структуру
```

**Файлы, которые будут затронуты:**

- doc/INDEX.md (обновить)
- doc/README.md (создать или обновить, если существует)
- doc/archive/ (убедиться, что файлы правильно архивированы)

**Риски и меры предосторожности:**

- ✅ Низкий риск: в основном удаления и переименования

**Критерии завершения:**

- [ ] Все опечатки исправлены
- [ ] Тестовые файлы удалены
- [ ] Индекс обновлён
- [ ] Структура соответствует плану
- [ ] Все файлы доступны и найдены

---

### Фаза 6: Обновление индексов и ссылок

**Цель:** Обновить все перекрестные ссылки и индексы, убедиться, что ничего не сломалось

**Стратегия поиска и замены ссылок:**

Смотрите [раздел "Стратегия обновления ссылок"](#стратегия-обновления-ссылок)

**Файлы, которые будут затронуты:**

- Все файлы, содержащие ссылки на перемещённые документы
- doc/INDEX.md, doc/README.md
- Файлы в doc/architecture/README.md, других категориях README.md
- Возможно, файлы в .github/, scripts/, tests/

**Риски и меры предосторожности:**

- ⚠️ **Риск 1:** Автоматическая замена может нарушить форматирование
  - Мера: Проверить результаты замен вручную

- ⚠️ **Риск 2:** Некоторые ссылки могут быть в комментариях кода
  - Мера: Включить файлы .py, .js и т.д. в поиск, но быть осторожным при замене

- ⚠️ **Риск 3:** Относительные ссылки могут ломаться
  - Мера: Использовать абсолютные пути относительно doc/

**Критерии завершения:**

- [ ] Обновлены все ссылки в документации
- [ ] Проверены ссылки в коде (особенно в скриптах и GitHub Actions)
- [ ] doc/INDEX.md полностью актуален
- [ ] Все README.md в категориях содержат корректные ссылки
- [ ] `grep -r "PRODUCTION_DEPLOYMENT_GUIDE" doc/` не находит результатов (кроме archive/)
- [ ] `grep -r "SYSTEM_ARCHITECTURE" doc/` не находит результатов (кроме комментариев)

---

## 📍 Стратегия обновления ссылок

### Анализ файлов, содержащих ссылки

**Файлы с высоким риском (содержат много ссылок):**

1. **doc/INDEX.md** - главный индекс, содержит ссылки на все документы
2. **doc/architecture/README.md** - навигация по архитектуре
3. **README.md** (корневой) - может содержать ссылки на документацию
4. **doc/MIGRATION_V0.2.0.md** - содержит ссылки на другие гайды (сейчас в migrations/)
5. **doc/architecture/developer-guide.md** (сейчас в guides/) - references к структуре

**Файлы со средним риском:**

- doc/architecture/integration-guide.md (сейчас в guides/)
- doc/architecture/component-details.md
- Все файлы в doc/, содержащие ссылки друг на друга

**Процесс обновления:**

### Шаг 1: Создать карту соответствия старых и новых путей

```
PRODUCTION_DEPLOYMENT_GUIDE.md → doc/deployment/deployment-guide.md
QUICKSTART.md → doc/getting-started/quickstart.md
doc/architecture/SYSTEM_ARCHITECTURE.md → doc/architecture/system-overview.md
doc/architecture/deployment-guide.md → doc/deployment/deployment-guide.md
... (и так далее для всех 70+ файлов)
```

### Шаг 2: Найти все ссылки на старые пути

```bash
# Поиск всех типов ссылок на документацию
grep -r "PRODUCTION_DEPLOYMENT_GUIDE" . --include="*.md" --include="*.py" --include="*.js" --include="*.yml" --include="*.yaml"
grep -r "SYSTEM_ARCHITECTURE" . --include="*.md" --include="*.py"
grep -r "doc/architecture/deployment" . --include="*.md" --include="*.py"
grep -r "architecture/SYSTEM" . --include="*.md"

# Поиск в GitHub Actions
grep -r "PRODUCTION_DEPLOYMENT\|SYSTEM_ARCHITECTURE" .github/ --include="*.yml" --include="*.yaml"

# Поиск в скриптах
grep -r "PRODUCTION_DEPLOYMENT\|SYSTEM_ARCHITECTURE" scripts/ --include="*.py" --include="*.md"
```

### Шаг 3: Типы ссылок и паттерны замены

| Тип ссылки | Паттерн | Пример замены |
|---|---|---|
| Markdown ссылка | `[text](path/to/file.md)` | `[Production Guide](../../deployment/deployment-guide.md)` |
| HTML ссылка | `<a href="path">text</a>` | `<a href="deployment/deployment-guide.md">Production Guide</a>` |
| URL в тексте | `See path/to/file.md for` | `See doc/deployment/deployment-guide.md for` |
| Code comment | `# See path/to/file.md` | `# See doc/deployment/deployment-guide.md` |
| Относительная ссылка | `../../../doc/path` | `../../deployment/deployment-guide.md` |

### Шаг 4: Автоматизированная замена

```bash
# Используя sed или другие утилиты

# Замена абсолютных путей относительно doc/
find . -type f \( -name "*.md" -o -name "*.py" \) -exec sed -i '' \
  's|PRODUCTION_DEPLOYMENT_GUIDE\.md|doc/deployment/deployment-guide.md|g' {} \;

find . -type f \( -name "*.md" -o -name "*.py" \) -exec sed -i '' \
  's|doc/architecture/SYSTEM_ARCHITECTURE\.md|doc/architecture/system-overview.md|g' {} \;

# Замена по категориям (примеры)
find . -type f -name "*.md" -exec sed -i '' \
  's|doc/setup-guide|doc/getting-started/setup-guide|g' {} \;

find . -type f -name "*.md" -exec sed -i '' \
  's|doc/rest-api|doc/api/rest-api|g' {} \;

# И так далее для всех файлов...
```

### Шаг 5: Ручная проверка критических файлов

```bash
# Проверить главный INDEX
cat doc/INDEX.md | grep -E "href|]\("

# Проверить README
cat README.md | grep -E "href|]\("

# Проверить конфиг файлы
grep -r "PRODUCTION_DEPLOYMENT\|SYSTEM_ARCHITECTURE" . --include="*.json" --include="*.toml" --include="*.yaml" --include="*.yml"
```

### Шаг 6: Валидация ссылок

```bash
# Проверить, что файлы на месте
find doc -name "*.md" | sort

# Проверить, что все ссылки указывают на существующие файлы
for link in $(grep -r "]\(" doc/ | grep -o '\]\([^)]*\)' | sed 's/\]\(//;s/)//'); do
  if [ ! -f "doc/${link}" ]; then
    echo "Broken link: ${link}"
  fi
done

# Проверить на старые пути в документации
grep -r "PRODUCTION_DEPLOYMENT\|SYSTEM_ARCHITECTURE" doc/ --include="*.md" | grep -v archive
```

---

## ✅ Чеклист проверки

### После Фазы 1: Создание структуры

- [ ] `find doc -type d | wc -l` показывает 12 основных категорий + подкатегории
- [ ] `ls -la doc/` показывает все созданные директории
- [ ] Нет ошибок при создании директорий
- [ ] `git status` показывает только новые директории

### После Фазы 2: Перемещение из корня

- [ ] `ls *.md | wc -l` показывает не более 5-6 файлов (README, LICENSE и т.д.)
- [ ] `ls doc/changelogs/*.md | wc -l` = 8 (все CHANGELOG файлы)
- [ ] `ls doc/reports/*.md | wc -l` >= 8 (все отчёты)
- [ ] Нет файлов test.md в корне
- [ ] Нет файлов test.md в doc/
- [ ] `git log --follow QUICKSTART.md` показывает историю (если используется `git mv`)

### После Фазы 3: Реорганизация в doc/

- [ ] `doc/getting-started/` содержит: quickstart.md, setup-guide.md, infrastructure-setup.md
- [ ] `doc/api/` содержит: rest-api.md, sse-event-streaming.md, streaming-fetch-api.md, api-specification.md
- [ ] `doc/guides/` содержит: developer-guide.md, integration-guide.md, llm-error-handling.md, technical-requirements.md
- [ ] `doc/integrations/` содержит: litellm-*.md, langfuse-*.md, llm-providers-api.md
- [ ] `doc/features/` содержит: agent-*.md, tool-*.md, session-id-propagation.md, idempotency.md
- [ ] `doc/deployment/` содержит: deployment-guide.md, production-checklist.md
- [ ] `doc/changelogs/` содержит все CHANGELOG_*.md
- [ ] `doc/implementation/` содержит: implementation-summary.md, release-specification-v0.2.0.md
- [ ] `doc/reports/` содержит все отчёты о багах и анализе
- [ ] `doc/bugfixes/` содержит все исправления
- [ ] `doc/migrations/` содержит все гайды по миграции
- [ ] `doc/archive/` содержит устаревшие документы
- [ ] Нет файлов в корне doc/ (кроме README.md, INDEX.md, .gitkeep)

### После Фазы 4: Объединение дубликатов

- [ ] `doc/deployment/deployment-guide.md` содержит контент из обоих файлов
- [ ] `doc/architecture/system-overview.md` содержит контент из обоих файлов
- [ ] Файл PRODUCTION_DEPLOYMENT_GUIDE.md удалён из корня
- [ ] Файл doc/architecture/SYSTEM_ARCHITECTURE.md удалён
- [ ] Объединённые файлы имеют правильную структуру (проверить `# ## ###`)
- [ ] Нет дубликатов в содержимом

### После Фазы 5: Очистка

- [ ] Все опечатки исправлены (`technical-requirements.md` вместо `techincal-requrements.md`)
- [ ] Файл test.md удалён
- [ ] Файл SESSION_ID_PROPAGATION_IMPLEMENTATION_PLAN.md удалён (дублирует strategy)
- [ ] doc/INDEX.md обновлён и отражает новую структуру
- [ ] `find doc -type f -name "*.md" | wc -l` = ~73 (после удаления дубликатов)

### После Фазы 6: Обновление ссылок

- [ ] `grep -r "PRODUCTION_DEPLOYMENT_GUIDE" doc/ --include="*.md"` не показывает результатов (кроме archive/)
- [ ] `grep -r "SYSTEM_ARCHITECTURE" doc/ --include="*.md"` не показывает результатов (кроме archive/)
- [ ] `grep -r "doc/architecture/deployment-guide" doc/ --include="*.md"` не показывает результатов
- [ ] Все ссылки в doc/INDEX.md рабочие
- [ ] Все README.md в категориях содержат правильные ссылки
- [ ] Нет broken links в документации (проверить вручную)
- [ ] doc/architecture/README.md обновлён
- [ ] ROOT README.md обновлён (если содержит ссылки на документацию)

### Интеграция с кодом

- [ ] `grep -r "PRODUCTION_DEPLOYMENT\|SYSTEM_ARCHITECTURE" . --include="*.py"` показывает только комментарии (если есть)
- [ ] `grep -r "PRODUCTION_DEPLOYMENT\|SYSTEM_ARCHITECTURE" .github/` не показывает результатов (или показывает только очищенные ссылки)
- [ ] `grep -r "PRODUCTION_DEPLOYMENT\|SYSTEM_ARCHITECTURE" scripts/` проверена
- [ ] `grep -r "doc/architecture/deployment" . --include="*.py"` проверена
- [ ] Документация, на которую ссылается код, находится в правильных местах

### Общее качество

- [ ] Структура документации логична и интуитивна
- [ ] Каждая категория имеет README.md с навигацией (если требуется)
- [ ] Нет пустых категорий
- [ ] Все файлы имеют читаемые имена (lowercase, без дефисов в начале)
- [ ] Проведена локальная сборка документации (если используется Sphinx, MkDocs и т.д.)
- [ ] Нет ошибок в Markdown синтаксисе
- [ ] Все изображения и диаграммы по-прежнему ссылаются правильно

---

## 🔄 Откат (если что-то пошло не так)

Если во время реорганизации что-то пошло не так, можно откатиться:

```bash
# Откат всех изменений до последнего commit
git reset --hard HEAD

# Или откатить отдельные файлы
git checkout HEAD -- doc/deployment/deployment-guide.md

# Проверить статус
git status
```

---

## 📝 Заметки и рекомендации

1. **Используйте `git mv` вместо обычного `mv`** - это сохраняет историю файла в git
2. **Создавайте commits после каждой фазы** - это позволит откатиться, если что-то пошло не так
3. **Проверяйте ссылки после каждого перемещения** - особенно внутренние ссылки между документами
4. **Обновляйте README файлы в категориях** - чтобы помочь пользователям навигировать по документации
5. **Учитывайте SEO и URL структуру** - если документация публикуется онлайн, новые пути должны быть более intuitive
6. **Проверяйте CI/CD** - убедитесь, что ваша система CI/CD не ломается из-за новых путей
7. **Уведомите команду** - перед реорганизацией и после, чтобы все знали о новых путях

---

## 📊 Итоговая статистика

### Заполнено

| Метрика | До | После | Изменение |
|---------|-----|-------|-----------|
| Файлов в корне | 29 | 3-5 | -80% |
| Файлов в doc/ | 45 | 73 | +62% (но организовано) |
| Дубликатов | 2 основных | 0 | -100% |
| Категорий в doc/ | 1 | 12 | +1100% |
| Структурированность | ⭐⭐ | ⭐⭐⭐⭐⭐ | Отличный результат |

### Затронутые файлы

- **Перемещено:** ~70 файлов
- **Объединено:** 2 пары (4 файла → 2 файла)
- **Удалено:** 3 файла (тестовые, дубликаты)
- **Переименовано:** ~10 файлов (исправления опечаток, переформатирование имён)
- **Обновлено:** ~40 файлов (обновление ссылок)

---

## 📞 Контакты и поддержка

При возникновении вопросов:
1. Проверьте соответствующий раздел в этом документе
2. Используйте `git diff` для просмотра изменений
3. Проверьте `git log` для истории изменений
4. Откатитесь, если что-то сломалось

---

**Документ создан:** 17 марта 2026  
**Версия:** 1.0  
**Статус:** Готов к реализации

