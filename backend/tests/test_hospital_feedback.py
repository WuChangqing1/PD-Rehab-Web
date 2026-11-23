import json
import pytest
from app.db.models import Patient, PianoSession, PatientAccessGrant
from app.db.base import utcnow
from tests.test_staff_accounts import headers


def test_nurse_can_create_and_edit_notes_but_not_delete_or_manage_staff(app_client, db, staff_user):
    staff_user.role='NURSE'; db.commit(); h=headers(staff_user)
    created=app_client.post('/api/patients',headers=h,json={'name':'护理记录','doctor_notes':'初次观察'})
    assert created.status_code==201,created.text
    row=created.json()
    response=app_client.patch('/api/patients/'+row['id'],headers=h,json={'doctor_notes':'本次观察','expected_updated_at':row['updated_at']})
    assert response.status_code==200 and response.json()['doctor_notes']=='本次观察'
    assert app_client.delete('/api/patients/'+row['id'],headers=h).status_code==403
    assert app_client.get('/api/auth/staff',headers=h).status_code==403


def completed(db):
    p=Patient(name='不得外发姓名',hospital_number='private-review',phone='13800000000',doctor_notes='不得外发病历')
    db.add(p);db.flush()
    s=PianoSession(patient_id=p.id,mode='SINGLE_KEY_RHYTHM',completed_at=utcnow(),accuracy=.8,mean_response_latency_ms=320,
      difficulty_before_json=json.dumps({'completion_status':'COMPLETED','secret':'不得外发原始数据'}))
    db.add(s);db.commit();return p,s


def test_review_requires_consent_and_uses_only_saved_allowlist(app_client,db,staff_user,monkeypatch):
    from app.api import integration
    p,s=completed(db);calls=[]
    def provider(system,question):
        calls.append((system,question))
        assert all(x not in system+question for x in [p.name,p.phone,p.doctor_notes,p.id,s.id,'不得外发原始数据'])
        assert '0.8' in system and '320' in system
        return '本次记录的准确率为80%。'
    monkeypatch.setattr(integration,'_ask_llm',provider)
    h=headers(staff_user);body={'question':'这次训练怎么样','training':{'kind':'piano','id':s.id}}
    assert app_client.post('/api/integration/v1/expert/chat',headers=h,json=body).status_code==422
    body['training_data_consent']=True
    r=app_client.post('/api/integration/v1/expert/chat',headers=h,json=body)
    assert r.status_code==200,r.text
    assert r.json()['patient_data_used'] is True and len(calls)==1
    # Reopening the same handoff must not call the provider again.
    assert app_client.post('/api/integration/v1/expert/chat',headers=h,json=body).status_code==200
    assert len(calls)==1
    db.add(PatientAccessGrant(patient_id=p.id,staff_user_id=staff_user.id,active=False));db.commit()
    assert app_client.post('/api/integration/v1/expert/chat',headers=h,json=body).status_code in (403,404)
    assert len(calls)==1


@pytest.mark.parametrize('state',['pending','interrupted'])
def test_review_refuses_incomplete_records(app_client,db,staff_user,state):
    p,s=completed(db)
    if state=='pending':s.completed_at=None
    else:s.difficulty_before_json=json.dumps({'completion_status':'INTERRUPTED'})
    db.commit()
    r=app_client.post('/api/integration/v1/expert/chat',headers=headers(staff_user),json={'question':'点评','training':{'kind':'piano','id':s.id},'training_data_consent':True})
    assert r.status_code==409,r.text


@pytest.mark.asyncio
async def test_concurrent_review_retries_call_provider_once(app_client,db,staff_user,monkeypatch):
    import asyncio,time,httpx
    from app.api import integration
    p,s=completed(db);calls=[]
    def provider(system,question):
        calls.append(1);time.sleep(.1);return '本次指标解释'
    monkeypatch.setattr(integration,'_ask_llm',provider)
    body={'question':'并发点评','training':{'kind':'piano','id':s.id},'training_data_consent':True}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app_client.app),base_url='http://testserver') as client:
        first,second=await asyncio.gather(*[client.post('/api/integration/v1/expert/chat',headers=headers(staff_user),json=body) for _ in range(2)])
    assert first.status_code==second.status_code==200,(first.text,second.text)
    assert first.json()['id']==second.json()['id'] and len(calls)==1


def test_completed_record_without_metrics_never_calls_provider(app_client,db,staff_user,monkeypatch):
    from app.api import integration
    p,s=completed(db);s.accuracy=None;s.mean_response_latency_ms=None;db.commit()
    monkeypatch.setattr(integration,'_ask_llm',lambda *_:pytest.fail('No metrics must not call a model'))
    r=app_client.post('/api/integration/v1/expert/chat',headers=headers(staff_user),json={'question':'点评','training':{'kind':'piano','id':s.id},'training_data_consent':True})
    assert r.status_code==409


def test_pose_and_song_use_saved_numeric_metrics_only(db,staff_user):
    from app.db.models import PoseSession
    from app.db.models.guided_song import GuidedSongSession
    from app.services.training_review import summary
    p,_=completed(db)
    pose=PoseSession(patient_id=p.id,exercise_type='BALLET_TENDU',completed_at=utcnow(),hold_time_sec=3.2,repetition_count=5,raw_metrics_json=json.dumps({'private_note':'must not leave'}))
    song=GuidedSongSession(patient_id=p.id,owner_id=staff_user.id,client_request_id='saved-song',status='COMPLETED',completed_at=utcnow(),config={'song_id':'two_tigers','selected_hand':'LEFT','initial_difficulty':'BEGINNER','input_source':'SYNTHETIC_SELFTEST','segment_1_bpm':40,'private':'must not leave'},result={'metrics':{'completion_rate':1,'mean_response_latency_ms':400,'private':'must not leave'},'notes':[{'private':'must not leave'}]})
    db.add_all([pose,song]);db.commit()
    _,a=summary(db,staff_user,'pose',pose.id);_,b=summary(db,staff_user,'song',song.id)
    assert a['metrics']=={'hold_time_sec':3.2,'repetition_count':5}
    assert b['input_source']=='SYNTHETIC_SELFTEST' and b['segment_1_bpm']==40
    assert b['metrics']=={'completion_rate':1,'mean_response_latency_ms':400}
    assert 'must not leave' not in json.dumps([a,b])
