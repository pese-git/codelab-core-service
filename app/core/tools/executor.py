"""Tool Executor - Main orchestrator for tool execution with approval workflow"""

import asyncio
from datetime import datetime
from typing import Optional, Tuple
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tools.definitions import ToolName, AVAILABLE_TOOLS
from app.core.tools.validator import PathValidator
from app.core.tools.command_whitelist import CommandValidator
from app.core.tools.size_limiter import SizeLimiter
from app.core.tools.risk_assessor import RiskAssessor, RiskLevel
from app.core.approval_manager import ApprovalManager
from app.core.stream_manager import StreamManager
from app.schemas.tool import ToolExecutionResponse
from app.schemas.event import StreamEvent, StreamEventType
from app.logging_config import get_logger

logger = get_logger(__name__)


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
        tool_id = str(uuid4())
        created_at = datetime.utcnow().isoformat()

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
            is_valid, error = await self._validate_tool_params(tool_name, tool_params)
            if not is_valid:
                self.logger.warning(
                    "tool_validation_failed",
                    tool_id=tool_id,
                    tool_name=tool_name,
                    error=error,
                )
                return ToolExecutionResponse(
                    tool_id=tool_id,
                    tool_name=tool_name,
                    status="failed",
                    error=error,
                    created_at=created_at,
                )

            # ====================================================================
            # STEP 2: Assess risk level
            # ====================================================================
            risk_level = self.risk_assessor.assess_tool_risk(tool_name, tool_params)
            self.logger.debug(
                "tool_risk_assessed",
                tool_id=tool_id,
                tool_name=tool_name,
                risk_level=risk_level.value,
            )

            # ====================================================================
            # STEP 3: Handle approval workflow
            # ====================================================================
            approval_id = None

            # Check if LOW risk (auto-approve)
            if await self.approval_manager.auto_approve_tool_if_low_risk(risk_level.value):
                self.logger.info(
                    "tool_auto_approved",
                    tool_id=tool_id,
                    tool_name=tool_name,
                    risk_level=risk_level.value,
                )
            else:
                # Request approval for MEDIUM/HIGH risk
                timeout_seconds = self.risk_assessor.get_timeout_for_risk_level(risk_level)

                self.logger.info(
                    "requesting_tool_approval",
                    tool_id=tool_id,
                    tool_name=tool_name,
                    risk_level=risk_level.value,
                    timeout=timeout_seconds,
                )

                approval = await self.approval_manager.request_tool_execution_approval(
                    tool_name=tool_name,
                    tool_params=tool_params,
                    risk_level=risk_level.value,
                    timeout_seconds=timeout_seconds,
                    session_id=session_id,
                )
                approval_id = approval.id

                # Wait for approval decision
                approved, reason = await self.approval_manager.wait_for_tool_approval(
                    approval_id=approval_id,
                    timeout_seconds=timeout_seconds,
                )

                if not approved:
                    self.logger.warning(
                        "tool_execution_rejected",
                        tool_id=tool_id,
                        tool_name=tool_name,
                        approval_id=str(approval_id),
                        reason=reason,
                    )
                    return ToolExecutionResponse(
                        tool_id=tool_id,
                        tool_name=tool_name,
                        status="rejected",
                        approval_id=approval_id,
                        error=f"Tool execution rejected: {reason}",
                        created_at=created_at,
                    )

            # ====================================================================
            # STEP 4: Send tool execution request to client
            # ====================================================================
            self.logger.info(
                "sending_tool_to_client",
                tool_id=tool_id,
                tool_name=tool_name,
                approval_id=str(approval_id) if approval_id else None,
            )

            result = await self._send_tool_execution_request(
                tool_id=tool_id,
                tool_name=tool_name,
                tool_params=tool_params,
                session_id=session_id,
            )

            # ====================================================================
            # STEP 5: Return successful response
            # ====================================================================
            self.logger.info(
                "tool_execution_completed",
                tool_id=tool_id,
                tool_name=tool_name,
                status="completed",
            )

            return ToolExecutionResponse(
                tool_id=tool_id,
                tool_name=tool_name,
                status="completed",
                approval_id=approval_id,
                requires_approval=risk_level != RiskLevel.LOW,
                result=result,
                created_at=created_at,
                completed_at=datetime.utcnow().isoformat(),
            )

        except Exception as e:
            self.logger.error(
                "tool_execution_error",
                tool_id=tool_id,
                tool_name=tool_name,
                error=str(e),
                exc_info=True,
            )
            return ToolExecutionResponse(
                tool_id=tool_id,
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

                # Check file size
                if msg:  # msg contains resolved path
                    import os
                    try:
                        file_size = os.path.getsize(msg)
                        is_valid, size_error = self.size_limiter.validate_read_size(file_size)
                        if not is_valid:
                            return False, size_error
                    except OSError as e:
                        return False, f"Error checking file size: {str(e)}"

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
    ) -> Optional[dict]:
        """Send tool execution request to client via StreamManager
        
        Broadcasts TOOL_EXECUTION_REQUEST event to client (typically VS Code Extension)
        The client receives this and executes the tool locally, then sends back result
        
        Args:
            tool_id: Unique ID for this execution
            tool_name: Name of the tool
            tool_params: Tool parameters
            session_id: Optional session ID for routing
            
        Returns:
            Tool result (placeholder for now, actual result comes from client)
        """
        try:
            if not self.stream_manager:
                self.logger.warning(
                    "stream_manager_not_available",
                    tool_id=tool_id,
                )
                return None

            # Create and broadcast tool execution request
            event = StreamEvent(
                event_type=StreamEventType.TOOL_EXECUTION_REQUEST,
                payload={
                    "tool_id": tool_id,
                    "tool_name": tool_name,
                    "tool_params": tool_params,
                    "session_id": str(session_id) if session_id else None,
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )

            sent_count = await self.stream_manager.broadcast_to_user(
                self.user_id,
                event,
                buffer=True,
            )

            self.logger.info(
                "tool_execution_request_sent",
                tool_id=tool_id,
                tool_name=tool_name,
                sent_to_connections=sent_count,
            )

            # In a real implementation, would wait for client response here
            # For now, return placeholder
            return {
                "success": True,
                "message": "Tool execution request sent to client",
            }

        except Exception as e:
            self.logger.error(
                "send_tool_execution_request_failed",
                tool_id=tool_id,
                error=str(e),
                exc_info=True,
            )
            return None
