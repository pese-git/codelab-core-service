# llm-call-tracing Specification

## Назначение

Автоматическое захватывание LLM вызовов через `langfuse.openai.AsyncOpenAI` wrapper с отправкой полной информации в Langfuse v4 SDK. LiteLLM callbacks не реализованы (планируется на будущее).

## Requirements

### Requirement: Автоматическое логирование LLM вызовов через langfuse.openai.AsyncOpenAI

LLM вызовы ДОЛЖНЫ автоматически захватываться через Langfuse OpenAI wrapper без дополнительной конфигурации.

#### Scenario: Успешное логирование LLM вызова
- **WHEN** [`ContextualAgent.execute()`](app/agents/contextual_agent.py:147-148) вызывает [`self.openai_client.chat.completions.create()`](app/agents/contextual_agent.py:136)
- **THEN** Langfuse wrapper автоматически захватывает: {model, prompt_tokens, completion_tokens, latency, cost}
- **AND** данные отправляются в Langfuse SDK без явного вмешательства

#### Scenario: Логирование с инструментами
- **WHEN** LLM запрос выполняется с инструментами (tools parameter)
- **THEN** Langfuse захватывает: tool_calls, tool_names, tool_execution_results
- **AND** вложенные spans создаются для каждого вызова инструмента

#### Scenario: Логирование ошибок LLM
- **WHEN** LLM запрос завершается с ошибкой (timeout, API error, invalid key)
- **THEN** ошибка логируется как child span с метаданными ошибки
- **AND** обработка ошибок происходит gracefully без прерывания workflow

#### Scenario: Сессионный контекст в трейсах
- **WHEN** LLM вызов выполняется через [`@observe(name="Executor")`](app/agents/contextual_agent.py:147-148) decorated функцию
- **THEN** LLM span будет nested под root trace с правильным session_id
- **AND** metadata включает: user_id, project_id, agent_name, model_name

### Requirement: Интеграция langfuse.openai.AsyncOpenAI в ContextualAgent

ContextualAgent ДОЛЖЕН использовать Langfuse OpenAI wrapper для автоматического трейсинга.

#### Scenario: Инициализация OpenAI client
- **WHEN** [`ContextualAgent.__init__()`](app/agents/contextual_agent.py:31-80) вызывается
- **THEN** создается [`openai.AsyncOpenAI`](app/agents/contextual_agent.py:71) с параметрами:
  - `api_key`: litellm_master_key (для LiteLLM REST API)
  - `base_url`: litellm_url (для маршрутизации на LiteLLM)
- **AND** клиент автоматически оборачивается Langfuse (через пакет langfuse[openai])
- **AND** никакой дополнительной конфигурации не требуется

#### Scenario: LLM вызов с контекстом
- **WHEN** [`_call_llm_with_trace()`](app/agents/contextual_agent.py:101-136) выполняет `chat.completions.create()`
- **THEN** Langfuse автоматически захватывает полный контекст запроса
- **AND** parent span наследуется из `@observe(name="Executor")` decorator

#### Scenario: Сохранение контекста в истории
- **WHEN** LLM запрос завершается успешно
- **THEN** результат сохраняется в [`AgentContextStore`](app/agents/contextual_agent.py:74-80)
- **AND** trace обновляется с результатом через metadata

### Requirement: Метаданные в LLM traces

LLM traces ДОЛЖНЫ содержать полный контекст для отладки и аналитики.

#### Scenario: Базовые метаданные
- **WHEN** LLM span создается через Langfuse wrapper
- **THEN** span содержит:
  - `model`: имя используемого модели (e.g. "gpt-4-turbo-preview")
  - `provider`: "openai" (через LiteLLM)
  - `input`: сообщения и параметры запроса
  - `output`: ответ или ошибка
  - `usage`: токены (prompt_tokens, completion_tokens)
  - `duration`: время выполнения

#### Scenario: Кастомные метаданные
- **WHEN** LLM вызов выполняется в контексте агента с [`@observe`](app/agents/contextual_agent.py:147-148)
- **THEN** метаданные дополняются:
  - `agent_name`: имя текущего агента
  - `agent_id`: ID агента
  - `session_id`: ID чат-сессии (для группировки)
  - `task_id`: опциональный ID задачи
  - `user_id`: ID пользователя (из parent trace)

#### Scenario: Tool-связанные метаданные
- **WHEN** LLM вызов содержит tool_calls
- **THEN** metadata включает:
  - `tools_available`: список имен доступных инструментов
  - `tool_calls`: информация о вызванных инструментах
  - `tool_results_count`: количество результатов инструментов

## Текущая реализация

### LLM Tracing через OpenAI wrapper

Файл: [`app/agents/contextual_agent.py`](app/agents/contextual_agent.py)

**Инициализация:**
```python
from langfuse.openai import openai

client_kwargs = {
    "api_key": settings.litellm_master_key,
    "base_url": settings.litellm_url,
}
self.openai_client = openai.AsyncOpenAI(**client_kwargs)
```

