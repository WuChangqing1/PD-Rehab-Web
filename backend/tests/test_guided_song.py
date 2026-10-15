import io
import wave

import pytest

MELODY = [60,62,64,60,60,62,64,60,64,65,67,64,65,67,67,69,67,65,64,60,67,69,67,65,64,60,60,67,60,60,67,60]


def events(start=0, end=32, offset=0):
    result = []
    for i in range(start, end):
        for kind, delta in [('CUE',0),('DOWN',200),('UP',450)]:
            item = dict(seq=offset+len(result), type=kind, segment_index=1 if i<14 else 2,
                        note_index=i, time_ms=i*1000+delta)
            if kind != 'CUE': item.update(midi=MELODY[i], press_id=f'p{i}')
            result.append(item)
    return result


@pytest.fixture
def setup_session(app_client, auth_headers, patient_payload):
    patient = app_client.post('/api/patients', headers=auth_headers, json=patient_payload).json()
    body = dict(patient_id=patient['id'], client_request_id='test-request', selected_hand='LEFT', initial_difficulty='INTERMEDIATE')
    response = app_client.post('/api/guided-song/sessions', headers=auth_headers, json=body)
    assert response.status_code == 201, response.text
    return response.json(), body


def test_creation_authorization_and_idempotency(app_client, auth_headers, setup_session):
    session, body = setup_session
    assert app_client.post('/api/guided-song/sessions', json=body).status_code == 401
    assert app_client.post('/api/guided-song/sessions', headers=auth_headers, json=body).json()['id'] == session['id']
    assert app_client.post('/api/guided-song/sessions', headers=auth_headers, json={**body,'patient_id':'missing','client_request_id':'other'}).status_code == 404


def test_complete_requires_ordered_segments_and_recomputes(app_client, auth_headers, setup_session):
    session, body = setup_session
    url = '/api/guided-song/sessions/'+session['id']
    assert app_client.post(url+'/complete',headers=auth_headers).status_code == 409
    assert app_client.post(url+'/events',headers=auth_headers,json={'events':events()}).status_code == 409
    first = events(0,14)
    r = app_client.post(url+'/events',headers=auth_headers,json={'events':first})
    assert r.status_code == 200, r.text
    assert app_client.post(url+'/events',headers=auth_headers,json={'events':first}).json()['metrics']['completed_notes'] == 14
    assert app_client.post(url+'/segment-2',headers=auth_headers).status_code == 200
    r = app_client.post(url+'/events',headers=auth_headers,json={'events':events()})
    assert r.status_code == 200, r.text
    r = app_client.post(url+'/complete',headers=auth_headers)
    assert r.status_code == 200, r.text
    data=r.json()
    assert data['metrics']['total_attempt_accuracy'] == 1
    assert data['metrics']['completed_notes'] == 32
    assert data['notes'][0]['response_latency_ms'] == 200
    assert data['notes'][0]['hold_duration_ms'] == 250
    assert data['audio_url'] is None
    assert len(app_client.get(f"/api/patients/{body['patient_id']}/guided-song/history",headers=auth_headers).json()['items'])==1
    assert app_client.post(url+'/audio',headers=auth_headers,files={'file':('bad.wav',b'bad','audio/wav')}).status_code==400
    assert app_client.get(url,headers=auth_headers).json()['status']=='COMPLETED'


def test_raw_validator_preserves_wrong_attempts_and_rejects_invalid_sequence():
    from app.services.guided_song_service import analyze_events
    raw=events(0,1)
    wrong={**raw[1], 'midi':62,'press_id':'wrong','time_ms':100}
    release={**wrong,'type':'UP','time_ms':150}
    raw=[raw[0],wrong,release,*raw[1:]]
    for i,e in enumerate(raw): e['seq']=i
    notes,metrics=analyze_events(raw)
    assert metrics['wrong_press_count']==1
    assert metrics['total_attempt_accuracy']==0.5
    assert metrics['first_attempt_accuracy']==0
    assert notes[0]['response_latency_ms']==200
    with pytest.raises(Exception): analyze_events([{**raw[0],'note_index':3}])
    with pytest.raises(Exception): analyze_events([raw[0],raw[1],raw[1]])


def test_immutable_snapshots_forged_metrics_and_cancel(app_client,auth_headers,setup_session):
    session,_=setup_session
    url='/api/guided-song/sessions/'+session['id']
    raw=events(0,1)
    assert app_client.post(url+'/events',headers=auth_headers,json={'events':raw,'accuracy':1}).status_code==422
    assert app_client.post(url+'/events',headers=auth_headers,json={'events':raw}).status_code==200
    assert app_client.post(url+'/events',headers=auth_headers,json={'events':[]}).status_code==409
    assert app_client.post(url+'/cancel',headers=auth_headers).json()['status']=='CANCELLED'
    assert app_client.post(url+'/cancel',headers=auth_headers).status_code==200
    assert app_client.post(url+'/complete',headers=auth_headers).status_code==409
    assert app_client.post(url+'/events',headers=auth_headers,json={'events':events(0,2)}).status_code==409


