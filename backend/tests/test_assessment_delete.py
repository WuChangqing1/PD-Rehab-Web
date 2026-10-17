from sqlalchemy import select,func,update

from app.core.config import settings
from app.db.base import utcnow
from app.db.models import AssessmentSession,Patient,MediaFile,FingerTappingResult,MicroExpressionResult,FunctionalAssessment,AuditLog


def setup_records(db, user_id):
    patient=Patient(hospital_number='delete-qa',name='Test only')
    db.add(patient);db.flush()
    records=[AssessmentSession(patient_id=patient.id,session_type='COMPREHENSIVE',
        status='IN_PROGRESS',created_by=user_id) for _ in range(2)]
    db.add_all(records);db.commit()
    return patient,records


def test_delete_only_selected_unfinished_assessment(app_client,auth_headers,db,staff_user):
    patient,records=setup_records(db,staff_user.id)
    reply=app_client.delete(f'/api/assessment-sessions/{records[0].id}',headers=auth_headers)
    assert reply.status_code==200
    assert reply.json()['deleted'] is True
    assert app_client.get(f'/api/assessment-sessions/{records[0].id}',headers=auth_headers).status_code==404
    assert app_client.get(f'/api/assessment-sessions/{records[1].id}',headers=auth_headers).status_code==200
    page=app_client.get(f'/api/patients/{patient.id}/assessment-sessions?status=IN_PROGRESS',headers=auth_headers).json()
    assert page['total']==1 and page['items'][0]['id']==records[1].id
    audit=db.scalar(select(AuditLog).where(AuditLog.action=='ASSESSMENT_SESSION_DELETE'))
    assert audit is not None and audit.entity_id==records[0].id


def test_completed_assessment_is_not_deleted(app_client,auth_headers,db,staff_user):
    _,records=setup_records(db,staff_user.id)
    records[0].status='COMPLETED';db.commit()
    assert app_client.delete(f'/api/assessment-sessions/{records[0].id}',headers=auth_headers).status_code==409
    assert app_client.get(f'/api/assessment-sessions/{records[0].id}',headers=auth_headers).status_code==200


def test_delete_requires_authentication_and_handles_missing_record(app_client,auth_headers,db,staff_user):
    _,records=setup_records(db,staff_user.id)
    assert app_client.delete(f'/api/assessment-sessions/{records[0].id}').status_code==401
    assert app_client.delete('/api/assessment-sessions/missing',headers=auth_headers).status_code==404


def test_delete_cleans_owned_results_and_media_but_preserves_other_record(app_client,auth_headers,db,staff_user,tmp_path,monkeypatch):
    monkeypatch.setattr(settings,'upload_dir',str(tmp_path))
    _,records=setup_records(db,staff_user.id)
    first=tmp_path/'first.mp4';first.write_bytes(b'QA only')
    second=tmp_path/'second.mp4';second.write_bytes(b'QA only')
    media=[MediaFile(patient_id=r.patient_id,assessment_session_id=r.id,type='FINGER_TAPPING_VIDEO',stored_path=str(path))
           for r,path in zip(records,[first,second])]
    db.add_all(media);db.flush()
    db.add_all([FingerTappingResult(assessment_session_id=r.id,media_file_id=m.id,hand='LEFT',input_source='SYNTHETIC_SELFTEST') for r,m in zip(records,media)])
    db.add(MicroExpressionResult(assessment_session_id=records[0].id,model_name='TEST_ONLY'))
    db.add(FunctionalAssessment(patient_id=records[0].patient_id,assessment_session_id=records[0].id,
        test_type='NINE_HOLE_PEG',value_primary=1,unit='s',performed_at=utcnow()))
    db.commit()
    reply=app_client.delete(f'/api/assessment-sessions/{records[0].id}',headers=auth_headers)
    assert reply.status_code==200
    assert not first.exists() and second.exists()
    assert db.scalar(select(func.count()).select_from(FingerTappingResult))==1
    assert db.scalar(select(func.count()).select_from(MicroExpressionResult))==0
    assert db.scalar(select(func.count()).select_from(FunctionalAssessment))==0
    assert db.scalar(select(func.count()).select_from(MediaFile))==1


