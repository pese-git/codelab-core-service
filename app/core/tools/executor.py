"""Tool Executor - Main orchestrator for tool execution with approval workflow"""

import asyncio
from datetime import datetime
from typing import Optional, Tuple
from uuid import UUID, uuid4

from langfuse import get_client, observe
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tools.definitions import ToolName, AVAILABLE_TOOLS
from app.core.tools.validator import PathValidator
from app.core.tools.command_whitelist import CommandValidator
from app.core.tools.size_limiter import SizeLimiter
from app.core.tools.risk_assessor import RiskAssessor, RiskLevel
from app.core.approval_manager import ApprovalManager
from app.core.stream_manager import StreamManager
from app.core.outbox_repository import OutboxRepository
from app.schemas.tool import ToolExecutionResponse
from app.schemas.event import StreamEventType
from app.logging_config import get_logger
from app.models.tool_execution import ToolExecution

logger = get_logger(__name__)


def _safe_tool_input(tool_name: str, tool_params: dict, session_id: Optional[UUID]) -> dict:
    """Build sanitized input payload for Langfuse tool span."""
    payload: dict = {
        "tool_name": tool_name,
        "session_id": str(session_id) if session_id else None,
        "param_keys": sorted(list(tool_params.keys())),
    }
    if "path" in tool_params:
        payload["path"] = str(tool_params.get("path", ""))[:300]
    if "recursive" in tool_params:
        payload["recursive"] = bool(tool_params.get("recursive"))
    if "mode" in tool_params:
        payload["mode"] = str(tool_params.get("mode", ""))
    if "pattern" in tool_params:
        payload["pattern"] = str(tool_params.get("pattern", ""))[:120]
    if "command" in tool_params:
        payload["command"] = str(tool_params.get("command", ""))[:80]
    if "args" in tool_params and isinstance(tool_params.get("args"), list):
        payload["args_count"] = len(tool_params.get("args", []))
    if "content" in tool_params:
        content = tool_params.get("content")
        payload["content_length"] = len(content) if isinstance(content, str) else 0
    return payload


def _update_langfuse_span(*, input_data: dict | None = None, output_data: dict | None = None) -> None:
    """Safely attach sanitized IO payload to current Langfuse span."""
    try:
        get_client().update_current_span(input=input_data, output=output_data)
    except Exception:
        logger.debug("langfuse_span_update_skipped", exc_info=True)


