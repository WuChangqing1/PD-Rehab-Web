"""Patient-only enrollment; no publicly assignable staff roles or patient IDs."""
from datetime import timedelta
import hashlib
import secrets
import threading
import time
from typing import Literal

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select, update, func, or_, text
from sqlalchemy.exc import IntegrityError

from app.api.deps import DbSession, CurrentUser, client_ip
from app.core.errors import APIError, conflict, unauthorized, forbidden
from app.core.security import hash_password, verify_password, create_access_token
from app.db.base import utcnow
from app.db.models import StaffUser, Patient, PatientNumberAllocation
from app.db.models.mobile_account import MobileAccount, MobileSession

def no_store(response: Response):
    response.headers['Cache-Control'] = 'private, no-store'


router = APIRouter(prefix='/mobile/auth', tags=['Mobile accounts'], dependencies=[Depends(no_store)])
_attempts: dict[tuple[str, str], list[float]] = {}
_lock = threading.Lock()


def rate_limit(request, action, limit=12):
    # This per-worker limit supplements the documented edge rate limit.
    key = (client_ip(request) or 'unknown', action)
    now = time.monotonic()
    with _lock:
        if len(_attempts) > 10000:
            for old in list(_attempts):
                if not _attempts[old] or _attempts[old][-1] < now - 600:
                    del _attempts[old]
        values = [t for t in _attempts.get(key, []) if t > now - 600]
        if len(values) >= limit:
            raise APIError(429, 'RATE_LIMITED', '尝试过于频繁，请稍后重试。', headers={'Retry-After': '600'})
        _attempts[key] = values + [now]


