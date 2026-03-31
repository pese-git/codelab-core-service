# Спецификация: Token Blacklist Integration в Middleware

**Версия:** 1.0.0  
**Дата:** 31 марта 2026  
**Сервис:** codelab-core-service

---

## 📋 Назначение компонента

**Token Blacklist Integration** — интеграция проверки отозванных токенов в [`UserIsolationMiddleware`](../../middleware/user_isolation.py). Обеспечивает немедленную блокировку использования revoked токенов в core-service, поддерживая согласованность с auth-service.

### Ключевые функции

- 🔐 **Проверка blacklist** для каждого запроса перед обработкой
- ⚡ **Быстрая проверка** (O(1) Redis EXISTS, <10ms)
- 🛡️ **Graceful degradation** если Redis недоступен (rely на exp)
- 📝 **Логирование** попыток использования revoked токенов
- 🔄 **Fallback механизм** при ошибках подключения к Redis

---

## 🔌 API (Интерфейсы)

### Middleware Integration Point

```python
class UserIsolationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        """
        Процесс обработки:
        1. Extract JWT token from Authorization header
        2. Validate JWT signature (JWKS)
        3. ✨ NEW: Check if token in blacklist (Redis)
        4. Inject user_id to request.state
        5. Process request
        """
```

### Middleware Flow Diagram

```
Request
  │
  ├─ Extract Authorization header
  │   └─ Format: "Bearer {token}"
  │
  ├─ Parse JWT (without validation yet)
  │   └─ Extract: jti, sub, exp
  │
  ├─ Validate JWT signature via JWKS
  │   └─ Check: signature, issuer, audience, expiration
  │
  ├─ ✨ NEW: Check Token Blacklist
  │   ├─ Get blacklist_service
  │   ├─ Call is_token_revoked(jti)
  │   ├─ If TRUE (revoked)
  │   │   └─ Return 401 Unauthorized
  │   └─ If FALSE (active)
  │       └─ Continue
  │
  ├─ Inject user context to request.state
  │   ├─ user_id = UUID(payload["sub"])
  │   ├─ user_email = payload.get("email")
  │   ├─ token_jti = payload.get("jti")
  │   └─ token_exp = payload.get("exp")
  │
  ├─ Call next handler
  │
  └─ Return response
```

---

## 🔄 Примеры использования

### Пример 1: Middleware Implementation

```python
from app.services.token_blacklist_service import get_token_blacklist_service
from app.services.jwks_client import get_jwks_client

class UserIsolationMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        """Process request with token blacklist check"""
        
        # Skip middleware for public routes
        if not request.url.path.startswith("/my/"):
            return await call_next(request)
        
        try:
            # Extract JWT token
            auth_header = request.headers.get("Authorization")
            if not auth_header or not auth_header.startswith("Bearer "):
                logger.warning("missing_authorization_header")
                return JSONResponse(
                    status_code=401,
                    content={"error": "Missing Authorization header"}
                )
            
            token = auth_header.split(" ")[1]
            
            # Validate JWT signature
            jwks_client = await get_jwks_client()
            payload = await jwks_client.validate_token(
                token,
                issuer=settings.jwt_issuer,
                audience=settings.jwt_audience
            )
            
            user_id_str = payload.get("sub")
            token_jti = payload.get("jti")
            
            if not user_id_str or not token_jti:
                raise JWTError("Missing required claims")
            
            # ✨ NEW: Check if token in blacklist
            if settings.use_token_blacklist:
                try:
                    blacklist_service = await get_token_blacklist_service()
                    is_revoked = await blacklist_service.is_token_revoked(token_jti)
                    
                    if is_revoked:
                        logger.warning(
                            "revoked_token_used",
                            user_id=user_id_str,
                            token_jti=token_jti,
                            path=request.url.path
                        )
                        return JSONResponse(
                            status_code=401,
                            content={"error": "Token has been revoked"}
                        )
                
                except RedisConnectionError:
                    # Graceful degradation: rely on exp claim
                    logger.error("redis_unavailable_for_blacklist_check")
                    # Token will be valid until exp, risk but system stays up
            
            # Token is valid, inject user context
            request.state.user_id = UUID(user_id_str)
            request.state.token_jti = token_jti
            request.state.token_exp = payload.get("exp")
            request.state.user_email = payload.get("email")
            
            # Process request
            response = await call_next(request)
            return response
        
        except JWTError as e:
            logger.warning("invalid_jwt_token", error=str(e))
            return JSONResponse(
                status_code=401,
                content={"error": "Invalid or expired token"}
            )
```

### Пример 2: Error Response Format

