"""Authentication dependencies and helpers."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ErrorCode, forbidden, unauthorized
from app.core.security import decode_access_token
from app.db.models import StaffUser
from app.db.session import get_db

# auto_error=False so we can emit our own unified error envelope.
_bearer = HTTPBearer(auto_error=False)

DbSession = Annotated[Session, Depends(get_db)]


def get_current_user(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)] = None,
) -> StaffUser:
    if credentials is None or not credentials.credentials:
        raise unauthorized(
            "未提供登录凭证，请先登录。",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_access_token(credentials.credentials)
    user = db.execute(
        select(StaffUser).where(StaffUser.id == payload["sub"])
    ).scalar_one_or_none()
    if user is None:
        raise unauthorized("账号不存在，请重新登录。")
    if not user.is_active:
        raise unauthorized("账号已被停用。", code=ErrorCode.INACTIVE_USER)
    return user


CurrentUser = Annotated[StaffUser, Depends(get_current_user)]


def require_admin(user: CurrentUser) -> StaffUser:
    if user.role != "ADMIN":
        raise forbidden("该操作仅限管理员。")
    return user


AdminUser = Annotated[StaffUser, Depends(require_admin)]


def client_ip(request: Request) -> str | None:
    if request.client:
        return request.client.host
    return None
