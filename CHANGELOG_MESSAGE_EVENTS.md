# Changelog: Message Events Fix

## Дата: 2026-02-16

## Проблема
Клиент не получал сообщения от ассистента через streaming API. Сообщения сохранялись в базе данных, но не передавались клиенту в реальном времени.

## Решение
Добавлен новый тип события `MESSAGE_CREATED`, который отправляется при создании любого сообщения (от пользователя или ассистента).

## Изменения

### 1. Новый тип события
- **Файл**: [`app/schemas/event.py`](app/schemas/event.py)
- **Изменение**: Добавлен `MESSAGE_CREATED = "message_created"` в `StreamEventType`

### 2. Отправка событий для сообщений
- **Файл**: [`app/routes/chat.py`](app/routes/chat.py)
- **Изменения**:
  - Строка 190: Отправка события при создании сообщения пользователя
  - Строка 344: Отправка события при создании сообщения ассистента
  - Строка 407: Отправка события для placeholder ответа в режиме оркестратора

### 3. Обновление документации
- **Файл**: [`app/routes/streaming.py`](app/routes/streaming.py)
- **Изменение**: Добавлено описание события `message_created` в документацию API

### 4. Тестовый скрипт
- **Файл**: [`scripts/test_message_events.py`](scripts/test_message_events.py)
- **Назначение**: Автоматическая проверка отправки событий MESSAGE_CREATED

### 5. Документация
- **Файл**: [`doc/bugfix-message-events.md`](doc/bugfix-message-events.md)
- **Содержание**: Подробное описание проблемы, решения и примеры использования

## Структура события

### Сообщение пользователя:
```json
{
  "event_type": "message_created",
  "payload": {
    "message_id": "uuid",
    "role": "user",
    "content": "текст",
    "timestamp": "ISO-8601"
  },
  "session_id": "uuid",
  "timestamp": "ISO-8601"
}
```

### Сообщение ассистента:
```json
{
  "event_type": "message_created",
  "payload": {
    "message_id": "uuid",
    "role": "assistant",
    "content": "текст",
    "agent_id": "uuid",
    "agent_name": "имя",
    "timestamp": "ISO-8601"
  },
  "session_id": "uuid",
  "timestamp": "ISO-8601"
}
```

## Обратная совместимость
✅ Полностью обратно совместимо
- Добавлен новый тип события, существующие не изменены
- API endpoints не изменены
- Структура БД не изменена

## Тестирование
```bash
# Запустить сервер
make dev

# Запустить тест
python scripts/test_message_events.py
```

## Действия для клиента
Клиент должен подписаться на событие `message_created` и добавлять полученные сообщения в UI.

Пример обработки см. в [`doc/bugfix-message-events.md`](doc/bugfix-message-events.md#рекомендации-для-клиента)