```python
# 401 Response when token is revoked
{
    "detail": "Token has been revoked",
    "error_code": "TOKEN_REVOKED",
    "status_code": 401
}

# 401 Response when Redis unavailable (fallback to exp)
# Token will work if not yet expired, even if Redis down

# 401 Response on JWT validation error
{
    "detail": "Invalid or expired token",
    "error_code": "INVALID_TOKEN",
    "status_code": 401
}
```

---

## ⚠️ Обработка ошибок

### Сценарий 1: Redis недоступен

```python
try:
    is_revoked = await blacklist_service.is_token_revoked(jti)
except RedisConnectionError:
    logger.error("redis_unavailable_for_blacklist_check")
    # Fallback: rely only on JWT exp claim
    # Token is valid if not expired
    is_revoked = False  # Assume not revoked
    # ⚠️ ALERT: должна быть отправлена в мониторинг
```

### Сценарий 2: Missing JTI claim

```python
jti = payload.get("jti")
if not jti:
    logger.warning("missing_jti_claim_in_token")
    # Можно:
    # Option 1: Fail (require jti)
    # raise JWTError("Missing 'jti' claim")
    # Option 2: Skip blacklist check
    is_revoked = False
```

### Сценарий 3: Blacklist service не инициализирована

```python
try:
    blacklist_service = await get_token_blacklist_service()
except RuntimeError:
    logger.error("blacklist_service_not_initialized")
    # Fallback
    is_revoked = False
```

---

## 🧪 Тесты

### Unit Test 1: Valid token (not revoked)

```python
@pytest.mark.asyncio
async def test_valid_token_allowed(client, token_not_revoked):
    """Test that valid (not revoked) token is allowed"""
    
    headers = {"Authorization": f"Bearer {token_not_revoked}"}
    response = await client.get("/my/projects", headers=headers)
    
    assert response.status_code == 200
```

### Unit Test 2: Revoked token blocked

```python
@pytest.mark.asyncio
async def test_revoked_token_blocked(client, blacklist_service, token_revoked):
    """Test that revoked token is blocked"""
    
    # Revoke token
    await blacklist_service.revoke_token(
        token_jti=token_revoked.jti,
        user_id="user-123",
        exp_timestamp=int(time.time()) + 3600
    )
    
    # Try to use revoked token
    headers = {"Authorization": f"Bearer {token_revoked}"}
    response = await client.get("/my/projects", headers=headers)
    
    assert response.status_code == 401
    assert "revoked" in response.json()["detail"].lower()
```

### Unit Test 3: Redis unavailable fallback

```python
@pytest.mark.asyncio
async def test_redis_unavailable_fallback(
    client, token, mock_redis_down
):
    """Test graceful degradation when Redis is down"""
    
    # Mock Redis connection error
    with patch("app.services.token_blacklist_service.get_token_blacklist_service") as mock:
        mock.side_effect = RedisConnectionError("Connection failed")
        
        # Token should still work (fallback to exp)
        headers = {"Authorization": f"Bearer {token}"}
        response = await client.get("/my/projects", headers=headers)
        
        # If token not expired, should work
        if token_not_expired:
            assert response.status_code == 200
```

### Unit Test 4: Missing JTI claim

```python
@pytest.mark.asyncio
async def test_token_without_jti(client, token_without_jti):
    """Test token without jti claim"""
    
    # Depending on implementation:
    # Either fail or skip blacklist check
    headers = {"Authorization": f"Bearer {token_without_jti}"}
    response = await client.get("/my/projects", headers=headers)
    
    # Should either fail or work with fallback
    assert response.status_code in [200, 401]
```

---

## 📋 Acceptance Criteria

- ✅ Revoked токен возвращает 401 Unauthorized
- ✅ Active токен пропускается через middleware
- ✅ Redis недоступен → graceful fallback (rely на exp)
- ✅ Logging: revoked token attempts залогированы
- ✅ Performance: blacklist check < 10ms
- ✅ Missing JTI обрабатывается (fail или skip)
- ✅ Unit тесты: 100% coverage
- ✅ Error responses содержат правильные codes
- ✅ Middleware не падает при Redis error
- ✅ Integration тесты: full flow работает

---

## 🔗 Связанные компоненты

- [`TokenBlacklistService`](../../../codelab-auth-service/openspec/changes/2026-03-31-implement-user-sync-events/specs/token-blacklist-service/spec.md)
- [`EventConsumer`](../event-consumer/spec.md) — потребляет user.deleted события
- [`UserIsolationMiddleware`](../../middleware/user_isolation.py) — основной файл
