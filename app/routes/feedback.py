"""REST API routes для записи feedback и scores в Langfuse."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from app.logging_config import get_logger
from app.middleware.user_isolation import get_current_user_id
from app.services.langfuse_integration import get_langfuse

logger = get_logger(__name__)

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("/traces/{trace_id}/rating")
async def rate_trace(
    trace_id: str,
    rating: int = Query(..., ge=1, le=5, description="Оценка от 1 до 5"),
    comment: Optional[str] = Query(None, description="Опциональный комментарий"),
    current_user_id: UUID = Depends(get_current_user_id),
):
    """
    Оценить качество trace/ответа агента.

    Args:
        trace_id: ID trace для оценки
        rating: Оценка (1-5 звезд)
        comment: Опциональный комментарий

    Returns:
        Результат записи оценки
    """
    try:
        if not trace_id or len(trace_id.strip()) == 0:
            raise HTTPException(
                status_code=400,
                detail="Trace ID cannot be empty",
            )

        if not 1 <= rating <= 5:
            raise HTTPException(
                status_code=400,
                detail="Rating must be between 1 and 5",
            )

        langfuse = get_langfuse()

        # Нормализовать rating к 0-1 (1 star = 0.2, 5 stars = 1.0)
        normalized_score = rating / 5.0

        success = langfuse.record_score(
            trace_id=trace_id,
            name="user_satisfaction",
            value=normalized_score,
            comment=comment,
        )

        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to record rating",
            )

        logger.info(
            "trace_rating_recorded",
            trace_id=trace_id,
            rating=rating,
            user_id=str(current_user_id),
        )

        return {
            "success": True,
            "trace_id": trace_id,
            "rating": rating,
            "normalized_score": normalized_score,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "trace_rating_failed",
            trace_id=trace_id,
            error=str(e),
            user_id=str(current_user_id),
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to record rating",
        ) from e


@router.post("/traces/{trace_id}/thumbs")
async def thumbs_feedback(
    trace_id: str,
    thumbs_up: bool = Query(
        ..., description="True для одобрения, False для неодобрения"
    ),
    current_user_id: UUID = Depends(get_current_user_id),
):
    """
    Простой thumbs up/down feedback для trace.

    Args:
        trace_id: ID trace
        thumbs_up: True если лайк, False если дизлайк

    Returns:
        Результат записи feedback
    """
    try:
        if not trace_id or len(trace_id.strip()) == 0:
            raise HTTPException(
                status_code=400,
                detail="Trace ID cannot be empty",
            )

        langfuse = get_langfuse()

        # Thumbs up = 1.0, Thumbs down = 0.0
        score = 1.0 if thumbs_up else 0.0

        success = langfuse.record_score(
            trace_id=trace_id,
            name="thumbs",
            value=score,
            comment="thumbs_up" if thumbs_up else "thumbs_down",
        )

        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to record feedback",
            )

        logger.info(
            "trace_thumbs_recorded",
            trace_id=trace_id,
            thumbs_up=thumbs_up,
            user_id=str(current_user_id),
        )

        return {
            "success": True,
            "trace_id": trace_id,
            "thumbs_up": thumbs_up,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "trace_thumbs_failed",
            trace_id=trace_id,
            error=str(e),
            user_id=str(current_user_id),
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to record feedback",
        ) from e


@router.post("/traces/{trace_id}/scores/{score_name}")
async def record_custom_score(
    trace_id: str,
    score_name: str,
    score_value: float = Query(..., ge=0.0, le=1.0, description="Значение от 0.0 до 1.0"),
    comment: Optional[str] = Query(None, description="Опциональный комментарий"),
    current_user_id: UUID = Depends(get_current_user_id),
):
    """
    Записать пользовательскую оценку для trace.

    Args:
        trace_id: ID trace
        score_name: Имя оценки (например, "relevance", "accuracy")
        score_value: Значение оценки (0.0-1.0)
        comment: Опциональный комментарий

    Returns:
        Результат записи оценки
    """
    try:
        if not trace_id or len(trace_id.strip()) == 0:
            raise HTTPException(
                status_code=400,
                detail="Trace ID cannot be empty",
            )

        if not score_name or len(score_name.strip()) == 0:
            raise HTTPException(
                status_code=400,
                detail="Score name cannot be empty",
            )

        if not 0.0 <= score_value <= 1.0:
            raise HTTPException(
                status_code=400,
                detail="Score value must be between 0.0 and 1.0",
            )

        langfuse = get_langfuse()

        success = langfuse.record_score(
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
            trace_id=trace_id,
            score_name=score_name,
            error=str(e),
            user_id=str(current_user_id),
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to record score",
        ) from e
