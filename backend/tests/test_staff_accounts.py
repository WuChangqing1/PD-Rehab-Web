from sqlalchemy import select
from app.db.models import StaffUser, Patient
from app.core.security import create_access_token

def headers(user):
    return {'Authorization': 'Bearer '+create_access_token(user.id,role='ADMIN')}

def test_pending_review(app_client,db,staff_user):
    body=dict(username='NewNurse',password='strong-pass-123',display_name='护士',phone='13800138000',requested_role='NURSE')
    r=app_client.post('/api/auth/register',json=body)
    assert r.status_code==201,r.text
    aid=r.json()['id']; assert 'access_token' not in r.json()
    assert db.scalar(select(StaffUser).where(StaffUser.username=='newnurse')) is None
    assert app_client.post('/api/auth/register',json={**body,'username':'NEWNURSE'}).status_code==409
    assert app_client.get('/api/auth/staff',headers=headers(staff_user)).status_code==403
    staff_user.role='ADMIN';db.commit()
    for _ in range(2):
        assert app_client.post(f'/api/auth/staff-applications/{aid}/review',headers=headers(staff_user),json={'decision':'APPROVE'}).status_code==200
    nurse=db.scalar(select(StaffUser).where(StaffUser.username=='newnurse'))
    assert nurse.role=='NURSE'
    assert app_client.post('/api/auth/login',json={'username':'NEWNURSE','password':body['password']}).status_code==200
    assert app_client.get('/api/auth/staff',headers=headers(nurse)).status_code==403
    assert app_client.patch(f'/api/auth/staff/{staff_user.id}',headers=headers(staff_user),json={'is_active':False}).status_code==409

def test_profile(app_client):
    from app.api.mobile_auth import _attempts
    _attempts.clear()
    r=app_client.post('/api/mobile/auth/register',json=dict(username='namepatient',password='password-123',display_name='旧姓名',sync_consent_version='account-sync-v1'))
    assert r.status_code==201,r.text
    data=r.json();h={'Authorization':'Bearer '+data['access_token']}
    r=app_client.patch('/api/mobile/auth/profile',headers=h,json={'display_name':'新姓名','expected_name':'旧姓名'})
    assert r.status_code==200,r.text
    assert r.json()['patient']['name']==r.json()['user']['display_name']=='新姓名'
    assert r.json()['user']['id']==data['user']['id']
    assert app_client.patch('/api/mobile/auth/profile',headers=h,json={'display_name':'覆盖','expected_name':'旧姓名'}).status_code==409
    assert app_client.patch('/api/mobile/auth/profile',headers=h,json={'display_name':'覆盖','expected_name':'新姓名','role':'ADMIN'}).status_code==422

def test_nurse_boundary(app_client,db,staff_user,patient_payload):
    from app.schemas.patient import PatientCreate
    p=Patient(**PatientCreate(**patient_payload).model_dump());db.add(p);db.commit()
    staff_user.role='NURSE';db.commit();h=headers(staff_user)
    assert app_client.get(f'/api/patients/{p.id}',headers=h).status_code==200
    assert app_client.patch(f'/api/patients/{p.id}',headers=h,json={'doctor_notes':'diagnosis'}).status_code==403
    assert app_client.delete(f'/api/patients/{p.id}',headers=h).status_code==403
    assert app_client.patch(f'/api/patients/{p.id}',headers=h,json={'name':'姓名'}).status_code==200
    staff_user.role='UNKNOWN';db.commit()
    assert app_client.get('/api/patients',headers=h).status_code==403


def test_web_name_sync_and_legacy_canonical(app_client,db,staff_user):
    from app.api.mobile_auth import _attempts
    from app.db.models import MobileAccount
    _attempts.clear()
    data=app_client.post('/api/mobile/auth/register',json=dict(username='canonical',password='password-123',display_name='Original',sync_consent_version='account-sync-v1')).json()
    h={'Authorization':'Bearer '+data['access_token']};pid=data['patient']['id']
    assert app_client.patch(f'/api/patients/{pid}',headers=headers(staff_user),json={'name':'Web name'}).status_code==200
    db.expire_all()
    assert db.get(StaffUser,data['user']['id']).display_name=='Web name'
    p=db.get(Patient,pid);p.name='Legacy changed';db.commit()
    identity=app_client.get('/api/mobile/auth/me',headers=h).json()
    assert identity['user']['display_name']=='Legacy changed'
    assert app_client.get('/api/integration/v1/bootstrap',headers=h).json()['user']['display_name']=='Legacy changed'


def test_pending_cleanup_owner_and_plan_boundary(app_client,db,staff_user,patient_payload):
    from app.schemas.patient import PatientCreate
    from app.db.models import AssessmentSession
    p=Patient(**PatientCreate(**patient_payload).model_dump());db.add(p);db.flush()
    session=AssessmentSession(patient_id=p.id,created_by=None,status='IN_PROGRESS')
    db.add(session);db.commit();staff_user.role='NURSE';db.commit()
    h=headers(staff_user)
    assert app_client.delete(f'/api/assessment-sessions/{session.id}',headers=h).status_code==403
    session.created_by=staff_user.id;db.commit()
    assert app_client.delete(f'/api/assessment-sessions/{session.id}',headers=h).status_code==200
    body=dict(patient_id=p.id,device_id='test-device',local_profile_id='test-profile',source_record_id='plan-1',record_type='TRAINING_PLAN',schema_version='1',payload={})
    assert app_client.post('/api/integration/v1/records',headers=h,json=body).status_code==403


def test_profile_control_characters(app_client):
    from app.api.mobile_auth import Profile
    import pytest
    with pytest.raises(ValueError):Profile(display_name='hello\nworld',expected_name='old')
