# Authentication Middleware Specification

**Версия:** 1.0.0  
**Статус:** ✅ Production Ready  
**Дата обновления:** 29 марта 2026

---

## 📋 Обзор

Authentication Middleware — компонент, отвечающий за:
1. **Извлечение JWT токена** из HTTP запроса
2. **Валидацию токена** через JWKS клиент
3. **Инъекцию user context** в request для использования в handlers
4. **Обработку ошибок аутентификации** с понятными сообщениями

**Локация:** [`app/middleware/user_isolation.py`](../../../app/middleware/user_isolation.py)

---

## 🔄 Жизненный цикл запроса

### Схема обработки запроса

```
HTTP Request
    ↓
[1] Извлечь Authorization header
    ↓
[2] Разбить "Bearer <token>"
    ↓
[3] Получить заголовок токена → kid
    ↓
[4] Получить публичный ключ через JWKS
    ↓
[5] Валидировать подпись RS256
    ↓
[6] Проверить claims (iss, aud, exp, type)
    ↓
[7] Инъекция user context в request.state
    ↓
[8] Переход к handler
    ↓
HTTP Response
```

---

## 🔐 Шаги обработки

### Шаг 1: Извлечение Authorization Header

```python
def extract_token_from_header(request: Request) -> Optional[str]:
    """Извлечь JWT токен из Authorization header"""
    auth_header = request.headers.get("Authorization")
    
    if not auth_header:
        return None
    
    # Ожидаем формат: "Bearer <token>"
    parts = auth_header.split()
    
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=401,
            detail="Invalid Authorization header format. Expected: Bearer <token>"
        )
    
    return parts[1]  # Вернуть сам токен
```

**Ожидаемый формат:**

```
Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6IjIwMjQtMDEta2V5LTEifQ.eyJpc3MiOiJodHRwczovL2F1dGguY29kZWxhYi5sb2NhbCIsInN1YiI6IjU1MGU4NDAwLWUyOWItNDFkNC1hNzE2LTQ0NjY1NTQ0MDAwMCJ9...
                   ↑                                                                                                                                   ↑
                   Префикс "Bearer"                                                                                                           JWT токен
```

**Возможные ошибки:**

| Ошибка | HTTP Статус | Сообщение |
|--------|------------|-----------|
| Нет Authorization header | 401 | `"Missing Authorization header"` |
| Неверный формат | 401 | `"Invalid Authorization header format"` |
| Неверный префикс | 401 | `"Authorization header must start with 'Bearer'"` |

### Шаг 2: Декодирование заголовка токена (без проверки подписи)

```python
from jose import jwt

def get_token_header(token: str) -> dict:
    """
    Получить заголовок JWT БЕЗ проверки подписи
    (чтобы узнать kid и алгоритм)
    """
    try:
        header = jwt.get_unverified_header(token)
        # header = {
        #   "alg": "RS256",
        #   "typ": "JWT",
        #   "kid": "2024-01-key-1"
        # }
        return header
    except JWTError as e:
        raise HTTPException(
            status_code=401,
            detail="Invalid token format"
        )
```

**Важно:** Это **не валидирует** подпись! Используется только для получения `kid`.

### Шаг 3: Получение Key ID (kid)

```python
def get_kid_from_token(token: str) -> str:
    """Получить Key ID (kid) из заголовка токена"""
    header = get_token_header(token)
    
    kid = header.get("kid")
    
    if not kid:
        raise HTTPException(
            status_code=401,
            detail="Token missing 'kid' header"
        )
    
    return kid
```

**Назначение:** `kid` указывает, какой публичный ключ использовать для проверки подписи (нужно для ротации ключей).

### Шаг 4: Получение публичного ключа

