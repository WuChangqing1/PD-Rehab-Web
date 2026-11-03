from app.db.models import Patient, StaffUser
from app.core.security import hash_password
from app.core.config import settings

def patient(db, n=1):
    row=Patient(hospital_number=f"SEC{n}",name=f"Integration QA {n}")
    db.add(row);db.commit();db.refresh(row)
    return row

def admin(db,staff_user):
    staff_user.role="ADMIN";db.commit()

def other_token(client,db):
    row=StaffUser(username="otherqa",display_name="Other QA",role="DOCTOR",is_active=True,password_hash=hash_password("qa-other-pass"))
    db.add(row);db.commit()
    token=client.post('/api/auth/login',json={'username':'otherqa','password':'qa-other-pass'}).json()['access_token']
    return row,{'Authorization':'Bearer '+token}

def test_unassigned_patient_hidden_and_denied(app_client,auth_headers,db):
    p=patient(db)
    assert app_client.get('/api/integration/v1/bootstrap',headers=auth_headers).json()['patients']==[]
    for endpoint in ['records','patient-data']:
        assert app_client.get('/api/integration/v1/'+endpoint,params={'patient_id':p.id},headers=auth_headers).status_code==403
    assert app_client.post('/api/integration/v1/bindings',json={'device_id':'device-security','local_profile_id':'profile-security','patient_id':p.id},headers=auth_headers).status_code==403

def test_binding_owner_is_enforced_and_revocable(app_client,auth_headers,db,staff_user):
    admin(db,staff_user);p=patient(db)
    base={'device_id':'device-security','local_profile_id':'profile-security','patient_id':p.id}
    link=app_client.post('/api/integration/v1/bindings',json=base,headers=auth_headers).json()
    other,headers=other_token(app_client,db)
    grant=app_client.put('/api/integration/v1/access/'+p.id+'/'+other.id,json={'active':True},headers=auth_headers)
    assert grant.status_code==200,grant.text
    # A patient grant does not grant ownership of someone else's device profile.
    assert app_client.post('/api/integration/v1/bindings',json=base,headers=headers).status_code==403
    assert app_client.delete('/api/integration/v1/bindings/'+link['binding_id'],headers=auth_headers).status_code==200
    data={**base,'source_record_id':'r1','record_type':'PIANO_SESSION','schema_version':'flutter-v4','payload':{}}
    assert app_client.post('/api/integration/v1/records',json=data,headers=auth_headers).status_code==403

def test_record_metadata_conflict_is_not_idempotent(app_client,auth_headers,db,staff_user):
    admin(db,staff_user);p=patient(db)
    base={'device_id':'device-security','local_profile_id':'profile-security','patient_id':p.id}
    app_client.post('/api/integration/v1/bindings',json=base,headers=auth_headers)
    data={**base,'source_record_id':'r1','record_type':'PIANO_SESSION','schema_version':'flutter-v4','task_version':'v1','metric_version':'m1','captured_at_ms':1000,'payload':{'ok':True}}
    assert app_client.post('/api/integration/v1/records',json=data,headers=auth_headers).status_code==201
    for key,value in [('task_version','v2'),('metric_version','m2'),('captured_at_ms',2000),('local_profile_id','another-profile')]:
        result=app_client.post('/api/integration/v1/records',json={**data,key:value},headers=auth_headers)
        assert result.status_code in (403,409),(key,result.text)

def test_foreign_job_denied_and_review_bounds_checked(app_client,auth_headers,db,staff_user,monkeypatch,tmp_path):
    from app.db.models import MobileFaceJob
    from app.api import integration
    admin(db,staff_user);p=patient(db)
    monkeypatch.setattr(settings,'upload_dir',str(tmp_path))
    video=tmp_path/'fake.mp4';video.write_bytes(b'fixture')
    job=MobileFaceJob(patient_id=p.id,operator_id=staff_user.id,status='REVIEW_REQUIRED',stored_path='fake.mp4',size_bytes=7,source_filename='fake.mp4')
    db.add(job);db.commit();db.refresh(job)
    other,headers=other_token(app_client,db)
    for suffix in ['', '/candidates']:
        assert app_client.get('/api/integration/v1/face/jobs/'+job.id+suffix,headers=headers).status_code in (403,404)
    monkeypatch.setattr(integration,'inspect_review_video',lambda path: {'frame_count':12})
    data={'onset_frame':1,'apex_frame':6,'offset_frame':13,'review_confirmed':True}
    response=app_client.post('/api/integration/v1/face/jobs/'+job.id+'/review',json=data,headers=auth_headers)
    assert response.status_code==422,response.text
    db.refresh(job);assert job.status=='REVIEW_REQUIRED'

def test_platform_knowledge_has_real_sources_without_provider(app_client,auth_headers,monkeypatch):
    monkeypatch.setattr(settings,'expert_llm_api_key','')
    response=app_client.post('/api/integration/v1/expert/chat',json={'question':'面部视频如何录制和分析？'},headers=auth_headers)
    assert response.status_code==200,response.text
    assert response.json()['sources'] and response.json()['provider_used'] is False
    response=app_client.post('/api/integration/v1/expert/chat',json={'question':'我应该怎么加药？'},headers=auth_headers)
    assert response.status_code==200 and response.json()['safety_limited'] is True


