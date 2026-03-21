"""Streaming Event schemas."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class StreamEventType(str, Enum):
    """Типы потоковых событий системы.
    
    События категоризируются по типам:
    - Доменные события: сохраняются через Outbox паттерн (message_created, agent_switched)
    - Технические события: прямая потоковая передача или опциональный outbox (task_started, tool_execution)
    - События одобрения: синхронные сигналы (tool_approval_request, tool_execution_signal)
    - Системные события: heartbeat, обработка ошибок
    """

    # ==================== СООБЩЕНИЯ И КОММУНИКАЦИЯ ====================
    MESSAGE_CREATED = "message_created"
    """Отправляется при создании нового сообщения (от пользователя или ассистента).
    
    Payload:
        - message_id: UUID сообщения
        - role: "user" или "assistant"
        - content: текст сообщения
        - session_id: UUID чат-сессии
    
    Доставка: Outbox паттерн (асинхронная)
    """

    # ==================== ЖИЗНЕННЫЙ ЦИКЛ АГЕНТА ====================
    AGENT_SWITCHED = "agent_switched"
    """Отправляется при переключении активного агента оркестратором.
    
    Payload:
        - agent_id: UUID нового активного агента
        - agent_name: имя агента
        - reason: причина переключения (например, "specialized_for_task")
        - session_id: UUID чат-сессии
    
    Доставка: Outbox паттерн (асинхронная)
    """

    DIRECT_AGENT_CALL = "direct_agent_call"
    """Отправляется при прямом вызове агента (режим direct, не через оркестратор).
    
    Payload:
        - agent_id: UUID агента
        - task_id: UUID задачи
        - timestamp: когда был сделан вызов
    
    Доставка: Прямая потоковая передача (синхронная)
    """

    AGENT_STATUS_CHANGED = "agent_status_changed"
    """Отправляется при изменении статуса агента (ready ↔ busy ↔ error).
    
    Payload:
        - agent_id: UUID агента
        - old_status: предыдущий статус
        - new_status: текущий статус (ready|busy|error|idle)
        - timestamp: когда произошло изменение
    
    Доставка: Прямая потоковая передача (синхронная)
    """

    # ==================== УПРАВЛЕНИЕ ЗАДАЧАМИ ====================
    TASK_PLAN_CREATED = "task_plan_created"
    """Отправляется при создании оркестратором плана выполнения задач.
    
    Payload:
        - plan_id: UUID плана
        - tasks: список определений задач
        - estimated_cost: ожидаемая стоимость API запросов
        - estimated_duration: ожидаемое время выполнения в секундах
    
    Доставка: Прямая потоковая передача (синхронная)
    """

    TASK_STARTED = "task_started"
    """Отправляется при начале выполнения задачи.
    
    Payload:
        - task_id: UUID задачи
        - agent_id: UUID агента, выполняющего задачу
        - description: описание задачи
        - timestamp: когда началось выполнение
    
    Доставка: Прямая потоковая передача (синхронная)
    """

    TASK_PROGRESS = "task_progress"
    """Отправляется для отчёта о промежуточном прогрессе выполнения задачи.
    
    Payload:
        - task_id: UUID задачи
        - progress_percent: процент завершения (0-100)
        - message: понятное пользователю сообщение о прогрессе
        - details: опциональная дополнительная информация
    
    Доставка: Прямая потоковая передача (синхронная)
    """

    TASK_COMPLETED = "task_completed"
    """Отправляется при завершении выполнения задачи.
    
    Payload:
        - task_id: UUID задачи
        - result: результат выполнения или резюме
        - duration: время выполнения в секундах
        - status: "completed", "failed" или "cancelled"
        - timestamp: когда завершилась задача
    
    Доставка: Прямая потоковая передача (синхронная)
    """

    # ==================== ВЫПОЛНЕНИЕ ИНСТРУМЕНТОВ (Устаревшее) ====================
    TOOL_REQUEST = "tool_request"
    """УСТАРЕВШИЙ: Старый тип события для уведомления о запросе инструмента.
    
    Используйте вместо этого TOOL_EXECUTION_REQUEST, TOOL_APPROVAL_REQUEST.
    """

    # ==================== WORKFLOW ВЫПОЛНЕНИЯ ИНСТРУМЕНТОВ ====================
    TOOL_EXECUTION_REQUEST = "tool_execution_request"
    """Отправляется после валидации инструмента и оценки риска, перед одобрением.
    
    Это событие указывает, что инструмент готов к принятию решения об одобрении:
    - Параметры прошли валидацию
    - Уровень риска был оценён
    - Ожидается одобрение (явное для MEDIUM/HIGH риска, или автоматическое для LOW)
    
    Payload:
        - tool_id: UUID выполнения инструмента
        - tool_name: имя инструмента (read_file, write_file, execute_command и т.д.)
        - tool_params: параметры для инструмента
        - session_id: UUID чат-сессии
        - timestamp: когда был создан запрос
    
    Следующие события:
    - Если LOW риск: переход к TOOL_EXECUTION_SIGNAL
    - Если MEDIUM/HIGH риск: переход к TOOL_APPROVAL_REQUEST (пользователь решает)
    
    Доставка: Outbox паттерн (асинхронная)
    """

    TOOL_APPROVAL_REQUEST = "tool.approval_request"
    """Отправляется только когда MEDIUM/HIGH риск инструмента требует явного одобрения пользователя.
    
    Это событие должно вызвать диалог одобрения на клиенте.
    Клиент должен ответить либо одобрением, либо отклонением.
    
    Payload:
        - approval_id: UUID запроса одобрения
        - tool_id: UUID выполнения инструмента
        - tool_name: имя инструмента
        - risk_level: "LOW", "MEDIUM" или "HIGH"
        - timeout_seconds: секунды для ожидания решения пользователя (по умолчанию: 300)
        - description: понятное описание того, что будет делать инструмент
        - payload: дополнительный контекст одобрения
    
    Ответ клиента: POST /approvals/{approval_id}/confirm или /reject
    
    Следующее событие: TOOL_EXECUTION_SIGNAL (если одобрено)
    
    Доставка: Прямая потоковая передача (синхронная)
    """

    TOOL_EXECUTION_SIGNAL = "tool.execution_signal"
    """Отправляется после одобрения (явное или автоматическое) для команды клиенту выполнить инструмент.
    
    Это событие говорит клиенту, что все проверки пройдены и инструмент
    одобрен для выполнения. Клиент должен выполнить инструмент локально
    и вернуть результат через REST API.
    
    Payload:
        - tool_id: UUID выполнения инструмента
        - tool_name: имя инструмента
        - tool_params: параметры для выполнения инструмента
        - timestamp: когда был отправлен сигнал
    
    Действие клиента: Выполнить инструмент локально и POST результат на /tools/{tool_id}/result
    
    Доставка: Прямая потоковая передача (синхронная)
    """

    TOOL_RESULT = "tool_result"
    """Отправляется при получении результата выполнения инструмента от клиента.
    
    Payload:
        - tool_id: UUID выполнения инструмента
        - status: "completed" или "failed"
        - result: результат выполнения (stdout, содержимое файла, список каталога и т.д.)
        - error: сообщение об ошибке если не удалось
        - execution_time: время выполнения
    
    Доставка: Outbox паттерн (асинхронная)
    """

    TOOL_RESULT_ACK = "tool.result_ack"
    """Опциональное подтверждение, отправляемое клиенту после получения сервером результата инструмента.
    
    Подтверждает, что сервер получил и обработал результат инструмента.
    
    Payload:
        - tool_id: UUID выполнения инструмента
        - status: "received" или "error"
        - timestamp: когда был получен результат
    
    Доставка: Прямая потоковая передача (синхронная)
    """

    TOOL_ERROR = "tool_error"
    """Отправляется при возникновении ошибки во время выполнения инструмента.
    
    Payload:
        - tool_id: UUID выполнения инструмента
        - tool_name: имя инструмента
        - error_type: "validation_error", "execution_error", "timeout" и т.д.
        - error_message: понятное описание ошибки
        - timestamp: когда произошла ошибка
    
    Доставка: Прямая потоковая передача (синхронная)
    """

    # ==================== ОДОБРЕНИЕ ПЛАНА ====================
    PLAN_REQUEST = "plan_request"
    """Отправляется при создании оркестратором плана, требующего одобрения пользователя.
    
    Payload:
        - approval_id: UUID запроса одобрения
        - plan: детали плана задач
        - estimated_cost: ожидаемая стоимость API в USD
        - estimated_duration: ожидаемое время выполнения в секундах
    
    Ответ клиента: Одобрить или отклонить через /approvals/{approval_id}/confirm|reject
    
    Доставка: Прямая потоковая передача (синхронная)
    """

    # ==================== КОНТЕКСТ И ИЗВЛЕЧЕНИЕ ====================
    CONTEXT_RETRIEVED = "context_retrieved"
    """Отправляется при извлечении контекста RAG из векторной базы данных (Qdrant).
    
    Это внутреннее техническое событие для отслеживания операций RAG.
    Обычно не видно пользователю.
    
    Payload:
        - agent_id: UUID агента
        - context_items_count: количество извлечённых элементов контекста
        - relevance_scores: список оценок релевантности для каждого элемента
        - retrieval_time: время на извлечение
    
    Доставка: Прямая потоковая передача (синхронная)
    """

    # ==================== WORKFLOW ОДОБРЕНИЯ ====================
    APPROVAL_REQUIRED = "approval_required"
    """Родовое событие, указывающее, что требуется одобрение пользователя.
    
    Payload:
        - approval_id: UUID запроса одобрения
        - approval_type: тип требуемого одобрения
        - timeout_seconds: секунды для ожидания решения
        - details: контекст одобрения
    
    Доставка: Outbox паттерн (асинхронная)
    """

    APPROVAL_RESOLVED = "approval_resolved"
    """Отправляется при ответе пользователя на запрос одобрения.
    
    Payload:
        - approval_id: UUID одобрения
        - status: "approved" или "rejected"
        - decision: опциональное объяснение от пользователя
        - timestamp: когда было принято решение
    
    Доставка: Прямая потоковая передача (синхронная)
    """

    APPROVAL_TIMEOUT = "approval_timeout"
    """Отправляется при превышении таймаута ожидания одобрения.
    
    Payload:
        - approval_id: UUID одобрения
        - timeout_seconds: превышенный таймаут
        - timestamp: когда произошёл таймаут
    
    Доставка: Прямая потоковая передача (синхронная)
    """

    APPROVAL_TIMEOUT_WARNING = "approval_timeout_warning"
    """Отправляется как предупреждение перед таймаутом одобрения (обычно за 30 сек до таймаута).
    
    Даёт пользователю шанс ответить перед тем, как одобрение будет автоматически отклонено.
    
    Payload:
        - approval_id: UUID одобрения
        - timeout_seconds: секунды, оставшиеся до таймаута
        - timestamp: когда было отправлено предупреждение
    
    Доставка: Прямая потоковая передача (синхронная)
    """

    # ==================== СИСТЕМНЫЕ СОБЫТИЯ ====================
    HEARTBEAT = "heartbeat"
    """Сигнал поддержки связи (keep-alive), отправляемый периодически для сохранения подключения SSE.
    
    Предотвращает закрытие соединения из-за неактивности.
    Отправляется каждые 30 секунд по умолчанию.
    
    Payload:
        - timestamp: время сервера
    
    Доставка: Прямая потоковая передача (синхронная)
    """

    ERROR = "error"
    """Родовое событие об ошибке для системных ошибок, не подходящих под другие категории.
    
    Payload:
        - error_type: тип ошибки
        - error_message: описание ошибки
        - timestamp: когда произошла ошибка
    
    Доставка: Прямая потоковая передача (синхронная)
    """


class StreamEvent(BaseModel):
    """Stream event schema for JSON Lines (NDJSON) format."""

    event_type: StreamEventType = Field(..., description="Event type")
    payload: dict[str, Any] = Field(..., description="Event payload")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Event timestamp"
    )
    session_id: UUID | None = Field(default=None, description="Session UUID (if applicable)")

    model_config = {"json_schema_extra": {
        "example": {
            "event_type": "task_started",
            "payload": {
                "task_id": "task_1",
                "agent_name": "coder",
                "description": "Fix bug in auth.py"
            },
            "timestamp": "2026-02-11T07:00:00Z",
            "session_id": "550e8400-e29b-41d4-a716-446655440000"
        }
    }}

    def to_ndjson(self) -> str:
        """
        Convert to NDJSON (Newline Delimited JSON) format.
        
        Returns:
            JSON string with newline terminator
        """
        return self.model_dump_json() + "\n"

    def to_sse_format(self) -> str:
        """
        Convert to SSE (Server-Sent Events) format.
        
        Returns SSE format with event type and JSON data.
        Format: event: <event_type>\ndata: <json>\n\n
        
        Returns:
            String in SSE format
        """
        event_type = self.event_type.value if hasattr(self.event_type, 'value') else str(self.event_type)
        json_data = self.model_dump_json()
        return f"event: {event_type}\ndata: {json_data}\n\n"


# Backward compatibility aliases
SSEEventType = StreamEventType
SSEEvent = StreamEvent
