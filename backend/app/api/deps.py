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


def validate_mobile_session(db, user, claims):
    """Session revocation is checked even for non-Bearer media capabilities."""
    from app.api.mobile_auth import identity
    from app.db.models.mobile_account import MobileSession
    from app.db.base import utcnow
    session = db.get(MobileSession, claims.get('sid'), populate_existing=True) if claims.get('sid') else None
    if (claims.get('client') != 'mobile' or session is None or session.user_id != user.id
            or session.revoked or session.expires_at <= utcnow()):
        raise unauthorized()
    identity(db, user)


def patient_endpoint_allowed(method: str, path: str):
    import re
    fixed = {
        ('GET', '/mobile/auth/identities'),
        ('POST', '/mobile/auth/identities/sms/challenge'),
        ('POST', '/mobile/auth/identities/sms/bind'),
        ('POST', '/mobile/auth/identities/wechat/challenge'),
        ('POST', '/mobile/auth/identities/wechat/bind'),
        ('GET', '/mobile/auth/me'), ('POST', '/mobile/auth/change-password'),
        ('GET', '/integration/v1/bootstrap'), ('POST', '/integration/v1/bindings'),
        ('POST', '/integration/v1/records'), ('GET', '/integration/v1/records'),
        ('GET', '/integration/v1/plans'), ('GET', '/integration/v1/patient-data'),
        ('GET', '/integration/v1/changes'), ('GET', '/integration/v1/capabilities'),
        ('POST', '/integration/v1/expert/chat'), ('POST', '/integration/v1/face/jobs'),
    }
    if (method, path) in fixed:
        return True
    uid = r'[0-9a-fA-F-]{36}'
    rules = (
        ('GET', rf'/integration/v1/records/{uid}'),
        ('DELETE', rf'/integration/v1/bindings/{uid}'),
        ('GET', rf'/integration/v1/face/jobs/{uid}(?:/candidates)?'),
        ('POST', rf'/integration/v1/face/jobs/{uid}/review'),
        ('GET', rf'/integration/v1/face/recordings(?:/{uid}(?:/segments)?)?'),
        ('POST', r'/integration/v1/face/recordings'),
        ('POST', rf'/integration/v1/face/recordings/{uid}/(?:complete|cancel|retry)'),
        ('DELETE', rf'/integration/v1/face/recordings/{uid}'),
        ('PUT', rf'/integration/v1/face/recordings/{uid}/files/{uid}/chunks/[0-9]+'),
        ('POST', rf'/integration/v1/face/recordings/{uid}/files/{uid}/playback'),
    )
    return any(method == verb and re.fullmatch(pattern, path) for verb, pattern in rules)


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
    if payload.get('client') == 'mobile' and user.role != 'PATIENT':
        raise unauthorized("账号身份已变化，请重新登录。")
    if user.role == 'PATIENT':
        validate_mobile_session(db, user, payload)
        path = request.url.path.removeprefix('/api')
        if not patient_endpoint_allowed(request.method, path):
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
