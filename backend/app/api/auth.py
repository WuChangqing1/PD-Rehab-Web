"""Auth endpoints (spec V2 section 48)."""

from __future__ import annotations

from fastapi import APIRouter, Request
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession, client_ip
from app.core.config import settings
from app.core.errors import ErrorCode, unauthorized
from app.core.logging import get_logger
from app.core.security import create_access_token, verify_password
from app.db.models import StaffUser
from app.schemas.auth import LoginRequest, StaffUserRead, TokenResponse
from app.schemas.common import Message
from app.services import audit_service

router = APIRouter(prefix="/auth", tags=["Auth"])
logger = get_logger(__name__)


@router.post("/login", response_model=TokenResponse, summary="医生 / 管理员登录")
def login(payload: LoginRequest, db: DbSession, request: Request) -> TokenResponse:
    user = db.execute(
        select(StaffUser).where(StaffUser.username == payload.username)
    ).scalar_one_or_none()

    if user is None or not verify_password(payload.password, user.password_hash):
        # Same message for unknown user and wrong password: do not leak which.
        audit_service.record(
            db,
            staff_user_id=None,
            action="LOGIN_FAILED",
            entity_type="staff_user",
            entity_id=user.id if user else None,
            detail={"username": payload.username, "ip": client_ip(request)},
        )
        raise unauthorized(
            "用户名或密码错误。",
            code=ErrorCode.INVALID_CREDENTIALS,
        )

    if not user.is_active:
        raise unauthorized("账号已被停用，请联系管理员。", code=ErrorCode.INACTIVE_USER)

    token = create_access_token(user.id, role=user.role)
    audit_service.record(
        db,
        staff_user_id=user.id,
        action="LOGIN_SUCCESS",
        entity_type="staff_user",
        entity_id=user.id,
        detail={"ip": client_ip(request)},
    )
    return TokenResponse(
        access_token=token,
        expires_in=settings.access_token_expire_minutes * 60,
        user=StaffUserRead.model_validate(user),
    )


@router.post("/logout", response_model=Message, summary="登出")
def logout(db: DbSession, user: CurrentUser) -> Message:
    """Stateless JWT: the client discards the token. Recorded for auditing."""
    audit_service.record(
        db,
        staff_user_id=user.id,
        action="LOGOUT",
        entity_type="staff_user",
        entity_id=user.id,
    )
    return Message(message="已登出。")


@router.get("/me", response_model=StaffUserRead, summary="当前登录用户")
def me(user: CurrentUser) -> StaffUserRead:
    return StaffUserRead.model_validate(user)
