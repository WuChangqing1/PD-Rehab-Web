"""Exports use synthetic in-memory records; never production data."""
import hashlib
import json
from datetime import date, datetime

import pytest
from sqlalchemy import select

from app.core.errors import APIError
from app.db.models import Patient, PatientAccessGrant, ExternalPracticeRecord, ExpertChatTurn, MediaFile, AuditLog, StaffUser


def patient(db, **kw):
    row = Patient(hospital_number=kw.pop('hospital_number', 'EXPORT-TEST'), name='导出测试', **kw)
    db.add(row); db.commit()
    return row


def test_export_authorization_scope_and_credentials(db, staff_user):
    from app.services.business_export import build_patient_export
    p = patient(db)
    other = patient(db, hospital_number='OTHER')
    another = StaffUser(username='another', display_name='Another', password_hash='SECRET', role='DOCTOR', is_active=True)
    db.add(another); db.commit()
    for owner in (staff_user.id, another.id):
        db.add(ExpertChatTurn(patient_id=p.id, operator_id=owner, question='问题', answer='答复', model='test'))
    db.add(ExternalPracticeRecord(patient_id=p.id, operator_id=staff_user.id, device_id='d', source_record_id='r', record_type='plan_snapshot', schema_version='1', payload_sha256='0'*64,
        payload_json=json.dumps({'plan': {'daily_progress': [1], 'password_hash': 'SECRET', 'nested': {'accessToken': 'SECRET', 'score': 2}}})))
    db.add(ExternalPracticeRecord(patient_id=other.id, operator_id=staff_user.id, device_id='d2', source_record_id='r2', record_type='piano', schema_version='1', payload_sha256='0'*64, payload_json='{}'))
    db.commit()
    data = build_patient_export(db, p.id, staff_user)
    assert len(data['records']['external_practice_records']) == 1
    assert len(data['records']['expert_chat_turns']) == 1
    assert 'SECRET' not in json.dumps(data)
    assert data['records']['external_practice_records'][0]['payload_json']['plan']['daily_progress'] == [1]
    body = {k:v for k,v in data.items() if k != 'integrity'}
    assert data['integrity']['sha256'] == hashlib.sha256(json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
    db.add(PatientAccessGrant(patient_id=p.id, staff_user_id=staff_user.id, active=False)); db.commit()
    with pytest.raises(APIError) as error:
        build_patient_export(db, p.id, staff_user)
    assert error.value.status_code == 403
    staff_user.role = 'PATIENT'
    with pytest.raises(APIError): build_patient_export(db, other.id, staff_user)


def test_inclusive_dates_and_invalid_range(db, staff_user):
    from app.services.business_export import build_patient_export
    p = patient(db)
    for index, stamp in enumerate((datetime(2025,12,31,15,59,59), datetime(2025,12,31,16), datetime(2026,1,1,15,59,59), datetime(2026,1,1,16))):
        db.add(ExternalPracticeRecord(patient_id=p.id, operator_id=staff_user.id, device_id=str(index),source_record_id=str(index),record_type='piano',schema_version='1',payload_sha256='0'*64,payload_json='{}',captured_at_ms=int(stamp.replace(tzinfo=__import__('datetime').timezone.utc).timestamp()*1000)))
    db.commit()
    data = build_patient_export(db, p.id, staff_user, date(2026,1,1), date(2026,1,1))
    assert len(data['records']['external_practice_records']) == 2
    with pytest.raises(APIError): build_patient_export(db, p.id, staff_user, date(2026,2,1), date(2026,1,1))


def test_attachment_metadata_excludes_missing_deleted_and_traversal(db, staff_user, tmp_path, monkeypatch):
    from app.services import business_export as service
    p = patient(db)
    monkeypatch.setattr(service.settings, 'upload_dir', str(tmp_path))
    # Config path may be data_dir-relative: bind the concrete property on its type.
    monkeypatch.setattr(type(service.settings), 'upload_path', property(lambda self: tmp_path))
    (tmp_path/'live.mp4').write_bytes(b'synthetic')
    for path in ('live.mp4','missing.mp4','../outside.mp4'):
        db.add(MediaFile(patient_id=p.id, type='MICRO_EXPRESSION_VIDEO', stored_path=path, size_bytes=9, sha256='0'*64))
    db.commit()
    data = service.build_patient_export(db,p.id,staff_user)
    assert len(data['attachments']) == 1
    assert data['attachments'][0]['sha256'] == hashlib.sha256(b'synthetic').hexdigest()
    assert data['attachments'][0]['metadata_sha256_matches'] is False
    assert 'stored_path' not in json.dumps(data)


def test_csv_formula_safety_and_router_audit(db, staff_user):
    from app.api.business_exports import export_patient
    p = patient(db)
    p.name = '=1+1'; db.commit()
    response = export_patient(p.id, db, staff_user, format='csv')
    assert "'=1+1" in response.body.decode('utf-8-sig')
    assert response.headers['cache-control'] == 'private, no-store'
    assert response.headers['x-content-sha256'] == hashlib.sha256(response.body).hexdigest()
    assert db.scalar(select(AuditLog).where(AuditLog.action == 'BUSINESS_EXPORT')) is not None

def test_parent_children_and_guided_owner_scope(db, staff_user):
    from app.db.models import AssessmentSession, PianoSession, PianoEvent, MicroExpressionResult, FingerTappingResult, TrainingPlan
    from app.db.models.guided_song import GuidedSongSession
    from app.services.business_export import build_patient_export
    p = patient(db)
    another = StaffUser(username='owner2', password_hash='SECRET', display_name='Other', role='DOCTOR')
    db.add(another); db.flush()
    assessment = AssessmentSession(patient_id=p.id, status='COMPLETED', started_at=datetime(2026,1,1))
    piano = PianoSession(patient_id=p.id, mode='SINGLE_KEY_RHYTHM', started_at=datetime(2026,1,1))
    db.add_all([assessment,piano]); db.flush()
    db.add_all([MicroExpressionResult(assessment_session_id=assessment.id), FingerTappingResult(assessment_session_id=assessment.id,hand='LEFT'), PianoEvent(session_id=piano.id,event_index=1)])
    db.add(TrainingPlan(patient_id=p.id,name='Active old plan',created_at=datetime(2025,1,1),start_date=date(2025,1,1),end_date=date(2026,2,1)))
    for owner in (staff_user.id,another.id):
        db.add(GuidedSongSession(patient_id=p.id,owner_id=owner,client_request_id=owner,created_at=datetime(2026,1,1),events=[{'midi':60}],audio=b'SECRET'))
    db.commit()
    data = build_patient_export(db,p.id,staff_user,date(2026,1,1),date(2026,1,1))
    assert len(data['records']['micro_expression_results']) == 1
    assert len(data['records']['finger_tapping_results']) == 1
    assert len(data['records']['piano_events']) == 1
    assert len(data['records']['guided_song_sessions']) == 1
    assert data['records']['guided_song_sessions'][0]['events'] == [{'midi':60}]
    assert len(data['records']['training_plans']) == 1
    assert 'SECRET' not in json.dumps(data)


def test_admin_metadata_forbidden_to_staff_and_no_credentials(db,staff_user):
    from app.services.business_export import build_administration_export
    with pytest.raises(APIError): build_administration_export(db,staff_user)
    staff_user.role = 'ADMIN'; db.commit()
    data = build_administration_export(db,staff_user)
    assert data['records']['staff_users'][0]['username'] == staff_user.username
    assert 'password_hash' not in json.dumps(data)


def test_http_authentication_scope_format_and_dates(db,staff_user):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.api.business_exports import router
    from app.api.deps import get_current_user
    from app.db.session import get_db
    app = FastAPI()
    app.include_router(router,prefix='/api')
    app.dependency_overrides[get_db] = lambda: db
    p = patient(db)
    with TestClient(app) as client:
        assert client.get(f'/api/business-exports/patients/{p.id}').status_code == 401
        app.dependency_overrides[get_current_user] = lambda: staff_user
        assert client.get(f'/api/business-exports/patients/{p.id}?format=xlsx').status_code == 422
        assert client.get(f'/api/business-exports/patients/{p.id}?start_date=bad').status_code == 422
        assert client.get(f'/api/business-exports/patients/{p.id}').status_code == 200
        assert client.get('/api/business-exports/administration').status_code == 403
        db.add(PatientAccessGrant(patient_id=p.id,staff_user_id=staff_user.id,active=False)); db.commit()
        assert client.get(f'/api/business-exports/patients/{p.id}').status_code == 403

def test_deleted_expired_training_media_not_in_manifest(db,staff_user,tmp_path,monkeypatch):
    from datetime import timedelta
    from uuid import uuid4
    from app.db.base import utcnow
    from app.db.models.face_recording import FaceRecording
    from app.services import business_export as service
    monkeypatch.setattr(type(service.settings),'upload_path',property(lambda self:tmp_path))
    p=patient(db)
    source=ExternalPracticeRecord(patient_id=p.id,operator_id=staff_user.id,device_id='d',source_record_id='r',record_type='piano',schema_version='1',payload_sha256='0'*64,payload_json='{}')
    db.add(source);db.flush()
    for state in ('live','deleted','expired','erased'):
        identifier,file_id=str(uuid4()),str(uuid4())
        created=utcnow()-timedelta(days=8) if state=='expired' else utcnow()
        blob={'manifest':{'files':[{'file_id':file_id,'sha256':'0'*64}]},'segments':[],'upload_complete':True,'media_deleted':state=='erased'}
        row=FaceRecording(id=identifier,patient_id=p.id,operator_id=staff_user.id,device_id='d',local_profile_id='p',client_capture_id=identifier,external_record_id=source.id,status='DELETED' if state=='deleted' else 'SUCCESS',manifest_sha256='0'*64,data_json=json.dumps(blob),created_at=created,updated_at=created)
        db.add(row)
        directory=tmp_path/'training-face'/identifier/file_id
        directory.mkdir(parents=True);(directory/'video.mp4').write_bytes(b'synthetic')
    db.commit()
    data=service.build_patient_export(db,p.id,staff_user)
    assert len([a for a in data['attachments'] if a['kind']=='training_video']) == 1
    assert len(data['records']['face_recordings']) == 3
    erased=next(r for r in data['records']['face_recordings'] if r['data_json'].get('media_deleted'))
    assert 'manifest' not in erased['data_json']


def test_explicit_allowlists_cover_columns_not_relationships():
    from app.services.business_export import EXPORT_FIELDS
    for model,fields in EXPORT_FIELDS.items():
        assert set(fields) <= {column.name for column in model.__table__.columns}
        assert not set(fields) & {'password_hash','refresh_hash','recovery_hash','stored_path','audio','analysis_config_json'}
