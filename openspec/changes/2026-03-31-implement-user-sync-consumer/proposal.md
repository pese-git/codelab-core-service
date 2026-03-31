# OpenSpec Change: Event-Driven синхронизация и Token Blacklist (Core Service)

**Версия:** 1.0.0  
**Дата:** 31 марта 2026  
**Сервис:** codelab-core-service

---

## 🔴 Проблема (Why)

### Текущее состояние

В текущей системе:

1. **Удаленные пользователи оставляют данные в БД** — Когда auth-service удаляет пользователя, в core-service остаются:
   - Orphaned проекты (UserProject)
   - Orphaned агенты (UserAgent)
   - Orphaned чат-сессии (ChatSession)
   - Orphaned сообщения (Message)

2. **Нет синхронизации профиля** — Когда пользователь обновляет профиль в auth-service (email, имя), в core-service остается старая информация.

3. **Отозванные токены все еще работают в core-service** — Даже если auth-service отозвал токен, core-service может не проверить blacklist, позволяя использовать токен.

### Влияние на систему

- ⚠️ **Целостность данных**: orphaned записи в БД → утечки памяти, неправильная статистика
- ⚠️ **Безопасность**: отозванный токен может быть использован в core-service
- ⚠️ **Пользовательский опыт**: удаленный пользователь может случайно увидеть старые данные
- ⚠️ **Рассогласованность**: два сервиса имеют разные состояния пользователя

---

## 💚 Решение (What Changes)

### Компоненты, которые добавляются/обновляются в core-service

#### 1. **Event Consumer (Redis Streams)**
- Async consumer для прослушивания `user_events` stream
- Автоматическая обработка событий (user.created, user.updated, user.deleted)
- Retry logic с exponential backoff
- Dead Letter Queue для failed событий
- Consumer Groups для надежной доставки

#### 2. **Token Blacklist Integration** 
- Интеграция TokenBlacklistService в UserIsolationMiddleware
- Проверка if token in blacklist перед обработкой запроса
- Graceful fallback если Redis недоступен

#### 3. **User Sync Handlers**
- `handle_user_created()` — синхронизировать profile пользователя
- `handle_user_updated()` — обновить profile и отправить notifications
- `handle_user_deleted()` — CASCADE delete всех данных пользователя
- Idempotent обработка (safe to replay)

#### 4. **Database Schema Updates**
- Добавить `user_profile_version` для отслеживания синхронизации
- Добавить `synced_from_auth_at` для аудита

#### 5. **Middleware Updates**
- Добавить blacklist проверку в UserIsolationMiddleware
- Логирование revoked tokens
- Graceful degradation если Redis down

---

## 🔄 Диаграмма взаимодействия

```
┌─────────────────────────────────────┐
│  Auth Service                       │
│  (deleted user, events published)  │
└────────────────┬────────────────────┘
                 │
                 ▼
        ┌─────────────────┐
        │ Redis Streams   │
        │ (user_events)   │
        └────────┬────────┘
                 │
        ┌────────▼─────────────────────┐
        │ Core Service                 │
        │                              │
        │ ┌────────────────────────┐  │
        │ │ EventConsumer          │  │
        │ │ (XREAD, XACK)         │  │
        │ └────────┬───────────────┘  │
        │          │ user.deleted     │
        │          ▼                  │
        │ ┌────────────────────────┐  │
        │ │ Handle user.deleted    │  │
        │ │                        │  │
        │ │ 1. Get user_id        │  │
        │ │ 2. Delete projects    │  │
        │ │ 3. Delete agents      │  │
        │ │ 4. Delete sessions    │  │
        │ │ 5. Delete user        │  │
        │ │ 6. ACK event          │  │
        │ └────────────────────────┘  │
        │          │                  │
        │ ┌────────▼─────────────────┐ │
        │ │ UserIsolationMiddleware  │ │
        │ │                          │ │
        │ │ 1. Validate JWT          │ │
        │ │ 2. Check blacklist (new) │ │
        │ │ 3. Inject user context   │ │
        │ └──────────────────────────┘ │
        │                              │
        └──────────────────────────────┘
```

---

## 📊 Альтернативные решения (Alternatives)

### Альтернатива 1: Polling вместо Event Consumer

**Преимущества:**
- Проще реализовать (cron job)
- Нет need для consumer groups
- Можно контролировать timing

**Недостатки:**
- ❌ Высокая latency (polling каждые N сек)
- ❌ Нагрузка на БД (много queries)
- ❌ Не масштабируется
- ❌ Может пропустить события

**Рекомендация:** Используем Event Consumer (async, real-time, scalable).

### Альтернатива 2: Синхронный REST call из auth-service

**Преимущества:**
- Известен результат сразу
- Нет need для consumer

**Недостатки:**
- 🔴 Тесная связь между сервисами
- 🔴 Если core-service down, удаление падает
- 🔴 Медленнее (ждем ответ)

**Рекомендация:** НЕ рекомендуется. Async > Sync для микросервисов.

---

## ⚠️ Риски и Митигация

| Риск | Вероятность | Impact | Митигация |
|------|------------|--------|-----------|
| Event потеряется | Низкая | Критический | Consumer Groups + Redis persistence |
| Middleware не проверяет blacklist | Низкая | Критический | Unit тесты + middleware tests |
| Cascade delete ошибка | Средняя | Критический | Транзакции + rollback |
| Consumer зависает | Средняя | Высокий | Timeout + health check + restart |
| Redis недоступен | Средняя | Высокий | Graceful degradation + alerts |
| Race condition (delete перед create) | Низкая | Средний | Idempotent handlers + version tracking |

**Стратегия:**
1. ✅ Consumer Groups для at-least-once delivery
2. ✅ Idempotent handlers (safe to replay)
3. ✅ DLQ для failed события
4. ✅ Graceful fallback если Redis/broker down
5. ✅ Alerts на DLQ growth

---

## 🎯 Успешное внедрение означает

- ✅ Удаленный пользователь → все данные удалены
- ✅ Обновленный пользователь → profile синхронизирован
- ✅ Revoked токен → blocked в core-service
- ✅ Event delivery > 99.9%
- ✅ Cascade delete < 5s
- ✅ Нет orphaned данных в БД

---

## 📈 Метрики успеха

### Функциональные
- Event consumption latency: p95 < 500ms
- Cascade delete latency: p95 < 5s
- Event delivery rate: > 99.9%
- DLQ size: < 100 messages

### Операционные
- Consumer lag: < 5 seconds
- Middleware blacklist check: < 10ms
- Event handler success rate: > 99%

---

## 🔗 Связанные документы

- [`plans/event-driven-sync-token-blacklist-architecture.md`](../../plans/event-driven-sync-token-blacklist-architecture.md) — полная архитектура
- [`plans/redis-streams-implementation-guide.md`](../../plans/redis-streams-implementation-guide.md) — детальное руководство реализации
- `openspec/changes/2026-03-31-implement-user-sync-events/` — auth-service спецификации