def test_audio_roundtrip_and_owner_authorization(app_client,auth_headers,setup_session,db):
    from app.db.models import StaffUser
    from app.core.security import create_access_token
    session,_=setup_session
    other=StaffUser(username='other',password_hash='unused',display_name='Other',role='DOCTOR',is_active=True)
    db.add(other); db.commit()
    headers={'Authorization':'Bearer '+create_access_token(other.id,role=other.role)}
    url='/api/guided-song/sessions/'+session['id']
    assert app_client.get(url,headers=headers).status_code==403
    assert app_client.post(url+'/cancel',headers=headers).status_code==403
    app_client.post(url+'/events',headers=auth_headers,json={'events':events(0,14)})
    app_client.post(url+'/segment-2',headers=auth_headers)
    app_client.post(url+'/events',headers=auth_headers,json={'events':events()})
    app_client.post(url+'/complete',headers=auth_headers)
    buf=io.BytesIO()
    with wave.open(buf,'wb') as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(24000); wav.writeframes(bytes(48000))
    r=app_client.post(url+'/audio',headers=auth_headers,files={'file':('play.wav',buf.getvalue(),'audio/wav')})
    assert r.status_code==200,r.text
    assert r.json()['audio_source']=='SYNTHESIZED_FROM_KEY_EVENTS'
    assert r.json()['duration_ms']==1000
    assert app_client.get(url+'/audio',headers=auth_headers).content==buf.getvalue()
    assert app_client.get(url+'/audio',headers=headers).status_code==403


def test_metrics_latency_and_pause_validation():
    from app.services.guided_song_service import analyze_events
    notes,metrics=analyze_events(events(0,2))
    assert metrics['mean_response_latency_ms']==200
    raw=events(0,1)
    raw.insert(1,dict(seq=1,type='PAUSE',segment_index=1,note_index=0,time_ms=100))
    for i,e in enumerate(raw): e['seq']=i
    with pytest.raises(Exception): analyze_events(raw)

def test_simulation_gate_and_camera_audit(app_client,auth_headers,setup_session):
    session,body=setup_session
    denied=app_client.post('/api/guided-song/sessions',headers=auth_headers,json={**body,'client_request_id':'sim','is_simulation':True,'input_source':'SYNTHETIC_SELFTEST'})
    assert denied.status_code==403
    url='/api/guided-song/sessions/'+session['id']
    result=app_client.post(url+'/emotion-status',headers=auth_headers,json={'consent':True,'status':'UNAVAILABLE'})
    assert result.status_code==200
    assert result.json()['metadata']['camera_transport_status']=='UNAVAILABLE'
    assert result.json()['emotion_source'] is None
    assert result.json()['metrics']['first_attempt_accuracy'] is None


def test_page_exit_cancel_can_save_final_raw_snapshot(app_client,auth_headers,setup_session):
    session,_=setup_session
    url='/api/guided-song/sessions/'+session['id']
    result=app_client.post(url+'/cancel',headers=auth_headers,json={'events':events(0,1)})
    assert result.status_code==200,result.text
    assert result.json()['status']=='CANCELLED'
    assert result.json()['metrics']['completed_notes']==1
    assert result.json()['audio_url'] is None


def test_upgrade_from_previous_schema_preserves_existing_patient():
    import subprocess,sys,os,sqlite3
    from pathlib import Path
    backend=Path(__file__).resolve().parents[1]
    import tempfile
    temporary=tempfile.TemporaryDirectory(prefix='guided-migration-')
    database=Path(temporary.name)/'guided-migration-test.sqlite'
    env={**os.environ,'DATABASE_URL':'sqlite:///'+database.as_posix()}
    for revision in ['g3b5c7d9e1f2','head']:
        result=subprocess.run([sys.executable,'-m','alembic','upgrade',revision],cwd=backend,env=env,capture_output=True,text=True)
        assert result.returncode==0,result.stderr
        with sqlite3.connect(database) as conn:
            if revision=='g3b5c7d9e1f2':
                conn.execute("INSERT INTO patients(id,hospital_number,name,sex,dominant_hand,affected_side,medication_state,is_deleted,created_at,updated_at) VALUES('migration-patient','M001','Preserved','UNKNOWN','UNKNOWN','UNKNOWN','UNKNOWN',0,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)")
            else:
                assert conn.execute("SELECT name FROM patients WHERE id='migration-patient'").fetchone()==('Preserved',)
                assert conn.execute("SELECT name FROM sqlite_master WHERE name='guided_song_sessions'").fetchone()

        conn.close()
    temporary.cleanup()

def test_history_does_not_select_audio_or_raw_event_payload(app_client,auth_headers,setup_session,engine):
    from sqlalchemy import event
    session,body=setup_session
    statements=[]
    def record(_conn,_cursor,statement,_parameters,_context,_many):
        if statement.lstrip().upper().startswith('SELECT') and 'guided_song_sessions' in statement:
            statements.append(statement)
    event.listen(engine,'before_cursor_execute',record)
    try:
        response=app_client.get(f"/api/patients/{body['patient_id']}/guided-song/history",headers=auth_headers)
    finally:
        event.remove(engine,'before_cursor_execute',record)
    assert response.status_code==200
    assert statements
    assert all('guided_song_sessions.audio,' not in sql and 'guided_song_sessions.events,' not in sql for sql in statements)
