"""Password hashing and JWT helpers.

Uses `bcrypt` directly rather than passlib's CryptContext: passlib 1.7.4 reads
`bcrypt.__about__.__version__`, which was removed in bcrypt 4.1+, and the
resulting warning path is fragile. Calling bcrypt directly is simpler.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings
from app.core.errors import ErrorCode, unauthorized

# bcrypt only considers the first 72 bytes of a password.
_BCRYPT_MAX_BYTES = 72


def _truncate(password: str) -> bytes:
    return password.encode("utf-8")[:_BCRYPT_MAX_BYTES]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_truncate(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    if not plain or not hashed:
        return False
    try:
        return bcrypt.checkpw(_truncate(plain), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(
    subject: str,
    *,
    role: str | None = None,
    expires_minutes: int | None = None,
    extra: dict[str, Any] | None = None,
) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(
        minutes=expires_minutes or settings.access_token_expire_minutes
    )
    payload: dict[str, Any] = {
        "sub": str(subject),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "typ": "access",
    }
    if role:
        payload["role"] = role
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
    except JWTError as exc:  # expired / malformed / bad signature
        raise unauthorized(
            "登录状态无效或已过期，请重新登录。",
            code=ErrorCode.NOT_AUTHENTICATED,
            detail={"reason": str(exc)},
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    if payload.get("typ") != "access" or not payload.get("sub"):
        raise unauthorized(headers={"WWW-Authenticate": "Bearer"})
    return payload
