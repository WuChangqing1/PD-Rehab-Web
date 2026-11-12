"""Provider-verified login and explicit binding to the current patient account."""
from datetime import timedelta
import secrets
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select, update, delete
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentUser, DbSession, client_ip, validate_mobile_session
from app.api.mobile_auth import begin_auth_write, create_patient_account, digest, identity, issue, no_store, rate_limit
from app.core.config import settings
from app.core.errors import APIError, conflict, forbidden, unauthorized
from app.core.security import decode_access_token
from app.db.base import utcnow
from app.db.models import StaffUser
from app.db.models.mobile_account import MobileSession
from app.db.models.mobile_identity import MobileIdentity, MobileLoginChallenge, MobileAuthLimit
from app.services.mobile_login_providers import LoginProviders, get_login_providers, unavailable

router = APIRouter(prefix='/mobile/auth', tags=['Mobile external login'], dependencies=[Depends(no_store)])
Provider = Annotated[LoginProviders, Depends(get_login_providers)]


class PhoneRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    phone: str = Field(pattern=r'^(?:\+86)?1[3-9][0-9]{9}$')

    @field_validator('phone')
    @classmethod
    def normalize(cls, value):
        return value.removeprefix('+86')


class SmsProof(BaseModel):
    model_config = ConfigDict(extra='forbid')
    challenge_id: UUID
    code: str = Field(pattern=r'^[0-9]{6}$')


class SmsLogin(SmsProof):
    sync_consent_version: Literal['account-sync-v1']


class WechatProof(BaseModel):
    model_config = ConfigDict(extra='forbid')
    challenge_id: UUID
    code: str = Field(min_length=1, max_length=256)
    state: str = Field(min_length=32, max_length=128)


class WechatLogin(WechatProof):
    sync_consent_version: Literal['account-sync-v1']


def _claims(db, user, request, *, fresh=False):
    if user.role != 'PATIENT':
        raise forbidden('仅普通账号可绑定登录方式。')
    claims = decode_access_token(request.headers['authorization'].split(' ', 1)[1])
    validate_mobile_session(db, user, claims)
    session = db.get(MobileSession, claims['sid'], populate_existing=True)
    if fresh and session.created_at < utcnow() - timedelta(minutes=15):
        raise APIError(403, 'REAUTHENTICATION_REQUIRED', '为保护账号，请重新登录后再绑定。')
    return claims


def _limit(db, scope, limit, seconds):
    key, now = digest(scope), utcnow()
    row = db.scalar(select(MobileAuthLimit).where(MobileAuthLimit.key == key).with_for_update())
    if row is None:
        db.add(MobileAuthLimit(key=key, count=1, resets_at=now + timedelta(seconds=seconds)))
        db.flush()
    elif row.resets_at <= now:
        row.count, row.resets_at = 1, now + timedelta(seconds=seconds)
    elif row.count >= limit:
        raise APIError(429, 'RATE_LIMITED', '操作过于频繁，请稍后重试。',
                       headers={'Retry-After': str(max(1, int((row.resets_at-now).total_seconds())))})
    else:
        row.count += 1


def _new_challenge(db, request, provider, purpose, subject='', user=None):
    claims = _claims(db, user, request, fresh=True) if user is not None else None
    begin_auth_write(db)
    try:
        if provider == 'sms':
            _limit(db, 'sms:minute:' + subject, 1, 60)
            _limit(db, 'sms:day:' + subject, 10, 86400)
            _limit(db, 'sms:ip:' + (client_ip(request) or 'unknown'), 20, 3600)
            _limit(db, 'sms:global', settings.mobile_sms_daily_budget, 86400)
            db.execute(update(MobileLoginChallenge).where(
                MobileLoginChallenge.provider == 'sms', MobileLoginChallenge.subject == subject,
                MobileLoginChallenge.status.in_(['pending', 'sent', 'checking'])).values(status='used'))
        else:
            rate_limit(request, 'wechat-challenge', 30)
        state = secrets.token_urlsafe(32)
        challenge = MobileLoginChallenge(provider=provider, purpose=purpose, subject=subject,
            state_hash=digest(state), user_id=user.id if user else None,
            session_id=claims['sid'] if claims else None,
            status='pending' if provider == 'sms' else 'sent', expires_at=utcnow()+timedelta(minutes=5))
        db.add(challenge)
        # Keep this operational data bounded; no patient/business rows are deleted.
        db.execute(delete(MobileLoginChallenge).where(MobileLoginChallenge.expires_at < utcnow()-timedelta(days=1)))
        db.execute(delete(MobileAuthLimit).where(MobileAuthLimit.resets_at < utcnow()-timedelta(days=1)))
        db.commit()
    except IntegrityError:
        db.rollback()
        raise APIError(429, 'RATE_LIMITED', '操作过于频繁，请稍后重试。') from None
    return challenge, state


