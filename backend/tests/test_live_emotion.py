import math
import pytest
from app.services.live_emotion_service import SongDifficultyPolicy, simulation_result, capabilities, StreamGuard

def test_missing_model_has_no_probabilities():
    value = capabilities()
    assert value['status'] == 'MODEL_NOT_CONFIGURED'
    assert value['capture_required'] is False
    assert 'probabilities' not in value

@pytest.mark.parametrize('before,after', [(60,80),(80,100),(100,110),(110,120),(120,120)])
def test_simulation_only_at_boundary(before, after):
    result = simulation_result('s', 'p', now_ms=1000)
    assert SongDifficultyPolicy.decide(before, True, result, True, 1000)['bpm_after'] == after
    assert SongDifficultyPolicy.decide(before, False, result, True, 1000)['bpm_after'] == before
    assert SongDifficultyPolicy.decide(before, True, result, False, 1000)['bpm_after'] == before

@pytest.mark.parametrize('patch', [{'quality':'LOW'}, {'result_timestamp_ms':-99999}, {'source':'MODEL'}, {'probabilities':[math.nan]*7}, {'probabilities':[0.5]*7}, {'probabilities':[1]}])
def test_invalid_results_never_upgrade(patch):
    result = simulation_result('s','p',now_ms=1000) | patch
    assert SongDifficultyPolicy.decide(60,True,result,True,1000)['bpm_after'] == 60

def test_guard_rejects_overlap_oversize_sequence_and_rate():
    guard = StreamGuard()
    guard.begin({'seq':0,'capture_timestamp_ms':1000,'duration_ms':1000,'byte_length':10},now=1)
    with pytest.raises(ValueError): guard.begin({'seq':1},now=2)
    guard.finish(10)
    with pytest.raises(ValueError): guard.begin({'seq':1,'capture_timestamp_ms':2000,'duration_ms':1000,'byte_length':10},now=1.1)
    with pytest.raises(ValueError): guard.begin({'seq':1,'capture_timestamp_ms':2000,'duration_ms':1000,'byte_length':9999999},now=3)

@pytest.fixture
def live_client(db,staff_user):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.api.live_emotion import router
    from app.db.session import get_db
    from app.db.models import Patient
    from app.db.models.guided_song import GuidedSongSession
    from app.core.security import create_access_token
    patient = Patient(hospital_number='live-1',name='test')
    db.add(patient); db.flush()
    session = GuidedSongSession(patient_id=patient.id,owner_id=staff_user.id,client_request_id='live-1')
    db.add(session); db.commit()
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as client:
        yield client, dict(type='auth',token=create_access_token(staff_user.id),session_id=session.id,patient_id=patient.id), session

def test_authenticated_missing_model_does_not_request_video(live_client):
    client, auth, _ = live_client
    with client.websocket_connect('/live-emotion/stream') as ws:
        ws.send_json(auth)
        reply = ws.receive_json()
        assert reply['status'] == 'MODEL_NOT_CONFIGURED'
        assert reply['capture_required'] is False
        assert 'probabilities' not in reply

@pytest.mark.parametrize('patch',[{'token':''},{'patient_id':'other'},{'session_id':'other'},{'type':'chunk'}])
def test_stream_rejects_unauthorized_bindings(live_client,patch):
    from starlette.websockets import WebSocketDisconnect
    client,auth,_ = live_client
    with client.websocket_connect('/live-emotion/stream') as ws:
        ws.send_json(auth | patch)
        with pytest.raises(WebSocketDisconnect) as error: ws.receive_json()
        assert error.value.code == 4403

def test_auth_timeout(live_client,monkeypatch):
    from starlette.websockets import WebSocketDisconnect
    import app.api.live_emotion as api
    monkeypatch.setattr(api,'AUTH_TIMEOUT',.01)
    with live_client[0].websocket_connect('/live-emotion/stream') as ws:
        with pytest.raises(WebSocketDisconnect) as error: ws.receive_json()
        assert error.value.code == 4408

def test_simulation_requires_server_flag_session_and_explicit_optin(live_client,monkeypatch,db):
    from app.core.config import settings
    client,auth,session = live_client
    monkeypatch.setattr(settings,'emotion_simulation_mode',True)
    monkeypatch.setattr(settings,'app_env','test')
    with client.websocket_connect('/live-emotion/stream') as ws:
        ws.send_json(auth | {'simulation_demo':True})
        assert ws.receive_json()['status'] == 'MODEL_NOT_CONFIGURED'
    session.config = {'is_simulation':True}
    db.commit()
    with client.websocket_connect('/live-emotion/stream') as ws:
        ws.send_json(auth | {'simulation_demo':True})
        result = ws.receive_json()
        assert result['source'] == 'SIMULATED'
        assert result['clinical_eligible'] is False
    monkeypatch.setattr(settings,'app_env','production')
    with client.websocket_connect('/live-emotion/stream') as ws:
        ws.send_json(auth | {'simulation_demo':True})
        assert ws.receive_json()['status'] == 'MODEL_NOT_CONFIGURED'


def test_verified_temporal_adapter_receives_binary_and_acks(live_client,monkeypatch):
    import app.services.live_emotion_service as service
    class Adapter:
        requirements = dict(fps=30,window_ms=1000,width=640,height=480,optical_flow=False,continuous=True)
        labels = service.LABELS
        model_name = 'TEST_ONLY'
        model_version = '1'
        def open(self): return []
        def infer(self,state,chunk,metadata):
            state.append(chunk)
            assert state == [b'video']
            return dict(probabilities=[.05,.35,.05,.35,.05,.1,.05],quality='GOOD')
        def close(self,state): pass
    monkeypatch.setattr(service,'temporal_adapter',Adapter())
    client,auth,_ = live_client
    with client.websocket_connect('/live-emotion/stream') as ws:
        ws.send_json(auth)
        assert ws.receive_json()['status'] == 'READY'
        ws.send_json(dict(type='chunk',seq=0,capture_timestamp_ms=1000,duration_ms=1000,byte_length=5,mime_type='video/webm'))
        ws.send_bytes(b'video')
        assert ws.receive_json()['type'] == 'result'
        assert ws.receive_json() == {'type':'ack','seq':0}