def test_review_is_durable_and_duplicate_rejected(app_client,auth_headers,db,staff_user,monkeypatch,tmp_path):
    import json
    from app.db.models import MobileFaceJob
    from app.api import integration
    admin(db,staff_user);p=patient(db)
    monkeypatch.setattr(settings,'upload_dir',str(tmp_path));(tmp_path/'fake.mp4').write_bytes(b'fixture')
    job=MobileFaceJob(patient_id=p.id,operator_id=staff_user.id,status='REVIEW_REQUIRED',stored_path='fake.mp4',size_bytes=7)
    db.add(job);db.commit();db.refresh(job)
    monkeypatch.setattr(integration,'inspect_review_video',lambda path:{'frame_count':12})
    data={'onset_frame':1,'apex_frame':6,'offset_frame':12,'review_confirmed':True}
    url='/api/integration/v1/face/jobs/'+job.id+'/review'
    assert app_client.post(url,json=data,headers=auth_headers).status_code==202
    db.refresh(job);assert job.status=='PENDING' and json.loads(job.indices_json)==[1,6,12]
    assert app_client.post(url,json=data,headers=auth_headers).status_code==409

def test_revocation_overrides_creator_and_denies_all_reads(app_client,auth_headers,db,staff_user):
    admin(db,staff_user);p=patient(db)
    other,headers=other_token(app_client,db)
    url='/api/integration/v1/access/'+p.id+'/'+other.id
    app_client.put(url,json={'active':True},headers=auth_headers)
    assert app_client.get('/api/integration/v1/patient-data',params={'patient_id':p.id},headers=headers).status_code==200
    app_client.put(url,json={'active':False},headers=auth_headers)
    assert app_client.get('/api/integration/v1/patient-data',params={'patient_id':p.id},headers=headers).status_code==403
    assert app_client.post('/api/integration/v1/expert/chat',json={'patient_id':p.id,'question':'平台如何使用'},headers=headers).status_code==403

def test_restart_resumes_pending_and_fails_running(engine,db,staff_user,monkeypatch,tmp_path):
    from sqlalchemy.orm import sessionmaker
    from app.services import integration_jobs
    from app.db.models import MobileFaceJob
    p=patient(db)
    monkeypatch.setattr(settings,'upload_dir',str(tmp_path))
    monkeypatch.setattr(integration_jobs,'SessionLocal',sessionmaker(bind=engine,expire_on_commit=False))
    jobs=[]
    for state in ['PENDING','RUNNING','UPLOADING']:
        (tmp_path/(state+'.mp4')).write_bytes(b'fixture')
        j=MobileFaceJob(patient_id=p.id,operator_id=staff_user.id,status=state,stored_path=state+'.mp4',indices_json='[1,2,3]',size_bytes=7)
        db.add(j);jobs.append(j)
    db.commit();integration_jobs.recover_jobs();db.expire_all()
    assert jobs[0].status=='PENDING' and (tmp_path/'PENDING.mp4').exists()
    assert jobs[1].status=='FAILED' and jobs[2].status=='FAILED'
    assert not (tmp_path/'RUNNING.mp4').exists()

def test_single_atomic_job_claim(engine,db,staff_user,monkeypatch):
    from sqlalchemy.orm import sessionmaker
    from app.services import integration_jobs
    from app.db.models import MobileFaceJob
    p=patient(db)
    j=MobileFaceJob(patient_id=p.id,operator_id=staff_user.id,status='SUCCESS',size_bytes=0)
    db.add(j);db.commit()
    monkeypatch.setattr(integration_jobs,'SessionLocal',sessionmaker(bind=engine))
    integration_jobs.run_face(j.id)
    db.refresh(j);assert j.status=='SUCCESS'


def test_grant_cannot_be_bypassed_via_existing_web_api(app_client,auth_headers,db):
    p=patient(db)
    assert app_client.get('/api/patients/'+p.id,headers=auth_headers).status_code in (403,404)
    result=app_client.get('/api/patients',headers=auth_headers).json()
    assert not any(x['id']==p.id for x in result['items'])

def test_revoked_device_cannot_read_existing_job(app_client,auth_headers,db,staff_user):
    from app.db.models import MobileFaceJob
    admin(db,staff_user);p=patient(db)
    base={'device_id':'revoked-device','local_profile_id':'revoked-profile','patient_id':p.id}
    link=app_client.post('/api/integration/v1/bindings',json=base,headers=auth_headers).json()
    j=MobileFaceJob(patient_id=p.id,operator_id=staff_user.id,device_id=base['device_id'],local_profile_id=base['local_profile_id'],status='REVIEW_REQUIRED',size_bytes=0)
    db.add(j);db.commit()
    app_client.delete('/api/integration/v1/bindings/'+link['binding_id'],headers=auth_headers)
    assert app_client.get('/api/integration/v1/face/jobs/'+j.id,headers=auth_headers).status_code==403


def test_hidden_patient_number_is_still_globally_unique(app_client,auth_headers,db):
    p=patient(db)
    response=app_client.post('/api/patients',headers=auth_headers,json={'hospital_number':p.hospital_number,'name':'New QA'})
    assert response.status_code==409,response.text


def test_public_proxy_api_docs_use_relative_schema(app_client):
    response=app_client.get('/api/docs')
    assert response.status_code==200 and "url: 'openapi.json'" in response.text
    schema=app_client.get('/api/openapi.json').json()
    assert '/api/integration/v1/records' in schema['paths']