class ToolExecutor:
    """Orchestrates tool execution with security validation and approval workflow
    
    Workflow:
    1. Validate parameters (PathValidator, CommandValidator, SizeLimiter)
    2. Assess risk level (RiskAssessor)
    3. Handle approval if needed (ApprovalManager)
    4. Send tool execution request to client
    5. Handle tool result/error
    """

    def __init__(
        self,
        user_id: UUID,
        project_id: UUID,
        workspace_root: str,
        db: AsyncSession,
        approval_manager: ApprovalManager,
        stream_manager: Optional[StreamManager] = None
    ):
        """Initialize Tool Executor
        
        Args:
            user_id: UUID of the user
            project_id: UUID of the project
            workspace_root: Absolute path to workspace root
            db: AsyncSession for database operations
            approval_manager: ApprovalManager instance
            stream_manager: Optional StreamManager for SSE events
        """
        self.user_id = user_id
        self.project_id = project_id
        self.workspace_root = workspace_root
        self.db = db
        self.approval_manager = approval_manager
        self.stream_manager = stream_manager
        

        # Initialize validators
        self.path_validator = PathValidator(workspace_root)
        self.command_validator = CommandValidator()
        self.risk_assessor = RiskAssessor()
        self.size_limiter = SizeLimiter()

        self.logger = logger

    @observe(as_type="tool", name="ExecuteTool", capture_input=False, capture_output=False)
    async def execute_tool(
        self,
        tool_name: str,
        tool_params: dict,
        session_id: Optional[UUID] = None,
    ) -> ToolExecutionResponse:
        """Execute tool with full validation and approval workflow
        
        Main entry point for tool execution. Includes both OpenTelemetry and Langfuse tracing.
        
        Args:
            tool_name: Name of the tool to execute
            tool_params: Parameters for the tool
            session_id: Optional chat session ID
            
        Returns:
            ToolExecutionResponse with status and result
        """
        tool_id = uuid4()
        created_at = datetime.utcnow().isoformat()

        execution: ToolExecution | None = None
        _update_langfuse_span(input_data=_safe_tool_input(tool_name, tool_params, session_id))

        # Validate tool name
        available_tools = {tool.value for tool in ToolName}
        if tool_name not in available_tools:
            error = f"Unknown tool: {tool_name}"
            _update_langfuse_span(
                output_data={"status": "failed", "error_type": "unknown_tool", "tool_id": str(tool_id)}
            )
            return ToolExecutionResponse(
                tool_id=str(tool_id),
                tool_name=tool_name,
                status="failed",
                requires_approval=False,
                error=error,
                created_at=created_at,
                completed_at=datetime.utcnow().isoformat(),
            )

        # Validate tool params
        is_valid, validation_error = await self._validate_tool_params(tool_name, tool_params)
        if not is_valid:
            _update_langfuse_span(
                output_data={
                    "status": "failed",
                    "error_type": "validation_error",
                    "tool_id": str(tool_id),
                }
            )
            return ToolExecutionResponse(
                tool_id=str(tool_id),
                tool_name=tool_name,
                status="failed",
                requires_approval=False,
                error=validation_error,
                created_at=created_at,
                completed_at=datetime.utcnow().isoformat(),
            )

        # Assess risk and create execution record
        risk_level = self.risk_assessor.assess_tool_risk(tool_name, tool_params)
        timeout_seconds = self.risk_assessor.get_timeout_for_risk_level(risk_level)
        requires_approval = self.risk_assessor.requires_approval(risk_level)

        execution = await self._create_tool_execution(
            tool_id=tool_id,
            tool_name=tool_name,
            tool_params=tool_params,
            risk_level=risk_level.value,
            session_id=session_id,
        )

        approval_id: UUID | None = None

        # Approval workflow for MEDIUM/HIGH risk
        if requires_approval:
            approval = await self.approval_manager.request_tool_execution_approval(
                tool_name=tool_name,
                tool_params=tool_params,
                risk_level=risk_level.value,
                timeout_seconds=timeout_seconds,
                session_id=session_id,
            )
            approval_id = approval.id
            execution.approval_id = approval_id
            await self.db.flush()

            approved, reason = await self.approval_manager.wait_for_tool_approval(
                approval_id=approval_id,
                timeout_seconds=timeout_seconds,
            )
            if not approved:
                execution.status = "rejected"
                execution.error = reason or "Approval rejected"
                execution.completed_at = datetime.utcnow()
                await self.db.flush()
                _update_langfuse_span(
                    output_data={
                        "status": "rejected",
                        "tool_id": str(tool_id),
                        "risk_level": risk_level.value,
                        "requires_approval": True,
                        "approval_id": str(approval_id),
                    }
                )
                return ToolExecutionResponse(
                    tool_id=str(tool_id),
                    tool_name=tool_name,
                    status="rejected",
                    approval_id=approval_id,
                    requires_approval=True,
                    error=execution.error,
                    created_at=execution.created_at.isoformat(),
                    completed_at=execution.completed_at.isoformat() if execution.completed_at else None,
                )

        # Approved: dispatch execution signal to client and return async status
        execution.status = "approved"
        await self.db.flush()
        await self._send_tool_execution_request(
            tool_id=str(tool_id),
            tool_name=tool_name,
            tool_params=tool_params,
            session_id=session_id,
            execution_id=tool_id,
        )
        await self.approval_manager.send_tool_execution_signal(
            tool_id=str(tool_id),
            tool_name=tool_name,
            tool_params=tool_params,
            session_id=session_id,
        )

        _update_langfuse_span(
            output_data={
                "status": "approved",
                "tool_id": str(tool_id),
                "risk_level": risk_level.value,
                "requires_approval": requires_approval,
                "approval_id": str(approval_id) if approval_id else None,
            }
        )
        return ToolExecutionResponse(
            tool_id=str(tool_id),
            tool_name=tool_name,
            status="approved",
            approval_id=approval_id,
            requires_approval=requires_approval,
            created_at=execution.created_at.isoformat(),
            completed_at=None,
        )

    @observe(as_type="tool", name="ValidateTool", capture_input=False, capture_output=False)
    async def _validate_tool_params(
        self,
        tool_name: str,
        params: dict,
    ) -> Tuple[bool, Optional[str]]:
        """Validate tool parameters using appropriate validators
        
        Args:
            tool_name: Name of the tool
            params: Tool parameters to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # ================================================================
            # read_file validation
            # ================================================================
            if tool_name == "read_file":
                path = params.get("path")
                if not path:
                    return False, "Missing 'path' parameter"

                is_valid, msg = self.path_validator.validate_read_path(path)
                if not is_valid:
                    return False, msg

                # NOTE: File size validation happens on CLIENT side
                # Server cannot check file size on client filesystem
                # PathValidator ensures path is safe, client handles FS checks

                return True, None

            # ================================================================
            # write_file validation
            # ================================================================
            elif tool_name == "write_file":
                path = params.get("path")
                content = params.get("content")

                if not path or content is None:
                    return False, "Missing 'path' or 'content' parameter"

                # Validate path
                is_valid, msg = self.path_validator.validate_write_path(path)
                if not is_valid:
                    return False, msg

                # Validate content size
                is_valid, msg = self.size_limiter.validate_write_size(len(content))
                if not is_valid:
                    return False, msg

                return True, None

            # ================================================================
            # execute_command validation
            # ================================================================
            elif tool_name == "execute_command":
                command = params.get("command")
                args = params.get("args", [])
                timeout = params.get("timeout", 30)

                if not command:
                    return False, "Missing 'command' parameter"

                # Validate command is allowed
                is_valid, msg = self.command_validator.validate_command(command)
                if not is_valid:
                    return False, msg

                # Validate command safety with args
                is_valid, msg = self.command_validator.validate_command_safety(command, args)
                if not is_valid:
                    return False, msg

                # Validate timeout
                is_valid, msg = self.size_limiter.validate_timeout(timeout)
                if not is_valid:
                    return False, msg

                return True, None

            # ================================================================
            # list_directory validation
            # ================================================================
            elif tool_name == "list_directory":
                path = params.get("path")
                if not path:
                    return False, "Missing 'path' parameter"

                is_valid, msg = self.path_validator.validate_directory_path(path)
                if not is_valid:
                    return False, msg

                return True, None

            # ================================================================
            # Unknown tool
            # ================================================================
            else:
                return False, f"Unknown tool: {tool_name}"

        except Exception as e:
            self.logger.error(f"Validation error for {tool_name}: {str(e)}", exc_info=True)
            return False, f"Validation error: {str(e)}"

    async def _send_tool_execution_request(
        self,
        tool_id: str,
        tool_name: str,
        tool_params: dict,
        session_id: Optional[UUID] = None,
        execution_id: Optional[UUID] = None,
    ) -> Optional[dict]:
        """Record tool execution request via outbox and notify client."""
        try:
            # Record outbox event for tool execution request
            if execution_id is None:
                execution_id = UUID(tool_id)

            await OutboxRepository.record_event(
                session=self.db,
                aggregate_type="tool_execution",
                aggregate_id=execution_id,
                user_id=self.user_id,
                project_id=self.project_id,
                event_type=StreamEventType.TOOL_EXECUTION_REQUEST.value,
                payload={
                    "tool_id": tool_id,
                    "tool_name": tool_name,
                    "tool_params": tool_params,
                    "session_id": str(session_id) if session_id else None,
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )

            self.logger.info(
                "tool_execution_request_recorded",
                tool_id=tool_id,
                tool_name=tool_name,
            )
            return None

        except Exception as e:
            self.logger.error(
                "send_tool_execution_request_failed",
                tool_id=tool_id,
                error=str(e),
                exc_info=True,
            )
            return None

    async def _wait_for_tool_result(
        self,
        tool_id: str,
        execution_id: UUID,
        timeout_seconds: int = 300,
    ) -> tuple[Optional[dict], Optional[str]]:
        """Wait for tool execution result from client
        
        Polls tool execution status until result is received or timeout occurs.
        
        Args:
            tool_id: ID of the tool execution
            execution_id: ID of the execution record
            timeout_seconds: Timeout in seconds
            
        Returns:
            Tuple of (result, error)
            - result: Result dict if successful
            - error: Error message if failed
        """
        import time as time_module
        
        start_time = time_module.time()
        
        self.logger.info(
            "wait_for_tool_result_started",
            tool_id=tool_id,
            execution_id=str(execution_id),
            timeout=timeout_seconds,
        )
        
        while time_module.time() - start_time < timeout_seconds:
            # Check execution status in database
            from sqlalchemy.future import select
            
            result = await self.db.execute(
                select(ToolExecution).where(ToolExecution.id == execution_id)
            )
            execution = result.scalar_one_or_none()
            
            if not execution:
                error = "Tool execution record not found"
                self.logger.error(error, tool_id=tool_id, execution_id=str(execution_id))
                return None, error
            
            # Check if result is available
            if execution.status == "completed":
                self.logger.info(
                    "tool_result_received",
                    tool_id=tool_id,
                    execution_id=str(execution_id),
                )
                return execution.result, None
            
            # Check if execution failed
            if execution.status in ["failed", "rejected"]:
                error = execution.error or "Tool execution failed"
                self.logger.warning(
                    "tool_execution_failed",
                    tool_id=tool_id,
                    execution_id=str(execution_id),
                    error=error,
                )
                return None, error
            
            # Wait before checking again (poll every 0.5 seconds)
            await asyncio.sleep(0.5)
        
        # Timeout occurred
        error = f"Tool execution timeout after {timeout_seconds}s"
        self.logger.warning(
            "tool_result_timeout",
            tool_id=tool_id,
            execution_id=str(execution_id),
            timeout=timeout_seconds,
        )
        return None, error

    async def _create_tool_execution(
        self,
        tool_id: UUID,
        tool_name: str,
        tool_params: dict,
        risk_level: str,
        session_id: Optional[UUID],
    ) -> ToolExecution:
        """Create tool execution record."""
        execution = ToolExecution(
            id=tool_id,
            user_id=self.user_id,
            project_id=self.project_id,
            session_id=session_id,
            tool_name=tool_name,
            tool_params=tool_params,
            risk_level=risk_level,
            status="pending",
        )
        self.db.add(execution)
        await self.db.flush()
        return execution
