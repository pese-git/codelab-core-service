"""Approval Manager for controlling HIGH risk operations and expensive plans."""

import time
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.logging_config import get_logger
from app.models.approval_request import ApprovalRequest
from app.models.task_plan import TaskPlan
from app.core.stream_manager import StreamManager
from app.schemas.approval import ApprovalStatus, ApprovalType
from app.schemas.event import StreamEvent, StreamEventType

logger = get_logger(__name__)


class ApprovalManager:
    """Manages approval workflow for tools and plans."""

    # Risk assessment constants
    HIGH_RISK_TOOLS = {"write_file", "execute_command", "delete_file", "system_command"}
    MEDIUM_RISK_TOOLS = {"read_file", "list_directory", "api_call", "create_directory"}
    LOW_RISK_TOOLS = {"search", "analyze", "extract_info"}

    # Auto-approve thresholds
    LOW_RISK_COST_THRESHOLD = 0.10
    MEDIUM_RISK_COST_THRESHOLD = 0.10
    MEDIUM_RISK_DURATION_THRESHOLD = 30
    HIGH_RISK_COST_THRESHOLD = 1.00
    HIGH_RISK_DURATION_THRESHOLD = 300

    # Plan approval thresholds
    PLAN_HIGH_RISK_COST = 1.00
    PLAN_MEDIUM_RISK_COST = 0.10
    PLAN_MEDIUM_RISK_DURATION = 30
    PLAN_MIN_TASKS_FOR_APPROVAL = 3

    # Timeout management
    DEFAULT_TIMEOUT = 300
    TIMEOUT_WARNING_THRESHOLD = 60

    def __init__(
        self,
        user_id: UUID,
        project_id: UUID,
        db: AsyncSession,
        stream_manager: Optional[StreamManager] = None,
    ):
        """Initialize ApprovalManager.

        Args:
            user_id: UUID of the user
            project_id: UUID of the project
            db: AsyncSession for database operations
            stream_manager: Optional StreamManager for SSE notifications
        """
        self.user_id = user_id
        self.project_id = project_id
        self.db = db
        self.stream_manager = stream_manager
        self.logger = get_logger(__name__)

    async def request_plan_approval(
        self,
        plan: TaskPlan,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> ApprovalRequest:
        """Request user approval for plan execution.

        Args:
            plan: TaskPlan instance to request approval for
            timeout: Timeout in seconds (default 300)

        Returns:
            ApprovalRequest instance

        Raises:
            HTTPException: If approval request creation fails
        """
        try:
            self.logger.info(
                "request_plan_approval_started",
                plan_id=str(plan.id),
                estimated_cost=plan.total_estimated_cost,
                estimated_duration=plan.total_estimated_duration,
                task_count=len(plan.tasks) if hasattr(plan, "tasks") else 0,
            )

            # Calculate risk level
            risk_level = self.assess_plan_risk(plan)
            self.logger.debug("plan_risk_assessed", risk_level=risk_level, plan_id=str(plan.id))

            # Check if auto-approve (LOW risk + cost < $0.10)
            if self.should_auto_approve(risk_level, plan.total_estimated_cost):
                self.logger.info(
                    "plan_auto_approved",
                    plan_id=str(plan.id),
                    risk_level=risk_level,
                    estimated_cost=plan.total_estimated_cost,
                )
                approval = ApprovalRequest(
                    user_id=self.user_id,
                    type=ApprovalType.PLAN,
                    payload={
                        "plan_id": str(plan.id),
                        "original_request": plan.original_request,
                        "estimated_cost": plan.total_estimated_cost,
                        "estimated_duration": plan.total_estimated_duration,
                        "task_count": len(plan.tasks) if hasattr(plan, "tasks") else 0,
                        "agents_involved": [],
                        "risk_level": risk_level,
                        "auto_approved": True,
                    },
                    status=ApprovalStatus.APPROVED,
                    resolved_at=datetime.now(timezone.utc),
                    decision="Auto-approved (LOW risk)",
                )
            else:
                # Create approval request that requires user confirmation
                approval = ApprovalRequest(
                    user_id=self.user_id,
                    type=ApprovalType.PLAN,
                    payload={
                        "plan_id": str(plan.id),
                        "original_request": plan.original_request,
                        "estimated_cost": plan.total_estimated_cost,
                        "estimated_duration": plan.total_estimated_duration,
                        "task_count": len(plan.tasks) if hasattr(plan, "tasks") else 0,
                        "agents_involved": [],
                        "risk_level": risk_level,
                        "auto_approved": False,
                        "created_at_timestamp": datetime.now(timezone.utc).isoformat(),
                        "timeout_seconds": timeout,
                    },
                    status=ApprovalStatus.PENDING,
                )

            self.db.add(approval)
            await self.db.flush()

            self.logger.info(
                "approval_request_created",
                approval_id=str(approval.id),
                type="plan",
                status=approval.status,
                risk_level=risk_level,
            )

            # Send SSE notification
            if self.stream_manager:
                await self._send_approval_notification(
                    approval,
                    event_type=StreamEventType.APPROVAL_REQUIRED,
                    timeout=timeout,
                )

            return approval

        except Exception as e:
            self.logger.error("request_plan_approval_failed", error=str(e), plan_id=str(plan.id))
            raise HTTPException(status_code=500, detail="Failed to create approval request")

    async def request_tool_approval(
        self,
        tool_name: str,
        tool_params: dict,
        agent_id: UUID,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> ApprovalRequest:
        """Request user approval for tool execution.

        Args:
            tool_name: Name of the tool
            tool_params: Parameters for the tool
            agent_id: UUID of the requesting agent
            timeout: Timeout in seconds (default 300)

        Returns:
            ApprovalRequest instance

        Raises:
            HTTPException: If approval request creation fails
        """
        try:
            self.logger.info(
                "request_tool_approval_started",
                tool_name=tool_name,
                agent_id=str(agent_id),
                param_keys=list(tool_params.keys()),
            )

            # Assess tool risk level
            risk_level = self.assess_tool_risk(tool_name, tool_params)
            self.logger.debug("tool_risk_assessed", risk_level=risk_level, tool_name=tool_name)

            # Check if auto-approve
            if self.should_auto_approve(risk_level, 0.0):
                self.logger.info(
                    "tool_auto_approved",
                    tool_name=tool_name,
                    risk_level=risk_level,
                )
                approval = ApprovalRequest(
                    user_id=self.user_id,
                    type=ApprovalType.TOOL,
                    payload={
                        "tool_name": tool_name,
                        "parameters": tool_params,
                        "agent_id": str(agent_id),
                        "risk_level": risk_level,
                        "auto_approved": True,
                    },
                    status=ApprovalStatus.APPROVED,
                    resolved_at=datetime.now(timezone.utc),
                    decision="Auto-approved (LOW risk)",
                )
            else:
                # Create approval request that requires user confirmation
                approval = ApprovalRequest(
                    user_id=self.user_id,
                    type=ApprovalType.TOOL,
                    payload={
                        "tool_name": tool_name,
                        "parameters": tool_params,
                        "agent_id": str(agent_id),
                        "risk_level": risk_level,
                        "auto_approved": False,
                        "created_at_timestamp": datetime.now(timezone.utc).isoformat(),
                        "timeout_seconds": timeout,
                    },
                    status=ApprovalStatus.PENDING,
                )

            self.db.add(approval)
            await self.db.flush()

            self.logger.info(
                "tool_approval_request_created",
                approval_id=str(approval.id),
                tool_name=tool_name,
                status=approval.status,
                risk_level=risk_level,
            )

            # Send SSE notification
            if self.stream_manager:
                await self._send_approval_notification(
                    approval,
                    event_type=StreamEventType.APPROVAL_REQUIRED,
                    timeout=timeout,
                    tool_name=tool_name,
                )

            return approval

        except Exception as e:
            self.logger.error("request_tool_approval_failed", error=str(e), tool_name=tool_name)
            raise HTTPException(status_code=500, detail="Failed to create tool approval request")

    async def confirm_approval(
        self,
        approval_id: UUID,
    ) -> ApprovalRequest:
        """User confirms approval.

        Args:
            approval_id: UUID of the approval request

        Returns:
            Updated ApprovalRequest instance

        Raises:
            HTTPException: If approval not found or already resolved
        """
        try:
            self.logger.info("confirm_approval_started", approval_id=str(approval_id))

            # Load approval request
            result = await self.db.execute(
                select(ApprovalRequest).where(ApprovalRequest.id == approval_id)
            )
            approval = result.scalar_one_or_none()

            if not approval:
                self.logger.warning("approval_not_found", approval_id=str(approval_id))
                raise HTTPException(status_code=404, detail="Approval request not found")

            if approval.status != ApprovalStatus.PENDING:
                self.logger.warning(
                    "approval_already_resolved",
                    approval_id=str(approval_id),
                    status=approval.status,
                )
                raise HTTPException(status_code=400, detail="Approval already resolved")

            # Check timeout
            elapsed = await self.check_timeout(approval_id)
            if elapsed:
                self.logger.warning(
                    "approval_already_timed_out",
                    approval_id=str(approval_id),
                )
                raise HTTPException(status_code=410, detail="Approval request has timed out")

            # Update status to 'approved'
            approval.status = ApprovalStatus.APPROVED
            approval.resolved_at = datetime.now(timezone.utc)
            approval.decision = "Approved by user"

            await self.db.flush()

            self.logger.info(
                "approval_confirmed",
                approval_id=str(approval_id),
                type=approval.type,
            )

            # Send SSE notification
            if self.stream_manager:
                await self._send_approval_resolved_notification(approval, approved=True)

            return approval

        except HTTPException:
            raise
        except Exception as e:
            self.logger.error("confirm_approval_failed", error=str(e), approval_id=str(approval_id))
            raise HTTPException(status_code=500, detail="Failed to confirm approval")

    async def reject_approval(
        self,
        approval_id: UUID,
        reason: Optional[str] = None,
    ) -> ApprovalRequest:
        """User rejects approval.

        Args:
            approval_id: UUID of the approval request
            reason: Optional reason for rejection

        Returns:
            Updated ApprovalRequest instance

        Raises:
            HTTPException: If approval not found or already resolved
        """
        try:
            self.logger.info(
                "reject_approval_started",
                approval_id=str(approval_id),
                reason=reason,
            )

            # Load approval request
            result = await self.db.execute(
                select(ApprovalRequest).where(ApprovalRequest.id == approval_id)
            )
            approval = result.scalar_one_or_none()

            if not approval:
                self.logger.warning("approval_not_found", approval_id=str(approval_id))
                raise HTTPException(status_code=404, detail="Approval request not found")

            if approval.status != ApprovalStatus.PENDING:
                self.logger.warning(
                    "approval_already_resolved",
                    approval_id=str(approval_id),
                    status=approval.status,
                )
                raise HTTPException(status_code=400, detail="Approval already resolved")

            # Update status to 'rejected'
            approval.status = ApprovalStatus.REJECTED
            approval.resolved_at = datetime.now(timezone.utc)
            approval.decision = reason or "Rejected by user"

            await self.db.flush()

            self.logger.info(
                "approval_rejected",
                approval_id=str(approval_id),
                type=approval.type,
                reason=reason,
            )

            # Send SSE notification
            if self.stream_manager:
                await self._send_approval_resolved_notification(approval, approved=False)

            return approval

        except HTTPException:
            raise
        except Exception as e:
            self.logger.error("reject_approval_failed", error=str(e), approval_id=str(approval_id))
            raise HTTPException(status_code=500, detail="Failed to reject approval")

    async def check_timeout(
        self,
        approval_id: UUID,
    ) -> bool:
        """Check if approval request timed out and auto-reject if needed.

        Args:
            approval_id: UUID of the approval request

        Returns:
            True if timed out, False otherwise

        Raises:
            HTTPException: If approval not found
        """
        try:
            # Load approval request
            result = await self.db.execute(
                select(ApprovalRequest).where(ApprovalRequest.id == approval_id)
            )
            approval = result.scalar_one_or_none()

            if not approval:
                self.logger.warning("approval_not_found_timeout_check", approval_id=str(approval_id))
                raise HTTPException(status_code=404, detail="Approval request not found")

            # If already resolved, no timeout needed
            if approval.status != ApprovalStatus.PENDING:
                return False

            # Get timeout from payload or use default
            timeout_seconds = approval.payload.get("timeout_seconds", self.DEFAULT_TIMEOUT)
            created_at = approval.created_at

            # Calculate elapsed time
            elapsed = (datetime.now(timezone.utc) - created_at.replace(tzinfo=timezone.utc)).total_seconds()

            self.logger.debug(
                "timeout_check",
                approval_id=str(approval_id),
                elapsed_seconds=elapsed,
                timeout_seconds=timeout_seconds,
            )

            # If elapsed time > timeout, auto-reject
            if elapsed > timeout_seconds:
                approval.status = ApprovalStatus.TIMEOUT
                approval.resolved_at = datetime.now(timezone.utc)
                approval.decision = f"Auto-rejected after {timeout_seconds}s timeout"

                await self.db.flush()

                self.logger.warning(
                    "approval_timeout_auto_rejected",
                    approval_id=str(approval_id),
                    type=approval.type,
                    elapsed_seconds=elapsed,
                    timeout_seconds=timeout_seconds,
                )

                # Send SSE notification
                if self.stream_manager:
                    await self._send_timeout_notification(approval)

                return True

            # Check if timeout warning should be sent
            remaining = timeout_seconds - elapsed
            if remaining <= self.TIMEOUT_WARNING_THRESHOLD and remaining > 0:
                self.logger.info(
                    "approval_timeout_warning",
                    approval_id=str(approval_id),
                    remaining_seconds=remaining,
                )
                if self.stream_manager:
                    await self._send_timeout_warning_notification(approval, remaining)

            return False

        except HTTPException:
            raise
        except Exception as e:
            self.logger.error("check_timeout_failed", error=str(e), approval_id=str(approval_id))
            raise HTTPException(status_code=500, detail="Failed to check timeout")

    def assess_plan_risk(
        self,
        plan: TaskPlan,
    ) -> str:
        """Assess risk level for plan.

        HIGH if:
        - Any HIGH risk task OR
        - Cost > $1.00 OR
        - Duration > 300s

        MEDIUM if:
        - Any MEDIUM risk task OR
        - Cost > $0.10 OR
        - Duration > 30s

        LOW otherwise

        Args:
            plan: TaskPlan instance

        Returns:
            Risk level: "HIGH", "MEDIUM", or "LOW"
        """
        try:
            # Check cost and duration thresholds
            if (
                plan.total_estimated_cost > self.PLAN_HIGH_RISK_COST
                or plan.total_estimated_duration > self.HIGH_RISK_DURATION_THRESHOLD
            ):
                self.logger.debug(
                    "plan_risk_high_by_cost_duration",
                    plan_id=str(plan.id),
                    cost=plan.total_estimated_cost,
                    duration=plan.total_estimated_duration,
                )
                return "HIGH"

            if (
                plan.total_estimated_cost > self.PLAN_MEDIUM_RISK_COST
                or plan.total_estimated_duration > self.MEDIUM_RISK_DURATION_THRESHOLD
            ):
                self.logger.debug(
                    "plan_risk_medium_by_cost_duration",
                    plan_id=str(plan.id),
                    cost=plan.total_estimated_cost,
                    duration=plan.total_estimated_duration,
                )
                return "MEDIUM"

            # Check task count
            task_count = len(plan.tasks) if hasattr(plan, "tasks") else 0
            if task_count >= self.PLAN_MIN_TASKS_FOR_APPROVAL:
                self.logger.debug(
                    "plan_risk_medium_by_task_count",
                    plan_id=str(plan.id),
                    task_count=task_count,
                )
                return "MEDIUM"

            self.logger.debug("plan_risk_low", plan_id=str(plan.id))
            return "LOW"

        except Exception as e:
            self.logger.error("assess_plan_risk_failed", error=str(e), plan_id=str(plan.id))
            # Default to HIGH on error for safety
            return "HIGH"

    def assess_tool_risk(
        self,
        tool_name: str,
        tool_params: dict,
    ) -> str:
        """Assess risk level for tool.

        HIGH: write_file, execute_command, delete_file, system_command
        MEDIUM: read_file (large files), list_directory, api_call, create_directory
        LOW: search, analyze, extract_info

        Args:
            tool_name: Name of the tool
            tool_params: Parameters for the tool

        Returns:
            Risk level: "HIGH", "MEDIUM", or "LOW"
        """
        try:
            tool_name_lower = tool_name.lower()

            # Check HIGH risk tools
            if any(risk_tool in tool_name_lower for risk_tool in self.HIGH_RISK_TOOLS):
                self.logger.debug("tool_risk_high", tool_name=tool_name)
                return "HIGH"

            # Check MEDIUM risk tools
            if any(risk_tool in tool_name_lower for risk_tool in self.MEDIUM_RISK_TOOLS):
                # For read_file, check if large
                if "read_file" in tool_name_lower:
                    file_size = tool_params.get("file_size", 0)
                    if file_size > 10_000_000:  # > 10MB
                        self.logger.debug("tool_risk_high_large_file", tool_name=tool_name, size=file_size)
                        return "HIGH"

                self.logger.debug("tool_risk_medium", tool_name=tool_name)
                return "MEDIUM"

            # Check LOW risk tools
            if any(risk_tool in tool_name_lower for risk_tool in self.LOW_RISK_TOOLS):
                self.logger.debug("tool_risk_low", tool_name=tool_name)
                return "LOW"

            # Default to MEDIUM for unknown tools (safe fallback)
            self.logger.debug("tool_risk_default_medium", tool_name=tool_name)
            return "MEDIUM"

        except Exception as e:
            self.logger.error("assess_tool_risk_failed", error=str(e), tool_name=tool_name)
            # Default to HIGH on error for safety
            return "HIGH"

    def should_auto_approve(
        self,
        risk_level: str,
        estimated_cost: float,
    ) -> bool:
        """Determine if operation should be auto-approved.

        Auto-approve if: risk_level == "LOW" AND cost < $0.10

        Args:
            risk_level: Risk level ("LOW", "MEDIUM", "HIGH")
            estimated_cost: Estimated cost in USD

        Returns:
            True if should auto-approve, False otherwise
        """
        should_approve = (
            risk_level == "LOW"
            and estimated_cost < self.LOW_RISK_COST_THRESHOLD
        )

        self.logger.debug(
            "should_auto_approve_evaluated",
            risk_level=risk_level,
            estimated_cost=estimated_cost,
            should_approve=should_approve,
        )

        return should_approve

    async def _send_approval_notification(
        self,
        approval: ApprovalRequest,
        event_type: StreamEventType,
        timeout: int = DEFAULT_TIMEOUT,
        tool_name: Optional[str] = None,
    ) -> None:
        """Send SSE notification for approval request.

        Args:
            approval: ApprovalRequest instance
            event_type: Type of event to send
            timeout: Timeout in seconds
            tool_name: Optional tool name for tool approvals
        """
        try:
            if not self.stream_manager:
                return

            payload = {
                "approval_id": str(approval.id),
                "type": approval.type,
                "status": approval.status,
                "payload": approval.payload,
                "timeout": timeout,
                "timestamp": time.time(),
            }

            event = StreamEvent(
                event_type=event_type,
                payload=payload,
            )

            # Broadcast to user
            sent_count = await self.stream_manager.broadcast_to_user(
                self.user_id,
                event,
                buffer=True,
            )

            self.logger.info(
                "approval_notification_sent",
                approval_id=str(approval.id),
                event_type=event_type,
                sent_to_connections=sent_count,
                tool_name=tool_name,
            )

        except Exception as e:
            self.logger.error(
                "approval_notification_failed",
                error=str(e),
                approval_id=str(approval.id),
            )

    async def _send_approval_resolved_notification(
        self,
        approval: ApprovalRequest,
        approved: bool,
    ) -> None:
        """Send SSE notification when approval is resolved.

        Args:
            approval: ApprovalRequest instance
            approved: True if approved, False if rejected
        """
        try:
            if not self.stream_manager:
                return

            payload = {
                "approval_id": str(approval.id),
                "type": approval.type,
                "status": approval.status,
                "approved": approved,
                "decision": approval.decision,
                "resolved_at": approval.resolved_at.isoformat() if approval.resolved_at else None,
                "timestamp": time.time(),
            }

            event = StreamEvent(
                event_type=StreamEventType.APPROVAL_RESOLVED,
                payload=payload,
            )

            # Broadcast to user
            sent_count = await self.stream_manager.broadcast_to_user(
                self.user_id,
                event,
                buffer=True,
            )

            self.logger.info(
                "approval_resolved_notification_sent",
                approval_id=str(approval.id),
                approved=approved,
                sent_to_connections=sent_count,
            )

        except Exception as e:
            self.logger.error(
                "approval_resolved_notification_failed",
                error=str(e),
                approval_id=str(approval.id),
            )

    async def _send_timeout_notification(
        self,
        approval: ApprovalRequest,
    ) -> None:
        """Send SSE notification when approval times out.

        Args:
            approval: ApprovalRequest instance
        """
        try:
            if not self.stream_manager:
                return

            payload = {
                "approval_id": str(approval.id),
                "type": approval.type,
                "status": approval.status,
                "message": "Approval request timed out",
                "timestamp": time.time(),
            }

            event = StreamEvent(
                event_type=StreamEventType.APPROVAL_TIMEOUT,
                payload=payload,
            )

            # Broadcast to user
            sent_count = await self.stream_manager.broadcast_to_user(
                self.user_id,
                event,
                buffer=True,
            )

            self.logger.info(
                "approval_timeout_notification_sent",
                approval_id=str(approval.id),
                sent_to_connections=sent_count,
            )

        except Exception as e:
            self.logger.error(
                "approval_timeout_notification_failed",
                error=str(e),
                approval_id=str(approval.id),
            )

    async def _send_timeout_warning_notification(
        self,
        approval: ApprovalRequest,
        remaining_seconds: float,
    ) -> None:
        """Send SSE notification when approval is about to timeout.

        Args:
            approval: ApprovalRequest instance
            remaining_seconds: Seconds remaining before timeout
        """
        try:
            if not self.stream_manager:
                return

            payload = {
                "approval_id": str(approval.id),
                "type": approval.type,
                "remaining_seconds": int(remaining_seconds),
                "message": f"Approval request will timeout in {int(remaining_seconds)}s",
                "timestamp": time.time(),
            }

            event = StreamEvent(
                event_type=StreamEventType.APPROVAL_TIMEOUT_WARNING,
                payload=payload,
            )

            # Broadcast to user
            sent_count = await self.stream_manager.broadcast_to_user(
                self.user_id,
                event,
                buffer=True,
            )

            self.logger.debug(
                "approval_timeout_warning_notification_sent",
                approval_id=str(approval.id),
                remaining_seconds=remaining_seconds,
                sent_to_connections=sent_count,
            )

        except Exception as e:
            self.logger.error(
                "approval_timeout_warning_notification_failed",
                error=str(e),
                approval_id=str(approval.id),
            )
