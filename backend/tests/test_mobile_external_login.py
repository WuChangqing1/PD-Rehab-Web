"""Isolated provider doubles: no SMS costs, WeChat accounts or production data."""
from datetime import timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, func
from sqlalchemy.orm import sessionmaker

from app.api.deps import get_db
from app.api.mobile_auth import _attempts
from app.api import mobile_external_auth as routes
from app.core.config import settings
from app.core.errors import APIError
from app.db.base import utcnow
from app.db.models import Patient, StaffUser
from app.db.models.mobile_account import MobileSession
from app.db.models.mobile_identity import MobileIdentity, MobileLoginChallenge, MobileAuthLimit
from app.services.mobile_login_providers import get_login_providers, LoginProviders


class Providers:
    sms_enabled = True
    wechat_enabled = True
    wechat_app_id = 'wx0123456789abcdef'

    def __init__(self):
        self.sends, self.checks = [], []
        self.send_fails = self.verify_fails = False

    def send_sms(self, phone, challenge_id):
        self.sends.append((phone, challenge_id))
        if self.send_fails:
            raise APIError(503, 'TEST', 'Provider offline')

    def verify_sms(self, phone, code, challenge_id):
        self.checks.append((phone, challenge_id))
        if self.verify_fails:
            raise APIError(503, 'TEST', 'Provider offline')
        return code == '826193' and (phone, challenge_id) in self.sends

    def wechat_subject(self, code):
        if code == 'denied':
            raise APIError(401, 'INVALID', '微信授权已失效。')
        return 'wx_user_' + code


@pytest.fixture
def setup_external(engine, monkeypatch):
    from app.main import app
    factory = sessionmaker(bind=engine, autoflush=False)
    def isolated():
        with factory() as session:
            yield session
    provider = Providers()
    clock = [utcnow()]
    monkeypatch.setattr(routes, 'utcnow', lambda: clock[0])
    app.dependency_overrides[get_db] = isolated
    app.dependency_overrides[get_login_providers] = lambda: provider
    _attempts.clear()
    client = TestClient(app)
    yield client, provider, clock
    client.close()
    app.dependency_overrides.clear()


def register(client, username='legacy_one'):
    r = client.post('/api/mobile/auth/register', json={'username': username,
        'password': 'test-password-12', 'display_name': '已有用户', 'sync_consent_version': 'account-sync-v1'})
    assert r.status_code == 201, r.text
    return r.json()


def auth(body):
    return {'Authorization': 'Bearer ' + body['access_token']}


def send(client, phone='13800138000', headers=None):
    path = '/identities/sms/challenge' if headers else '/sms/challenge'
    r = client.post('/api/mobile/auth'+path, json={'phone': phone}, headers=headers)
    assert r.status_code == 200, r.text
    assert phone not in r.text and '826193' not in r.text
    return r.json()


def sms(client, challenge, headers=None, code='826193'):
    path = '/identities/sms/bind' if headers else '/sms/login'
    data = {'challenge_id': challenge['challenge_id'], 'code': code}
    if not headers: data['sync_consent_version'] = 'account-sync-v1'
    return client.post('/api/mobile/auth'+path, json=data, headers=headers)


