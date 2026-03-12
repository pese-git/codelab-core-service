# agent-llm-provider-binding Specification (Delta)

## MODIFIED Requirements

### Requirement: Интеграция провайдера с LiteLLM для Langfuse callbacks

Существующая привязка провайдера должна гарантировать что LiteLLM использует правильные callbacks для отправки данных в Langfuse.

#### Scenario: LiteLLM callbacks включены для всех LLM вызовов
- **WHEN** агент использует litellm_model_name провайдера для выполнения LLM запроса
- **THEN** LiteLLM автоматически запускает success/failure callbacks
- **AND** callbacks отправляют в Langfuse: {model, prompt_tokens, completion_tokens, latency, cost, user_id, workspace_id}
- **AND** метаданные содержат: provider_id, provider_type, agent_name

#### Scenario: Metadata о провайдере включается в Langfuse trace
- **WHEN** LiteLLM callback срабатывает для LLM запроса
- **THEN** callback содержит в metadata: {provider_id, provider_type, provider_display_name, litellm_model_name}
- **AND** эта информация доступна в Langfuse trace для аналитики

#### Scenario: Ошибки провайдера отслеживаются в Langfuse
- **WHEN** LLM запрос завершается с ошибкой из-за проблемы с провайдером
- **THEN** LiteLLM отправляет failure callback в Langfuse с: {error_type, error_message, provider_id, attempted_model}
- **AND** ошибка логируется в llm_provider_audit_log и в Langfuse

#### Scenario: Usage статистика обновляется после успешного Langfuse callback
- **WHEN** LLM запрос успешно выполняется и callback успешно отправлен в Langfuse
- **THEN** система обновляет provider.usage_count и provider.last_used_at как обычно
- **AND** дополнительно логирует успешность callback отправки в audit log
