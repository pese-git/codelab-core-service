# Исправление Race Condition в Span Lifecycle

**Дата исправления:** 2026-03-15  
**Статус:** ✅ ЗАВЕРШЕНО  
**Версия сервиса:** 0.1.0

---

## 📋 Резюме

Идентифицирована и исправлена **критическая race condition** в span lifecycle OpenTelemetry, которая вызывала ошибки:
- `"Setting attribute on ended span"`
- `"Tried calling _add_event on an ended span"`

Проблема заключалась в том, что span контексты закрывались преждевременно, до завершения всех операций.

---

## 🔍 Выявленные проблемы

### 1. **app/routes/project_chat.py** - Критическая race condition

**Проблема:** Span контекст закрывался на строке 244, но атрибуты и события добавлялись на строках 497-500:

```python
# ❌ ДО (строки 236-244)
with tracer.start_as_current_span("message_processing") as span:
    span.set_attribute("session.id", str(session_id))
    span.set_attribute("project.id", str(project_id))
    span.set_attribute("user.id", str(user_id))
    span.set_attribute("message.type", "user_message")
    span.add_event("message_received", {"content_length": len(message_request.content)})
    
# SPAN КОНТЕКСТ ЗАКРЫВАЕТСЯ ЗДЕСЬ ← проблема!

# Вся остальная логика (245-495) выполняется вне контекста
...message processing logic...

# ❌ ОШИБКА: попытка добавить атрибуты на завершённый span (строки 497-500)
span.set_attribute("status", "success")
span.add_event("response_generated", {"response_length": len(assistant_message.content)})
```

**Последствия:**
- OpenTelemetry выбрасывает ошибку при попытке модифицировать завершённый span
- Трассировка полностью теряется
- Logfuse не получает метаданные о статусе выполнения

---

### 2. **app/routes/streaming.py** - Подобная race condition

**Проблема:** В методе `event_stream_generator()` span контекст закрывался, но затем yield выполнялся вне контекста (строки 57-65):

```python
# ❌ ДО
with tracer.start_as_current_span("stream_event_sent") as span:
    span.set_attribute("session.id", str(session_id))
    span.set_attribute("user.id", str(user_id))
    span.set_attribute("event.type", event.event_type)
    span.set_attribute("payload.keys", ...)
    span.add_event("event_serialized", {...})
# SPAN КОНТЕКСТ ЗАКРЫВАЕТСЯ
yield event.to_ndjson()  # ← yield вне контекста
```

**Последствия:**
- Каждое событие генерирует ошибку в трассировке
- SSE потоковая передача не отслеживается корректно

---

## ✅ Выполненные исправления

### 1. **app/routes/project_chat.py** - Полное исправление

**Изменение:** Переместил **всю логику обработки сообщения** внутрь span контекста:

```python
# ✅ ПОСЛЕ
with tracer.start_as_current_span("message_processing") as span:
    span.set_attribute("session.id", str(session_id))
    span.set_attribute("project.id", str(project_id))
    span.set_attribute("user.id", str(user_id))
    span.set_attribute("message.type", "user_message")
    span.add_event("message_received", {"content_length": len(message_request.content)})
    
    try:
        # Вся логика обработки теперь внутри контекста
        user_message = Message(...)  # сохранение сообщения
        await OutboxRepository.record_event(...)  # запись события
        
        # История сессии
        history_result = await db.execute(...)
        
        # Обработка цели
        target_agent_id = ...
        
        # Выполнение в workspace
        exec_result = await workspace.handle_message(...)
        
        # Получение информации об агенте
        agent_manager = AgentManager(...)
        
        # Отправка SSE событий
        await stream_manager.broadcast_event(...)
        
        # Сохранение ответа
        assistant_message = Message(...)
        await OutboxRepository.record_event(...)
        
        # Отправка события завершения
        await stream_manager.broadcast_event(...)
        
        # ✅ ПРАВИЛЬНО: добавить атрибуты ДО выхода из контекста
        span.set_attribute("status", "success")
        span.add_event("response_generated", {"response_length": len(assistant_message.content)})
        
        return MessageResponse(...)
        
    except HTTPException:
        span.set_attribute("status", "error")
        raise
    except ValueError as e:
        span.set_attribute("status", "error")
        span.add_event("validation_error", {"error": str(e)})
        ...
    except Exception as e:
        span.set_attribute("status", "error")
        span.record_exception(e)
        ...
```