**LLM вызов:**
```python
@observe(name="Executor")
async def execute(self, user_message: str, ...):
    response = await self.openai_client.chat.completions.create(
        model=model_name,
        messages=messages,
        temperature=self.config.temperature,
        max_tokens=self.config.max_tokens,
        tools=tools,  # optional
    )
```

**Автоматический захват:**
- Langfuse wrapper автоматически перехватывает все `chat.completions.create()` вызовы
- Запрос и ответ логируются как child span под `@observe(name="Executor")`
- Метаданные и использованные токены захватываются без явного кода

### Поток трейсинга

1. **Инициализация trace** - [`send_project_message`](app/routes/project_chat.py:195) с `@observe(name="ChatMessage")`
2. **Обновление метаданных** - [`update_trace_metadata(user_id, project_id)`](app/routes/project_chat.py:219-222)
3. **Запуск агента** - [`ContextualAgent.execute()`](app/agents/contextual_agent.py:147-148) с `@observe(name="Executor")`
4. **LLM вызов** - [`openai_client.chat.completions.create()`](app/agents/contextual_agent.py:273-279)
5. **Автоматический захват** - Langfuse wrapper создает LLM span
6. **Tool execution** - если инструменты вызваны, они логируются как child spans
7. **Flush** - traces асинхронно отправляются в Langfuse

## Ограничения текущей реализации

1. **Нет LiteLLM callbacks** - используется OpenAI wrapper вместо этого (более прямой и надежный)
2. **Нет явной конфигурации callbacks** - все управляется через Langfuse SDK автоматически
3. **Нет batch callbacks** - каждый вызов логируется отдельно, но batched на уровне SDK flush
4. **Нет контекстных переменных** - metadata добавляются через @observe decorator, не через structlog context

## Roadmap

### Phase 1: LiteLLM callbacks (будущее)
- Интеграция LiteLLM success/failure callbacks
- Дополнительный контекст из LiteLLM (retry count, fallback info)
- Параллельный трейсинг через OpenAI wrapper и LiteLLM callbacks
- Приоритет: низкий (текущая реализация через OpenAI wrapper достаточна)

### Phase 2: Структурированные метаданные
- Автоматический захват параметров модели (temperature, top_p, frequency_penalty)
- Логирование стоимости запроса (cost per token)
- Трейсинг версии модели и deployment environment
- Приоритет: средний

### Phase 3: Advanced context propagation
- Propagation через микросервисы
- Корреляция LLM вызовов с tool execution
- Tracking цепочек агентов
- Приоритет: средний

## Архитектура

```mermaid
graph TB
    subgraph "Application"
        ChatEndpoint["Chat Endpoint<br/>@observe(ChatMessage)"]
        Agent["Agent.execute()<br/>@observe(Executor)"]
    end
    
    subgraph "LLM Integration"
        OpenAIWrapper["langfuse.openai.AsyncOpenAI<br/>(автоматический захват)"]
        LiteLLMProxy["LiteLLM REST API<br/>(через base_url)"]
    end
    
    subgraph "LLM Provider"
        OpenAIAPI["OpenAI API<br/>(или другой через LiteLLM)"]
    end
    
    subgraph "Langfuse"
        LFSDKClient["Langfuse SDK<br/>(v4)"]
        LFAPI["Langfuse API"]
        LFUI["Web UI"]
    end
    
    ChatEndpoint -->|trace| LFSDKClient
    Agent -->|@observe| LFSDKClient
    OpenAIWrapper -->|monitor| LFSDKClient
    
    Agent -->|call| OpenAIWrapper
    OpenAIWrapper -->|proxy| LiteLLMProxy
    LiteLLMProxy -->|call| OpenAIAPI
    
    LFSDKClient -->|HTTP batch| LFAPI
    LFUI -->|query| LFAPI
```

## Нефункциональные требования

### Performance
- Overhead на LLM запрос: < 50ms (асинхронный wrapper, non-blocking)
- Latency захвата: < 10ms (в процессе OpenAI call)
- Async flush every 30 sec: не блокирует приложение

### Reliability
- Auto-retry при сетевых ошибках (встроено в SDK)
- Graceful degradation если Langfuse down
- Fail-open: если SDK error, LLM вызов продолжает работу

### Security
- API ключи передаются через TLS
- Никакие ключи не логируются в metadata
- User_id используется для row-level security в Langfuse

### Scalability
- Поддержка 10+ LLM вызовов в секунду
- In-memory batching в SDK
- Connection pooling для HTTPS

---

**Version**: 2.0 (Actualizado)  
**Status**: Implemented (langfuse.openai.AsyncOpenAI wrapper)  
**Last Updated**: 2026-03-16  
**Previous**: v1.0 (использовала LiteLLM callbacks - удалено)
