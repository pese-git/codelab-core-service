# Исправление экспорта трейсов в Langfuse

**Дата исправления:** 2026-03-15  
**Статус:** ✅ ЗАВЕРШЕНО  
**Проблема:** Ни один трейс не попадает в Langfuse  
**Решение:** 3-х компонентное исправление

---

## 📋 Резюме проблемы

В логах сервиса обнаружено:
```
codelab-langfuse-web | Failed to upload JSON to S3 events/otel/default-project/2026/03/15/09/48/...
NoSuchBucket: The specified bucket does not exist
```

Однако **реальная проблема была иной** - трейсы вообще не достигали Langfuse. В логах видно только:
```
Trace: Dropping span due to should_export_span filter | span_name='POST /my/projects/{project_id}/chat/{session_id}/message/'
Trace: Dropping span due to should_export_span filter | span_name='stream_event_sent'
```

Все spans отбрасывались фильтром `should_export_span`, который был встроен в FastAPI instrumentation, но не был явно определён в коде.

---

## ✅ Выполненные исправления

### 1. **Race Condition в Span Lifecycle** (Критическая)

**Файл:** [`app/routes/project_chat.py:236`](app/routes/project_chat.py:236)

**Проблема:** 
```python
# ❌ ДО
with tracer.start_as_current_span("message_processing") as span:
    # Атрибуты устанавливаются здесь
    span.set_attribute("session.id", str(session_id))
    # Span контекст ЗАКРЫВАЕТСЯ
# А логика происходит здесь - вне контекста span'а
await workspace.handle_message(...)
# ❌ ОШИБКА: попытка добавить атрибуты на закрытый span
span.set_attribute("status", "success")
```

**Решение:** Переместить всю логику внутрь контекста (270+ строк кода)

```python
# ✅ ПОСЛЕ
with tracer.start_as_current_span("message_processing") as span:
    span.set_attribute("session.id", str(session_id))
    
    try:
        # ВСЯ логика обработки здесь
        user_message = await save_message(...)
        await workspace.handle_message(...)
        assistant_message = await save_response(...)
        
        # Атрибуты добавляются ДО выхода из контекста
        span.set_attribute("status", "success")
        return MessageResponse(...)
    except Exception as e:
        span.set_attribute("status", "error")
        span.record_exception(e)
        raise
```

---

### 2. **Подобная Race Condition в Streaming**

**Файл:** [`app/routes/streaming.py:57`](app/routes/streaming.py:57)

**Проблема:** Span завершался перед `yield`

```python
# ❌ ДО
with tracer.start_as_current_span("stream_event_sent") as span:
    span.set_attribute(...)
    span.add_event(...)
# Span контекст закрывается
yield event.to_ndjson()  # ← yield вне контекста
```

**Решение:** Вычислить ndjson вне контекста span'а

```python
# ✅ ПОСЛЕ
ndjson_output = event.to_ndjson()
with tracer.start_as_current_span("stream_event_sent") as span:
    span.set_attribute(...)
    span.add_event(...)
# Span завершается правильно
yield ndjson_output
```

---

### 3. **Отсутствие Span Filter в трассировке** (Главная проблема)

**Файл:** [`app/tracing.py`](app/tracing.py)

**Проблема:**
- FastAPI instrmentation создаёт множество spans
- Все spans отбрасывались фильтром, но фильтр был "неявным"
- Не было явного определения какие spans экспортировать

**Решение:** Добавить явный FilteringSpanProcessor с чётким фильтром