def _send_sms(payload, db, request, providers, user=None):
    if not providers.sms_enabled:
        raise unavailable()
    challenge, _ = _new_challenge(db, request, 'sms', 'bind' if user else 'login', payload.phone, user)
    # The reservation is committed BEFORE a network operation; failed sends still
    # consume rate/budget slots, preventing retry storms and multi-worker bypasses.
    try:
        providers.send_sms(challenge.subject, challenge.id)
    except Exception:
        db.execute(update(MobileLoginChallenge).where(MobileLoginChallenge.id == challenge.id).values(status='failed'))
        db.commit()
        error = unavailable()
        error.headers = {'Retry-After': '60'}
        raise error from None
    changed = db.execute(update(MobileLoginChallenge).where(
        MobileLoginChallenge.id == challenge.id, MobileLoginChallenge.status == 'pending').values(status='sent'))
    db.commit()
    if changed.rowcount != 1:
        raise unavailable()
    return {'challenge_id': challenge.id, 'expires_in': 300, 'retry_after': 60,
            'phone_hint': challenge.subject[:3] + '****' + challenge.subject[-4:]}


def _proof_error(message, purpose):
    # A bad verification code is not an expired account token. Binding must not
    # trigger the client's session refresh/logout path or a second OTP attempt.
    return APIError(400 if purpose == 'bind' else 401, 'INVALID_LOGIN_PROOF', message)


def _claim(db, payload, provider, purpose, providers, request, user=None):
    claims = _claims(db, user, request, fresh=True) if user else None
    begin_auth_write(db)
    challenge = db.get(MobileLoginChallenge, str(payload.challenge_id), populate_existing=True)
    if (challenge is None or challenge.provider != provider or challenge.purpose != purpose
            or challenge.user_id != (user.id if user else None)
            or challenge.session_id != (claims['sid'] if claims else None)
            or challenge.expires_at <= utcnow() or challenge.attempts >= 5 or challenge.status != 'sent'):
        raise _proof_error('验证码或授权已失效，请重新获取。', purpose)
    if provider == 'wechat' and (challenge.subject != providers.wechat_app_id
            or not secrets.compare_digest(challenge.state_hash, digest(payload.state))):
        raise _proof_error('微信授权校验失败，请重新授权。', purpose)
    changed = db.execute(update(MobileLoginChallenge).where(
        MobileLoginChallenge.id == challenge.id, MobileLoginChallenge.status == 'sent',
        MobileLoginChallenge.attempts == challenge.attempts).values(status='checking', attempts=challenge.attempts+1))
    if changed.rowcount != 1:
        db.rollback()
        raise _proof_error('此请求已处理，请重新获取验证码或授权。', purpose)
    db.commit()
    try:
        subject = providers.wechat_subject(payload.code) if provider == 'wechat' else challenge.subject
        verified = provider == 'wechat' or providers.verify_sms(subject, payload.code, challenge.id)
    except Exception as error:
        db.execute(update(MobileLoginChallenge).where(MobileLoginChallenge.id == challenge.id,
            MobileLoginChallenge.status == 'checking').values(status='used' if provider == 'wechat' else 'sent'))
        db.commit()
        if isinstance(error, APIError):
            if error.status_code == 401 and purpose == 'bind':
                raise _proof_error('授权已失效，请重新获取。', purpose) from None
            raise error
        raise unavailable() from None
    if not verified:
        db.execute(update(MobileLoginChallenge).where(MobileLoginChallenge.id == challenge.id,
            MobileLoginChallenge.status == 'checking').values(status='sent'))
        db.commit()
        raise _proof_error('验证码错误或已失效。', purpose)
    return challenge, subject, claims


