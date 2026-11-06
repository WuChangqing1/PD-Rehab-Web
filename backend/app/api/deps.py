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
    request: Request,
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
    if user.role == 'PATIENT':
        from app.api.mobile_auth import identity
        from app.db.models.mobile_account import MobileSession
        from app.db.base import utcnow
        session = db.get(MobileSession, payload.get('sid')) if payload.get('sid') else None
        if (payload.get('client') != 'mobile' or session is None or session.user_id != user.id
                or session.revoked or session.expires_at <= utcnow()):
            raise unauthorized()
        identity(db, user)
        # Reject all staff/Web routes before their handler can run.
        import re
        path = request.url.path.removeprefix('/api')
        allowed = {
            ('GET', '/mobile/auth/me'), ('POST', '/mobile/auth/change-password'),
            ('POST', '/integration/v1/bindings'), ('POST', '/integration/v1/records'),
            ('GET', '/integration/v1/records'), ('GET', '/integration/v1/patient-data'),
            ('GET', '/integration/v1/changes'), ('GET', '/integration/v1/capabilities'),
        }
        capture = re.fullmatch(r'/integration/v1/face/recordings(?:/[A-Za-z0-9-]+(?:/files/[A-Za-z0-9-]+/chunks/[0-9]+|/complete|/cancel|/retry|/segments)?)?', path)
        if (request.method, path) not in allowed and not (capture and request.method in ('GET', 'POST', 'PUT', 'DELETE')):
            raise forbidden('普通用户不能访问工作人员功能。')
    from app.services.integration_access import install_request_scope
    install_request_scope(db,user)
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
