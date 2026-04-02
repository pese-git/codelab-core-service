"""JWKS (JSON Web Key Set) client for RS256 JWT validation."""

import asyncio
import time
import base64
import json
from typing import Any, Optional

import httpx
from jose import JWTError, jwt

from app.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)


class JWKSClient:
    """
    Асинхронный клиент для получения и кеширования JWKS от auth-service.

    Features:
    - Асинхронные HTTP запросы для получения JWKS
    - Кеширование JWKS с TTL (по умолчанию 1 час)
    - Автоматическое обновление кеша при истечении TTL
    - Fallback на кешированный JWKS при ошибках сети
    - Получение публичного ключа по Key ID (kid)
    """

    def __init__(
        self,
        jwks_url: str = settings.auth_service_jwks_url,
        cache_ttl: int = settings.jwks_cache_ttl,
        timeout: int = 10,
    ) -> None:
        """
        Инициализация JWKS клиента.

        Args:
            jwks_url: URL JWKS endpoint auth-service
            cache_ttl: TTL кеша в секундах (по умолчанию 3600 = 1 час)
            timeout: Timeout для HTTP запроса в секундах
        """
        self.jwks_url = jwks_url
        self.cache_ttl = cache_ttl
        self.timeout = timeout
        self._jwks_cache: Optional[dict[str, Any]] = None
        self._cache_timestamp: float = 0
        self._http_client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "JWKSClient":
        """Асинхронный контекстный менеджер."""
        self._http_client = httpx.AsyncClient(timeout=self.timeout)
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Закрытие асинхронного контекстного менеджера."""
        if self._http_client:
            await self._http_client.aclose()

    async def _get_http_client(self) -> httpx.AsyncClient:
        """Получить или создать HTTP клиент."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=self.timeout)
        return self._http_client

    async def _fetch_jwks(self) -> dict[str, Any]:
        """
        Получить JWKS от auth-service.

        Returns:
            JWKS словарь с публичными ключами

        Raises:
            JWTError: Если не удалось получить или спарсить JWKS
        """
        try:
            client = await self._get_http_client()
            logger.debug(
                "fetching_jwks",
                url=self.jwks_url,
            )

            response = await client.get(self.jwks_url)
            response.raise_for_status()

            jwks = response.json()
            logger.info(
                "jwks_fetched_successfully",
                url=self.jwks_url,
                keys_count=len(jwks.get("keys", [])),
            )

            return jwks

        except httpx.HTTPError as e:
            error_msg = f"HTTP error fetching JWKS: {str(e)}"
            logger.error(
                "jwks_fetch_failed",
                error=error_msg,
                url=self.jwks_url,
            )

            # Fallback на кешированный JWKS если он есть
            if self._jwks_cache:
                logger.warning(
                    "using_cached_jwks",
                    message="JWKS fetch failed, using cached version",
                )
                return self._jwks_cache

            raise JWTError(error_msg) from e

        except ValueError as e:
            error_msg = f"Invalid JWKS format: {str(e)}"
            logger.error(
                "invalid_jwks_format",
                error=error_msg,
            )

            if self._jwks_cache:
                logger.warning(
                    "using_cached_jwks",
                    message="JWKS parsing failed, using cached version",
                )
                return self._jwks_cache

            raise JWTError(error_msg) from e

    async def _refresh_cache(self) -> None:
        """Обновить кеш JWKS."""
        try:
            self._jwks_cache = await self._fetch_jwks()
            self._cache_timestamp = time.time()
            logger.debug(
                "jwks_cache_updated",
                cache_ttl=self.cache_ttl,
            )
        except JWTError as e:
            logger.error(
                "failed_to_refresh_jwks_cache",
                error=str(e),
            )
            raise

    def _is_cache_expired(self) -> bool:
        """Проверить, истек ли кеш JWKS."""
        if not self._jwks_cache:
            return True

        elapsed = time.time() - self._cache_timestamp
        return elapsed > self.cache_ttl

    async def get_jwks(self) -> dict[str, Any]:
        """
        Получить JWKS, используя кеш с автоматическим обновлением.

        Returns:
            JWKS словарь с публичными ключами
        """
        if self._is_cache_expired():
            await self._refresh_cache()

        if not self._jwks_cache:
            raise JWTError("Failed to load JWKS")

        return self._jwks_cache

    def _jwk_to_pem(self, jwk: dict[str, Any]) -> str:
        """
        Конвертировать JWK (JSON Web Key) в PEM формат.

        Args:
            jwk: JWK словарь

        Returns:
            PEM-formatted публичный ключ

        Raises:
            Exception: Если не удалось конвертировать
        """
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.backends import default_backend
        from cryptography.hazmat.primitives.asymmetric import rsa

        # Получить компоненты RSA ключа из JWK
        # добавляем padding если необходимо для base64.urlsafe_b64decode
        def decode_int(value: str) -> int:
            # Add padding if necessary
            padding = 4 - len(value) % 4
            if padding != 4:
                value += "=" * padding
            decoded = base64.urlsafe_b64decode(value)
            return int.from_bytes(decoded, "big")

        try:
            e = decode_int(jwk.get("e", "AQAB"))  # Exponent
            n = decode_int(jwk.get("n", ""))  # Modulus

            # Создать RSA публичный ключ
            public_numbers = rsa.RSAPublicNumbers(e, n)
            public_key = public_numbers.public_key(default_backend())

            # Сериализовать в PEM формат
            public_key_pem = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )

            if isinstance(public_key_pem, bytes):
                return public_key_pem.decode("utf-8")
            return public_key_pem

        except (KeyError, ValueError, Exception) as e:
            raise ValueError(f"Failed to convert JWK to PEM: {str(e)}") from e

    async def get_public_key(self, kid: str) -> str:
        """
        Получить публичный ключ по Key ID из JWKS.

        Args:
            kid: Key ID из JWT токена

        Returns:
            PEM-formatted публичный ключ

        Raises:
            JWTError: Если ключ с указанным kid не найден
        """
        try:
            jwks = await self.get_jwks()
            keys = jwks.get("keys", [])

            # Найти ключ по kid
            for key in keys:
                if key.get("kid") == kid:
                    logger.debug(
                        "public_key_found",
                        kid=kid,
                    )
                    try:
                        # Конвертировать JWK в PEM
                        public_key_pem = self._jwk_to_pem(key)
                        return public_key_pem
                    except Exception as e:
                        logger.error(
                            "failed_to_convert_jwk_to_pem",
                            kid=kid,
                            error=str(e),
                        )
                        raise

            logger.warning(
                "public_key_not_found",
                kid=kid,
                available_kids=[key.get("kid") for key in keys],
            )
            raise JWTError(f"Unable to find a signing key that matches: {kid}")

        except (JWTError, KeyError, Exception) as e:
            logger.error(
                "failed_to_get_public_key",
                kid=kid,
                error=str(e),
            )
            raise

    async def validate_token(
        self,
        token: str,
        issuer: Optional[str] = None,
        audience: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Валидировать JWT токен подписанный с помощью RS256.

        Args:
            token: JWT токен
            issuer: Ожидаемый issuer (опционально)
            audience: Ожидаемый audience (опционально)

        Returns:
            Payload токена после успешной валидации

        Raises:
            JWTError: Если токен невалидный или не прошел валидацию
        """
        try:
            # Декодировать заголовок токена без верификации
            unverified_header = jwt.get_unverified_header(token)
            kid = unverified_header.get("kid")

            if not kid:
                raise JWTError("Token header missing 'kid' claim")

            logger.debug(
                "validating_token",
                kid=kid,
            )

            # Получить публичный ключ
            public_key = await self.get_public_key(kid)

            # Подготовить параметры валидации
            options: dict[str, Any] = {}
            verify_kwargs: dict[str, Any] = {
                "algorithms": ["RS256"],
            }

            if issuer:
                verify_kwargs["issuer"] = issuer

            if audience:
                verify_kwargs["audience"] = audience

            # Валидировать токен
            payload = jwt.decode(
                token,
                public_key,
                options=options,
                **verify_kwargs,
            )

            logger.info(
                "token_validated_successfully",
                kid=kid,
                sub=payload.get("sub"),
            )

            return payload

        except JWTError as e:
            logger.warning(
                "token_validation_failed",
                error=str(e),
            )
            raise

    async def close(self) -> None:
        """Закрыть HTTP клиент."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None


# Глобальный экземпляр JWKS клиента
_jwks_client: Optional[JWKSClient] = None


async def get_jwks_client() -> JWKSClient:
    """
    Получить глобальный экземпляр JWKS клиента.

    Returns:
        JWKSClient экземпляр
    """
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = JWKSClient()
    return _jwks_client


async def close_jwks_client() -> None:
    """Закрыть глобальный экземпляр JWKS клиента."""
    global _jwks_client
    if _jwks_client:
        await _jwks_client.close()
        _jwks_client = None
