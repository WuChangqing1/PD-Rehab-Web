"""Negative authorization, concurrent account invariants and media capabilities."""
import json
import uuid
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from app.db.base import Base
from app.db.models import StaffUser, Patient, PatientAccessGrant, AssessmentSession, PianoSession, AuditLog
from app.db.models.staff_application import StaffApplication
from app.core.security import hash_password, create_access_token
from tests.test_staff_accounts import headers
from tests.test_training_face_recordings import setup_recording, create, send


def test_database_role_and_deactivation_invalidate_old_jwt(app_client,db,staff_user):
    old=headers(staff_user)
    staff_user.role='ADMIN';db.commit()
    assert app_client.get('/api/auth/staff',headers=old).status_code==200
    staff_user.role='NURSE';db.commit()
    assert app_client.get('/api/auth/staff',headers=old).status_code==403
    staff_user.is_active=False;db.commit()
    assert app_client.get('/api/auth/me',headers=old).status_code==401


def test_application_validation_rejection_and_no_secret(app_client,db,staff_user):
    from app.api.mobile_auth import _attempts
    _attempts.clear();staff_user.role='ADMIN';db.commit();h=headers(staff_user)
    body=dict(username='applicant',password='password-123',display_name='Applicant',phone='13800138000',requested_role='DOCTOR')
    for extra in ({'requested_role':'ADMIN'},{'is_active':True},{'patient_id':str(uuid.uuid4())}):
        assert app_client.post('/api/auth/register',json={**body,**extra}).status_code==422
    r=app_client.post('/api/auth/register',json=body);assert r.status_code==201
    row=db.get(StaffApplication,r.json()['id']);assert row.password_hash!=body['password']
    listing=app_client.get('/api/auth/staff-applications?status=PENDING',headers=h)
    assert listing.status_code==200 and 'password' not in listing.text
    assert app_client.post('/api/mobile/auth/register',json=dict(username='APPLICANT',password='password-123',display_name='Patient',sync_consent_version='account-sync-v1')).status_code==409
    rejected=app_client.post(f'/api/auth/staff-applications/{row.id}/review',headers=h,json={'decision':'REJECT','reason':'Needs verification'})
    assert rejected.status_code==200 and rejected.json()['status']=='REJECTED'
    assert app_client.post(f'/api/auth/staff-applications/{row.id}/review',headers=h,json={'decision':'APPROVE'}).status_code==409
    assert app_client.post('/api/auth/login',json={'username':body['username'],'password':body['password']}).status_code==401
    _attempts.clear()


def test_registration_rate_limit(app_client):
    from app.api.mobile_auth import _attempts
    _attempts.clear()
    body=dict(username='rateuser',password='password-123',display_name='Applicant',phone='13800138000',requested_role='NURSE')
    for i in range(6):assert app_client.post('/api/auth/register',json={**body,'username':f'rateuser{i}'}).status_code==201
    assert app_client.post('/api/auth/register',json={**body,'username':'rateuser99'}).status_code==429
    _attempts.clear()


def test_explicit_denial_still_applies_shared_workspace(app_client,db,staff_user):
    p=Patient(name='Shared patient',hospital_number='shared');db.add(p);db.flush()
    db.add(PatientAccessGrant(patient_id=p.id,staff_user_id=staff_user.id,active=False));db.commit()
    assert app_client.get(f'/api/patients/{p.id}',headers=headers(staff_user)).status_code==404
    assert app_client.get('/api/integration/v1/patient-data',params={'patient_id':p.id},headers=headers(staff_user)).status_code==403


def test_patient_cannot_reach_staff_or_other_patient_or_plan_write(app_client,db):
    from app.api.mobile_auth import _attempts
    _attempts.clear()
    data=app_client.post('/api/mobile/auth/register',json=dict(username='ownpatient',password='password-123',display_name='Own patient',sync_consent_version='account-sync-v1')).json()
    h={'Authorization':'Bearer '+data['access_token']}
    p=Patient(name='Other',hospital_number='other');db.add(p);db.commit()
    for path in ('/api/auth/staff','/api/patients','/api/system/dashboard'):
        assert app_client.get(path,headers=h).status_code==403
    assert app_client.get('/api/integration/v1/patient-data',params={'patient_id':p.id},headers=h).status_code==403
    body=dict(device_id='own-device',local_profile_id='own-profile',patient_id=data['patient']['id'])
    assert app_client.post('/api/integration/v1/bindings',headers=h,json=body).status_code==200
    assert app_client.post('/api/integration/v1/records',headers=h,json={**body,'record_type':'TRAINING_PLAN','source_record_id':'own-plan','schema_version':'1','payload':{}}).status_code==201