```python
async def get_public_key_from_jwks(kid: str) -> str:
    """Получить публичный ключ из JWKS по Key ID"""
    jwks_client = get_jwks_client()
    
    try:
        public_key = await jwks_client.get_public_key(kid)
        return public_key
    except JWTError:
        raise HTTPException(
            status_code=401,
            detail="Token key not found in JWKS (key may have been rotated)"
        )
    except Exception as e:
        logger.error(f"Failed to get public key: {e}")
        raise HTTPException(
            status_code=503,
            detail="Authentication service temporarily unavailable"
        )
```

**Процесс:**

```
kid = "2024-01-key-1"
    ↓
Запросить JWKS от auth-service
    ↓
Найти ключ с kid = "2024-01-key-1" в JWKS
    ↓
Вернуть публичный ключ в PEM формате
```

### Шаг 5: Валидация подписи RS256

```python
def validate_token_signature(
    token: str,
    public_key: str,
    issuer: str,
    audience: str
) -> dict:
    """Валидировать подпись и claims JWT токена"""
    try:
        payload = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],  # ✅ Только RS256
            audience=audience,      # ✅ Должна совпадать
            issuer=issuer,         # ✅ Должна совпадать
            options={
                "verify_signature": True,  # ✅ Проверить подпись
                "verify_exp": True,        # ✅ Проверить истечение
                "verify_aud": True,        # ✅ Проверить аудиторию
                "verify_iss": True,        # ✅ Проверить издателя
            }
        )
        return payload
        
    except JWTError as e:
        error_message = str(e)
        
        if "expired" in error_message.lower():
            raise HTTPException(
                status_code=401,
                detail="Token has expired"
            )
        elif "signature" in error_message.lower():
            raise HTTPException(
                status_code=401,
                detail="Invalid token signature"
            )
        elif "audience" in error_message.lower():
            raise HTTPException(
                status_code=401,
                detail="Token audience mismatch"
            )
        elif "issuer" in error_message.lower():
            raise HTTPException(
                status_code=401,
                detail="Token issuer mismatch"
            )
        else:
            raise HTTPException(
                status_code=401,
                detail="Token validation failed"
            )
```

**Что проверяется:**

| Проверка | Значение | Описание |
|----------|---------|---------|
| **Алгоритм** | `RS256` | Только RSA + SHA-256 |
| **Подпись** | Валидна | Подпись верна для данного публичного ключа |
| **Издатель** | `https://auth.codelab.local` | Токен выдан auth-service |
| **Аудитория** | `codelab-api` | Токен предназначен для этого сервиса |
| **Истечение** | `exp > now` | Токен ещё не истёк |

### Шаг 6: Проверка типа токена

```python
def validate_token_type(payload: dict) -> None:
    """Проверить, что это access token, а не refresh"""
    token_type = payload.get("type")
    
    if token_type == "refresh":
        raise HTTPException(
            status_code=401,
            detail="Cannot use refresh token for API access. Use access token instead."
        )
    
    if token_type != "access":
        raise HTTPException(
            status_code=401,
            detail=f"Unsupported token type: {token_type}"
        )
```

**Назначение:** Refresh tokens предназначены только для получения новых access tokens, их нельзя использовать для доступа к API.

### Шаг 7: Инъекция User Context

```python
def inject_user_context(request: Request, payload: dict) -> None:
    """
    Инъекция информации о пользователе в request.state
    для использования в handlers
    """
    # Извлечь user_id из claim "sub" (UUID)
    user_id = payload.get("sub")
    
    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="Token missing 'sub' claim (user ID)"
        )
    
    # Валидировать, что это UUID
    try:
        uuid.UUID(user_id)  # Проверить формат UUID
    except ValueError:
        raise HTTPException(
            status_code=401,
            detail="Invalid user ID format in token"
        )
    
    # Сохранить в request.state для использования в handlers
    request.state.user_id = user_id
    request.state.token_payload = payload
    
    # Опционально: префикс для Redis ключей (изоляция по пользователю)
    request.state.user_prefix = f"user:{user_id}:"
    
    # Опционально: фильтр для БД запросов
    request.state.db_filter = {"user_id": user_id}
    
    logger.debug(
        "user_context_injected",
        user_id=user_id,
        path=request.url.path
    )
```