def _finish(db, proof, provider, providers, request, response, user=None):
    if not (providers.sms_enabled if provider == 'sms' else providers.wechat_enabled):
        raise unavailable()
    rate_limit(request, 'external-verify', 60)
    challenge, subject, claims = _claim(db, proof, provider, 'bind' if user else 'login', providers, request, user)
    begin_auth_write(db)
    try:
        changed = db.execute(update(MobileLoginChallenge).where(
            MobileLoginChallenge.id == challenge.id, MobileLoginChallenge.status == 'checking',
            MobileLoginChallenge.expires_at > utcnow()).values(status='used'))
        if changed.rowcount != 1:
            raise _proof_error('此请求已处理或过期，请重新获取。', 'bind' if user else 'login')
        # Commit the single-use claim even when binding conflicts. No replay may
        # be used to attach a verified identity to a different patient.
        db.commit()
        begin_auth_write(db)
        app_id = challenge.subject if provider == 'wechat' else ''
        bound = db.scalar(select(MobileIdentity).where(MobileIdentity.provider == provider,
            MobileIdentity.app_id == app_id, MobileIdentity.subject == subject).with_for_update())
        if user:
            user = db.get(StaffUser, user.id, populate_existing=True)
            if user is None or not user.is_active or user.role != 'PATIENT':
                raise unauthorized()
            validate_mobile_session(db, user, claims)
            if bound and bound.user_id != user.id:
                raise conflict('此登录方式已绑定其他账号，请使用原账号登录。')
            existing = db.scalar(select(MobileIdentity).where(MobileIdentity.user_id == user.id,
                MobileIdentity.provider == provider))
            if existing and (existing.subject != subject or existing.app_id != app_id):
                raise conflict('账号已绑定此类登录方式，请联系维护人员处理更换。')
            if not bound:
                db.add(MobileIdentity(user_id=user.id, provider=provider, app_id=app_id, subject=subject))
            db.commit()
            return {'message': '绑定成功，原训练档案保持不变。'}
        recovery = None
        if bound:
            user = db.get(StaffUser, bound.user_id)
        else:
            label = '手机用户' + subject[-4:] if provider == 'sms' else '微信用户'
            user, recovery = create_patient_account(db, 'p_'+secrets.token_hex(10),
                secrets.token_urlsafe(40), label, proof.sync_consent_version)
            db.add(MobileIdentity(user_id=user.id, provider=provider, app_id=app_id, subject=subject))
            db.flush()
        result = issue(db, user, response)
        if recovery:
            result['recovery_code'] = recovery
        return result
    except IntegrityError:
        db.rollback()
        raise conflict('账号绑定正在变化，请重新登录或获取验证码。') from None


@router.get('/providers')
def providers_config(providers: Provider):
    return {'wechat_enabled': providers.wechat_enabled, 'sms_enabled': providers.sms_enabled,
            'wechat_app_id': providers.wechat_app_id if providers.wechat_enabled else '', 'phone_region': 'CN'}


@router.post('/sms/challenge')
def sms_challenge(payload: PhoneRequest, db: DbSession, request: Request, providers: Provider):
    return _send_sms(payload, db, request, providers)


@router.post('/sms/login')
def sms_login(payload: SmsLogin, db: DbSession, request: Request, response: Response, providers: Provider):
    return _finish(db, payload, 'sms', providers, request, response)


def _wechat_challenge(db, request, providers, user=None):
    if not providers.wechat_enabled:
        raise unavailable()
    challenge, state = _new_challenge(db, request, 'wechat', 'bind' if user else 'login', providers.wechat_app_id, user)
    return {'challenge_id': challenge.id, 'state': state, 'app_id': providers.wechat_app_id, 'expires_in': 300}


@router.post('/wechat/challenge')
def wechat_challenge(db: DbSession, request: Request, providers: Provider):
    return _wechat_challenge(db, request, providers)


@router.post('/wechat/login')
def wechat_login(payload: WechatLogin, db: DbSession, request: Request, response: Response, providers: Provider):
    return _finish(db, payload, 'wechat', providers, request, response)


@router.get('/identities')
def identities(db: DbSession, user: CurrentUser):
    identity(db, user)
    rows = db.scalars(select(MobileIdentity).where(MobileIdentity.user_id == user.id)).all()
    return {'items': [{'provider': row.provider, 'label':
        row.subject[:3]+'****'+row.subject[-4:] if row.provider == 'sms' else '已绑定微信'} for row in rows]}


@router.post('/identities/sms/challenge')
def bind_sms_challenge(payload: PhoneRequest, db: DbSession, request: Request, providers: Provider, user: CurrentUser):
    return _send_sms(payload, db, request, providers, user)


@router.post('/identities/sms/bind')
def bind_sms(payload: SmsProof, db: DbSession, request: Request, response: Response, providers: Provider, user: CurrentUser):
    return _finish(db, payload, 'sms', providers, request, response, user)


@router.post('/identities/wechat/challenge')
def bind_wechat_challenge(db: DbSession, request: Request, providers: Provider, user: CurrentUser):
    return _wechat_challenge(db, request, providers, user)


@router.post('/identities/wechat/bind')
def bind_wechat(payload: WechatProof, db: DbSession, request: Request, response: Response, providers: Provider, user: CurrentUser):
    return _finish(db, payload, 'wechat', providers, request, response, user)
