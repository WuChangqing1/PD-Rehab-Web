"""Isolated protocol, privacy and lifecycle checks, without model fabrication."""
import hashlib
import json
import uuid
import pytest
from app.db.models import Patient, MobileFaceJob
from app.db.models.face_recording import FaceRecording
from app.api import face_recordings as api


@pytest.fixture
def setup_recording(app_client, auth_headers, staff_user, db, monkeypatch, tmp_path):
    staff_user.role='ADMIN';db.commit()
    monkeypatch.setattr(api,'available',lambda:True)
    monkeypatch.setattr(api.settings,'upload_dir',str(tmp_path))
    patient=Patient(hospital_number='FACE-001',name='Face Test',sex='UNKNOWN')
    db.add(patient);db.commit();db.refresh(patient)
    binding={'device_id':'capture-device-1','local_profile_id':'capture-profile-1','patient_id':patient.id}
    link=app_client.post('/api/integration/v1/bindings',json=binding,headers=auth_headers)
    assert link.status_code==200
    record=app_client.post('/api/integration/v1/records',json={**binding,'source_record_id':'training-1',
        'record_type':'PIECE_PERFORMANCE','schema_version':'flutter-v4','payload':{'original':True}},headers=auth_headers)
    assert record.status_code==201
    content=b'fake-media-for-protocol-tests-only'
    manifest={**binding,'client_capture_id':str(uuid.uuid4()),'external_record_id':record.json()['id'],
        'consent_version':'face-capture-v1','agreed_at_ms':123,
        'files':[{'file_id':str(uuid.uuid4()),'sequence':0,'size_bytes':len(content),
            'sha256':hashlib.sha256(content).hexdigest(),'chunk_count':1,'mime_type':'video/mp4','duration_ms':2000}],
        'timeline':[]}
    return manifest,content,link.json()


def create(client,headers,manifest):
    response=client.post('/api/integration/v1/face/recordings',json=manifest,headers=headers)
    assert response.status_code==201,response.text
    return response.json()['recording_id']


def send(client,headers,identifier,manifest,content,digest=None,index=0):
    return client.put(f"/api/integration/v1/face/recordings/{identifier}/files/{manifest['files'][0]['file_id']}/chunks/{index}",
        content=content,headers={**headers,'X-Chunk-SHA256':digest or hashlib.sha256(content).hexdigest(),
            'Content-Type':'application/octet-stream'})


def test_parent_idempotency_and_manifest_conflict(app_client,auth_headers,setup_recording):
    manifest,_,_=setup_recording
    ident=create(app_client,auth_headers,manifest)
    assert create(app_client,auth_headers,manifest)==ident
    changed={**manifest,'timeline':[{'event':'CHANGED'}]}
    assert app_client.post('/api/integration/v1/face/recordings',json=changed,headers=auth_headers).status_code==409


def test_chunks_retry_hash_and_bounds(app_client,auth_headers,setup_recording):
    manifest,content,_=setup_recording;ident=create(app_client,auth_headers,manifest)
    assert send(app_client,auth_headers,ident,manifest,content).status_code==200
    assert send(app_client,auth_headers,ident,manifest,content).status_code==200
    other=b'x'*len(content)
    assert send(app_client,auth_headers,ident,manifest,other).status_code==409
    assert send(app_client,auth_headers,ident,manifest,content,index=10000).status_code==422
    assert send(app_client,auth_headers,ident,manifest,content+b'x').status_code==413
    assert send(app_client,auth_headers,ident,manifest,content,digest='0'*64).status_code==422


def test_resume_and_complete_do_not_duplicate_analysis(app_client,auth_headers,setup_recording):
    manifest,content,_=setup_recording;ident=create(app_client,auth_headers,manifest)
    path=f'/api/integration/v1/face/recordings/{ident}'
    assert app_client.post(path+'/complete',headers=auth_headers).status_code==409
    assert send(app_client,auth_headers,ident,manifest,content).status_code==200
    assert app_client.get(path,headers=auth_headers).json()['uploaded_chunks'][manifest['files'][0]['file_id']]==[0]
    first=app_client.post(path+'/complete',headers=auth_headers)
    assert first.status_code==202 and first.json()['status']=='PROCESSING'
    assert app_client.post(path+'/complete',headers=auth_headers).json()['recording_id']==ident
    assert send(app_client,auth_headers,ident,manifest,content).status_code==409


