"""REST API routes для feedback и scores в Langfuse."""

from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.logging_config import get_logger
from app.middleware.user_isolation import get_current_user_id
from app.services.langfuse_rest_client import get_langfuse_rest_client
from app.services.traces_service import get_traces_service

logger = get_logger(__name__)

router = APIRouter(prefix="/traces", tags=["feedback"])


class ScoreRequest(BaseModel):
    """Запрос для записи score."""

    score_name: str = Field(..., description="Имя score (например, user_satisfaction)")
    score_value: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Значение score (0.0-1.0)",
    )
    comment: Optional[str] = Field(None, description="Опциональный комментарий")


class ScoreResponse(BaseModel):
    """Ответ при успешной записи score."""

    success: bool
    trace_id: str
    score_name: str
    score_value: float
    message: str


@router.post(
    "/{trace_id}/scores",
    name="record_trace_score",
    response_model=ScoreResponse,
)
async def record_trace_score(
    trace_id: str,
    request: ScoreRequest,
    current_user_id: UUID = Depends(get_current_user_id),
    db_session: AsyncSession = Depends(get_db),
) -> ScoreResponse:
    """
    Записать score (оценку) для trace.

    Args:
        trace_id: ID trace
        request: ScoreRequest с параметрами score

    Returns:
        ScoreResponse с результатом операции
    """
    try:
        # Проверяем что trace принадлежит пользователю (через workspace_id)
        traces_service = get_traces_service()

        # Получаем trace для проверки прав доступа
        trace = await traces_service.get_trace_by_id(trace_id)

        if not trace:
            logger.warning(
                "trace_not_found_for_score",
                trace_id=trace_id,
                user_id=str(current_user_id),
            )
            raise HTTPException(
                status_code=404,
                detail=f"Trace {trace_id} not found",
            )

        # Записываем score через REST API клиент
        rest_client = get_langfuse_rest_client()

        success = await rest_client.record_score(
            trace_id=trace_id,
            score_name=request.score_name,
            score_value=request.score_value,
            comment=request.comment,
        )

        if not success:
            logger.error(
                "score_recording_failed",
                trace_id=trace_id,
                score_name=request.score_name,
                user_id=str(current_user_id),
            )
            raise HTTPException(
                status_code=500,
                detail="Failed to record score",
            )

        logger.info(
            "trace_score_recorded",
            trace_id=trace_id,
            score_name=request.score_name,
            score_value=request.score_value,
            user_id=str(current_user_id),
        )

        return ScoreResponse(
            success=True,
            trace_id=trace_id,
            score_name=request.score_name,
            score_value=request.score_value,
            message="Score recorded successfully",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "score_recording_error",
            error=str(e),
            trace_id=trace_id,
            user_id=str(current_user_id),
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to record score",
        ) from e


@router.get(
    "/{trace_id}/scores",
    name="get_trace_scores",
)
async def get_trace_scores(
    trace_id: str,
    current_user_id: UUID = Depends(get_current_user_id),
    db_session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Получить все scores для trace.

    Args:
        trace_id: ID trace

    Returns:
        Словарь с list of scores
    """
    try:
        traces_service = get_traces_service()

        # Получаем trace для проверки прав доступа
        trace = await traces_service.get_trace_by_id(trace_id)

        if not trace:
            logger.warning(
                "trace_not_found_for_scores",
                trace_id=trace_id,
                user_id=str(current_user_id),
            )
            raise HTTPException(
                status_code=404,
                detail=f"Trace {trace_id} not found",
            )

        # Langfuse хранит scores в trace data
        scores = trace.get("scores", []) if trace else []

        logger.info(
            "trace_scores_retrieved",
            trace_id=trace_id,
            score_count=len(scores),
            user_id=str(current_user_id),
        )

        return {
            "trace_id": trace_id,
            "scores": scores,
            "count": len(scores),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "scores_retrieval_error",
            error=str(e),
            trace_id=trace_id,
            user_id=str(current_user_id),
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve scores",
        ) from e
