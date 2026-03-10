"""REST API endpoints for LLM provider management."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.user_isolation import get_current_user_id
from app.schemas.llm_provider import (
    LLMProviderAuditLogListResponse,
    LLMProviderCreate,
    LLMProviderListResponse,
    LLMProviderResponse,
    LLMProviderTestRequest,
    LLMProviderTestResponse,
    LLMProviderTypeInfo,
    LLMProviderUpdate,
    get_provider_types,
)
from app.services.llm_provider_service import (
    LLMProviderInUseError,
    LLMProviderNotFoundError,
    LLMProviderService,
)

private_router = APIRouter(prefix="/my/llm-providers", tags=["llm-providers"])
public_router = APIRouter(prefix="/llm-providers", tags=["llm-providers"])

# Alias for backward compatibility
router = private_router


# ==================== CREATE ====================
@private_router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=LLMProviderResponse,
)
async def create_llm_provider(
    provider_data: LLMProviderCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> LLMProviderResponse:
    """
    Создаёт новый LLM провайдер для пользователя.
    
    Требует аутентификации.
    
    Args:
        provider_data: Данные для создания провайдера (provider_type, display_name, api_key, config)
        request: HTTP request
        db: Database session
        
    Returns:
        Созданный провайдер
        
    Raises:
        HTTPException: Если ошибка при создании
    """
    user_id = get_current_user_id(request)
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    try:
        service = LLMProviderService(db)
        provider = await service.create_user_provider(
            user_id=user_id,
            provider_type=provider_data.provider_type.value,
            display_name=provider_data.display_name,
            api_key=provider_data.api_key,
            config=provider_data.config,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        await db.commit()
        return LLMProviderResponse.model_validate(provider)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create provider: {str(e)}",
        )


# ==================== LIST ====================
@private_router.get("", response_model=LLMProviderListResponse)
async def list_llm_providers(
    request: Request,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
) -> LLMProviderListResponse:
    """
    Получает список LLM провайдеров пользователя.
    
    Требует аутентификации.
    
    Args:
        request: HTTP request
        skip: Количество записей для пропуска (пагинация)
        limit: Максимум записей (пагинация, макс 100)
        db: Database session
        
    Returns:
        Список провайдеров с пагинацией
    """
    user_id = get_current_user_id(request)
    limit = min(limit, 100)  # Max 100 items per page

    try:
        service = LLMProviderService(db)
        providers, total = await service.get_user_providers(
            user_id=user_id,
            limit=limit,
            offset=skip,
        )

        return LLMProviderListResponse(
            providers=[LLMProviderResponse.model_validate(p) for p in providers],
            total=total,
            page=skip // limit + 1 if limit > 0 else 1,
            page_size=limit,
            total_pages=(total + limit - 1) // limit if limit > 0 else 1,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list providers: {str(e)}",
        )


# ==================== SPECIFIC PATHS (before parameterized paths) ====================
@private_router.get("/available", response_model=LLMProviderListResponse)
async def get_available_llm_providers(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> LLMProviderListResponse:
    """
    Получает доступные провайдеры пользователя (активные и готовые к использованию).
    
    Требует аутентификации.
    
    Args:
        request: HTTP request
        db: Database session
        
    Returns:
        Список доступных провайдеров
    """
    user_id = get_current_user_id(request)

    try:
        service = LLMProviderService(db)
        providers, total = await service.get_user_providers(
            user_id=user_id,
            limit=1000,
        )

        return LLMProviderListResponse(
            providers=[LLMProviderResponse.model_validate(p) for p in providers],
            total=total,
            page=1,
            page_size=total,
            total_pages=1,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get available providers: {str(e)}",
        )


@private_router.get("/audit", response_model=LLMProviderAuditLogListResponse)
async def get_provider_audit_log(
    request: Request,
    db: AsyncSession = Depends(get_db),
    provider_id: str | None = Query(None),
    action: str | None = Query(None),
    skip: int = Query(0),
    limit: int = Query(100),
) -> LLMProviderAuditLogListResponse:
    """
    Получает audit log операций с провайдерами.
    
    Требует аутентификации.
    
    Args:
        provider_id: Фильтр по ID провайдера (опционально)
        action: Фильтр по типу действия (опционально)
        skip: Количество записей для пропуска
        limit: Максимум записей
        request: HTTP request
        db: Database session
        
    Returns:
        Audit log с пагинацией
    """
    user_id = get_current_user_id(request)
    limit = min(max(1, limit), 100)  # Ensure limit is between 1 and 100
    skip = max(0, skip)  # Ensure skip is >= 0

    try:
        # Convert provider_id string to UUID if provided
        provider_id_uuid = None
        if provider_id:
            try:
                provider_id_uuid = UUID(provider_id)
            except (ValueError, TypeError):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid provider_id format: {provider_id}",
                )

        from app.services.llm_provider_audit_service import LLMProviderAuditService

        audit_service = LLMProviderAuditService(db)
        logs, total = await audit_service.get_audit_log(
            user_id=user_id,
            provider_id=provider_id_uuid,
            action=action,
            limit=limit,
            offset=skip,
        )

        from app.schemas.llm_provider import LLMProviderAuditLogEntry

        return LLMProviderAuditLogListResponse(
            entries=[LLMProviderAuditLogEntry.model_validate(log) for log in logs],
            total=total,
            page=skip // limit + 1 if limit > 0 else 1,
            page_size=limit,
            total_pages=(total + limit - 1) // limit if limit > 0 else 1,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get audit log: {str(e)}",
        )


# ==================== PARAMETERIZED PATHS (after specific paths) ====================
@private_router.post("/{provider_id}/test", response_model=LLMProviderTestResponse)
async def test_llm_provider(
    provider_id: UUID,
    test_request: LLMProviderTestRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> LLMProviderTestResponse:
    """
    Тестирует подключение к LLM провайдеру.
    
    Требует аутентификации.
    
    Args:
        provider_id: UUID провайдера
        test_request: Параметры теста (test_prompt, max_tokens)
        request: HTTP request
        db: Database session
        
    Returns:
        Результат теста (success, response, error, latency_ms)
        
    Raises:
        HTTPException: Если провайдер не найден
    """
    user_id = get_current_user_id(request)
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    try:
        service = LLMProviderService(db)
        result = await service.test_provider(
            user_id=user_id,
            provider_id=provider_id,
            test_prompt=test_request.test_prompt,
            max_tokens=test_request.max_tokens,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        await db.commit()
        return LLMProviderTestResponse(**result)
    except LLMProviderNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Provider {provider_id} not found",
        )
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to test provider: {str(e)}",
        )


@private_router.get("/{provider_id}", response_model=LLMProviderResponse)
async def get_llm_provider(
    provider_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> LLMProviderResponse:
    """
    Получает конкретный LLM провайдер.
    
    Требует аутентификации.
    
    Args:
        provider_id: UUID провайдера
        request: HTTP request
        db: Database session
        
    Returns:
        Данные провайдера
        
    Raises:
        HTTPException: Если провайдер не найден
    """
    user_id = get_current_user_id(request)

    try:
        service = LLMProviderService(db)
        provider = await service.get_user_provider(user_id=user_id, provider_id=provider_id)
        return LLMProviderResponse.model_validate(provider)
    except LLMProviderNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Provider {provider_id} not found",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get provider: {str(e)}",
        )


@private_router.patch("/{provider_id}", response_model=LLMProviderResponse)
async def update_llm_provider(
    provider_id: UUID,
    update_data: LLMProviderUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> LLMProviderResponse:
    """
    Обновляет конфигурацию LLM провайдера.
    
    ВАЖНО: API ключ НЕ может быть изменён.
    Для смены ключа нужно удалить и пересоздать провайдер.
    
    Требует аутентификации.
    
    Args:
        provider_id: UUID провайдера
        update_data: Данные для обновления (display_name, config)
        request: HTTP request
        db: Database session
        
    Returns:
        Обновлённый провайдер
        
    Raises:
        HTTPException: Если провайдер не найден
    """
    user_id = get_current_user_id(request)
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    try:
        service = LLMProviderService(db)
        provider = await service.update_user_provider(
            user_id=user_id,
            provider_id=provider_id,
            display_name=update_data.display_name,
            config=update_data.config,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        await db.commit()
        return LLMProviderResponse.model_validate(provider)
    except LLMProviderNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Provider {provider_id} not found",
        )
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update provider: {str(e)}",
        )


@private_router.delete("/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_llm_provider(
    provider_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Удаляет LLM провайдер.
    
    Требует аутентификации.
    
    Args:
        provider_id: UUID провайдера
        request: HTTP request
        db: Database session
        
    Raises:
        HTTPException: Если провайдер не найден или используется агентами
    """
    user_id = get_current_user_id(request)
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    try:
        service = LLMProviderService(db)
        await service.delete_user_provider(
            user_id=user_id,
            provider_id=provider_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        await db.commit()
    except LLMProviderNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Provider {provider_id} not found",
        )
    except LLMProviderInUseError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete provider: {str(e)}",
        )


# ==================== PUBLIC ROUTES ====================
@public_router.get("/types", response_model=list[LLMProviderTypeInfo])
async def get_provider_types_list() -> list[LLMProviderTypeInfo]:
    """
    Получает список доступных типов LLM провайдеров.
    
    ПУБЛИЧНЫЙ endpoint (без аутентификации).
    
    Returns:
        Список типов провайдеров с информацией о каждом
    """
    return get_provider_types()
