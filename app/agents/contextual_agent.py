"""Contextual agent with RAG integration and tool support."""

import asyncio
import json
import time
from typing import Any, TYPE_CHECKING
from uuid import UUID

import openai
from opentelemetry import trace
from qdrant_client import AsyncQdrantClient
from sqlalchemy import select

from app.config import settings
from app.core.tools.definitions import AVAILABLE_TOOLS, ToolName
from app.logging_config import get_logger
from app.models.tool_execution import ToolExecution
from app.schemas.agent import AgentConfig
from app.services.langfuse_decorators import trace_llm_call
from app.services.langfuse_integration import get_langfuse
from app.tracing import get_tracer
from app.vectorstore.agent_context_store import AgentContextStore

if TYPE_CHECKING:
    from app.core.tools.executor import ToolExecutor

logger = get_logger(__name__)
tracer = get_tracer(__name__)


class ContextualAgent:
    """Agent with context retrieval capabilities and tool support."""

    def __init__(
        self,
        agent_id: UUID,
        user_id: UUID,
        agent_name: str,
        config: AgentConfig,
        qdrant_client: AsyncQdrantClient | None,
        tool_executor: 'ToolExecutor | None' = None,
        llm_provider: Any = None,
        embedding_llm_provider: Any = None,
    ):
        """Initialize contextual agent.
        
        Args:
            agent_id: Agent ID
            user_id: User ID
            agent_name: Agent name
            config: Agent configuration
            qdrant_client: Qdrant client instance, or None if Qdrant is disabled
            tool_executor: ToolExecutor instance for tool execution, or None if tools disabled
            llm_provider: UserLLMProvider instance for chat, or None to use default config
            embedding_llm_provider: UserLLMProvider instance for embeddings, or None to use default
        """
        self.agent_id = agent_id
        self.user_id = user_id
        self.agent_name = agent_name
        self.config = config
        self.tool_executor = tool_executor
        self.llm_provider = llm_provider
        self.embedding_llm_provider = embedding_llm_provider
        
        # Initialize OpenAI client (supports LiteLLM via base_url)
        # When calling LiteLLM REST API, always use litellm_master_key for authentication
        # The user's API keys are already registered in LiteLLM under litellm_model_name
        # base_url must always come from settings.litellm_url
        client_kwargs = {
            "api_key": settings.litellm_master_key,
            "base_url": settings.litellm_url,
        }
        
        self.openai_client = openai.AsyncOpenAI(**client_kwargs)
        
        # Initialize context store
        self.context_store = AgentContextStore(
            client=qdrant_client,
            user_id=user_id,
            agent_name=agent_name,
            llm_provider=llm_provider,
            embedding_llm_provider=embedding_llm_provider,
        )
        
        # Initialize Langfuse integration for LLM observability
        self.langfuse = get_langfuse()
    
    def _get_provider_name(self) -> str:
        """Get provider name for logging purposes.
        
        Uses display_name or provider_type to avoid accessing config which
        can trigger DetachedInstanceError if provider is detached from session.
        """
        if self.llm_provider:
            try:
                # Try display_name first, fallback to provider_type
                display_name = getattr(self.llm_provider, 'display_name', None)
                if display_name:
                    return display_name
                provider_type = getattr(self.llm_provider, 'provider_type', None)
                if provider_type:
                    return provider_type
            except Exception:
                pass
        return 'default'

    @trace_llm_call(name="agent_llm_generation")
    async def _call_llm_with_trace(
        self,
        model: str,
        messages: list,
        temperature: float | None = None,
        max_tokens: int | None = None,
        tools: list | None = None,
        langfuse_trace: Any | None = None,
    ) -> Any:
        """Call LLM with automatic Langfuse tracing.
        
        This method uses @trace_llm_call decorator to automatically capture
        LLM metrics (tokens, latency, errors) in Langfuse.
        
        Args:
            model: Model name
            messages: Chat messages
            temperature: Temperature parameter
            max_tokens: Max tokens
            tools: Optional tools
            langfuse_trace: Optional Langfuse trace for span creation
            
        Returns:
            OpenAI API response
        """
        llm_kwargs = {
            "model": model,
            "messages": messages,
        }
        
        if temperature is not None:
            llm_kwargs["temperature"] = temperature
        
        if max_tokens is not None:
            llm_kwargs["max_tokens"] = max_tokens
        
        if tools:
            llm_kwargs["tools"] = tools
            llm_kwargs["tool_choice"] = "auto"
        
        # Call OpenAI API - decorator will handle Langfuse tracing
        return await self.openai_client.chat.completions.create(**llm_kwargs)

    async def initialize(self) -> None:
        """Initialize agent (create Qdrant collection)."""
        await self.context_store.initialize()
        logger.info(
            "agent_initialized",
            agent_id=str(self.agent_id),
            agent_name=self.agent_name,
        )

    async def execute(
        self,
        user_message: str,
        session_history: list[dict[str, str]] | None = None,
        task_id: str | None = None,
        session_id: UUID | None = None,
        langfuse_trace: Any | None = None,
    ) -> dict[str, Any]:
        """Execute agent with context retrieval and optional tool support.
        
        Args:
            user_message: User's message
            session_history: Chat session history
            task_id: Optional task ID
            session_id: Optional chat session ID for tool execution
            
        Returns:
            Dictionary with execution result
        """
        with tracer.start_as_current_span("agent_execution") as span:
            span.set_attribute("agent.id", str(self.agent_id))
            span.set_attribute("agent.name", self.agent_name)
            # Safely access provider attributes to avoid DetachedInstanceError
            try:
                model_name = self.llm_provider.litellm_model_name if self.llm_provider else "unknown"
            except Exception:
                model_name = "unknown"
            span.set_attribute("model", model_name)
            if session_id:
                span.set_attribute("session.id", str(session_id))
            if task_id:
                span.set_attribute("task.id", task_id)

            # Link Langfuse trace with current OpenTelemetry trace
            if langfuse_trace and self.langfuse.enabled:
                try:
                    otel_ctx = span.get_span_context()
                    otel_trace_id = (
                        format(otel_ctx.trace_id, "032x") if otel_ctx and otel_ctx.trace_id else None
                    )
                    if otel_trace_id:
                        self.langfuse.create_event(
                            trace_id=langfuse_trace.id,
                            name="otel_trace_link",
                            metadata={"otel_trace_id": otel_trace_id},
                        )
                except Exception:
                    pass
            
            try:
                # Debug: Log executor status
                # Safely access provider attributes to avoid DetachedInstanceError
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
                    agent_id=str(self.agent_id),
                    agent_name=self.agent_name,
                    has_tool_executor=self.tool_executor is not None,
                    task_id=task_id,
                    llm_provider_id=provider_id,
                    llm_provider_type=provider_type,
                )
                
                # Retrieve relevant context
                context_results = await self.context_store.search(
                    query=user_message,
                    limit=settings.context_search_limit,
                    filter_success=True,
                )
                if langfuse_trace and self.langfuse.enabled:
                    self.langfuse.create_span(
                        trace=langfuse_trace,
                        name="context_retrieval",
                        input_data={"query": user_message, "limit": settings.context_search_limit},
                        output_data={"results": len(context_results)},
                    )

                # Build context string
                context_str = ""
                if context_results:
                    context_str = "\n\n## Relevant Context:\n"
                    for i, result in enumerate(context_results, 1):
                        context_str += f"\n{i}. {result['content']}\n"

                # Build messages
                messages = [
                    {"role": "system", "content": self.config.system_prompt + context_str}
                ]

                # Add session history
                if session_history:
                    messages.extend(session_history[-10:])  # Last 10 messages

                # Add user message
                messages.append({"role": "user", "content": user_message})

                # Determine which model to use: must come from registered llm_provider
                model_to_use = None
                try:
                    if self.llm_provider:
                        model_to_use = self.llm_provider.litellm_model_name
                except Exception as e:
                    logger.warning(
                        "failed_to_access_provider_model",
                        agent_id=str(self.agent_id),
                        error=str(e),
                    )
                
                if not model_to_use:
                    error_msg = "Agent must have a registered LLM provider to execute"
                    logger.error(
                        "agent_execution_failed",
                        agent_id=str(self.agent_id),
                        agent_name=self.agent_name,
                        error=error_msg,
                        error_type="missing_provider",
                    )
                    return {
                        "success": False,
                        "error": error_msg,
                        "error_type": "missing_provider",
                    }
                logger.debug(
                    "using_provider_model",
                    agent_id=str(self.agent_id),
                    provider_model=model_to_use,
                )
                
                # Prepare LLM call arguments
                llm_kwargs = {
                    "model": model_to_use,
                    "messages": messages,
                    "temperature": self.config.temperature,
                    "max_tokens": self.config.max_tokens,
                }
                
                # Add tools if available
                tools = self._get_available_tools()
                if tools:
                    logger.debug(
                        "tools_added_to_llm_request",
                        agent_id=str(self.agent_id),
                        tools_count=len(tools),
                        task_id=task_id,
                    )
                    llm_kwargs["tools"] = tools
                    # Allow model to decide whether to use tools
                    llm_kwargs["tool_choice"] = "auto"

                # Call LLM with automatic Langfuse tracing via decorator
                with tracer.start_as_current_span("llm_call") as llm_span:
                    llm_span.set_attribute("model", model_to_use)
                    llm_span.set_attribute("temperature", self.config.temperature)
                    llm_span.set_attribute("provider", settings.litellm_url or "openai")
                    
                    # Use _call_llm_with_trace which has @trace_llm_call decorator
                    # This automatically logs to Langfuse without manual span creation
                    response = await self._call_llm_with_trace(
                        model=model_to_use,
                        messages=messages,
                        temperature=self.config.temperature,
                        max_tokens=self.config.max_tokens,
                        tools=llm_kwargs.get("tools"),
                        langfuse_trace=langfuse_trace,
                    )
                    
                    if response.usage:
                        llm_span.set_attribute("tokens_prompt", response.usage.prompt_tokens)
                        llm_span.set_attribute("tokens_completion", response.usage.completion_tokens)
                        llm_span.set_attribute("tokens_total", response.usage.total_tokens)
                    
                    llm_span.add_event("llm_response_received", {
                        "model": model_to_use,
                        "tokens": response.usage.total_tokens if response.usage else 0,
                    })
                
                assistant_message = response.choices[0].message.content or ""
                total_tokens = response.usage.total_tokens if response.usage else 0
                
                # Handle tool calls if present
                tool_calls = response.choices[0].message.tool_calls
                if tool_calls and self.tool_executor:
                    span.add_event("tool_calls_detected", {"count": len(tool_calls)})
                    if langfuse_trace and self.langfuse.enabled:
                        self.langfuse.create_event(
                            trace_id=langfuse_trace.id,
                            name="tool_calls_detected",
                            metadata={"count": len(tool_calls)},
                        )
                    
                    logger.info(
                        "processing_tool_calls",
                        agent_id=str(self.agent_id),
                        tool_calls_count=len(tool_calls),
                        task_id=task_id,
                    )
                    
                    # Execute tools
                    tool_execution_results = await self._execute_tools(
                        tool_calls=tool_calls,
                        session_id=session_id,
                    )
                    
                    # Wait for tool results
                    tool_results = await self._wait_for_tool_results(
                        tool_execution_ids=tool_execution_results,
                        timeout_seconds=600,
                        poll_interval=1.0,
                    )
                    
                    # Format tool results for LLM
                    tool_results_formatted = []
                    for tool_call_id, tool_result in tool_results.items():
                        # Find tool call to get tool name
                        # tool_calls are ChatCompletionMessageFunctionToolCall objects
                        tool_call = next(
                            (tc for tc in tool_calls if tc.id == tool_call_id),
                            None
                        )
                        tool_name = tool_call.function.name if tool_call else "unknown"
                        
                        formatted = self._format_tool_result(
                            tool_call_id=tool_call_id,
                            tool_name=tool_name,
                            tool_result=tool_result,
                        )
                        tool_results_formatted.append(formatted)
                    
                    # Add assistant's initial response (may be empty if tool was called)
                    if assistant_message:
                        messages.append({"role": "assistant", "content": assistant_message})
                    else:
                        # Add tool calls info
                        messages.append({
                            "role": "assistant",
                            "content": "Executing tools...",
                        })
                    
                    # Add tool results to messages
                    for tool_result in tool_results_formatted:
                        messages.append({
                            "role": "user",
                            "content": tool_result.get("content", ""),
                        })
                    
                    # Get final response from LLM with tool results using traced method
                    final_response = await self._call_llm_with_trace(
                        model=model_to_use,
                        messages=messages,
                        temperature=self.config.temperature,
                        max_tokens=self.config.max_tokens,
                        langfuse_trace=langfuse_trace,
                    )
                    
                    assistant_message = final_response.choices[0].message.content or ""
                    total_tokens += final_response.usage.total_tokens if final_response.usage else 0
                    
                    logger.info(
                        "tool_calls_processed",
                        agent_id=str(self.agent_id),
                        tool_calls_count=len(tool_calls),
                        final_response_received=True,
                        task_id=task_id,
                    )

                # Store interaction in context
                await self.context_store.add_interaction(
                    content=f"User: {user_message}\nAssistant: {assistant_message}",
                    interaction_type="chat",
                    task_id=task_id,
                    success=True,
                    metadata={
                        "model": model_to_use,
                        "tokens": total_tokens,
                        "tools_used": len(tool_calls) if tool_calls else 0,
                    },
                )

                logger.info(
                    "agent_executed",
                    agent_id=str(self.agent_id),
                    agent_name=self.agent_name,
                    task_id=task_id,
                    context_used=len(context_results),
                    tools_used=len(tool_calls) if tool_calls else 0,
                )

                span.set_attribute("status", "success")
                span.add_event("response_generated", {
                    "response_length": len(assistant_message),
                })

                return {
                    "success": True,
                    "response": assistant_message,
                    "context_used": len(context_results),
                    "tokens_used": total_tokens,
                    "tools_used": len(tool_calls) if tool_calls else 0,
                }

            except openai.APITimeoutError as e:
                error_msg = f"LLM request timeout: model '{model_to_use}' did not respond in time"
                logger.error(
                    "agent_execution_failed",
                    agent_id=str(self.agent_id),
                    agent_name=self.agent_name,
                    error=error_msg,
                    error_type="timeout",
                    model=model_to_use,
                    provider=self._get_provider_name(),
                )

                span.record_exception(e)
                span.set_attribute("status", "error")

                # Store failed interaction
                await self.context_store.add_interaction(
                    content=f"User: {user_message}\nError: {error_msg}",
                    interaction_type="chat",
                    task_id=task_id,
                    success=False,
                )

                return {
                    "success": False,
                    "error": error_msg,
                    "error_type": "timeout",
                    "provider": self._get_provider_name(),
                    "model": model_to_use,
                }

            except openai.APIConnectionError as e:
                error_msg = f"Failed to connect to LLM provider: {str(e)}"
                logger.error(
                    "agent_execution_failed",
                    agent_id=str(self.agent_id),
                    agent_name=self.agent_name,
                    error=error_msg,
                    error_type="connection",
                    model=model_to_use,
                    provider=self._get_provider_name(),
                )

                span.record_exception(e)
                span.set_attribute("status", "error")

                # Store failed interaction
                await self.context_store.add_interaction(
                    content=f"User: {user_message}\nError: {error_msg}",
                    interaction_type="chat",
                    task_id=task_id,
                    success=False,
                )

                return {
                    "success": False,
                    "error": error_msg,
                    "error_type": "connection",
                    "provider": self._get_provider_name(),
                    "model": model_to_use,
                }

            except openai.RateLimitError as e:
                error_msg = f"LLM provider rate limit exceeded for model '{model_to_use}'"
                logger.error(
                    "agent_execution_failed",
                    agent_id=str(self.agent_id),
                    agent_name=self.agent_name,
                    error=error_msg,
                    error_type="rate_limit",
                    model=model_to_use,
                    provider=self._get_provider_name(),
                )

                span.record_exception(e)
                span.set_attribute("status", "error")

                # Store failed interaction
                await self.context_store.add_interaction(
                    content=f"User: {user_message}\nError: {error_msg}",
                    interaction_type="chat",
                    task_id=task_id,
                    success=False,
                )

                return {
                    "success": False,
                    "error": error_msg,
                    "error_type": "rate_limit",
                    "provider": self._get_provider_name(),
                    "model": model_to_use,
                }

            except openai.AuthenticationError as e:
                error_msg = f"LLM provider authentication failed: invalid API key"
                logger.error(
                    "agent_execution_failed",
                    agent_id=str(self.agent_id),
                    agent_name=self.agent_name,
                    error=error_msg,
                    error_type="authentication",
                    model=model_to_use,
                    provider=self._get_provider_name(),
                )

                span.record_exception(e)
                span.set_attribute("status", "error")

                # Store failed interaction
                await self.context_store.add_interaction(
                    content=f"User: {user_message}\nError: {error_msg}",
                    interaction_type="chat",
                    task_id=task_id,
                    success=False,
                )

                return {
                    "success": False,
                    "error": error_msg,
                    "error_type": "authentication",
                    "provider": self._get_provider_name(),
                    "model": model_to_use,
                }

            except openai.BadRequestError as e:
                error_msg = f"Invalid request to LLM provider: {str(e)}"
                logger.error(
                    "agent_execution_failed",
                    agent_id=str(self.agent_id),
                    agent_name=self.agent_name,
                    error=error_msg,
                    error_type="bad_request",
                    model=model_to_use,
                    provider=self._get_provider_name(),
                )

                span.record_exception(e)
                span.set_attribute("status", "error")

                # Store failed interaction
                await self.context_store.add_interaction(
                    content=f"User: {user_message}\nError: {error_msg}",
                    interaction_type="chat",
                    task_id=task_id,
                    success=False,
                )

                return {
                    "success": False,
                    "error": error_msg,
                    "error_type": "bad_request",
                    "provider": self._get_provider_name(),
                    "model": model_to_use,
                }

            except Exception as e:
                error_msg = f"Unexpected error during LLM execution: {str(e)}"
                logger.error(
                    "agent_execution_failed",
                    agent_id=str(self.agent_id),
                    agent_name=self.agent_name,
                    error=error_msg,
                    error_type="unknown",
                    model=model_to_use,
                )

                span.record_exception(e)
                span.set_attribute("status", "error")

                # Store failed interaction
                await self.context_store.add_interaction(
                    content=f"User: {user_message}\nError: {error_msg}",
                    interaction_type="chat",
                    task_id=task_id,
                    success=False,
                )

                return {
                    "success": False,
                    "error": error_msg,
                    "error_type": "unknown",
                    "model": model_to_use,
                }

    def _get_available_tools(self) -> list[dict[str, Any]]:
        """Get available tools in OpenAI Function Calling format.
        
        Returns:
            List of tool definitions for OpenAI API
        """
        logger.debug(
            "get_available_tools_called",
            agent_id=str(self.agent_id),
            has_tool_executor=self.tool_executor is not None,
            tool_executor_type=type(self.tool_executor).__name__ if self.tool_executor else None,
        )
        
        if not self.tool_executor:
            logger.debug(
                "no_tool_executor_available",
                agent_id=str(self.agent_id),
                agent_name=self.agent_name,
            )
            return []
        
        tools = []
        for tool_name, tool_def in AVAILABLE_TOOLS.items():
            # Convert tool definition to OpenAI function format
            tool_schema = {
                "type": "function",
                "function": {
                    "name": tool_def.name.value,
                    "description": tool_def.description,
                    "parameters": {
                        "type": "object",
                        "properties": tool_def.parameters,
                        "required": list(tool_def.parameters.keys()),
                    }
                }
            }
            tools.append(tool_schema)
        
        logger.debug(
            "available_tools_retrieved",
            agent_id=str(self.agent_id),
            tools_count=len(tools),
        )
        
        return tools

    async def _execute_tools(
        self,
        tool_calls: Any,  # List of ChatCompletionMessageFunctionToolCall from OpenAI
        session_id: UUID | None = None,
    ) -> dict[str, Any]:
        """Execute tools via ToolExecutor.
        
        Args:
            tool_calls: List of tool calls from LLM (ChatCompletionMessageFunctionToolCall objects)
            session_id: Chat session ID (required for proper event streaming)
            
        Returns:
            Dictionary mapping tool_call_id to execution response
        """
        if not self.tool_executor:
            return {}
        
        # Validate session_id for proper event streaming
        if not session_id:
            logger.warning(
                "tool_execution_without_session_id",
                agent_id=str(self.agent_id),
                tool_calls_count=len(tool_calls),
                note="session_id is required for proper tool execution event streaming"
            )
        
        results = {}
        
        for tool_call in tool_calls:
            # tool_call is ChatCompletionMessageFunctionToolCall object
            tool_call_id = tool_call.id
            tool_name = tool_call.function.name
            
            try:
                # Parse tool arguments from ChatCompletionFunction object
                args_str = tool_call.function.arguments
                # arguments is already a string, parse it
                tool_params = json.loads(args_str) if isinstance(args_str, str) else args_str
                
                logger.info(
                    "executing_tool_from_llm",
                    agent_id=str(self.agent_id),
                    tool_call_id=tool_call_id,
                    tool_name=tool_name,
                    session_id=session_id,
                )
                
                # Execute tool via ToolExecutor
                response = await self.tool_executor.execute_tool(
                    tool_name=tool_name,
                    tool_params=tool_params,
                    session_id=session_id,
                )
                
                results[tool_call_id] = {
                    "tool_execution_id": response.tool_id,
                    "status": response.status,
                    "requires_approval": response.requires_approval,
                    "approval_id": str(response.approval_id) if response.approval_id else None,
                }
                
                logger.debug(
                    "tool_execution_requested",
                    agent_id=str(self.agent_id),
                    tool_call_id=tool_call_id,
                    tool_execution_id=response.tool_id,
                    status=response.status,
                )
                
            except Exception as e:
                logger.error(
                    "tool_execution_error",
                    agent_id=str(self.agent_id),
                    tool_call_id=tool_call_id,
                    tool_name=tool_name,
                    error=str(e),
                    exc_info=True,
                )
                results[tool_call_id] = {
                    "error": str(e),
                    "status": "failed",
                }
        
        return results

    async def _wait_for_tool_results(
        self,
        tool_execution_ids: dict[str, Any],
        timeout_seconds: int = 600,
        poll_interval: float = 1.0,
    ) -> dict[str, Any]:
        """Wait for tool execution results.
        
        Args:
            tool_execution_ids: Dictionary mapping tool_call_id to execution info
            timeout_seconds: Timeout for waiting (default 600 = 10 minutes)
            poll_interval: Polling interval in seconds (default 1.0)
            
        Returns:
            Dictionary mapping tool_call_id to result
        """
        if not self.tool_executor:
            return {}
        
        results = {}
        start_time = time.time()
        pending_tools = {
            call_id: info 
            for call_id, info in tool_execution_ids.items()
            if info.get("status") != "failed" and "error" not in info
        }
        
        while pending_tools and (time.time() - start_time) < timeout_seconds:
            # Check status of each pending tool
            tools_to_remove = []
            
            for tool_call_id, tool_info in pending_tools.items():
                tool_execution_id = tool_info.get("tool_execution_id")
                
                if not tool_execution_id:
                    results[tool_call_id] = tool_info
                    tools_to_remove.append(tool_call_id)
                    continue
                
                try:
                    # Query tool execution status from database using SQLAlchemy
                    query = select(ToolExecution).where(
                        ToolExecution.id == UUID(tool_execution_id)
                    )
                    result = await self.tool_executor.db.execute(query)
                    execution = result.scalar_one_or_none()
                    
                    if not execution:
                        logger.warning(
                            "tool_execution_not_found",
                            agent_id=str(self.agent_id),
                            tool_execution_id=tool_execution_id,
                        )
                        results[tool_call_id] = {
                            "error": f"Tool execution record not found: {tool_execution_id}",
                            "status": "not_found",
                        }
                        tools_to_remove.append(tool_call_id)
                        continue
                    
                    # Check if execution is complete
                    if execution.status in ["completed", "failed", "rejected"]:
                        results[tool_call_id] = {
                            "status": execution.status,
                            "result": execution.result,
                            "error": execution.error,
                        }
                        tools_to_remove.append(tool_call_id)
                        
                        logger.debug(
                            "tool_execution_completed",
                            agent_id=str(self.agent_id),
                            tool_execution_id=tool_execution_id,
                            status=execution.status,
                        )
                    
                except ValueError as e:
                    logger.error(
                        "invalid_tool_execution_id",
                        agent_id=str(self.agent_id),
                        tool_execution_id=tool_execution_id,
                        error=str(e),
                    )
                    results[tool_call_id] = {
                        "error": f"Invalid tool execution ID: {tool_execution_id}",
                        "status": "invalid",
                    }
                    tools_to_remove.append(tool_call_id)
                    
                except Exception as e:
                    logger.error(
                        "failed_to_check_tool_status",
                        agent_id=str(self.agent_id),
                        tool_execution_id=tool_execution_id,
                        error=str(e),
                        exc_info=True,
                    )
                    # On error, assume still pending
                    continue
            
            # Remove completed tools
            for tool_call_id in tools_to_remove:
                del pending_tools[tool_call_id]
            
            # Wait before next poll
            if pending_tools:
                await asyncio.sleep(poll_interval)
        
        # Collect all remaining pending results as timeouts
        for tool_call_id, tool_info in pending_tools.items():
            results[tool_call_id] = {
                "error": "Tool execution timed out after {} seconds".format(timeout_seconds),
                "status": "timeout",
            }
        
        return results

    def _format_tool_result(
        self,
        tool_call_id: str,
        tool_name: str,
        tool_result: dict[str, Any],
    ) -> dict[str, Any]:
        """Format tool result for LLM.
        
        Args:
            tool_call_id: ID of the tool call
            tool_name: Name of the tool
            tool_result: Result from tool execution
            
        Returns:
            Formatted result for LLM
        """
        # If tool execution is still pending/in progress, return status
        status = tool_result.get("status")
        if status in ["pending", "approved", "executing"]:
            return {
                "tool_call_id": tool_call_id,
                "content": f"Tool '{tool_name}' is executing. Status: {status}. Please wait for results.",
            }
        
        # If tool failed, return error
        if status == "failed" or "error" in tool_result:
            error_msg = tool_result.get("error", "Unknown error")
            return {
                "tool_call_id": tool_call_id,
                "content": f"Tool '{tool_name}' failed: {error_msg}",
                "is_error": True,
            }
        
        # If tool requires approval, return approval status
        if tool_result.get("requires_approval"):
            approval_id = tool_result.get("approval_id")
            return {
                "tool_call_id": tool_call_id,
                "content": f"Tool '{tool_name}' requires user approval (approval_id: {approval_id}). Waiting for approval decision.",
            }
        
        # Return successful result
        result = tool_result.get("result", {})
        return {
            "tool_call_id": tool_call_id,
            "content": str(result),
        }

    async def get_context_stats(self) -> dict[str, Any]:
        """Get context statistics."""
        return await self.context_store.get_stats()

    async def clear_context(self) -> None:
        """Clear agent context."""
        await self.context_store.clear()

    def _get_agent_provider_id(self) -> UUID | None:
        """Get agent's LLM provider ID.
        
        Returns:
            Provider ID if agent has one, None otherwise
        """
        if self.llm_provider:
            return self.llm_provider.id
        return None

    async def _record_provider_usage(self) -> None:
        """Record provider usage (action='use').
        
        This method logs that the provider was used by the agent.
        """
        if not self.llm_provider:
            return
        
        try:
            from app.services.llm_provider_service import LLMProviderService
            from sqlalchemy.ext.asyncio import AsyncSession
            from app.database import get_db
            
            # We can't directly access the db session here, so we just log
            # The actual recording should be done by the caller
            
            # Safely access provider attributes to avoid DetachedInstanceError
            provider_id = None
            provider_type = None
            try:
                provider_id = str(self.llm_provider.id)
                provider_type = self.llm_provider.provider_type
            except Exception:
                pass
            
            logger.debug(
                "recording_provider_usage",
                agent_id=str(self.agent_id),
                provider_id=provider_id,
                provider_type=provider_type,
            )
        except Exception as e:
            logger.warning(
                "failed_to_record_provider_usage",
                agent_id=str(self.agent_id),
                error=str(e),
            )
