"""Independent-review regressions: retries cannot acquire ownership; jobs obey scope."""
from sqlalchemy import select
from app.db.models import StaffUser, Patient, PatientAccessGrant, AuditLog
from tests.test_staff_accounts import headers


def test_nurse_cannot_claim_existing_piano_by_retry(app_client,db,staff_user):
    p=Patient(name='Retry patient',hospital_number='retry');db.add(p);db.commit()
    body={'mode':'SINGLE_KEY_RHYTHM','client_request_id':'copy-me'}
    path=f'/api/patients/{p.id}/piano/sessions'
    created=app_client.post(path,headers=headers(staff_user),json=body)
    assert created.status_code==201,created.text
    sid=created.json()['id'];cleanup=f'/api/patients/{p.id}/training/active/piano/{sid}'
    nurse=StaffUser(username='replaynurse',password_hash='hash',display_name='Nurse',role='NURSE',is_active=True)
    db.add(nurse);db.commit();nh=headers(nurse)
    assert app_client.get(f'/api/piano/sessions/{sid}',headers=nh).status_code==200
    assert app_client.delete(cleanup,headers=nh).status_code==403
    assert app_client.post(path,headers=nh,json=body).status_code==403
    assert db.scalar(select(AuditLog.id).where(AuditLog.entity_id==sid,AuditLog.staff_user_id==nurse.id,AuditLog.action=='PIANO_SESSION_START')) is None
    assert app_client.delete(cleanup,headers=nh).status_code==403
    retried=app_client.post(path,headers=headers(staff_user),json=body)
    assert retried.status_code==201 and retried.json()['id']==sid


def test_jobs_patient_scope_and_unscoped_fail_closed(app_client,db,staff_user):
    from app.jobs.manager import job_manager
    from app.services import integration_access
    allowed=Patient(name='Allowed',hospital_number='job-allowed')
    denied=Patient(name='Denied',hospital_number='job-denied')
    db.add_all([allowed,denied]);db.flush()
    db.add(PatientAccessGrant(patient_id=denied.id,staff_user_id=staff_user.id,active=False));db.commit()
    jobs=[]
    try:
        for pid,secret in ((allowed.id,'allowed-result'),(denied.id,'denied-result'),(None,'legacy-result')):
            job=job_manager.create('FINGER_TAPPING_ANALYSIS')
            job.patient_id=pid;job.result_ref={'outcome':secret};jobs.append(job)
        h=headers(staff_user)
        result=app_client.get('/api/jobs',headers=h)
        assert result.status_code==200
        ids={r['job_id'] for r in result.json()}
        assert jobs[0].job_id in ids and jobs[1].job_id not in ids and jobs[2].job_id not in ids
        assert 'denied-result' not in result.text and 'legacy-result' not in result.text
        assert app_client.get('/api/jobs/'+jobs[0].job_id,headers=h).status_code==200
        for job in jobs[1:]:assert app_client.get('/api/jobs/'+job.job_id,headers=h).status_code==403
        staff_user.role='ADMIN';db.commit()
        for job in jobs:assert app_client.get('/api/jobs/'+job.job_id,headers=h).status_code==200
    finally:
        for job in jobs:job_manager._jobs.pop(job.job_id,None)


def test_calibration_owner_retry_and_forged_later_start_cannot_claim(app_client,db,staff_user):
    from app.db.base import utcnow
    from datetime import timedelta
    p=Patient(name='Calibration retry',hospital_number='cal-retry');db.add(p);db.commit()
    path=f'/api/patients/{p.id}/piano/calibration';body={'client_request_id':'cal-copy'}
    first=app_client.post(path,headers=headers(staff_user),json=body)
    assert first.status_code==201,first.text
    sid=first.json()['id']
    assert app_client.post(path,headers=headers(staff_user),json=body).json()['id']==sid
    nurse=StaffUser(username='calnurse',password_hash='hash',display_name='Nurse',role='NURSE',is_active=True)
    db.add(nurse);db.commit();nh=headers(nurse)
    assert app_client.post(path,headers=nh,json=body).status_code==403
    # Simulate a duplicate legacy START emitted by an earlier release: later
    # events are never trusted as ownership, even if they name the caller.
    db.add(AuditLog(staff_user_id=nurse.id,entity_id=sid,entity_type='piano_session',action='PIANO_CALIBRATION_START',created_at=utcnow()+timedelta(seconds=1)));db.commit()
    assert app_client.delete(f'/api/patients/{p.id}/training/active/piano/{sid}',headers=nh).status_code==403
    pending=app_client.get(f'/api/patients/{p.id}/training/active',headers=nh).json()
    assert next(r for r in pending if r['id']==sid)['can_clear'] is False