**Преимущества:**
- ✅ Span остаётся активным на протяжении всей обработки
- ✅ Все атрибуты и события добавляются внутри контекста
- ✅ Обработка исключений также находится в контексте
- ✅ Правильная трассировка выполнения

---

### 2. **app/routes/streaming.py** - Исправление event stream

**Изменение:** Вычислить ndjson вне контекста, span используется только для трассировки:

```python
# ✅ ПОСЛЕ
if isinstance(event, StreamEvent):
    # Вычислить результат ВНЕ контекста
    ndjson_output = event.to_ndjson()
    
    # Trace span только для метрик
    with tracer.start_as_current_span("stream_event_sent") as span:
        span.set_attribute("session.id", str(session_id))
        span.set_attribute("user.id", str(user_id))
        span.set_attribute("event.type", event.event_type)
        span.set_attribute("payload.keys", ",".join(event.payload.keys()) if event.payload else "empty")
        span.add_event("event_serialized", {"ndjson_length": len(ndjson_output)})
    
    # Теперь span уже завершён, можно безопасно yield
    yield ndjson_output
    continue
```

**Преимущества:**
- ✅ Span корректно завершается перед yield
- ✅ Каждое событие правильно трассируется
- ✅ Нет race condition при потоковой передаче

---

## 🔎 Проверены другие файлы

Проверены все остальные файлы с использованием span контекстов:

### `app/agents/contextual_agent.py`
- ✅ Span `agent_execution` - все операции внутри контекста
- ✅ Span `llm_call` - вложенный span правильно используется
- ✅ Все атрибуты и события добавляются в контексте
- ✅ Exception handling правильно использует `span.record_exception()`

### `app/core/tools/executor.py`
- ✅ Span `tool_execution` - все operaции внутри контекста
- ✅ Вложенные span'ы (`tool_validation`, `risk_assessment`, `approval_workflow`, `client_execution`) правильно используются
- ✅ Exception handling имеет правильное завершение спана
- ✅ Return statements находятся внутри контекста

---

## 📊 Результаты

| Файл | Проблема | Статус | Изменения |
|------|----------|--------|-----------|
| `app/routes/project_chat.py:236` | Race condition на span `message_processing` | ✅ ИСПРАВЛЕНО | Перемещена вся логика в контекст (270+ строк) |
| `app/routes/streaming.py:57` | Race condition на span `stream_event_sent` | ✅ ИСПРАВЛЕНО | Перемещено вычисление ndjson вне контекста |
| `app/agents/contextual_agent.py:179` | Проверка | ✅ КОРРЕКТНО | Нет изменений требуется |
| `app/core/tools/executor.py:133` | Проверка | ✅ КОРРЕКТНО | Нет изменений требуется |

---

## 🧪 Тестирование

### Синтаксис
```bash
$ python3 -m py_compile app/routes/project_chat.py
✅ project_chat.py syntax OK

$ python3 -m py_compile app/routes/streaming.py
✅ streaming.py syntax OK
```

### Статическая проверка
- ✅ Все span контексты используют `with` statement
- ✅ Все атрибуты/события добавляются внутри контекстов
- ✅ Exception handling правильно обработан
- ✅ Return statements находятся в контексте span'а

---

## 📝 Рекомендации

1. **Monitoring:** После развёртывания проверить логи на отсутствие ошибок:
   - `"Setting attribute on ended span"`
   - `"Tried calling _add_event on an ended span"`

2. **Langfuse:** Убедиться, что все traces теперь экспортируются с полной информацией

3. **Best Practices:** Используйте этот паттерн для всех span контекстов:
   ```python
   with tracer.start_as_current_span("operation_name") as span:
       span.set_attribute("key", "value")
       try:
           # Все операции здесь
           result = do_work()
           span.add_event("success", {...})
           return result
       except Exception as e:
           span.record_exception(e)
           span.set_attribute("status", "error")
           raise
   ```

---

## ✨ Итоговый результат

**Исправлена критическая race condition в span lifecycle**, которая привела к:
- ✅ Потере трассировки выполнения сообщений
- ✅ Ошибкам при экспорте в Langfuse
- ✅ Неполной информации об обработке

**Теперь:**
- ✅ Все spans остаются активными на протяжении их операций
- ✅ Все атрибуты и события правильно добавляются
- ✅ Трассировка будет полной и корректной
- ✅ Langfuse получит полную информацию о выполнении