def digest(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def begin_auth_write(db):
    """Serialize SQLite credential reads with their writes, across processes.

    The application does not run a network operation inside this transaction.
    On row-locking databases each user/session lookup below also locks its row.
    """
    if db.get_bind().dialect.name == 'sqlite':
        connection = db.connection().connection.driver_connection
        if not connection.in_transaction:
            db.execute(text('BEGIN IMMEDIATE'))


class Login(BaseModel):
    model_config = ConfigDict(extra='forbid')
    username: str = Field(pattern=r'^[A-Za-z0-9_]{3,32}$')
    password: str = Field(min_length=8, max_length=64)

    @field_validator('username')
    @classmethod
    def normalize(cls, value):
        return value.lower()

    @field_validator('password')
    @classmethod
    def bounded_password(cls, value):
        if len(value.encode('utf-8')) > 72:
            raise ValueError('密码 UTF-8 长度不能超过 72 字节')
        return value


class Register(Login):
    display_name: str = Field(min_length=1, max_length=64)
    sync_consent_version: Literal['account-sync-v1']

    @field_validator('display_name')
    @classmethod
    def name(cls, value):
        if not value.strip():
            raise ValueError('请填写姓名或昵称')
        return value.strip()


class Refresh(BaseModel):
    model_config = ConfigDict(extra='forbid')
    refresh_token: str = Field(min_length=32, max_length=256)


class Reset(Login):
    recovery_code: str = Field(min_length=20, max_length=128)


class ChangePassword(BaseModel):
    model_config = ConfigDict(extra='forbid')
    current_password: str = Field(min_length=1, max_length=64)
    new_password: str = Field(min_length=8, max_length=64)

    @field_validator('new_password')
    @classmethod
    def bounded(cls, value):
        return Login.bounded_password(value)


def identity(db, user):
    account = db.get(MobileAccount, user.id)
    patient = db.get(Patient, account.patient_id) if account else None
    if user.role != 'PATIENT' or not user.is_active or patient is None or patient.is_deleted:
        raise unauthorized('账号或患者档案已停用。')
    return {
        'user': {'id': user.id, 'username': user.username, 'display_name': user.display_name, 'role': 'PATIENT'},
        'patient': {'id': patient.id, 'name': patient.name, 'hospital_number': patient.hospital_number},
    }


def issue(db, user, response, session=None):
    body = identity(db, user)
    secret = secrets.token_urlsafe(48)
    expires = utcnow() + timedelta(days=30)
    if session is None:
        session = MobileSession(user_id=user.id, refresh_hash=digest(secret), expires_at=expires)
        db.add(session)
    else:
        session.refresh_hash = digest(secret)
        session.expires_at = expires
    db.flush()
    body.update(access_token=create_access_token(user.id, role='PATIENT', expires_minutes=15,
                extra={'client': 'mobile', 'sid': session.id}), refresh_token=secret,
                expires_in=900, refresh_expires_at=expires.isoformat() + 'Z', token_type='bearer')
    db.commit()
    response.headers['Cache-Control'] = 'no-store'
    return body


@router.post('/register', status_code=201)
def register(payload: Register, db: DbSession, request: Request, response: Response):
    rate_limit(request, 'register', 6)
    begin_auth_write(db)
    if db.scalar(select(StaffUser.id).where(func.lower(StaffUser.username) == payload.username)):
        raise conflict('该用户名不可用。')
    recovery = secrets.token_urlsafe(24)
    try:
        user = StaffUser(username=payload.username, password_hash=hash_password(payload.password),
                         display_name=payload.display_name, role='PATIENT', is_active=True)
        db.add(user)
        db.flush()
        while True:
            reservation = PatientNumberAllocation()
            db.add(reservation)
            db.flush()
            number = f'P{reservation.id:06d}'
            if db.scalar(select(Patient.id).where(Patient.hospital_number == number)) is None:
                break
        patient = Patient(hospital_number=number, name=payload.display_name)
        db.add(patient)
        db.flush()
        db.add(MobileAccount(user_id=user.id, patient_id=patient.id, recovery_hash=digest(recovery), sync_consent_version=payload.sync_consent_version))
        db.flush()
        result = issue(db, user, response)
    except IntegrityError:
        db.rollback()
        raise conflict('注册信息已存在，请更换用户名或重试。') from None
    result['recovery_code'] = recovery
    return result


@router.post('/login')
def login(payload: Login, db: DbSession, request: Request, response: Response):
    rate_limit(request, 'login')
    begin_auth_write(db)
    user = db.scalar(select(StaffUser).where(StaffUser.username == payload.username, StaffUser.role == 'PATIENT').with_for_update())
    # Spend the same hash work on unknown accounts.
    if user is None:
        hash_password(payload.password)
        raise unauthorized('用户名或密码错误。')
    if not verify_password(payload.password, user.password_hash):
        raise unauthorized('用户名或密码错误。')
    return issue(db, user, response)


@router.post('/refresh')
def refresh(payload: Refresh, db: DbSession, request: Request, response: Response):
    rate_limit(request, 'refresh', 120)
    begin_auth_write(db)
    # Serialize the lookup on databases that support row locks, then CAS on all DBs.
    session = db.scalar(select(MobileSession).where(MobileSession.refresh_hash == digest(payload.refresh_token)).with_for_update())
    if session is None or session.revoked or session.expires_at <= utcnow():
        raise unauthorized()
    user = db.get(StaffUser, session.user_id)
    if user is None:
        raise unauthorized()
    identity(db, user)
    old = session.refresh_hash
    secret = secrets.token_urlsafe(48)
    expiry = utcnow() + timedelta(days=30)
    changed = db.execute(update(MobileSession).where(MobileSession.id == session.id,
        MobileSession.refresh_hash == old, MobileSession.revoked.is_(False)).values(
        previous_refresh_hash=old, refresh_hash=digest(secret), expires_at=expiry))
    if changed.rowcount != 1:
        db.rollback()
        raise unauthorized()
    body = identity(db, user)
    body.update(access_token=create_access_token(user.id, role='PATIENT', expires_minutes=15,
                extra={'client': 'mobile', 'sid': session.id}), refresh_token=secret,
                expires_in=900, refresh_expires_at=expiry.isoformat() + 'Z', token_type='bearer')
    db.commit()
    response.headers['Cache-Control'] = 'no-store'
    return body


@router.get('/me')
def me(db: DbSession, user: CurrentUser):
    return identity(db, user)


@router.post('/logout')
def logout(payload: Refresh, db: DbSession):
    begin_auth_write(db)
    value = digest(payload.refresh_token)
    db.execute(update(MobileSession).where(or_(MobileSession.refresh_hash == value,
        MobileSession.previous_refresh_hash == value)).values(revoked=True))
    db.commit()
    return {'message': '已退出登录。'}


@router.post('/reset-password')
def reset_password(payload: Reset, db: DbSession, request: Request):
    rate_limit(request, 'reset', 6)
    begin_auth_write(db)
    user = db.scalar(select(StaffUser).where(StaffUser.username == payload.username, StaffUser.role == 'PATIENT').with_for_update())
    account = db.get(MobileAccount, user.id) if user else None
    if account is None or not user.is_active:
        raise unauthorized('账号或恢复码错误。')
    next_code = secrets.token_urlsafe(24)
    changed = db.execute(update(MobileAccount).where(MobileAccount.user_id == user.id,
        MobileAccount.recovery_hash == digest(payload.recovery_code)).values(recovery_hash=digest(next_code)))
    if changed.rowcount != 1:
        db.rollback()
        raise unauthorized('账号或恢复码错误。')
    user.password_hash = hash_password(payload.password)
    db.execute(update(MobileSession).where(MobileSession.user_id == user.id).values(revoked=True))
    db.commit()
    return {'message': '密码已重置，请重新登录并保存新恢复码。', 'recovery_code': next_code}


@router.post('/change-password')
def change_password(payload: ChangePassword, db: DbSession, user: CurrentUser, request: Request):
    if user.role != 'PATIENT':
        raise forbidden()
    rate_limit(request, 'change-password', 6)
    begin_auth_write(db)
    user = db.scalar(select(StaffUser).where(StaffUser.id == user.id).with_for_update().execution_options(populate_existing=True))
    if user is None or not user.is_active:
        raise unauthorized()
    from app.api.deps import validate_mobile_session
    from app.core.security import decode_access_token
    validate_mobile_session(db, user, decode_access_token(request.headers['authorization'].split(' ', 1)[1]))
    if not verify_password(payload.current_password, user.password_hash):
        raise APIError(400, 'INVALID_CURRENT_PASSWORD', '当前密码错误。')
    user.password_hash = hash_password(payload.new_password)
    db.execute(update(MobileSession).where(MobileSession.user_id == user.id).values(revoked=True))
    db.commit()
    return {'message': '密码已修改，请重新登录。'}