def test_deletion_never_unlinks_paths_outside_configured_upload_root(app_client,auth_headers,db,staff_user,tmp_path,monkeypatch):
    root=tmp_path/'uploads';root.mkdir()
    monkeypatch.setattr(settings,'upload_dir',str(root))
    external=tmp_path/'keep.txt';external.write_text('not an upload')
    _,records=setup_records(db,staff_user.id)
    db.add(MediaFile(patient_id=records[0].patient_id,assessment_session_id=records[0].id,type='REPORT',stored_path=str(external)))
    db.commit()
    reply=app_client.delete(f'/api/assessment-sessions/{records[0].id}',headers=auth_headers)
    assert reply.status_code==200 and external.exists()


def test_patient_mismatch_does_not_delete_record(app_client,auth_headers,db,staff_user):
    _,records=setup_records(db,staff_user.id)
    reply=app_client.delete(f'/api/assessment-sessions/{records[0].id}?patient_id=another-patient',headers=auth_headers)
    assert reply.status_code==409
    assert app_client.get(f'/api/assessment-sessions/{records[0].id}',headers=auth_headers).status_code==200


def test_media_referenced_by_other_assessment_is_preserved(app_client,auth_headers,db,staff_user,tmp_path,monkeypatch):
    monkeypatch.setattr(settings,'upload_dir',str(tmp_path))
    _,records=setup_records(db,staff_user.id)
    path=tmp_path/'shared.mp4';path.write_bytes(b'QA shared media')
    media=MediaFile(patient_id=records[0].patient_id,assessment_session_id=records[0].id,type='FINGER_TAPPING_VIDEO',stored_path=str(path))
    db.add(media);db.flush()
    db.add(FingerTappingResult(assessment_session_id=records[1].id,media_file_id=media.id,hand='LEFT',input_source='SYNTHETIC_SELFTEST'))
    db.commit()
    assert app_client.delete(f'/api/assessment-sessions/{records[0].id}',headers=auth_headers).status_code==200
    db.expire_all()
    retained=db.get(MediaFile,media.id)
    assert retained is not None and retained.assessment_session_id is None and path.exists()
    assert db.scalar(select(func.count()).select_from(FingerTappingResult))==1


def test_delete_cleans_only_owned_unshared_timeseries(app_client,auth_headers,db,staff_user,tmp_path,monkeypatch):
    monkeypatch.setattr(settings,'output_dir',str(tmp_path))
    _,records=setup_records(db,staff_user.id)
    owned=tmp_path/'owned.npz';owned.write_bytes(b'QA owned')
    shared=tmp_path/'shared.npz';shared.write_bytes(b'QA shared')
    db.add_all([
        FingerTappingResult(assessment_session_id=records[0].id,hand='LEFT',raw_timeseries_path=str(owned)),
        FingerTappingResult(assessment_session_id=records[0].id,hand='RIGHT',raw_timeseries_path=str(shared)),
        FingerTappingResult(assessment_session_id=records[1].id,hand='RIGHT',raw_timeseries_path=str(shared)),
    ]);db.commit()
    assert app_client.delete(f'/api/assessment-sessions/{records[0].id}',headers=auth_headers).status_code==200
    assert not owned.exists() and shared.exists()


def test_concurrent_completion_rolls_back_all_deletion(app_client,auth_headers,db,staff_user,engine,monkeypatch):
    from app.services import assessment_service as service
    _,records=setup_records(db,staff_user.id)
    target_id=records[0].id
    db.add(FingerTappingResult(assessment_session_id=target_id,hand='LEFT'))
    db.commit()
    original=service.get_session
    def complete_after_read(current_db,session_id):
        stale=original(current_db,session_id)
        with engine.begin() as connection:
            connection.execute(update(AssessmentSession).where(AssessmentSession.id==session_id).values(status='COMPLETED'))
        return stale
    monkeypatch.setattr(service,'get_session',complete_after_read)
    reply=app_client.delete(f'/api/assessment-sessions/{target_id}',headers=auth_headers)
    assert reply.status_code==409
    db.expire_all()
    assert db.get(AssessmentSession,target_id).status=='COMPLETED'
    assert db.scalar(select(func.count()).select_from(FingerTappingResult))==1