def test_shared_recording_read_mutations_and_completed_erasure(app_client,auth_headers,setup_recording,db,staff_user):
    from app.db.models.face_recording import FaceRecording
    manifest,content,_=setup_recording;rid=create(app_client,auth_headers,manifest)
    assert send(app_client,auth_headers,rid,manifest,content).status_code==200
    base=f'/api/integration/v1/face/recordings/{rid}'
    assert app_client.post(base+'/complete',headers=auth_headers).status_code==202
    nurse=StaffUser(username='readnurse',display_name='Nurse',role='NURSE',is_active=True,password_hash=hash_password('password-123'))
    db.add(nurse);db.commit();nh=headers(nurse)
    assert app_client.get(base,headers=nh).status_code==200
    for suffix in ('/complete','/retry','/cancel'):
        assert app_client.post(base+suffix,headers=nh).status_code==403
    assert app_client.delete(base,headers=nh).status_code==403
    path=f"{base}/files/{manifest['files'][0]['file_id']}/playback"
    ticket=app_client.post(path,headers=nh);assert ticket.status_code==204
    cookie={'Cookie':ticket.headers['set-cookie'].split(';',1)[0]}
    assert app_client.get(path,headers=cookie).status_code==200
    assert app_client.head(path,headers=cookie).status_code==200
    nurse.is_active=False;db.commit()
    for method in (app_client.get,app_client.head):assert method(path,headers=cookie).status_code==401
    nurse.is_active=True;nurse.role='UNKNOWN';db.commit()
    assert app_client.get(path,headers=cookie).status_code==401
    row=db.get(FaceRecording,rid);row.status='SUCCESS';staff_user.role='DOCTOR';db.commit()
    assert app_client.delete(base,headers=auth_headers).status_code==403
    assert app_client.post(base+'/cancel',headers=auth_headers).status_code==403
    staff_user.role='ADMIN';db.commit()
    assert app_client.delete(base,headers=auth_headers).status_code==200


def test_nurse_cleanup_legacy_training_requires_owner(app_client,db,staff_user):
    from app.db.base import utcnow
    p=Patient(name='Pending',hospital_number='pending');db.add(p);db.flush()
    row=PianoSession(patient_id=p.id,mode='CALIBRATION',started_at=utcnow());db.add(row);db.commit()
    staff_user.role='NURSE';db.commit();h=headers(staff_user)
    path=f'/api/patients/{p.id}/training/active/piano/{row.id}'
    assert app_client.delete(path,headers=h).status_code==403
    db.add(AuditLog(staff_user_id=staff_user.id,entity_id=row.id,entity_type='piano_session',action='PIANO_CALIBRATION_START',created_at=utcnow()));db.commit()
    assert app_client.delete(path,headers=h).status_code==200


def test_concurrent_approval_and_last_admin_sqlite(tmp_path):
    from app.api.staff_accounts import review, Review, patch_staff, StaffPatch
    from app.core.errors import APIError
    engine=create_engine('sqlite:///'+(tmp_path/'concurrent.db').as_posix(),connect_args={'check_same_thread':False,'timeout':30})
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        a=StaffUser(username='admin1',display_name='Admin',role='ADMIN',password_hash='hash',is_active=True)
        b=StaffUser(username='admin2',display_name='Admin',role='ADMIN',password_hash='hash',is_active=True)
        app=StaffApplication(username='approval',password_hash='hash',display_name='Applicant',phone='1234567',requested_role='NURSE')
        db.add_all([a,b,app]);db.commit();ids=(a.id,b.id,app.id)
    barrier=Barrier(2)
    def approve(_):
        with Session(engine) as db:
            actor=db.get(StaffUser,ids[0]);barrier.wait()
            return review(ids[2],Review(decision='APPROVE'),db,actor)['user_id']
    with ThreadPoolExecutor(2) as pool:assert len(set(pool.map(approve,range(2))))==1
    with Session(engine) as db:assert len(db.scalars(select(StaffUser).where(StaffUser.username=='approval')).all())==1
    barrier=Barrier(2)
    def demote(actor_id):
        with Session(engine) as db:
            actor=db.get(StaffUser,actor_id);barrier.wait()
            try:patch_staff(actor_id,StaffPatch(role='DOCTOR'),db,actor);return 200
            except APIError as e:return e.status_code
    with ThreadPoolExecutor(2) as pool:assert sorted(pool.map(demote,ids[:2]))==[200,409]
    with Session(engine) as db:assert len(db.scalars(select(StaffUser).where(StaffUser.role=='ADMIN',StaffUser.is_active.is_(True))).all())==1
    engine.dispose()


def test_nurse_full_intake_preserves_professional_notes(app_client,db,staff_user):
    p=Patient(name='Intake',hospital_number='intake',doctor_notes='Doctor opinion')
    db.add(p);db.commit();staff_user.role='NURSE';db.commit();h=headers(staff_user)
    r=app_client.patch(f'/api/patients/{p.id}',headers=h,json={'name':'Updated intake','doctor_notes':'Doctor opinion','diagnosis_date':'2020-01-01','medical_history':'Collected history'})
    assert r.status_code==200,r.text
    assert r.json()['doctor_notes']=='Doctor opinion'
    assert app_client.patch(f'/api/patients/{p.id}',headers=h,json={'doctor_notes':None}).status_code==403
    assert app_client.post('/api/patients',headers=h,json={'name':'Nurse intake','doctor_notes':'New diagnosis'}).status_code==403
    assert app_client.post('/api/patients',headers=h,json={'name':'Nurse intake','medical_history':'Collected history'}).status_code==201