**Сохраняется в `request.state`:**

| Ключ | Тип | Описание |
|------|-----|---------|
| `user_id` | str (UUID) | Уникальный идентификатор пользователя |
| `token_payload` | dict | Полный payload токена |
| `user_prefix` | str | Префикс для Redis ключей (`user:{id}:`) |
| `db_filter` | dict | Фильтр для SQL запросов (`{"user_id": id}`) |

**Использование в handlers:**

```python
from fastapi import Request

@router.get("/my/projects")
async def get_my_projects(request: Request):
    """Получить проекты текущего пользователя"""
    user_id = request.state.user_id  # Извлечь из request.state
    
    # Использовать user_id для фильтрации данных
    projects = db.query(Project).filter_by(user_id=user_id).all()
    
    return {"projects": projects}
```

---

## 🔌 Middleware реализация

### Полная реализация Middleware

**Файл:** [`app/middleware/user_isolation.py`](../../../app/middleware/user_isolation.py)

```python
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from jose import jwt, JWTError
import logging

from app.config import settings
from app.services.jwks_client import get_jwks_client

logger = logging.getLogger(__name__)

class AuthenticationMiddleware(BaseHTTPMiddleware):
    """
    Middleware для валидации JWT токенов и инъекции user context
    """
    
    # Публичные endpoints, которые не требуют аутентификации
    PUBLIC_PATHS = {
        "/docs",
        "/openapi.json",
        "/health",
        "/ready",
        "/.well-known/",
        "/oauth/",
        "/api/v1/auth/",
    }
    
    async def dispatch(self, request: Request, call_next):
        """Обработать запрос"""
        try:
            # Пропустить публичные endpoints
            if self._is_public_path(request.url.path):
                return await call_next(request)
            
            # Требуется аутентификация для /my/* endpoints
            if request.url.path.startswith("/my/"):
                await self._authenticate_request(request)
            
            return await call_next(request)
            
        except HTTPException as e:
            logger.warning(f"Authentication failed: {e.detail}")
            return JSONResponse(
                status_code=e.status_code,
                content={"error": e.detail}
            )
        except Exception as e:
            logger.error(f"Unexpected error in auth middleware: {e}")
            return JSONResponse(
                status_code=500,
                content={"error": "Internal server error"}
            )
    
    def _is_public_path(self, path: str) -> bool:
        """Проверить, является ли path публичным"""
        for public_path in self.PUBLIC_PATHS:
            if path.startswith(public_path):
                return True
        return False
    
    async def _authenticate_request(self, request: Request) -> None:
        """Аутентифицировать запрос"""
        # Шаг 1: Извлечь токен из Authorization header
        auth_header = request.headers.get("Authorization")
        
        if not auth_header:
            raise HTTPException(
                status_code=401,
                detail="Missing Authorization header"
            )
        
        # Разделить "Bearer <token>"
        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            raise HTTPException(
                status_code=401,
                detail="Invalid Authorization header format"
            )
        
        token = parts[1]
        
        # Шаг 2: Получить kid из заголовка токена (без проверки подписи)
        try:
            header = jwt.get_unverified_header(token)
        except JWTError:
            raise HTTPException(
                status_code=401,
                detail="Invalid token format"
            )
        
        kid = header.get("kid")
        if not kid:
            raise HTTPException(
                status_code=401,
                detail="Token missing 'kid' in header"
            )
        
        # Шаг 3: Получить публичный ключ через JWKS клиент
        jwks_client = get_jwks_client()
        
        try:
            public_key = await jwks_client.get_public_key(kid)
        except JWTError:
            raise HTTPException(
                status_code=401,
                detail="Token key not found"
            )
        
        # Шаг 4: Валидировать токен
        try:
            payload = jwt.decode(
                token,
                public_key,
                algorithms=["RS256"],
                audience=settings.jwt_audience,
                issuer=settings.jwt_issuer,
                options={
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_aud": True,
                    "verify_iss": True,
                }
            )
        except JWTError as e:
            raise HTTPException(
                status_code=401,
                detail=f"Token validation failed: {str(e)}"
            )
        
        # Шаг 5: Проверить тип токена
        token_type = payload.get("type")
        if token_type != "access":
            raise HTTPException(
                status_code=401,
                detail=f"Invalid token type: {token_type}"
            )
        
        # Шаг 6: Инъекция user context
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=401,
                detail="Token missing 'sub' claim"
            )
        
        request.state.user_id = user_id
        request.state.token_payload = payload
        request.state.user_prefix = f"user:{user_id}:"
        request.state.db_filter = {"user_id": user_id}
        
        logger.debug(f"User authenticated: {user_id}")
```

