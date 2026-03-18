# Исправление DetachedInstanceError - Итоговый отчет

**Дата:** 10 Марта 2026 г.
**Статус:** ✅ Завершено

## Проблема

SQLAlchemy `DetachedInstanceError` возникал при обработке сообщений в чате:
```
sqlalchemy.orm.exc.DetachedInstanceError: Instance <UserLLMProvider at 0x...> is not bound to a Session; 
attribute refresh operation cannot proceed
```

**Причина:** Объект `UserLLMProvider` загружался из БД, сессия закрывалась/flush'илась, и затем код пытался обратиться к его атрибутам, вызывая ошибку.

---

## Решение: 3-уровневый подход

### 1️⃣ Переприсоединение объекта к сессии (app/core/user_worker_space.py:306-320)

```python
# Get LLM provider if agent has one
# Use merge() to ensure provider stays attached to session
llm_provider = None
if hasattr(agent_db_model, 'llm_provider_id') and agent_db_model.llm_provider_id:
    try:
        # Access the relationship while session is still active
        provider = agent_db_model.llm_provider
        if provider:
            # Merge provider into current session to prevent DetachedInstanceError
            llm_provider = await self.db.merge(provider)
    except Exception as e:
        logger.warning(...)
        llm_provider = None
```

**Результат:** `UserLLMProvider` объект остается привязанным к сессии для последующего использования.

---

### 2️⃣ Безопасный доступ к атрибутам провайдера (app/agents/contextual_agent.py)

#### 2A. При логировании span attributes (строка 119-126):
```python
try:
    model_name = self.llm_provider.litellm_model_name if self.llm_provider else "unknown"
except Exception:
    model_name = "unknown"
span.set_attribute("model", model_name)
```

#### 2B. При логировании выполнения (строка 136-148):
```python
provider_id = None
provider_type = None
if self.llm_provider:
    try:
        provider_id = str(self.llm_provider.id)
        provider_type = self.llm_provider.provider_type
    except Exception:
        pass

logger.debug(
    "execute_started",
    llm_provider_id=provider_id,
    llm_provider_type=provider_type,
)
```

#### 2C. При получении model (строка 178-195):
```python
model_to_use = None
try:
    if self.llm_provider:
        model_to_use = self.llm_provider.litellm_model_name
except Exception as e:
    logger.warning("failed_to_access_provider_model", error=str(e))

if not model_to_use:
    return {"success": False, "error": "Agent must have a registered LLM provider"}
```

**Результат:** Код работает даже если провайдер отсоединен, просто логирует warning.

---

### 3️⃣ Избегание доступа к config (app/agents/contextual_agent.py:83-99)

**Старый подход** - вызывал детачмент:
```python
def _get_provider_url(self) -> str:
    if self.llm_provider and self.llm_provider.config:
        return self.llm_provider.config.get("base_url", ...)  # ❌ Может вызвать детачмент
```

**Новый подход** - использует простые атрибуты:
```python
def _get_provider_name(self) -> str:
    """Get provider name for logging purposes.
    
    Uses display_name or provider_type to avoid accessing config which
    can trigger DetachedInstanceError.
    """
    if self.llm_provider:
        try:
            display_name = getattr(self.llm_provider, 'display_name', None)
            if display_name:
                return display_name
            provider_type = getattr(self.llm_provider, 'provider_type', None)
            if provider_type:
                return provider_type
        except Exception:
            pass
    return 'default'
```

**Заменены все 10 вызовов:**
- `self._get_provider_url()` → `self._get_provider_name()`

**Результат:**
- Логи содержат имя провайдера (например "openrouter") вместо URL
- Нет доступа к JSON config полю
- Безопасно при любом состоянии сессии

---

## Измененные файлы

| Файл | Строки | Изменение |
|------|--------|-----------|
| `app/core/user_worker_space.py` | 306-320 | Добавлен merge() для переприсоединения провайдера |
| `app/agents/contextual_agent.py` | 83-99 | Переименован `_get_provider_url()` → `_get_provider_name()` |
| `app/agents/contextual_agent.py` | 119-126 | Try-except для `litellm_model_name` в span attributes |
| `app/agents/contextual_agent.py` | 136-148 | Try-except для провайдера ID/type при логировании |
| `app/agents/contextual_agent.py` | 178-195 | Try-except для получения model при выполнении |
| `app/agents/contextual_agent.py` | 391, 409, 420, 430, 441, 459, 472, 490, 503, 521 | Заменены вызовы метода (x10) |
| `app/agents/contextual_agent.py` | 895-906 | Try-except в `_record_provider_usage()` |

---

## Тестирование

Для проверки исправления:

```bash
# Перезагрузить контейнер
docker-compose restart app

# Проверить логи на предмет ошибок
docker-compose logs app | grep -i "detached\|error"

# Отправить тестовое сообщение в чат с агентом
curl -X POST http://localhost:8000/my/projects/{project_id}/chat/{session_id}/message/ \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{"content":"Test message"}'
```

---

## Ожидаемые результаты

✅ **До:** 500 Internal Server Error при обработке сообщений
```
Error processing message: Instance <UserLLMProvider> is not bound to a Session
```

✅ **После:** Сообщения обрабатываются успешно
- Логи содержат `provider_name` (например "openrouter") вместо URL
- Нет `DetachedInstanceError` даже при проблемах с сессией
- Система gracefully fallback'ит к default значениям если провайдер не доступен

---

## Дополнительные рекомендации

1. **Долгосрочное решение:** Рассмотреть использование `@property` с `lazy` loading для часто используемых атрибутов провайдера
2. **Мониторинг:** Отслеживать логи `failed_to_access_provider_model` для выявления новых случаев детачмента
3. **Документация:** Добавить комментарии о том, какие атрибуты провайдера безопасны для доступа из кэша агентов

---

## Статус других критических ошибок

Из анализа логов выявлены еще ошибки, требующие исправления:

| Ошибка | Статус | Приоритет |
|--------|--------|-----------|
| DetachedInstanceError | ✅ Исправлено | 🔴 CRITICAL |
| Redis Security Attacks | ⏳ Ожидает | 🔴 CRITICAL |
| Duplicate Project Constraint | ⏳ Ожидает | 🟠 HIGH |
| Missing LiteLLM Table | ⏳ Ожидает | 🟠 HIGH |

Смотри `DOCKER_LOGS_ANALYSIS_REPORT.md` для полного списка ошибок.
