"""Health check endpoints."""

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.config import settings
from app.logging_config import get_logger
from app.services.langfuse_rest_client import LangfuseRestClient

logger = get_logger(__name__)
router = APIRouter(tags=["health"])


@router.get("/health", status_code=status.HTTP_200_OK)
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}


@router.get("/ready", status_code=status.HTTP_200_OK)
async def readiness_check() -> dict[str, str]:
    """Readiness check endpoint."""
    return {"status": "ready"}


@router.get("/health/langfuse")
async def langfuse_health_check() -> JSONResponse:
    """
    Health check endpoint для Langfuse интеграции.
    
    Проверяет connectivity и availability Langfuse сервиса.
    
    Returns:
        JSONResponse с status и optional error message:
        - {status: "healthy"} - HTTP 200 если Langfuse доступен
        - {status: "unhealthy", error: "..."} - HTTP 503 если недоступен
        - {status: "disabled"} - HTTP 200 если Langfuse отключен в конфигурации
    """
    # Если Langfuse отключен в конфигурации
    if not settings.langfuse_enabled:
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"status": "disabled", "message": "Langfuse disabled in configuration"},
        )
    
    try:
        # Проверяем connectivity через REST API клиент
        client = LangfuseRestClient(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            base_url=settings.langfuse_host,
        )
        
        # Проверяем доступность Langfuse
        is_healthy = await client.check_health()
        
        if is_healthy:
            logger.info("langfuse_health_check_passed")
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={"status": "healthy"},
            )
        else:
            logger.warning("langfuse_health_check_failed")
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"status": "unhealthy", "error": "Langfuse service unavailable"},
            )
    
    except Exception as e:
        error_msg = str(e)
        logger.error(
            "langfuse_health_check_error",
            error=error_msg,
        )
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "error": f"Failed to check Langfuse health: {error_msg}",
            },
        )
