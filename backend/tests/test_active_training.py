from datetime import timedelta,timezone
import pytest
from sqlalchemy import select
from app.db.base import utcnow
from app.db.models import Patient, PianoSession, PoseSession
from app.schemas.piano import PianoSessionCreate
from app.schemas.pose import PoseSessionCreate
from app.services import piano_service, pose_service
from app.core.errors import APIError
from tests.test_piano_concurrent_retries import engine
from tests.test_piano_extended_recipes import event

def patient(db):
    p=Patient(hospital_number='ACTIVE-TEST',name='小明')
    db.add(p);db.commit();return p

def test_same_patient_cannot_open_second_piano_or_pose(db):
    p=patient(db)
    first=piano_service.create_session(db,p.id,PianoSessionCreate(mode='SINGLE_KEY_RHYTHM',client_request_id='one'))
    assert piano_service.create_session(db,p.id,PianoSessionCreate(mode='SINGLE_KEY_RHYTHM',client_request_id='one')).id==first.id
    with pytest.raises(APIError) as caught:
        pose_service.create_session(db,p.id,PoseSessionCreate(exercise_type='BALLET_PORT_DE_BRAS'))
    assert caught.value.status_code==409
    db.rollback()
    with pytest.raises(APIError):
        piano_service.create_session(db,p.id,PianoSessionCreate(mode='CALIBRATION',client_request_id='two'))

def test_clear_pending_preserves_raw_state_and_allows_new(db):
    from app.services.active_training_service import clear_pending, pending
    p=patient(db)
    first=pose_service.create_session(db,p.id,PoseSessionCreate(exercise_type='BALLET_PORT_DE_BRAS'))
    assert len(pending(db,p.id))==1
    clear_pending(db,p.id,'pose',first.id,owner_id='staff')
    assert pending(db,p.id)==[]
    db.refresh(first)
    assert first.completed_at is None
    assert first.difficulty_json and 'CANCELLED' in first.difficulty_json
    assert piano_service.create_session(db,p.id,PianoSessionCreate(mode='SINGLE_KEY_RHYTHM')).id

def test_other_patient_and_previous_day_do_not_block(db):
    p=patient(db)
    yesterday=utcnow()-timedelta(days=1)
    db.add(PianoSession(patient_id=p.id,mode='SINGLE_KEY_RHYTHM',started_at=yesterday))
    db.commit()
    assert pose_service.create_session(db,p.id,PoseSessionCreate(exercise_type='BALLET_PORT_DE_BRAS')).id

def test_finished_piano_does_not_block(db):
    p=patient(db)
    db.add(PianoSession(patient_id=p.id,mode='SINGLE_KEY_RHYTHM',started_at=utcnow(),completed_at=utcnow()))
    db.commit()
    assert pose_service.create_session(db,p.id,PoseSessionCreate(exercise_type='BALLET_PORT_DE_BRAS')).id

def test_backdated_client_start_cannot_bypass_server_day(db):
    p=patient(db)
    piano_service.create_session(db,p.id,PianoSessionCreate(mode='SINGLE_KEY_RHYTHM',started_at=(utcnow()-timedelta(days=2)).replace(tzinfo=timezone.utc)))
    with pytest.raises(APIError):pose_service.create_session(db,p.id,PoseSessionCreate(exercise_type='BALLET_PORT_DE_BRAS'))


def test_late_pose_outcome_rechecks_cancellation(db,engine):
    from sqlalchemy.orm import Session
    from app.services.active_training_service import clear_pending
    p=patient(db)
    session=pose_service.create_session(db,p.id,PoseSessionCreate(exercise_type='BALLET_PORT_DE_BRAS'))
    db.commit()
    with Session(engine) as other:
        clear_pending(other,p.id,'pose',session.id,owner_id='staff')
    with pytest.raises(APIError) as caught:
        pose_service.write_outcome(db,session,object())
    assert caught.value.status_code==409
    db.rollback()
    db.refresh(session)
    assert session.completed_at is None and session.raw_metrics_json is None

def test_api_clear_is_patient_bound_and_late_events_cannot_mutate_cancelled(app_client,auth_headers):
    p=app_client.post('/api/patients',json={'name':'小明'},headers=auth_headers).json()
    r=app_client.post(f"/api/patients/{p['id']}/piano/sessions",json={'mode':'SINGLE_KEY_RHYTHM'},headers=auth_headers).json()
    assert app_client.get(f"/api/patients/{p['id']}/training/active").status_code==401
    assert app_client.delete(f"/api/patients/not-this-patient/training/active/piano/{r['id']}",headers=auth_headers).status_code==404
    assert app_client.delete(f"/api/patients/{p['id']}/training/active/piano/{r['id']}",headers=auth_headers).status_code==200
    assert app_client.post(f"/api/piano/sessions/{r['id']}/events/batch",json={'events':[event(0,None,actual=500)]},headers=auth_headers).status_code==409

def test_parallel_cross_module_start_has_only_one_winner(app_client,auth_headers):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    p=app_client.post('/api/patients',json={'name':'小明'},headers=auth_headers).json()
    barrier=Barrier(2)
    def start(kind):
        barrier.wait(timeout=5)
        return app_client.post(f"/api/patients/{p['id']}/{kind}/sessions",json={'mode':'SINGLE_KEY_RHYTHM'} if kind=='piano' else {'exercise_type':'BALLET_PORT_DE_BRAS'},headers=auth_headers).status_code
    with ThreadPoolExecutor(2) as pool:
        futures=[pool.submit(start,kind) for kind in ['piano','pose']]
        statuses=[f.result(timeout=15) for f in futures]
    assert sorted(statuses)==[201,409]
