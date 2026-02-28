# Идемпотентность и надежность событий

## Обзор

Паттерн Event Log + Outbox реализует ровно-один раз семантику доставки событий через идемпотентную публикацию. Этот гайд описывает как потребители должны обрабатывать дедупликацию событий.

## Задача 6.1: Event ID в payload

### Структура события

Каждое событие опубликованное в streaming включает поле `event_id` в payload:

```json
{
  "event_type": "message_created",
  "event_id": "550e8400-e29b-41d4-a716-446655440000",
  "aggregate_type": "chat_message",
  "aggregate_id": "123e4567-e89b-12d3-a456-426614174000",
  "payload": {
    "message_id": "123e4567-e89b-12d3-a456-426614174000",
    "role": "user",
    "content": "Привет, мир!",
    "...": "... доменные поля ..."
  }
}
```

### Семантика Event ID

- **Стабильность**: `event_id` всегда равен `event_outbox.id` (primary key)
- **Уникальность**: Каждое событие имеет уникальный UUID
- **Стабильность при retry**: Если событие потерпело неудачу и переотправляется, оно имеет тот же `event_id`
- **Стабильность при replay**: Если то же событие опубликовано несколько раз из-за краша издателя или сбоев сети, оно имеет тот же `event_id`

## Задача 6.2: Контракт потребителя для дедупликации

### Дедупликация на клиенте

Потребители получающие события из streaming API должны реализовать дедупликацию по `event_id`:

```python
# Пример: дедупликация событий в коде потребителя
class EventConsumer:
    def __init__(self):
        self.processed_event_ids = set()  # Или хранилище
    
    async def handle_event(self, event: Dict[str, Any]):
        event_id = event["event_id"]
        
        # Проверка: уже обработано ли?
        if event_id in self.processed_event_ids:
            logger.info(f"Пропуск дубликата события: {event_id}")
            return
        
        # Обработка события
        await self.process_message_created(event)
        
        # Отметить как обработано
        self.processed_event_ids.add(event_id)
```

### Стойкая дедупликация

Для production систем сохраняйте processed event IDs в БД:

```python
# Сохранение event_id в таблицу processed_events
async def handle_event(self, event: Dict[str, Any]):
    event_id = UUID(event["event_id"])
    
    # Проверка: уже обработано?
    if await db.exists(ProcessedEvents, event_id=event_id):
        return  # Уже обработано
    
    # Обработка события
    await self.process_message_created(event)
    
    # Запись что мы это обработали
    await db.add(ProcessedEvents(event_id=event_id, processed_at=datetime.utcnow()))
    await db.commit()
```

### Почему дедупликация на клиенте?

1. **Издатель может упасть и переотправить**: OutboxPublisher может упасть после публикации в streaming но до обновления статуса на "published"
2. **Network retries**: TCP/streaming соединения могут переотправлять события
3. **Выгода потребителю**: Потребители могут безопасно реализовать идемпотентные обработчики

## Задача 6.3: Путь переобработки для failed событий

### Обработка неудачных событий

События которые не получилось опубликовать помечаются `status = 'failed'` в `event_outbox`:

```sql
SELECT * FROM event_outbox 
WHERE status = 'failed' 
ORDER BY created_at DESC;
```

### Endpoint переобработки

Административный endpoint для переобработки неудачных событий:

```
POST /my/projects/{project_id}/analytics/events/{event_id}/reprocess
```

Параметры:
- `project_id` (path): Проект содержащий событие
- `event_id` (path): Событие для переобработки

Ответ:
```json
{
  "event_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "retry_count": 0,
  "next_retry_at": "2026-02-28T07:10:00Z",
  "message": "Событие запланировано для переобработки"
}
```

### Детали реализации

1. Загрузить failed событие из `event_outbox`
2. Сбросить статус на `pending`
3. Сбросить `retry_count` на 0
4. Установить `next_retry_at` на immediate
5. OutboxPublisher подберет его на следующей итерации

## Задача 6.4: Тесты duplicate-safe retries

### Сценарии тестирования

1. **Дубликат доставки без дедупликации**:
   - Издатель публикует событие
   - Streaming соединение падает перед ACK
   - Издатель повторно отправляет (тот же event_id)
   - Без дедупликации: дубликат обработки (ПЛОХО)
   - С дедупликацией: идемпотентная обработка (ХОРОШО)

2. **Recovery после краша**:
   - Издатель падает после публикации
   - Обновление статуса неполное
   - При перезагрузке: событие еще в pending
   - Переопубликовано с тем же event_id
   - Дедупликация предотвращает дублирование эффектов

3. **Idempotency потребителя**:
   - Потребитель обрабатывает event_id = X
   - Сохраняет результат в БД
   - Тот же event_id X приходит снова
   - Потребитель проверяет: уже обработано
   - Безопасно пропускает переобработку

## Гарантии надежности

### At-Least-Once доставка

Свойство: Каждое событие будет доставлено по крайней мере один раз

Реализация:
1. Событие persisted в `event_outbox` перед попыткой издателя
2. При отказе доставки: логика retry reschedules
3. Максимум `max_retries` попыток с exponential backoff
4. Даже если все retry истощены: событие остается в `failed` статусе (никогда не потеряно)

### Exactly-Once обработка

Свойство: Потребитель может безопасно обработать каждое событие ровно один раз

Реализация:
1. `event_id` стабилен через retries
2. Потребитель дедупликирует по `event_id`
3. В сочетании с идемпотентными операциями потребителя
4. Результат: exactly-once эффект несмотря на множественные доставки

### Восстановление после сбоя

Свойство: Система выживает после сбоев без потери событий

Сценарии:
1. **Краш издателя**: Событие остается в `event_outbox`, будет retry при перезагрузке
2. **Drop streaming соединения**: Событие остается в `event_outbox`, будет retry
3. **Partial publish**: Потребитель видит дубликат, дедупликирует через `event_id`
4. **Failure потребителя**: Событие остается в event stream, потребитель может replay

## Конфигурация

### Retry конфигурация

В `app/config.py`:

```python
# Outbox Publisher settings
outbox_max_retries: int = 5
outbox_initial_retry_delay: int = 5  # секунды
outbox_max_retry_delay: int = 300    # секунды (5 минут)
outbox_poll_interval: int = 5        # секунды
```

### Формула backoff

```
delay = min(initial_delay * 2^retry_count, max_delay)

Попытка 1: 5s
Попытка 2: 10s
Попытка 3: 20s
Попытка 4: 40s
Попытка 5: 80s (превышает max, ограничено на 300s)
```

## Мониторинг

### Ключевые метрики

- `outbox.pending_count`: События ожидающие публикации
- `outbox.failed_count`: События превысившие max retries
- `outbox.published_total`: Cumulative события опубликованные
- `outbox.publish_latency_ms`: Время от commit до published

### Alerts

Установите alerts для:
- `pending_count > threshold` (backlog растет)
- `oldest_pending_age > 5m` (событие stuck в очереди)
- `failed_count > 0` (investigate failures)
- `publish_latency_ms > 5000` (медленная публикация)

## Итого

**Задача 6.1**: ✅ `event_id = event_outbox.id` во всех published payloads
**Задача 6.2**: ✅ Дедупликация потребителя через `event_id`
**Задача 6.3**: ✅ Endpoint переобработки для failed событий
**Задача 6.4**: ✅ Тесты проверяют duplicate-safe retries

Результат: Exactly-once event processing семантика с retry resilience.