### Регистрация Middleware в приложении

**Файл:** [`app/main.py`](../../../app/main.py)

```python
from fastapi import FastAPI
from app.middleware.user_isolation import AuthenticationMiddleware

app = FastAPI()

# Регистрировать middleware
app.add_middleware(AuthenticationMiddleware)

# Остальной код приложения...
```

---

## 🛡️ Обработка ошибок

### Таблица ошибок аутентификации

| Ошибка | HTTP Статус | Сообщение | Действие |
|--------|------------|-----------|---------|
| Missing header | 401 | `Missing Authorization header` | Добавить Authorization header |
| Invalid format | 401 | `Invalid Authorization header format` | Использовать формат `Bearer <token>` |
| Invalid token format | 401 | `Invalid token format` | Запросить новый токен |
| Token expired | 401 | `Token has expired` | Использовать refresh token |
| Invalid signature | 401 | `Invalid token signature` | Токен поддельный |
| Audience mismatch | 401 | `Token audience mismatch` | Токен для другого сервиса |
| Issuer mismatch | 401 | `Token issuer mismatch` | Токен от другого издателя |
| Key not found | 401 | `Token key not found` | Ключ был удалён (ротация) |
| Missing sub claim | 401 | `Token missing 'sub' claim` | Некорректный токен |
| JWKS unavailable | 503 | `Authentication service unavailable` | Повторить позже |

### Примеры ответов

#### Успешная аутентификация

```http
GET /my/projects HTTP/1.1
Host: api.codelab.local
Authorization: Bearer eyJhbGciOiJSUzI1NiIs...

HTTP/1.1 200 OK
Content-Type: application/json

{
  "projects": [...]
}
```

#### Ошибка: Нет заголовка

```http
GET /my/projects HTTP/1.1
Host: api.codelab.local

HTTP/1.1 401 Unauthorized
Content-Type: application/json

{
  "error": "Missing Authorization header"
}
```

#### Ошибка: Истёкший токен

```http
GET /my/projects HTTP/1.1
Host: api.codelab.local
Authorization: Bearer eyJhbGciOiJSUzI1NiIs...

HTTP/1.1 401 Unauthorized
Content-Type: application/json

{
  "error": "Token has expired"
}
```

---

## 📊 Диаграмма потока

