"""Approval management endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.approval_manager import ApprovalManager
from app.core.user_worker_space import UserWorkerSpace
from app.database import get_db
from app.dependencies import get_worker_space
from app.logging_config import get_logger
from app.middleware.user_isolation import get_current_user_id
from app.models.approval_request import ApprovalRequest
from app.models.task_plan import TaskPlan
from app.schemas.approval import (
    ApprovalDecisionRequest,
    ApprovalListResponse,
    ApprovalResponse,
)

logger = get_logger(__name__)
router = APIRouter(prefix="/my/approvals", tags=["approvals"])


@router.get("/", response_model=ApprovalListResponse)
async def list_approvals(
    request: Request,
    status_filter: str | None = None,
    offset: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
) -> ApprovalListResponse:
    """List approval requests for current user.

    Args:
        request: FastAPI request
        status_filter: Optional status filter (pending, approved, rejected, timeout)
        offset: Pagination offset
        limit: Pagination limit
        db: Database session

    Returns:
        List of approval requests with pagination

    Raises:
        HTTPException 400: If invalid status filter
    """
    user_id = get_current_user_id(request)

    logger.info(
        "list_approvals_requested",
        user_id=str(user_id),
        status_filter=status_filter,
        offset=offset,
        limit=limit,
    )

    # Build query
    query = select(ApprovalRequest).where(ApprovalRequest.user_id == user_id)

    # Apply status filter if provided
    if status_filter:
        valid_statuses = ["pending", "approved", "rejected", "timeout"]
        if status_filter not in valid_statuses:
            logger.warning(
                "invalid_status_filter",
                user_id=str(user_id),
                status_filter=status_filter,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status filter. Must be one of: {', '.join(valid_statuses)}",
            )
        query = query.where(ApprovalRequest.status == status_filter)

    # Get total count
    count_query = select(func.count(ApprovalRequest.id)).where(
        ApprovalRequest.user_id == user_id
    )
    if status_filter:
        count_query = count_query.where(ApprovalRequest.status == status_filter)

    count_result = await db.execute(count_query)
    total = count_result.scalar()

    # Apply pagination
    query = query.order_by(ApprovalRequest.created_at.desc()).offset(offset).limit(limit)

    # Execute query
    result = await db.execute(query)
    approvals = result.scalars().all()

    logger.info(
        "approvals_retrieved",
        user_id=str(user_id),
        count=len(approvals),
        total=total,
    )

    # Convert to response
    approvals_response = [
        ApprovalResponse(
            id=approval.id,
            type=approval.type,
            payload=approval.payload,
            status=approval.status,
            created_at=approval.created_at,
            resolved_at=approval.resolved_at,
            decision=approval.decision,
        )
        for approval in approvals
    ]

    return ApprovalListResponse(
        approvals=approvals_response,
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get("/{approval_id}", response_model=ApprovalResponse)
async def get_approval(
    approval_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> ApprovalResponse:
    """Get approval request details.

    Args:
        approval_id: Approval request UUID from path
        request: FastAPI request
        db: Database session

    Returns:
        Approval request details

    Raises:
        HTTPException 404: If approval not found
    """
    user_id = get_current_user_id(request)

    logger.info(
        "get_approval_requested",
        user_id=str(user_id),
        approval_id=str(approval_id),
    )

    # Load approval request
    result = await db.execute(
        select(ApprovalRequest).where(ApprovalRequest.id == approval_id)
    )
    approval = result.scalar_one_or_none()

    if not approval:
        logger.warning(
            "approval_not_found",
            user_id=str(user_id),
            approval_id=str(approval_id),
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Approval request not found",
        )

    # Check user ownership
    if approval.user_id != user_id:
        logger.warning(
            "approval_access_denied",
            user_id=str(user_id),
            approval_id=str(approval_id),
            owner_id=str(approval.user_id),
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    logger.info(
        "approval_retrieved",
        user_id=str(user_id),
        approval_id=str(approval_id),
        status=approval.status,
    )

    return ApprovalResponse(
        id=approval.id,
        type=approval.type,
        payload=approval.payload,
        status=approval.status,
        created_at=approval.created_at,
        resolved_at=approval.resolved_at,
        decision=approval.decision,
    )


@router.post("/{approval_id}/confirm", response_model=ApprovalResponse)
async def confirm_approval(
    approval_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    workspace: UserWorkerSpace = Depends(get_worker_space),
) -> ApprovalResponse:
    """User confirms approval.

    Args:
        approval_id: Approval request UUID from path
        request: FastAPI request
        db: Database session
        workspace: User worker space

    Returns:
        Updated approval request

    Raises:
        HTTPException 404: If approval not found
        HTTPException 400: If approval already resolved
        HTTPException 403: If user is not the approval owner
        HTTPException 410: If approval has timed out
        HTTPException 500: If confirmation fails
    """
    user_id = get_current_user_id(request)

    logger.info(
        "confirm_approval_requested",
        user_id=str(user_id),
        approval_id=str(approval_id),
    )

    try:
        # Create ApprovalManager
        approval_manager = ApprovalManager(
            user_id=user_id,
            project_id=None,  # Not needed for confirm/reject
            db=db,
            stream_manager=workspace.stream_manager,
        )

        # Confirm approval
        approval = await approval_manager.confirm_approval(approval_id)

        # Check user ownership after confirmation
        if approval.user_id != user_id:
            logger.warning(
                "approval_access_denied",
                user_id=str(user_id),
                approval_id=str(approval_id),
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied",
            )

        logger.info(
            "approval_confirmed",
            user_id=str(user_id),
            approval_id=str(approval_id),
        )

        return ApprovalResponse(
            id=approval.id,
            type=approval.type,
            payload=approval.payload,
            status=approval.status,
            created_at=approval.created_at,
            resolved_at=approval.resolved_at,
            decision=approval.decision,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "confirm_approval_error",
            approval_id=str(approval_id),
            user_id=str(user_id),
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to confirm approval",
        )


@router.post("/{approval_id}/reject", response_model=ApprovalResponse)
async def reject_approval(
    approval_id: UUID,
    decision: ApprovalDecisionRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    workspace: UserWorkerSpace = Depends(get_worker_space),
) -> ApprovalResponse:
    """User rejects approval.

    Args:
        approval_id: Approval request UUID from path
        decision: Rejection decision with optional reason
        request: FastAPI request
        db: Database session
        workspace: User worker space

    Returns:
        Updated approval request

    Raises:
        HTTPException 404: If approval not found
        HTTPException 400: If approval already resolved
        HTTPException 403: If user is not the approval owner
        HTTPException 410: If approval has timed out
        HTTPException 500: If rejection fails
    """
    user_id = get_current_user_id(request)

    logger.info(
        "reject_approval_requested",
        user_id=str(user_id),
        approval_id=str(approval_id),
        reason=decision.reason,
    )

    try:
        # Create ApprovalManager
        approval_manager = ApprovalManager(
            user_id=user_id,
            project_id=None,  # Not needed for confirm/reject
            db=db,
            stream_manager=workspace.stream_manager,
        )

        # Reject approval
        approval = await approval_manager.reject_approval(approval_id, decision.reason)

        # Check user ownership after rejection
        if approval.user_id != user_id:
            logger.warning(
                "approval_access_denied",
                user_id=str(user_id),
                approval_id=str(approval_id),
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied",
            )

        # If approval is for a plan, update plan status to rejected
        if approval.type.value == "plan" and approval.payload:
            plan_id_str = approval.payload.get("plan_id")
            if plan_id_str:
                try:
                    plan_id = UUID(plan_id_str)
                    plan_result = await db.execute(
                        select(TaskPlan).where(TaskPlan.id == plan_id)
                    )
                    plan = plan_result.scalar_one_or_none()
                    if plan:
                        plan.status = "rejected"
                        await db.flush()
                        logger.info(
                            "plan_status_updated_to_rejected",
                            plan_id=str(plan_id),
                            approval_id=str(approval_id),
                        )
                except (ValueError, Exception) as e:
                    logger.warning(
                        "failed_to_update_plan_status",
                        plan_id_str=plan_id_str,
                        error=str(e),
                    )

        logger.info(
            "approval_rejected",
            user_id=str(user_id),
            approval_id=str(approval_id),
        )

        return ApprovalResponse(
            id=approval.id,
            type=approval.type,
            payload=approval.payload,
            status=approval.status,
            created_at=approval.created_at,
            resolved_at=approval.resolved_at,
            decision=approval.decision,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "reject_approval_error",
            approval_id=str(approval_id),
            user_id=str(user_id),
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reject approval",
        )