def test_whole_file_hash_is_checked(app_client,auth_headers,setup_recording):
    manifest,content,_=setup_recording;manifest['files'][0]['sha256']='0'*64
    ident=create(app_client,auth_headers,manifest)
    send(app_client,auth_headers,ident,manifest,content)
    assert app_client.post(f'/api/integration/v1/face/recordings/{ident}/complete',headers=auth_headers).status_code==422


def test_video_playback_ranges_require_scoped_ticket_and_live_binding(app_client,auth_headers,setup_recording):
    manifest,content,link=setup_recording
    ident=create(app_client,auth_headers,manifest)
    base=f'/api/integration/v1/face/recordings/{ident}'
    path=f"{base}/files/{manifest['files'][0]['file_id']}/playback"
    assert app_client.get(path).status_code==401
    assert app_client.post(path,headers=auth_headers).status_code==404
    assert send(app_client,auth_headers,ident,manifest,content).status_code==200
    assert app_client.post(base+'/complete',headers=auth_headers).status_code==202
    ticket=app_client.post(path,headers=auth_headers)
    assert ticket.status_code==204
    assert 'HttpOnly' in ticket.headers['set-cookie'] and 'Secure' in ticket.headers['set-cookie']
    assert {cookie.split('Path=',1)[1].split(';',1)[0] for cookie in ticket.headers.get_list('set-cookie')} == {path,'/pd-rehab'+path}
    headers={'Cookie':ticket.headers['set-cookie'].split(';',1)[0], 'Range':'bytes=2-5'}
    media=app_client.get(path,headers=headers)
    assert media.status_code==206
    assert media.content==content[2:6] and media.headers['content-range']==f'bytes 2-5/{len(content)}'
    assert media.headers['cache-control']=='private, no-store'
    assert app_client.get(path.replace(ident,str(uuid.uuid4())),headers=headers).status_code==401
    assert app_client.delete('/api/integration/v1/bindings/'+link['binding_id'],headers=auth_headers).status_code==200
    assert app_client.get(path,headers=headers).status_code==403


def test_cancel_blocks_completion_and_removes_bytes(app_client,auth_headers,setup_recording,db):
    manifest,content,_=setup_recording;ident=create(app_client,auth_headers,manifest)
    send(app_client,auth_headers,ident,manifest,content)
    assert app_client.delete(f'/api/integration/v1/face/recordings/{ident}',headers=auth_headers).json()['deleted']
    assert not api.root(db.get(FaceRecording,ident)).exists()
    assert app_client.post(f'/api/integration/v1/face/recordings/{ident}/complete',headers=auth_headers).status_code==409


def test_binding_revocation_applies_to_every_path(app_client,auth_headers,setup_recording):
    manifest,content,link=setup_recording;ident=create(app_client,auth_headers,manifest)
    app_client.delete('/api/integration/v1/bindings/'+link['binding_id'],headers=auth_headers)
    assert app_client.get(f'/api/integration/v1/face/recordings/{ident}',headers=auth_headers).status_code==403
    assert send(app_client,auth_headers,ident,manifest,content).status_code==403
    assert app_client.get(f'/api/integration/v1/face/recordings/{ident}/segments',headers=auth_headers).status_code==403


def test_no_auth_or_wrong_training_source(app_client,auth_headers,setup_recording):
    manifest,_,_=setup_recording
    assert app_client.post('/api/integration/v1/face/recordings',json=manifest).status_code==401
    manifest['external_record_id']=str(uuid.uuid4())
    assert app_client.post('/api/integration/v1/face/recordings',json=manifest,headers=auth_headers).status_code==403


def test_manifest_prevents_sparse_chunks_and_duplicate_files(app_client,auth_headers,setup_recording):
    manifest,_,_=setup_recording
    manifest['files'][0]['chunk_count']=99
    assert app_client.post('/api/integration/v1/face/recordings',json=manifest,headers=auth_headers).status_code==422
    manifest['files'][0]['chunk_count']=1;manifest['files']*=2
    assert app_client.post('/api/integration/v1/face/recordings',json=manifest,headers=auth_headers).status_code==422


