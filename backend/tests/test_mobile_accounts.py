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
        'username': username, 'password': 'test-password-123', 'display_name': '测试用户',
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
    assert user.password_hash != 'test-password-123'
    assert 'password_hash' not in str(body)
    staff_user.role = 'ADMIN'
    db.commit()
    result = mobile_client.get('/api/patients', headers=headers({'access_token':create_access_token(staff_user.id)}))
    assert result.status_code == 200, result.text
    assert any(p['id'] == body['patient']['id'] for p in result.json()['items'])
    duplicate = mobile_client.post('/api/mobile/auth/register', json={
        'username': 'PATIENT_ONE', 'password':'test-password-123', 'display_name':'二', 'sync_consent_version':'account-sync-v1'})
    assert duplicate.status_code == 409
    assert db.scalar(select(func.count()).select_from(Patient)) == 1


def test_patient_permissions_and_staff_login_separation(mobile_client):
    first, other = register(mobile_client), register(mobile_client, 'patient_two')
    h = headers(first)
    for method, path in [('GET','/api/patients'), ('POST','/api/patients'), ('GET','/api/auth/me'),
                         ('GET','/api/system/info')]:
        assert mobile_client.request(method, path, headers=h, json={}).status_code == 403, path
    assert mobile_client.post('/api/auth/login', json={'username':'patient_one','password':'test-password-123'}).status_code == 401
    assert mobile_client.get('/api/mobile/auth/me', headers=h).status_code == 200
    bootstrap=mobile_client.get('/api/integration/v1/bootstrap',headers=h).json()
    assert bootstrap['staff']==[] and [p['id'] for p in bootstrap['patients']]==[first['patient']['id']]
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
    second = mobile_client.post('/api/mobile/auth/login', json={'username':'patient_one','password':'test-password-123'}).json()
    payload={'username':'patient_one','password':'new-password-123','recovery_code':body['recovery_code']}
    reset=mobile_client.post('/api/mobile/auth/reset-password',json=payload)
    assert reset.status_code == 200, reset.text
    assert reset.json()['recovery_code'] != body['recovery_code']
    assert mobile_client.post('/api/mobile/auth/reset-password',json=payload).status_code == 401
    for device in (body, second):
        assert mobile_client.get('/api/mobile/auth/me', headers=headers(device)).status_code == 401
    assert mobile_client.post('/api/mobile/auth/login',json={'username':'patient_one','password':'test-password-123'}).status_code == 401
    assert mobile_client.post('/api/mobile/auth/login',json={'username':'patient_one','password':'new-password-123'}).status_code == 200


def test_invalid_or_privileged_registration_does_not_create_patient(mobile_client, db):
    data={'username':'new_patient','password':'test-password-123','display_name':'用户','sync_consent_version':'account-sync-v1'}
    for changes in [{'role':'ADMIN'}, {'patient_id':'123'}, {'password':'短'}, {'sync_consent_version':'unknown'}]:
        assert mobile_client.post('/api/mobile/auth/register',json={**data,**changes}).status_code == 422
    assert db.scalar(select(func.count()).select_from(Patient)) == 0


def test_deactivated_account_and_deleted_patient_reject_login(mobile_client, db):
    body=register(mobile_client)
    patient=db.get(Patient,body['patient']['id']); patient.is_deleted=True; db.commit()
    assert mobile_client.post('/api/mobile/auth/login',json={'username':'patient_one','password':'test-password-123'}).status_code == 401
    assert mobile_client.get('/api/mobile/auth/me',headers=headers(body)).status_code == 401


def test_change_password_revokes_all_sessions_and_validates_bytes(mobile_client):
    body = register(mobile_client)
    h = headers(body)
    assert mobile_client.post('/api/mobile/auth/change-password', headers=h,
        json={'current_password':'wrong-password','new_password':'new-password-123'}).status_code == 400
    assert mobile_client.post('/api/mobile/auth/change-password', headers=h,
        json={'current_password':'test-password-123','new_password':'字'*30}).status_code == 422
    result = mobile_client.post('/api/mobile/auth/change-password', headers=h,
        json={'current_password':'test-password-123','new_password':'new-password-123'})
    assert result.status_code == 200, result.text
    assert mobile_client.get('/api/mobile/auth/me',headers=h).status_code == 401
    assert mobile_client.post('/api/mobile/auth/login',json={'username':'patient_one','password':'new-password-123'}).status_code == 200


def test_patient_role_without_revocable_mobile_session_is_rejected(mobile_client):
    body = register(mobile_client)
    token = create_access_token(body['user']['id'], role='ADMIN')
    assert mobile_client.get('/api/mobile/auth/me', headers={'Authorization':'Bearer '+token}).status_code == 401


def test_mobile_token_does_not_turn_into_staff_token_after_role_change(mobile_client, db):
    body=register(mobile_client)
    user=db.get(StaffUser,body['user']['id'])
    user.role='DOCTOR'
    db.commit()
    assert mobile_client.get('/api/auth/me',headers=headers(body)).status_code==401


def test_registration_cannot_shadow_case_variant_staff(mobile_client, db, staff_user):
    staff_user.username='Staff_Name'
    db.commit()
    response=mobile_client.post('/api/mobile/auth/register',json={
        'username':'STAFF_NAME','password':'test-password-123','display_name':'User',
        'sync_consent_version':'account-sync-v1'})
    assert response.status_code==409
    assert db.scalar(select(func.count()).select_from(MobileAccount))==0
    assert db.scalar(select(func.count()).select_from(Patient))==0