def wx_challenge(client, headers=None):
    r = client.post('/api/mobile/auth'+('/identities/wechat/challenge' if headers else '/wechat/challenge'), headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def wx(client, challenge, code='one', headers=None, **changes):
    data = {'challenge_id': challenge['challenge_id'], 'state': challenge['state'], 'code': code}
    if not headers: data['sync_consent_version'] = 'account-sync-v1'
    data.update(changes)
    return client.post('/api/mobile/auth'+('/identities/wechat/bind' if headers else '/wechat/login'), json=data, headers=headers)


def test_unconfigured_is_fail_closed_and_public_config_contains_no_secrets(setup_external, db):
    c, p, _ = setup_external
    p.sms_enabled = p.wechat_enabled = False
    r = c.get('/api/mobile/auth/providers')
    assert r.json() == {'wechat_enabled': False, 'sms_enabled': False, 'wechat_app_id': '', 'phone_region': 'CN'}
    assert r.headers['cache-control'] == 'private, no-store'
    assert c.post('/api/mobile/auth/sms/challenge', json={'phone':'13800138000'}).status_code == 503
    assert c.post('/api/mobile/auth/wechat/challenge').status_code == 503
    assert db.scalar(select(func.count()).select_from(Patient)) == 0
    assert not p.sends


def test_sms_first_login_creates_patient_once_and_existing_login_reuses_ids(setup_external, db):
    c, p, clock = setup_external
    challenge = send(c, '+8613800138000')
    assert sms(c, challenge, code='000000').status_code == 401
    r = sms(c, challenge)
    assert r.status_code == 200, r.text
    first = r.json()
    assert first['user']['role'] == 'PATIENT' and first['recovery_code']
    assert sms(c, challenge).status_code == 401
    clock[0] += timedelta(seconds=61)
    again = sms(c, send(c)).json()
    assert again['user']['id'] == first['user']['id']
    assert again['patient']['id'] == first['patient']['id']
    assert 'recovery_code' not in again
    assert db.scalar(select(func.count()).select_from(Patient)) == 1
    user = db.get(StaffUser, first['user']['id'])
    assert user.username.startswith('p_') and user.role == 'PATIENT'
    result = c.get('/api/mobile/auth/identities', headers=auth(again))
    assert result.json()['items'] == [{'provider':'sms','label':'138****8000'}]


def test_sms_binding_preserves_existing_account_and_patient(setup_external, db):
    c, _, clock = setup_external
    legacy = register(c)
    h = auth(legacy)
    assert sms(c, send(c, headers=h), h).status_code == 200
    clock[0] += timedelta(seconds=61)
    logged = sms(c, send(c)).json()
    assert logged['user']['id'] == legacy['user']['id']
    assert logged['patient'] == legacy['patient']
    assert db.scalar(select(func.count()).select_from(Patient)) == 1


def test_binding_conflicts_never_merge_or_replace_patients(setup_external, db):
    c, _, clock = setup_external
    owner = sms(c, send(c)).json()
    other = register(c)
    clock[0] += timedelta(seconds=61)
    challenge = send(c, headers=auth(other))
    assert sms(c, challenge, auth(other)).status_code == 409
    assert sms(c, challenge, auth(other)).status_code == 400
    assert db.scalar(select(MobileIdentity)).user_id == owner['user']['id']
    assert db.scalar(select(func.count()).select_from(Patient)) == 2


def test_wechat_login_state_replay_and_client_identity_injection(setup_external, db):
    c, _, _ = setup_external
    challenge = wx_challenge(c)
    assert wx(c, challenge, state='x'*43).status_code == 401
    assert wx(c, challenge, patient_id='attacker').status_code == 422
    first = wx(c, challenge)
    assert first.status_code == 200, first.text
    body = first.json()
    assert body['user']['role'] == 'PATIENT'
    assert wx(c, challenge).status_code == 401
    again = wx(c, wx_challenge(c)).json()
    assert again['user']['id'] == body['user']['id']
    assert again['patient']['id'] == body['patient']['id']
    assert 'recovery_code' not in again
    assert db.scalar(select(func.count()).select_from(Patient)) == 1


def test_wechat_binding_and_phone_are_two_paths_to_same_user(setup_external, db):
    c, _, clock = setup_external
    legacy = register(c)
    assert wx(c, wx_challenge(c, auth(legacy)), headers=auth(legacy)).status_code == 200
    assert sms(c, send(c, headers=auth(legacy)), auth(legacy)).status_code == 200
    logged = wx(c, wx_challenge(c)).json()
    assert logged['user']['id'] == legacy['user']['id']
    assert logged['patient'] == legacy['patient']
    assert len(c.get('/api/mobile/auth/identities', headers=auth(logged)).json()['items']) == 2
    assert db.scalar(select(func.count()).select_from(Patient)) == 1


def test_binding_challenge_cannot_be_used_for_login_or_another_session(setup_external):
    c, _, _ = setup_external
    first = register(c)
    second = register(c, 'legacy_two')
    challenge = wx_challenge(c, auth(first))
    assert wx(c, challenge).status_code == 401
    assert wx(c, challenge, headers=auth(second)).status_code == 400
    assert wx(c, challenge, headers=auth(first)).status_code == 200


def test_revoked_and_stale_sessions_cannot_bind(setup_external, db):
    c, _, clock = setup_external
    first = register(c)
    challenge = wx_challenge(c, auth(first))
    c.post('/api/mobile/auth/logout', json={'refresh_token':first['refresh_token']})
    assert wx(c, challenge, headers=auth(first)).status_code == 401
    second = register(c, 'legacy_two')
    clock[0] += timedelta(minutes=16)
    assert c.post('/api/mobile/auth/identities/wechat/challenge', headers=auth(second)).status_code == 403
    assert not db.scalars(select(MobileIdentity)).all()


def test_sms_expiry_attempt_limit_and_pending_claim(setup_external, db):
    c, p, clock = setup_external
    challenge = send(c)
    for _ in range(5): assert sms(c, challenge, code='000000').status_code == 401
    assert sms(c, challenge).status_code == 401
    assert len(p.checks) == 5
    clock[0] += timedelta(seconds=61)
    pending = send(c)
    row = db.get(MobileLoginChallenge, pending['challenge_id'])
    row.status = 'checking'
    db.commit()
    assert sms(c, pending).status_code == 401
    clock[0] += timedelta(seconds=61)
    expired = send(c)
    clock[0] += timedelta(seconds=301)
    assert sms(c, expired).status_code == 401
    assert len(p.checks) == 5


def test_sms_cooldown_global_budget_and_failed_send_reservations(setup_external, db, monkeypatch):
    c, p, _ = setup_external
    monkeypatch.setattr(settings, 'mobile_sms_daily_budget', 2)
    send(c)
    assert c.post('/api/mobile/auth/sms/challenge', json={'phone':'13800138000'}).status_code == 429
    p.send_fails = True
    assert c.post('/api/mobile/auth/sms/challenge', json={'phone':'13900139000'}).status_code == 503
    assert c.post('/api/mobile/auth/sms/challenge', json={'phone':'13700137000'}).status_code == 429
    assert len(p.sends) == 2
    assert db.scalar(select(func.count()).select_from(Patient)) == 0


def test_disabled_patient_cannot_login_by_verified_external_identity(setup_external, db):
    c, _, _ = setup_external
    first = wx(c, wx_challenge(c)).json()
    db.get(StaffUser, first['user']['id']).is_active = False
    db.commit()
    assert wx(c, wx_challenge(c)).status_code == 401


def test_wechat_appid_is_bound_to_challenge(setup_external):
    c, p, _ = setup_external
    challenge = wx_challenge(c)
    p.wechat_app_id = 'wx1111111111111111'
    assert wx(c, challenge).status_code == 401


def test_provider_adapters_use_official_success_semantics_and_hide_codes(monkeypatch):
    provider = LoginProviders()
    requests = []
    def fake(action, values):
        requests.append((action, values))
        return {'Code':'OK','Success':True,'Model':{'VerifyResult':'UNKNOWN'}}
    monkeypatch.setattr(provider, '_sms_rpc', fake)
    provider.send_sms('13800138000', 'challenge')
    assert requests[0][1]['ReturnVerifyCode'] == 'false'
    assert requests[0][1]['AutoRetry'] == '0'
    assert '##code##' in requests[0][1]['TemplateParam']
    assert not provider.verify_sms('13800138000','826193','challenge')


def test_rpc_signature_matches_official_sdk_unicode_reference_vector():
    params = {'Action':'SendSmsVerifyCode','Format':'JSON','Version':'2017-05-25',
        'SignName':'琴伴测试','TemplateParam':'{"code":"##code##","min":"5"}',
        'SignatureNonce':'fixed-test-nonce','Timestamp':'2026-11-12T00:00:00Z'}
    # Cross-checked against alibabacloud_openapi_util.Client.get_rpcsignature.
    assert LoginProviders.rpc_signature(params, 'test-secret') == 'EAub3sBfXhhDaVoFs911H8t4Kr4='


def test_provider_rpc_uses_fixed_https_post_and_pass_not_just_success(monkeypatch):
    import io, json, urllib.parse
    captured = []
    def open_request(request, timeout):
        assert request.full_url == 'https://dypnsapi.aliyuncs.com/'
        assert request.method == 'POST' and timeout == 8
        captured.append(urllib.parse.parse_qs(request.data.decode()))
        return io.BytesIO(json.dumps({'Code':'OK','Success':True,'Model':{'VerifyResult':'UNKNOWN'}}).encode())
    class Opener:
        open = staticmethod(open_request)
    monkeypatch.setattr('urllib.request.build_opener', lambda *args: Opener())
    for name, value in [('mobile_sms_enabled', True),('mobile_sms_access_key_id','test-ak'),
        ('mobile_sms_access_key_secret','test-secret'),('mobile_sms_sign_name','test-sign'),
        ('mobile_sms_template_code','100001')]:
        monkeypatch.setattr(settings, name, value)
    provider = LoginProviders()
    provider.send_sms('13800138000','test-challenge')
    assert captured[-1]['ReturnVerifyCode'] == ['false']
    assert 'test-secret' not in repr(captured)
    assert not provider.verify_sms('13800138000','826193','test-challenge')
    assert captured[-1]['OutId'] == ['test-challenge']