def test_review_requires_explicit_confirmation(app_client,auth_headers,setup_recording,db):
    manifest,_,_=setup_recording;ident=create(app_client,auth_headers,manifest)
    row=db.get(FaceRecording,ident);data=json.loads(row.data_json)
    sid=str(uuid.uuid4());data['segments']=[{'id':sid,'file_id':manifest['files'][0]['file_id'],'start_seconds':0,
        'status':'REVIEW_REQUIRED','stored_path':'not-used.mp4','candidates':[{'id':'candidate','onset_frame':1,'apex_frame':2,'offset_frame':3}]}]
    row.status='REVIEW_REQUIRED';row.data_json=json.dumps(data);db.commit()
    path=f'/api/integration/v1/face/recordings/{ident}/segments/{sid}/review'
    assert app_client.post(path,json={'candidate_id':'candidate'},headers=auth_headers).status_code==422
    rejected=app_client.post(path,json={'reject':True},headers=auth_headers)
    assert rejected.status_code==202
    assert app_client.post(path,json={'reject':True},headers=auth_headers).status_code==409


def test_review_creates_only_one_inference_job(app_client,auth_headers,setup_recording,db):
    manifest,_,_=setup_recording;ident=create(app_client,auth_headers,manifest)
    row=db.get(FaceRecording,ident);data=json.loads(row.data_json);sid=str(uuid.uuid4())
    clip=api.root(row)/'clip.mp4';clip.write_bytes(b'protocol-test-only')
    data['segments']=[{'id':sid,'file_id':manifest['files'][0]['file_id'],'start_seconds':0,
        'status':'REVIEW_REQUIRED','stored_path':str(clip.relative_to(api.settings.upload_path)),
        'candidates':[{'id':'candidate','onset_frame':1,'apex_frame':2,'offset_frame':3}]}]
    row.status='REVIEW_REQUIRED';row.data_json=json.dumps(data);db.commit()
    path=f'/api/integration/v1/face/recordings/{ident}/segments/{sid}/review'
    body={'candidate_id':'candidate','review_confirmed':True}
    assert app_client.post(path,json=body,headers=auth_headers).status_code==202
    assert app_client.post(path,json=body,headers=auth_headers).status_code==409
    from sqlalchemy import select
    jobs=db.scalars(select(MobileFaceJob)).all()
    assert len(jobs)==1 and jobs[0].status=='PENDING' and json.loads(jobs[0].indices_json)==[1,2,3]
    assert app_client.delete(f'/api/integration/v1/face/recordings/{ident}',headers=auth_headers).status_code==200
    db.expire_all();assert db.get(MobileFaceJob,jobs[0].id).status=='CANCELLED'


def test_expired_upload_is_cleaned_without_analysis(app_client,auth_headers,setup_recording,db,engine,monkeypatch):
    from datetime import timedelta
    from sqlalchemy.orm import sessionmaker
    from app.db.base import utcnow
    from app.services import training_face_jobs as worker
    manifest,content,_=setup_recording;ident=create(app_client,auth_headers,manifest)
    send(app_client,auth_headers,ident,manifest,content)
    row=db.get(FaceRecording,ident);row.created_at=utcnow()-timedelta(hours=25);db.commit()
    monkeypatch.setattr(worker,'SessionLocal',sessionmaker(bind=engine))
    worker.step();db.expire_all()
    assert db.get(FaceRecording,ident).status=='FAILED'
    assert not api.root(row).exists()


def test_real_video_is_split_without_automatic_approval(app_client,auth_headers,setup_recording,db,engine,monkeypatch,tmp_path):
    """Real encoder/decoder, synthetic non-patient video; no classifier result is faked."""
    import shutil
    ffmpeg=shutil.which('ffmpeg')
    if not ffmpeg or not shutil.which('ffprobe'):
        pytest.skip('system ffmpeg and ffprobe are required')
    import subprocess
    from sqlalchemy.orm import sessionmaker
    from app.services import training_face_jobs as worker
    from app.ml.micro_expression.adapter import analyzer
    original=subprocess.run
    source=tmp_path/'synthetic-source.mp4'
    original([ffmpeg,'-v','error','-f','lavfi','-i','testsrc2=size=64x64:rate=30','-t','23',
        '-an','-c:v','libx264',str(source)],check=True,capture_output=True)
    content=source.read_bytes();manifest,_,_=setup_recording
    manifest['files'][0].update(size_bytes=len(content),sha256=hashlib.sha256(content).hexdigest(),duration_ms=23000)
    ident=create(app_client,auth_headers,manifest)
    assert send(app_client,auth_headers,ident,manifest,content).status_code==200
    assert app_client.post(f'/api/integration/v1/face/recordings/{ident}/complete',headers=auth_headers).status_code==202
    inspected=[]
    def spot(path):
        fps,duration=worker._probe(path);inspected.append(duration)
        assert duration<=20.1 and duration*fps<=1800
        return {'candidates':[]}
    monkeypatch.setattr(worker,'SessionLocal',sessionmaker(bind=engine))
    monkeypatch.setattr(analyzer,'spot',spot)
    assert worker.step();assert worker.step();worker.step()
    db.expire_all();row=db.get(FaceRecording,ident);data=json.loads(row.data_json)
    assert [s['start_seconds'] for s in data['segments']]==[0,19]
    assert len(inspected)==2 and row.status=='NO_VALID_SEGMENTS'
    assert all('job_id' not in s for s in data['segments'])