def test_logout_with_rotated_token_still_revokes_the_device(mobile_client):
    body=register(mobile_client)
    renewed=mobile_client.post('/api/mobile/auth/refresh',json={'refresh_token':body['refresh_token']}).json()
    assert mobile_client.post('/api/mobile/auth/logout',json={'refresh_token':body['refresh_token']}).status_code==200
    assert mobile_client.get('/api/mobile/auth/me',headers=headers(renewed)).status_code==401


def test_patient_chat_rejects_other_patient_and_never_exposes_staff(mobile_client, monkeypatch):
    first,other=register(mobile_client),register(mobile_client,'second_patient')
    from app.services import integration_knowledge
    monkeypatch.setattr(integration_knowledge,'answer_question',lambda *args: {
        'answer':'test-help','model':'test','source':'test'})
    path='/api/integration/v1/expert/chat'
    assert mobile_client.post(path,headers=headers(first),json={'question':'help','patient_id':other['patient']['id']}).status_code==403
    assert mobile_client.post(path,headers=headers(first),json={'question':'help','patient_id':first['patient']['id']}).status_code==200


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


def test_parallel_registration_and_refresh_use_database_serialization(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from sqlalchemy import create_engine
    from app.db.base import Base
    from app.main import app
    eng=create_engine('sqlite:///'+str(tmp_path/'parallel.db'),connect_args={'check_same_thread':False,'timeout':15})
    Base.metadata.create_all(eng)
    factory=sessionmaker(bind=eng,autoflush=False)
    def isolated():
        with factory() as session:yield session
    app.dependency_overrides[get_db]=isolated
    _attempts.clear()
    try:
        with TestClient(app) as client:
            def signup(name):
                return client.post('/api/mobile/auth/register',json={
                    'username':name,'password':'test-password-123','display_name':'Parallel QA',
                    'sync_consent_version':'account-sync-v1'})
            with ThreadPoolExecutor(2) as pool:
                a,b=list(pool.map(signup,['parallel_a','parallel_b']))
            assert a.status_code==b.status_code==201
            assert a.json()['patient']['id']!=b.json()['patient']['id']
            assert a.json()['patient']['hospital_number']!=b.json()['patient']['hospital_number']
            with ThreadPoolExecutor(2) as pool:
                attempts=list(pool.map(signup,['same_name','SAME_NAME']))
            assert sorted(r.status_code for r in attempts)==[201,409]
            token=a.json()['refresh_token']
            with ThreadPoolExecutor(2) as pool:
                results=list(pool.map(lambda _:client.post('/api/mobile/auth/refresh',json={'refresh_token':token}),range(2)))
            assert sorted(r.status_code for r in results)==[200,401]
            renewed=next(r.json() for r in results if r.status_code==200)
            assert client.post('/api/mobile/auth/logout',json={'refresh_token':token}).status_code==200
            assert client.get('/api/mobile/auth/me',headers=headers(renewed)).status_code==401
            with factory() as db:
                assert db.scalar(select(func.count()).select_from(MobileAccount))==3
                assert db.scalar(select(func.count()).select_from(Patient))==3
    finally:
        app.dependency_overrides.clear()
        eng.dispose()


def test_patient_playback_cookie_stops_after_logout(mobile_client, db, monkeypatch, tmp_path):
    import hashlib
    import uuid
    from app.api import face_recordings as api
    monkeypatch.setattr(api,'available',lambda:True)
    monkeypatch.setattr(api.settings,'upload_dir',str(tmp_path))
    body=register(mobile_client);h=headers(body)
    binding={'device_id':'patient-play-device','local_profile_id':'patient-play-profile','patient_id':body['patient']['id']}
    assert mobile_client.post('/api/integration/v1/bindings',json=binding,headers=h).status_code==200
    record=mobile_client.post('/api/integration/v1/records',json={**binding,
        'source_record_id':'play-test','record_type':'DANCE_SESSION','schema_version':'test','payload':{}},headers=h).json()
    content=b'protocol-content-not-an-inference-video'
    fid=str(uuid.uuid4())
    manifest={**binding,'external_record_id':record['id'],'client_capture_id':str(uuid.uuid4()),
        'consent_version':'face-capture-v1','agreed_at_ms':123,
        'files':[{'file_id':fid,'sequence':0,'size_bytes':len(content),
            'sha256':hashlib.sha256(content).hexdigest(),'chunk_count':1,'mime_type':'video/mp4','duration_ms':1000}]}
    created=mobile_client.post('/api/integration/v1/face/recordings',json=manifest,headers=h)
    assert created.status_code==201,created.text
    path='/api/integration/v1/face/recordings/'+created.json()['recording_id']
    assert mobile_client.put(path+'/files/'+fid+'/chunks/0',content=content,
        headers={**h,'X-Chunk-SHA256':hashlib.sha256(content).hexdigest()}).status_code==200
    assert mobile_client.post(path+'/complete',headers=h).status_code==202
    media=path+'/files/'+fid+'/playback'
    ticket=mobile_client.post(media,headers=h)
    assert ticket.status_code==204,ticket.text
    cookie=ticket.headers.get_list('set-cookie')[0].split(';',1)[0]
    assert mobile_client.get(media,headers={'Cookie':cookie}).content==content
    assert mobile_client.post('/api/mobile/auth/logout',json={'refresh_token':body['refresh_token']}).status_code==200
    assert mobile_client.get(media+'?download=true',headers={'Cookie':cookie}).status_code==401
