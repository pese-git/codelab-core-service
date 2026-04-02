"""User isolation middleware."""

from typing import Callable
from uuid import UUID

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from jose import JWTError, jwt
from starlette.middleware.base import BaseHTTPMiddleware
from redis.exceptions import ConnectionError as RedisConnectionError

from app.config import settings
from app.logging_config import get_logger
from app.schemas.error import ErrorResponse
from app.services.jwks_client import get_jwks_client

logger = get_logger(__name__)


class UserIsolationMiddleware(BaseHTTPMiddleware):
    """Middleware to enforce user isolation across all requests."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Response]
    ) -> Response:
        """Process request and inject user context."""
        # Skip middleware for non-protected routes
        if not request.url.path.startswith("/my/"):
            return await call_next(request)

        # Skip for docs and health endpoints
        if request.url.path in ["/my/docs", "/my/openapi.json", "/health", "/ready"]:
            return await call_next(request)

        try:
            # Extract JWT token from Authorization header
            auth_header = request.headers.get("Authorization")
            if not auth_header or not auth_header.startswith("Bearer "):
                logger.warning(
                    "missing_authorization_header",
                    path=request.url.path,
                    method=request.method,
                )
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content=ErrorResponse(
                        detail="Missing or invalid Authorization header",
                        error_code="UNAUTHORIZED",
                    ).model_dump(mode='json'),
                )

            token = auth_header.split(" ")[1]

            # Validate JWT token with RS256 using JWKS
            user_id_str = None
            try:
                # Get JWKS client and validate token
                jwks_client = await get_jwks_client()
                payload = await jwks_client.validate_token(
                    token,
                    issuer=settings.jwt_issuer,
                    audience=settings.jwt_audience,
                )

                user_id_str = payload.get("sub")
                user_email = payload.get("email")
                if not user_id_str:
                    raise JWTError("Missing 'sub' claim in token")

                # Validate token type
                token_type = payload.get("type", "access")
                if token_type not in ("access", "refresh"):
                    raise JWTError(f"Invalid token type: {token_type}")

                # Convert to UUID
                user_id = UUID(user_id_str)
                
                # Extract JTI for blacklist check
                token_jti = payload.get("jti")
                token_exp = payload.get("exp")

            except JWTError as e:
                logger.warning(
                    "invalid_jwt_token",
                    error=str(e),
                    path=request.url.path,
                    method=request.method,
                )
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content=ErrorResponse(
                        detail="Invalid or expired token",
                        error_code="INVALID_TOKEN",
                    ).model_dump(mode='json'),
                )
            except ValueError as e:
                logger.warning(
                    "invalid_user_id_format",
                    error=str(e),
                    user_id=user_id_str,
                )
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content=ErrorResponse(
                        detail="Invalid user ID format",
                        error_code="INVALID_USER_ID",
                    ).model_dump(mode='json'),
                )

            # Check if token is blacklisted (revoked)
            if token_jti and settings.use_token_blacklist:
                try:
                    # Dynamically import to avoid circular imports
                    from app.services.token_blacklist_service import (
                        get_token_blacklist_service
                    )
                    
                    blacklist_service = await get_token_blacklist_service()
                    is_revoked = await blacklist_service.is_token_revoked(token_jti)
                    
                    if is_revoked:
                        logger.warning(
                            "revoked_token_used",
                            user_id=str(user_id),
                            token_jti=token_jti,
                            path=request.url.path,
                            method=request.method,
                        )
                        return JSONResponse(
                            status_code=status.HTTP_401_UNAUTHORIZED,
                            content=ErrorResponse(
                                detail="Token has been revoked",
                                error_code="REVOKED_TOKEN",
                            ).model_dump(mode='json'),
                        )

                except RedisConnectionError:
                    # Graceful degradation: log error and continue
                    # Token is still valid by JWT signature and exp claim
                    logger.warning(
                        "redis_unavailable_for_blacklist_check",
                        user_id=str(user_id),
                        token_jti=token_jti,
                    )
                    # Don't fail the request - rely on JWT exp claim

                except RuntimeError:
                    # Blacklist service not initialized - log and continue
                    logger.warning(
                        "token_blacklist_service_not_initialized",
                        user_id=str(user_id),
                    )

            # Inject user context into request state
            request.state.user_id = user_id
            request.state.user_email = user_email
            request.state.user_prefix = f"user{user_id}"
            request.state.db_filter = {"user_id": user_id}
            request.state.token_jti = token_jti
            request.state.token_exp = token_exp

            logger.info(
                "user_authenticated",
                user_id=str(user_id),
                path=request.url.path,
                method=request.method,
            )

            # Process request
            response = await call_next(request)
            return response

        except Exception as e:
            logger.error(
                "middleware_error",
                error=str(e),
                path=request.url.path,
                method=request.method,
            )
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content=ErrorResponse(
                    detail="Internal server error",
                    error_code="INTERNAL_ERROR",
                ).model_dump(mode='json'),
            )


def get_current_user_id(request: Request) -> UUID:
    """Get current user ID from request state."""
    if not hasattr(request.state, "user_id"):
        raise ValueError("User ID not found in request state")
    return request.state.user_id


def get_user_prefix(request: Request) -> str:
    """Get user prefix from request state."""
    if not hasattr(request.state, "user_prefix"):
        raise ValueError("User prefix not found in request state")
    return request.state.user_prefix


def get_db_filter(request: Request) -> dict[str, UUID]:
    """Get database filter from request state."""
    if not hasattr(request.state, "db_filter"):
        raise ValueError("DB filter not found in request state")
    return request.state.db_filter