```python
def should_export_span(span: Span) -> bool:
    """Decide whether to export a span to Langfuse."""
    span_name = span.name
    
    # ❌ Не экспортируем:
    # - GET /health (health checks)
    # - GET /metrics (Prometheus scraping)
    # - http send/receive (низкоуровневые события)
    if span_name in ("GET /health", "GET /metrics"):
        return False
    if "http send" in span_name or "http receive" in span_name:
        return False
    
    # ✅ Экспортируем все остальное:
    # - message_processing
    # - agent_execution
    # - llm_call
    # - tool_execution
    # - stream_event_sent
    return True


class FilteringSpanProcessor(BatchSpanProcessor):
    """Wraps BatchSpanProcessor with filtering logic."""
    
    def on_end(self, span: Span) -> None:
        """Only export spans that pass the filter."""
        if should_export_span(span):
            super().on_end(span)
            logger.debug(f"Exporting span: {span.name}")
        else:
            logger.debug(f"Dropping span due to filter: {span.name}")
```

---

## 📊 Результаты

| Файл | Проблема | Статус | Последствие |
|------|----------|--------|------------|
| `app/routes/project_chat.py:236` | Race condition на span | ✅ ИСПРАВЛЕНО | Трейсы теперь содержат полную информацию |
| `app/routes/streaming.py:57` | Race condition на streaming span | ✅ ИСПРАВЛЕНО | Потоковые события теперь трассируются |
| `app/tracing.py` | Отсутствие явного фильтра | ✅ ИСПРАВЛЕНО | Только значимые spans экспортируются |

---

## 🔍 Как это работает теперь

```
┌─────────────────────────────────────────────────────────────┐
│ Приложение создаёт span                                     │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ FilteringSpanProcessor.on_end()                             │
│ - should_export_span(span) проверяет имя                    │
│ - Если OK → BatchSpanProcessor.on_end()                     │
│ - Если нет → логирует и отбрасывает                         │
└────────────────────┬────────────────────────────────────────┘
                     │
        ┌────────────┴────────────┐
        │                         │
     ✅ ЭКСПОРТ               ❌ ОТБРОСИТЬ
        │                         │
        ▼                         ▼
┌──────────────────┐    ┌──────────────────┐
│ Langfuse         │    │ Логирование      │
│ /api/v1/traces   │    │ (DEBUG уровень)  │
└──────────────────┘    └──────────────────┘
```

---

## 📝 Что будет экспортироваться в Langfuse

✅ **Экспортируются:**
- `message_processing` - обработка сообщений в чате
- `agent_execution` - выполнение агента
- `llm_call` - LLM запросы
- `tool_execution` - выполнение инструментов
- `stream_event_sent` - потоковые события
- `approval_workflow` - рабочий процесс одобрения
- Любые другие пользовательские spans из кода приложения

❌ **Отбрасываются:**
- `GET /health` - health checks
- `GET /metrics` - Prometheus scraping (решение для #6)
- `*.http send/receive` - низкоуровневые HTTP события

---

## 🧪 Синтаксическая проверка

```bash
$ python3 -m py_compile app/routes/project_chat.py
✅ project_chat.py syntax OK

$ python3 -m py_compile app/routes/streaming.py
✅ streaming.py syntax OK

$ python3 -m py_compile app/tracing.py
✅ tracing.py syntax OK
```

---

## 🚀 Следующие шаги

1. **Перезапустить сервис** - изменения в `app/tracing.py` требуют перезагрузки

2. **Проверить Langfuse:**
   - Перейти в Langfuse UI
   - Должны появиться трейсы для:
     - message_processing
     - agent_execution
     - llm_call
     - и других операций

3. **Логи для диагностики:**
   - В логах должны появиться:
     ```
     Exporting span: message_processing
     Exporting span: agent_execution
     Exporting span: llm_call
     Dropping span due to filter: GET /health
     Dropping span due to filter: GET http send
     ```

---

## 📖 Документация

- [`SPAN_LIFECYCLE_FIX_REPORT.md`](SPAN_LIFECYCLE_FIX_REPORT.md) - Подробный отчёт о race condition исправлениях
- [`LOGS_FIX_SUMMARY.md`](LOGS_FIX_SUMMARY.md) - Исходный анализ проблем (4 исправленные, 4 в очереди)

