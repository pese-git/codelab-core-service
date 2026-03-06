"""Tool Executor - Main orchestrator for tool execution with approval workflow"""

import asyncio
from datetime import datetime
from typing import Optional, Tuple
from uuid import UUID, uuid4

from opentelemetry import trace
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
from app.tracing import get_tracer

logger = get_logger(__name__)
tracer = get_tracer(__name__)


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
        stream_manager: Optional[StreamManager] = None,
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

    async def execute_tool(
        self,
        tool_name: str,
        tool_params: dict,
        session_id: Optional[UUID] = None,
    ) -> ToolExecutionResponse:
        """Execute tool with full validation and approval workflow
        
        Main entry point for tool execution
        
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

        with tracer.start_as_current_span("tool_execution") as span:
            span.set_attribute("tool.name", tool_name)
            if session_id:
                span.set_attribute("session.id", str(session_id))
            
            try:
                self.logger.info(
                    "tool_execution_started",
                    tool_id=tool_id,
                    tool_name=tool_name,
                    user_id=str(self.user_id),
                )

                # ====================================================================
                # STEP 1: Validate tool parameters
                # ====================================================================
                with tracer.start_as_current_span("tool_validation") as val_span:
                    is_valid, error = await self._validate_tool_params(tool_name, tool_params)
                    val_span.set_attribute("validation_status", "passed" if is_valid else "failed")
                    
                    if not is_valid:
                        self.logger.warning(
                            "tool_validation_failed",
                            tool_id=tool_id,
                            tool_name=tool_name,
                            error=error,
                        )
                        val_span.add_event("validation_error", {"error": error})
                        span.set_attribute("status", "failed")
                        return ToolExecutionResponse(
                            tool_id=str(tool_id),
                            tool_name=tool_name,
                            status="failed",
                            error=error,
                            created_at=created_at,
                        )

                # ====================================================================
                # STEP 2: Assess risk level
                # ====================================================================
                with tracer.start_as_current_span("risk_assessment") as risk_span:
                    risk_level = self.risk_assessor.assess_tool_risk(tool_name, tool_params)
                    risk_span.set_attribute("risk_level", risk_level.value)
                    
                    self.logger.debug(
                        "tool_risk_assessed",
                        tool_id=str(tool_id),
                        tool_name=tool_name,
                        risk_level=risk_level.value,
                    )

                # Create execution record
                execution = await self._create_tool_execution(
                    tool_id=tool_id,
                    tool_name=tool_name,
                    tool_params=tool_params,
                    risk_level=risk_level.value,
                    session_id=session_id,
                )
                span.set_attribute("execution_record_id", str(execution.id))

                # ====================================================================
                # STEP 3: Handle approval workflow
                # ====================================================================
                approval_id = None

                # Check if LOW risk (auto-approve)
                if await self.approval_manager.auto_approve_tool_if_low_risk(risk_level.value):
                    self.logger.info(
                        "tool_auto_approved",
                        tool_id=str(tool_id),
                        tool_name=tool_name,
                        risk_level=risk_level.value,
                    )
                    span.add_event("auto_approved", {"risk_level": risk_level.value})
                    execution.status = "approved"
                else:
                    # Request approval for MEDIUM/HIGH risk
                    timeout_seconds = self.risk_assessor.get_timeout_for_risk_level(risk_level)

                    self.logger.info(
                        "requesting_tool_approval",
                        tool_id=str(tool_id),
                        tool_name=tool_name,
                        risk_level=risk_level.value,
                        timeout=timeout_seconds,
                    )

                    with tracer.start_as_current_span("approval_workflow") as approval_span:
                        approval = await self.approval_manager.request_tool_execution_approval(
                            tool_name=tool_name,
                            tool_params=tool_params,
                            risk_level=risk_level.value,
                            timeout_seconds=timeout_seconds,
                            session_id=session_id,
                        )
                        approval_id = approval.id
                        approval_span.set_attribute("approval_id", str(approval_id))
                        approval_span.set_attribute("timeout_seconds", timeout_seconds)
                        execution.approval_id = approval_id

                        # Wait for approval decision
                        approved, reason = await self.approval_manager.wait_for_tool_approval(
                            approval_id=approval_id,
                            timeout_seconds=timeout_seconds,
                        )

                        if not approved:
                            self.logger.warning(
                                "tool_execution_rejected",
                                tool_id=str(tool_id),
                                tool_name=tool_name,
                                approval_id=str(approval_id),
                                reason=reason,
                            )
                            approval_span.set_attribute("approval_status", "rejected")
                            execution.status = "rejected"
                            execution.error = f"Tool execution rejected: {reason}"
                            execution.completed_at = datetime.utcnow()
                            await self.db.flush()
                            span.set_attribute("status", "rejected")
                            return ToolExecutionResponse(
                                tool_id=str(tool_id),
                                tool_name=tool_name,
                                status="rejected",
                                approval_id=approval_id,
                                error=f"Tool execution rejected: {reason}",
                                created_at=created_at,
                            )

                        approval_span.set_attribute("approval_status", "approved")
                        execution.status = "approved"

                await self.db.flush()

                # ====================================================================
                # STEP 4: Send tool execution request to client
                # ====================================================================
                self.logger.info(
                    "sending_tool_to_client",
                    tool_id=str(tool_id),
                    tool_name=tool_name,
                    approval_id=str(approval_id) if approval_id else None,
                )

                with tracer.start_as_current_span("client_execution") as client_span:
                    await self._send_tool_execution_request(
                        tool_id=str(tool_id),
                        tool_name=tool_name,
                        tool_params=tool_params,
                        session_id=session_id,
                        execution_id=execution.id,
                    )
                    client_span.set_attribute("request_sent", True)

                # ====================================================================
                # STEP 5: Return pending response (client executes tool)
                # ====================================================================
                span.set_attribute("status", "pending")
                return ToolExecutionResponse(
                    tool_id=str(tool_id),
                    tool_name=tool_name,
                    status=execution.status,
                    approval_id=approval_id,
                    requires_approval=risk_level != RiskLevel.LOW,
                    created_at=created_at,
                )

            except Exception as e:
                self.logger.error(
                    "tool_execution_error",
                    tool_id=str(tool_id),
                    tool_name=tool_name,
                    error=str(e),
                    exc_info=True,
                )
                span.record_exception(e)
                span.set_attribute("status", "error")
                
                if execution is not None:
                    execution.status = "failed"
                    execution.error = str(e)
                    execution.completed_at = datetime.utcnow()
                    await self.db.flush()
                return ToolExecutionResponse(
                    tool_id=str(tool_id),
                    tool_name=tool_name,
                    status="failed",
                    error=f"Tool execution error: {str(e)}",
                    created_at=created_at,
                )

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