```
┌─────────────────────────────────────────────┐
│         HTTP Request                        │
│   GET /my/projects                          │
│   Authorization: Bearer <token>             │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
        ┌──────────────────────┐
        │  AuthenticationMiddleware
        │   dispatch()
        └──────┬───────────────┘
               │
               ├─ Публичный path? ──YES──▶ Пропустить
               │                          middleware
               │
               NO
               │
               ├─ /my/* path? ──NO──▶ Пропустить
               │                     middleware
               │
               YES
               │
               ▼
      ┌────────────────────┐
      │ Шаг 1: Извлечь     │
      │ Authorization      │
      │ header             │
      └────────┬───────────┘
               │
               ▼
      ┌────────────────────┐
      │ Шаг 2: Получить    │
      │ kid из заголовка   │
      │ токена             │
      └────────┬───────────┘
               │
               ▼
      ┌────────────────────┐
      │ Шаг 3: Получить    │
      │ публичный ключ из  │
      │ JWKS               │
      └────────┬───────────┘
               │
               ▼
      ┌────────────────────┐
      │ Шаг 4: Валидировать│
      │ подпись RS256      │
      └────────┬───────────┘
               │
               ▼
      ┌────────────────────┐
      │ Шаг 5: Проверить   │
      │ тип токена         │
      │ (access/refresh)   │
      └────────┬───────────┘
               │
               ▼
      ┌────────────────────┐
      │ Шаг 6: Инъекция    │
      │ user context в     │
      │ request.state      │
      └────────┬───────────┘
               │
               ▼
      ┌──────────────────────────┐
      │ Передать запрос к handler│
      └──────────────────────────┘
               │
               ▼
      ┌──────────────────────────┐
      │ HTTP Response             │
      │ (с данными пользователя) │
      └──────────────────────────┘
```

---

## 🔗 Использование User Context в Handlers

### Пример 1: Получить текущего пользователя

```python
from fastapi import Request

@router.get("/my/profile")
async def get_my_profile(request: Request):
    """Получить профиль текущего пользователя"""
    user_id = request.state.user_id  # UUID из token.sub
    
    user = db.query(User).filter_by(id=user_id).first()
    return user
```

### Пример 2: Фильтрация данных по пользователю

```python
@router.get("/my/projects")
async def get_my_projects(request: Request):
    """Получить проекты текущего пользователя"""
    user_id = request.state.user_id
    
    projects = db.query(Project)\
        .filter(Project.user_id == user_id)\
        .all()
    
    return {"projects": projects}
```

### Пример 3: Логирование с user_id

```python
import logging

logger = logging.getLogger(__name__)

@router.post("/my/projects")
async def create_project(request: Request, project_data: ProjectCreate):
    """Создать новый проект"""
    user_id = request.state.user_id
    
    logger.info(f"Creating project for user {user_id}", extra={
        "user_id": user_id,
        "project_name": project_data.name
    })
    
    project = Project(
        user_id=user_id,
        name=project_data.name
    )
    db.add(project)
    db.commit()
    
    return project
```

### Пример 4: Зависимость FastAPI для user_id

```python
from fastapi import Depends, Request

def get_current_user_id(request: Request) -> str:
    """Dependency для получения user_id текущего пользователя"""
    return request.state.user_id

@router.get("/my/profile")
async def get_my_profile(
    user_id: str = Depends(get_current_user_id)
):
    """Получить профиль используя dependency"""
    user = db.query(User).filter_by(id=user_id).first()
    return user
```

---

## ⚙️ Конфигурация

```python
# app/config.py

# JWT Configuration
JWT_ISSUER: str = "https://auth.codelab.local"
JWT_AUDIENCE: str = "codelab-api"
AUTH_SERVICE_JWKS_URL: str = "http://codelab-auth-service:8003/.well-known/jwks.json"
JWKS_CACHE_TTL: int = 3600  # 1 час
```

---

## 📚 Ссылки

- [FastAPI Middleware](https://fastapi.tiangolo.com/advanced/middleware/)
- [Starlette Middleware](https://www.starlette.io/middleware/)
- [PyJWT Documentation](https://pyjwt.readthedocs.io/)

---

## 🔗 Связанная документация

- Auth Service: [`jwt-rs256-integration.md`](../../codelab-auth-service/openspec/specs/jwt-rs256-integration.md)
- Core Service: [`jwt-validation/spec.md`](../jwt-validation/spec.md)
- Core Service: [`integration-with-auth-service/spec.md`](../integration-with-auth-service/spec.md)