def test_failed_analysis_retries_received_video_without_new_upload(app_client,auth_headers,setup_recording,db):
    manifest,content,_=setup_recording;ident=create(app_client,auth_headers,manifest)
    send(app_client,auth_headers,ident,manifest,content)
    base=f'/api/integration/v1/face/recordings/{ident}'
    assert app_client.post(base+'/complete',headers=auth_headers).status_code==202
    for _ in range(2):
        row=db.get(FaceRecording,ident,populate_existing=True);row.status='FAILED';db.commit()
        response=app_client.post(base+'/retry',headers=auth_headers)
        assert response.status_code==202 and response.json()['upload_complete'] is True
        assert app_client.post(base+'/retry',headers=auth_headers).status_code==409
    row=db.get(FaceRecording,ident,populate_existing=True);row.status='FAILED';db.commit()
    assert app_client.post(base+'/retry',headers=auth_headers).status_code==409


@pytest.mark.parametrize('cancel_mid_inference', [False, True])
def test_training_inference_publishes_only_to_parent(app_client, auth_headers, setup_recording, db, engine, monkeypatch, cancel_mid_inference):
    from sqlalchemy import select
    from sqlalchemy.orm import sessionmaker
    from types import SimpleNamespace
    from app.db.models import AssessmentSession, ExternalPracticeRecord
    from app.ml.micro_expression.adapter import analyzer
    from app.services import integration_jobs, training_face_jobs
    manifest, content, _ = setup_recording
    ident = create(app_client, auth_headers, manifest)
    row = db.get(FaceRecording, ident)
    segment_id = str(uuid.uuid4())
    clip = api.root(row) / 'segment.mp4'
    clip.write_bytes(content)
    data = json.loads(row.data_json)
    data['segments'] = [dict(id=segment_id, file_id=manifest['files'][0]['file_id'],
        start_seconds=0, status='REVIEW_REQUIRED', stored_path=str(clip.relative_to(api.settings.upload_path)),
        candidates=[dict(id='candidate', onset_frame=1, apex_frame=2, offset_frame=3)])]
    row.status = 'REVIEW_REQUIRED'
    row.data_json = json.dumps(data)
    db.commit()
    path = f'/api/integration/v1/face/recordings/{ident}'
    assert app_client.post(f'{path}/segments/{segment_id}/review', headers=auth_headers,
        json={'candidate_id': 'candidate', 'review_confirmed': True}).status_code == 202
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(integration_jobs, 'SessionLocal', factory)
    monkeypatch.setattr(training_face_jobs, 'SessionLocal', factory)
    monkeypatch.setattr(analyzer, 'refresh_status', lambda: SimpleNamespace(is_ready=True))
    # Substitute only the model boundary; this is a persistence test, not real inference.
    def analyze(*args, **kwargs):
        if cancel_mid_inference:
            assert app_client.post(path + '/cancel', headers=auth_headers).status_code == 200
        return dict(model_name='test-adapter', model_version='test', tag_distribution={'test': 1.0})
    monkeypatch.setattr(analyzer, 'analyze', analyze)
    assert integration_jobs.process_next()
    status = app_client.get(path, headers=auth_headers).json()
    assert status['status'] == ('DELETED' if cancel_mid_inference else 'SUCCESS')
    if cancel_mid_inference:
        assert status['results'] == []
    else:
        assert status['results'][0]['model_name'] == 'test-adapter'
    assert db.scalar(select(AssessmentSession)) is None
    assert app_client.delete(path, headers=auth_headers).status_code == 200
    assert app_client.get(path, headers=auth_headers).json()['results'] == []
    assert not clip.exists()
    assert db.get(ExternalPracticeRecord, manifest['external_record_id']) is not None
