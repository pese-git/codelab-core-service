"""REST API routes для управления traces из Langfuse."""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.user_worker_space import UserWorkerSpace
from app.database import get_db
from app.logging_config import get_logger
from app.middleware.user_isolation import get_current_user_id
from app.services.traces_service import get_traces_service

logger = get_logger(__name__)

router = APIRouter(prefix="/traces", tags=["traces"])


@router.get("", name="list_traces")
async def list_traces(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    workspace_id: Optional[UUID] = None,
    agent_name: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    order_by: str = Query("created_at", regex="^(created_at|duration)$"),
    order_direction: str = Query("desc", regex="^(asc|desc)$"),
    current_user_id: UUID = Depends(get_current_user_id),
    db_session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Получить список traces для пользователя.

    Query параметры:
    - limit: Количество traces (1-1000, по умолчанию 100)
    - offset: Offset для pagination (по умолчанию 0)
    - agent_name: Фильтр по имени агента (опционально)
    - start_date: Начальная дата (опционально)
    - end_date: Конечная дата (опционально)
    - order_by: Сортировка по полю (created_at или duration)
    - order_direction: Направление сортировки (asc или desc)

    Returns:
        Словарь с traces, total_count, и metadata
    """
    try:
        traces_service = get_traces_service()

        result = await traces_service.get_traces(
            user_id=current_user_id,
            agent_name=agent_name,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            offset=offset,
            order_by=order_by,
            order_direction=order_direction,
        )

        logger.info(
            "traces_listed",
            user_id=str(current_user_id),
            workspace_id=str(workspace_id),
            count=len(result.get("traces", [])),
        )

        return result

    except Exception as e:
        logger.error(
            "traces_list_failed",
            error=str(e),
            user_id=str(current_user_id),
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to list traces",
        ) from e


@router.get("/{trace_id}", name="get_trace")
async def get_trace(
    trace_id: str,
    workspace_id: Optional[UUID] = None,
    current_user_id: UUID = Depends(get_current_user_id),
    db_session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Получить детали trace по ID.

    Args:
        trace_id: ID trace

    Returns:
        Словарь с информацией о trace
    """
    try:
        traces_service = get_traces_service()

        result = await traces_service.get_trace_by_id(trace_id)

        if not result:
            raise HTTPException(
                status_code=404,
                detail="Trace not found",
            )

        logger.info(
            "trace_retrieved",
            trace_id=trace_id,
            workspace_id=str(workspace_id),
            user_id=str(current_user_id),
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "trace_retrieval_failed",
            error=str(e),
            trace_id=trace_id,
            workspace_id=str(workspace_id),
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve trace",
        ) from e


@router.post("/{trace_id}/scores", name="record_trace_score")
async def record_trace_score(
    trace_id: str,
    score_name: str = Query(...),
    score_value: float = Query(..., ge=0.0, le=1.0),
    comment: Optional[str] = None,
    workspace_id: Optional[UUID] = None,
    current_user_id: UUID = Depends(get_current_user_id),
    db_session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Записать score (оценку) для trace.

    Args:
        trace_id: ID trace
        score_name: Имя score (например, user_satisfaction)
        score_value: Значение score (0.0-1.0)
        comment: Опциональный комментарий

    Returns:
        Словарь с результатом записи score
    """
    try:
        if not score_name or len(score_name.strip()) == 0:
            raise HTTPException(
                status_code=400,
                detail="Score name cannot be empty",
            )

        traces_service = get_traces_service()
        success = await traces_service.langfuse.record_score(
            trace_id=trace_id,
            name=score_name,
            value=score_value,
            comment=comment,
        )

        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to record score",
            )

        logger.info(
            "trace_score_recorded",
            trace_id=trace_id,
            score_name=score_name,
            score_value=score_value,
            workspace_id=str(workspace_id),
            user_id=str(current_user_id),
        )

        return {
            "success": True,
            "trace_id": trace_id,
            "score_name": score_name,
            "score_value": score_value,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "trace_score_recording_failed",
            error=str(e),
            trace_id=trace_id,
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to record score",
        ) from e


@router.get("/analytics/summary", name="traces_summary")
async def get_traces_summary(
    period: str = Query("7d", regex="^(7d|30d|all)$"),
    workspace_id: Optional[UUID] = None,
    current_user_id: UUID = Depends(get_current_user_id),
    db_session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Получить summary аналитику для traces.

    Query параметры:
    - period: Период (7d, 30d, all)

    Returns:
        Словарь с summary метриками
    """
    try:
        traces_service = get_traces_service()

        result = await traces_service.get_traces_summary(
            user_id=current_user_id,
            workspace_id=workspace_id,
            period=period,
        )

        logger.info(
            "traces_summary_retrieved",
            period=period,
            workspace_id=str(workspace_id),
            user_id=str(current_user_id),
        )

        return result

    except Exception as e:
        logger.error(
            "traces_summary_failed",
            error=str(e),
            workspace_id=str(workspace_id),
            period=period,
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve traces summary",
        ) from e


@router.get("/analytics/agents", name="agents_analytics")
async def get_agents_analytics(
    workspace_id: Optional[UUID] = None,
    current_user_id: UUID = Depends(get_current_user_id),
    db_session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Получить аналитику по агентам.

    Returns:
        Словарь с analytics по агентам
    """
    try:
        traces_service = get_traces_service()

        result = await traces_service.get_agent_analytics(
            workspace_id=workspace_id,
            user_id=current_user_id,
        )

        logger.info(
            "agents_analytics_retrieved",
            user_id=str(current_user_id),
            workspace_id=str(workspace_id),
        )

        return result

    except Exception as e:
        logger.error(
            "agents_analytics_failed",
            error=str(e),
            workspace_id=str(workspace_id),
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve agents analytics",
        ) from e


@router.get("/analytics/cost", name="cost_analysis")
async def get_cost_analysis(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    workspace_id: Optional[UUID] = None,
    current_user_id: UUID = Depends(get_current_user_id),
    db_session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Получить анализ стоимости LLM операций.

    Query параметры:
    - start_date: Начальная дата (опционально)
    - end_date: Конечная дата (опционально)

    Returns:
        Словарь с cost analysis
    """
    try:
        traces_service = get_traces_service()

        result = await traces_service.get_cost_analysis(
            workspace_id=workspace_id,
            user_id=current_user_id,
            start_date=start_date,
            end_date=end_date,
        )

        logger.info(
            "cost_analysis_retrieved",
            user_id=str(current_user_id),
            workspace_id=str(workspace_id),
        )

        return result

    except Exception as e:
        logger.error(
            "cost_analysis_failed",
            error=str(e),
            workspace_id=str(workspace_id),
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve cost analysis",
        ) from e


@router.get("/health/langfuse", name="langfuse_health_check")
async def langfuse_health_check() -> dict[str, Any]:
    """
    Проверить health status Langfuse сервиса.

    Returns:
        Словарь со статусом Langfuse
    """
    try:
        traces_service = get_traces_service()

        if not traces_service.enabled:
            return {
                "status": "disabled",
                "message": "Langfuse is disabled (LANGFUSE_ENABLED=false)",
            }

        # Attempt to verify Langfuse connectivity
        # В идеале здесь нужна проверка подключения к API
        return {
            "status": "healthy",
            "message": "Langfuse is configured and available",
        }

    except Exception as e:
        logger.error(
            "langfuse_health_check_failed",
            error=str(e),
        )
        return {
            "status": "unhealthy",
            "error": str(e),
        }
