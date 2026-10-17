from datetime import datetime, timedelta

from app.db.models import Patient, AssessmentSession, PianoSession, PoseSession, StaffUser
from app.db.models.guided_song import GuidedSongSession


def add_patient(db, number='followup-qa'):
    person=Patient(hospital_number=number,name='QA only')
    db.add(person);db.flush();return person


def test_followup_requires_authentication(app_client):
    assert app_client.get('/api/patients/unknown/follow-up?start_date=2026-10-01&end_date=2026-10-31').status_code==401


def test_followup_date_boundaries_patient_isolation_and_no_fifty_row_limit(app_client,auth_headers,db):
    person=add_patient(db);other=add_patient(db,'other')
    start=datetime(2026,9,30,16)
    db.add_all([PianoSession(patient_id=person.id,mode='SINGLE_KEY_RHYTHM',started_at=start+timedelta(minutes=i),completed_at=start+timedelta(minutes=i+1)) for i in range(75)])
    db.add_all([
        PianoSession(patient_id=person.id,mode='SINGLE_KEY_RHYTHM',started_at=start-timedelta(seconds=1)),
        PianoSession(patient_id=other.id,mode='SINGLE_KEY_RHYTHM',started_at=start),
        PianoSession(patient_id=person.id,mode='SINGLE_KEY_RHYTHM',started_at=datetime(2026,10,1,16)),
        AssessmentSession(patient_id=person.id,session_type='COMPREHENSIVE',status='IN_PROGRESS',started_at=start),
        PoseSession(patient_id=person.id,exercise_type='BALLET_TENDU',started_at=start),
    ]);db.commit()
    reply=app_client.get(f'/api/patients/{person.id}/follow-up?start_date=2026-10-01&end_date=2026-10-01&offset_minutes=480',headers=auth_headers)
    assert reply.status_code==200
    data=reply.json();assert len(data['piano'])==75
    assert len(data['assessments'])==1 and data['assessments'][0]['status']=='IN_PROGRESS'
    assert len(data['pose'])==1 and data['pose'][0]['completed_at'] is None
    assert data['exercise_names']['BALLET_TENDU']=='伸腿点地'
    assert all(r['patient_id']==person.id for r in data['piano'])


def test_followup_preserves_guided_owner_scope_and_omits_raw_inputs(app_client,auth_headers,db,staff_user):
    person=add_patient(db)
    another=StaffUser(username='other-owner',password_hash='not-used',display_name='QA',role='DOCTOR')
    db.add(another);db.flush()
    for owner in [staff_user.id,another.id]:
        db.add(GuidedSongSession(patient_id=person.id,owner_id=owner,client_request_id=owner,
            created_at=datetime(2026,10,2),config={'input_source':'HUMAN_KEYBOARD','song_id':'two_tigers','selected_hand':'LEFT'},
            result={'metrics':{'first_attempt_accuracy':.8}},events=[{'private':'raw'}],audio=b'private'))
    db.commit()
    reply=app_client.get(f'/api/patients/{person.id}/follow-up?start_date=2026-10-01&end_date=2026-10-31',headers=auth_headers)
    assert reply.status_code==200
    rows=reply.json()['guided'];assert len(rows)==1
    assert rows[0]['metrics']['first_attempt_accuracy']==.8
    assert 'events' not in rows[0] and 'audio' not in rows[0] and 'owner_id' not in rows[0]


def test_followup_rejects_invalid_or_unbounded_ranges(app_client,auth_headers,db):
    person=add_patient(db);db.commit()
    for dates in ['start_date=2026-11-01&end_date=2026-10-01','start_date=2024-01-01&end_date=2026-10-01','start_date=invalid&end_date=2026-10-01','start_date=9999-12-31&end_date=9999-12-31']:
        assert app_client.get(f'/api/patients/{person.id}/follow-up?{dates}',headers=auth_headers).status_code==422
    assert app_client.get('/api/patients/missing/follow-up?start_date=2026-10-01&end_date=2026-10-31',headers=auth_headers).status_code==404


def test_feed_omits_piano_raw_events_but_retains_comparability(app_client,auth_headers,db):
    import json
    person=add_patient(db)
    row=PianoSession(patient_id=person.id,mode='SINGLE_KEY_RHYTHM',started_at=datetime(2026,10,2),
        difficulty_before_json=json.dumps({'tempo_ceiling_bpm':90,'weak_hand':'LEFT','recipe_algorithm_version':'v2',
            'server_metrics':{'hold_duration_mae_ms':20},'raw_presses':[{'private':'raw'}],'events_extra_json':[{'private':'raw'}]}))
    db.add(row);db.commit()
    reply=app_client.get(f'/api/patients/{person.id}/follow-up?start_date=2026-10-01&end_date=2026-10-31',headers=auth_headers)
    audit=reply.json()['piano'][0]['difficulty_before_json']
    assert 'raw_presses' not in audit and 'events_extra_json' not in audit
    assert audit['tempo_ceiling_bpm']==90 and audit['server_metrics']['hold_duration_mae_ms']==20
    assert 'raw_presses' in json.loads(db.get(PianoSession,row.id).difficulty_before_json)


def test_real_guided_workflow_exposes_metric_version_and_full_schedule(app_client,auth_headers,patient_payload):
    from runpy import run_path
    from pathlib import Path
    events=run_path(str(Path(__file__).with_name('test_guided_song.py')))['events']
    patient=app_client.post('/api/patients',headers=auth_headers,json=patient_payload).json()
    created=app_client.post('/api/guided-song/sessions',headers=auth_headers,json=dict(patient_id=patient['id'],client_request_id='followup-real',selected_hand='LEFT',initial_difficulty='INTERMEDIATE')).json()
    url='/api/guided-song/sessions/'+created['id']
    assert app_client.post(url+'/events',headers=auth_headers,json={'events':events(0,14)}).status_code==200
    assert app_client.post(url+'/segment-2',headers=auth_headers).status_code==200
    assert app_client.post(url+'/events',headers=auth_headers,json={'events':events()}).status_code==200
    assert app_client.post(url+'/complete',headers=auth_headers).status_code==200
    today=datetime.utcnow().date().isoformat()
    result=app_client.get(f"/api/patients/{patient['id']}/follow-up?start_date={today}&end_date={today}&offset_minutes=0",headers=auth_headers).json()['guided'][0]
    assert result['version']=='guided-song-1'
    assert result['segment_1_bpm']==80 and result['segment_2_bpm']==80
