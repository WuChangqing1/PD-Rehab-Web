"""Use an isolated DB and skip production lifespan/model loading entirely."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, func
from sqlalchemy.orm import sessionmaker
from app.api.deps import get_db
from app.api.mobile_auth import _attempts
from app.core.security import create_access_token
from app.db.models import StaffUser, Patient, ExternalPracticeRecord
from app.db.models.mobile_account import MobileAccount, MobileSession


@pytest.fixture
def mobile_client(engine):
    from app.main import app
    factory = sessionmaker(bind=engine, autoflush=False)
    def isolated():
        with factory() as session:
            yield session
    app.dependency_overrides[get_db] = isolated
    _attempts.clear()
    client = TestClient(app)
    yield client
    client.close()
    app.dependency_overrides.clear()


def register(client, username='patient_one'):
    response = client.post('/api/mobile/auth/register', json={
        'username': username, 'password': 'test-pass-123', 'display_name': '测试用户',
        'sync_consent_version': 'account-sync-v1'})
    assert response.status_code == 201, response.text
    return response.json()


def headers(body):
    return {'Authorization': 'Bearer ' + body['access_token']}


def test_register_creates_web_patient_atomically_and_staff_sees_it(mobile_client, db, staff_user):
    body = register(mobile_client)
    assert body['user']['role'] == 'PATIENT'
    assert body['patient']['hospital_number'].startswith('P')
    account = db.get(MobileAccount, body['user']['id'])
    assert account.patient_id == body['patient']['id']
    assert account.recovery_hash != body['recovery_code']
    session = db.scalar(select(MobileSession))
    assert session.refresh_hash != body['refresh_token']
    user = db.get(StaffUser, body['user']['id'])
    assert user.password_hash != 'test-pass-123'
    assert 'password_hash' not in str(body)
    staff_user.role = 'ADMIN'
    db.commit()
    result = mobile_client.get('/api/patients', headers=headers({'access_token':create_access_token(staff_user.id)}))
    assert result.status_code == 200, result.text
    assert any(p['id'] == body['patient']['id'] for p in result.json()['items'])
    duplicate = mobile_client.post('/api/mobile/auth/register', json={
        'username': 'PATIENT_ONE', 'password':'test-pass-123', 'display_name':'二', 'sync_consent_version':'account-sync-v1'})
    assert duplicate.status_code == 409
    assert db.scalar(select(func.count()).select_from(Patient)) == 1


def test_patient_permissions_and_staff_login_separation(mobile_client):
    first, other = register(mobile_client), register(mobile_client, 'patient_two')
    h = headers(first)
    for method, path in [('GET','/api/patients'), ('POST','/api/patients'), ('GET','/api/auth/me'),
                         ('GET','/api/integration/v1/bootstrap'), ('GET','/api/system/info')]:
        assert mobile_client.request(method, path, headers=h, json={}).status_code == 403, path
    assert mobile_client.post('/api/auth/login', json={'username':'patient_one','password':'test-pass-123'}).status_code == 401
    assert mobile_client.get('/api/mobile/auth/me', headers=h).status_code == 200
    assert mobile_client.get('/api/integration/v1/patient-data', headers=h, params={'patient_id':other['patient']['id']}).status_code == 403
    payload={'device_id':'mobile-device-1234','local_profile_id':'local-profile-1234','patient_id':first['patient']['id']}
    assert mobile_client.post('/api/integration/v1/bindings',headers=h,json={**payload,'patient_id':other['patient']['id']}).status_code == 403
    assert mobile_client.post('/api/integration/v1/bindings',headers=h,json=payload).status_code == 200
    record={**payload,'source_record_id':'session-1','record_type':'PIANO_SESSION','schema_version':'flutter-v4','payload':{'status':'COMPLETED','accuracy':0.5}}
    a=mobile_client.post('/api/integration/v1/records',headers=h,json=record)
    b=mobile_client.post('/api/integration/v1/records',headers=h,json=record)
    assert a.status_code == b.status_code == 201, a.text
    assert a.json()['id'] == b.json()['id'] and b.json()['already_synced']
    assert mobile_client.get('/api/integration/v1/records',headers=headers(other),params={'patient_id':first['patient']['id']}).status_code == 403


def test_refresh_rotation_logout_and_revoked_access(mobile_client):
    body = register(mobile_client)
    refresh = mobile_client.post('/api/mobile/auth/refresh',json={'refresh_token':body['refresh_token']})
    assert refresh.status_code == 200, refresh.text
    renewed=refresh.json()
    assert renewed['refresh_token'] != body['refresh_token']
    assert mobile_client.post('/api/mobile/auth/refresh',json={'refresh_token':body['refresh_token']}).status_code == 401
    assert mobile_client.get('/api/mobile/auth/me',headers=headers(renewed)).status_code == 200
    assert mobile_client.post('/api/mobile/auth/logout',json={'refresh_token':renewed['refresh_token']}).status_code == 200
    assert mobile_client.get('/api/mobile/auth/me',headers=headers(renewed)).status_code == 401
    assert mobile_client.post('/api/mobile/auth/refresh',json={'refresh_token':renewed['refresh_token']}).status_code == 401


def test_recovery_is_single_use_and_revokes_all_devices(mobile_client):
    body = register(mobile_client)
    second = mobile_client.post('/api/mobile/auth/login', json={'username':'patient_one','password':'test-pass-123'}).json()
    payload={'username':'patient_one','password':'new-password-123','recovery_code':body['recovery_code']}
    reset=mobile_client.post('/api/mobile/auth/reset-password',json=payload)
    assert reset.status_code == 200, reset.text
    assert reset.json()['recovery_code'] != body['recovery_code']
    assert mobile_client.post('/api/mobile/auth/reset-password',json=payload).status_code == 401
    for device in (body, second):
        assert mobile_client.get('/api/mobile/auth/me', headers=headers(device)).status_code == 401
    assert mobile_client.post('/api/mobile/auth/login',json={'username':'patient_one','password':'test-pass-123'}).status_code == 401
    assert mobile_client.post('/api/mobile/auth/login',json={'username':'patient_one','password':'new-password-123'}).status_code == 200


def test_invalid_or_privileged_registration_does_not_create_patient(mobile_client, db):
    data={'username':'new_patient','password':'test-pass-123','display_name':'用户','sync_consent_version':'account-sync-v1'}
    for changes in [{'role':'ADMIN'}, {'patient_id':'123'}, {'password':'短'}, {'sync_consent_version':'unknown'}]:
        assert mobile_client.post('/api/mobile/auth/register',json={**data,**changes}).status_code == 422
    assert db.scalar(select(func.count()).select_from(Patient)) == 0


def test_deactivated_account_and_deleted_patient_reject_login(mobile_client, db):
    body=register(mobile_client)
    patient=db.get(Patient,body['patient']['id']); patient.is_deleted=True; db.commit()
    assert mobile_client.post('/api/mobile/auth/login',json={'username':'patient_one','password':'test-pass-123'}).status_code == 401
    assert mobile_client.get('/api/mobile/auth/me',headers=headers(body)).status_code == 401


def test_change_password_revokes_all_sessions_and_validates_bytes(mobile_client):
    body = register(mobile_client)
    h = headers(body)
    assert mobile_client.post('/api/mobile/auth/change-password', headers=h,
        json={'current_password':'wrong-password','new_password':'new-password-123'}).status_code == 400
    assert mobile_client.post('/api/mobile/auth/change-password', headers=h,
        json={'current_password':'test-pass-123','new_password':'字'*30}).status_code == 422
    result = mobile_client.post('/api/mobile/auth/change-password', headers=h,
        json={'current_password':'test-pass-123','new_password':'new-password-123'})
    assert result.status_code == 200, result.text
    assert mobile_client.get('/api/mobile/auth/me',headers=h).status_code == 401
    assert mobile_client.post('/api/mobile/auth/login',json={'username':'patient_one','password':'new-password-123'}).status_code == 200


def test_patient_role_without_revocable_mobile_session_is_rejected(mobile_client):
    body = register(mobile_client)
    token = create_access_token(body['user']['id'], role='ADMIN')
    assert mobile_client.get('/api/mobile/auth/me', headers={'Authorization':'Bearer '+token}).status_code == 401


def test_registration_preserves_demo_patients_and_skips_existing_number(mobile_client, db):
    demo = Patient(hospital_number='P000001', name='原有示例患者')
    db.add(demo); db.commit()
    body = register(mobile_client)
    assert body['patient']['id'] != demo.id
    assert body['patient']['hospital_number'] == 'P000002'
    assert db.get(Patient, demo.id).name == '原有示例患者'


def test_downgrade_disables_patient_logins_without_deleting_patient_data(mobile_client, db, engine, monkeypatch):
    import importlib.util
    from pathlib import Path
    from sqlalchemy import text
    body = register(mobile_client)
    path=Path(__file__).resolve().parents[1]/'alembic/versions/n0c2d4e6f8a0_mobile_accounts.py'
    spec=importlib.util.spec_from_file_location('mobile_account_migration',path)
    migration=importlib.util.module_from_spec(spec); spec.loader.exec_module(migration)
    with engine.begin() as connection:
        monkeypatch.setattr(migration.op,'get_bind',lambda:connection)
        migration.downgrade()
        assert connection.execute(text('SELECT is_active FROM staff_users WHERE id=:id'),{'id':body['user']['id']}).scalar() == 0
        assert connection.execute(text('SELECT id FROM patients WHERE id=:id'),{'id':body['patient']['id']}).scalar() == body['patient']['id']


@pytest.mark.parametrize('password', ['1234567', 'x' * 17])
def test_new_password_policy_rejects_outside_8_to_16(mobile_client, password):
    payload={'username':'new_patient','password':password,'display_name':'昵称','sync_consent_version':'account-sync-v1'}
    assert mobile_client.post('/api/mobile/auth/register', json=payload).status_code == 422
    body = register(mobile_client)
    assert mobile_client.post('/api/mobile/auth/reset-password', json={
        'username':'patient_one','password':password,'recovery_code':body['recovery_code']}).status_code == 422
    assert mobile_client.post('/api/mobile/auth/change-password',headers=headers(body),json={
        'current_password':'test-pass-123','new_password':password}).status_code == 422


def test_new_policy_accepts_16_characters_and_keeps_legacy_login(mobile_client, db):
    from app.core.security import hash_password
    body = register(mobile_client)
    user = db.get(StaffUser,body['user']['id'])
    user.password_hash = hash_password('legacy-password-12345'); db.commit()
    assert mobile_client.post('/api/mobile/auth/login',json={
        'username':'patient_one','password':'legacy-password-12345'}).status_code == 200
    result = mobile_client.post('/api/mobile/auth/reset-password',json={
        'username':'patient_one','password':'x'*16,'recovery_code':body['recovery_code']})
    assert result.status_code == 200, result.text
    assert mobile_client.post('/api/mobile/auth/login',json={'username':'patient_one','password':'x'*16}).status_code == 200
