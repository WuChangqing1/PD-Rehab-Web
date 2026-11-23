import json
import pytest
from app.core.config import settings
from tests.test_staff_accounts import headers


def configured(monkeypatch):
    monkeypatch.setattr(settings,'asr_enabled',True,raising=False)
    monkeypatch.setattr(settings,'asr_api_key','test-secret-do-not-return',raising=False)
    monkeypatch.setattr(settings,'asr_ws_url','wss://dashscope.aliyuncs.com/api-ws/v1/inference',raising=False)


def test_capabilities_requires_login_and_never_exposes_secret(app_client,staff_user,monkeypatch):
    configured(monkeypatch)
    assert app_client.get('/api/asr/capabilities').status_code==401
    r=app_client.get('/api/asr/capabilities',headers=headers(staff_user))
    assert r.status_code==200,r.text
    assert r.json()['available'] is True and 'test-secret' not in r.text


def test_missing_config_does_not_issue_ticket(app_client,staff_user,monkeypatch):
    monkeypatch.setattr(settings,'asr_enabled',False,raising=False)
    assert app_client.post('/api/asr/tickets',headers=headers(staff_user)).status_code==503


def test_ticket_is_single_use_origin_checked_and_active_account_required(app_client,db,staff_user,monkeypatch):
    configured(monkeypatch)
    r=app_client.post('/api/asr/tickets',headers=headers(staff_user));assert r.status_code==200,r.text
    ticket=r.json()['ticket'];assert 'test-secret' not in r.text
    with app_client.websocket_connect('/api/asr/stream',headers={'origin':'https://evil.invalid'}) as ws:
        assert ws.receive_json()['code']=='ORIGIN_DENIED'
    staff_user.is_active=False;db.commit()
    with app_client.websocket_connect('/api/asr/stream',headers={'origin':'http://testserver'}) as ws:
        ws.send_json({'type':'auth','ticket':ticket})
        assert ws.receive_json()['code']=='AUTH_REQUIRED'
    staff_user.is_active=True;db.commit()
    with app_client.websocket_connect('/api/asr/stream',headers={'origin':'http://testserver'}) as ws:
        ws.send_json({'type':'auth','ticket':ticket})
        assert ws.receive_json()['code']=='AUTH_REQUIRED'


def test_endpoint_allowlist_and_pcm_limits():
    from app.services.asr_stream import valid_endpoint,AudioBudget
    assert valid_endpoint('wss://workspace-id.cn-beijing.maas.aliyuncs.com/api-ws/v1/inference')
    for url in ['ws://dashscope.aliyuncs.com/api-ws/v1/inference','wss://127.0.0.1/api-ws/v1/inference','wss://dashscope.aliyuncs.com.evil.invalid/api-ws/v1/inference','wss://user:secret@dashscope.aliyuncs.com/api-ws/v1/inference','wss://dashscope.aliyuncs.com/api-ws/v1/inference?key=secret']:
        assert not valid_endpoint(url)
    budget=AudioBudget(0)
    budget.accept(bytes(3200),.1)
    with pytest.raises(ValueError):budget.accept(b'odd',.2)
    with pytest.raises(ValueError):budget.accept(bytes(32002),.3)
    with pytest.raises(ValueError):budget.accept(bytes(16000),80)


def test_sentence_revisions_replace_not_append():
    from app.services.asr_stream import Transcript
    t=Transcript()
    assert t.apply({'begin_time':0,'end_time':None,'text':'我想'})=='我想'
    assert t.apply({'begin_time':0,'end_time':1000,'text':'我想训练'})=='我想训练'
    assert t.apply({'begin_time':1100,'end_time':None,'text':'左手'})=='我想训练左手'
    assert t.apply({'begin_time':1100,'end_time':2000,'text':'右手'})=='我想训练右手'


@pytest.fixture(autouse=True)
def clear_tickets():
    from app.api import asr
    asr._tickets.clear();asr._issued.clear();asr._active.clear()
    yield
    asr._tickets.clear();asr._issued.clear();asr._active.clear()


class FakeProvider:
    def __init__(self, fail=False):
        import asyncio
        self.queue=asyncio.Queue();self.sent=[];self.closed=False;self.fail=fail
    async def __aenter__(self):return self
    async def __aexit__(self,*args):self.closed=True
    async def send(self,data):
        self.sent.append(data)
        if isinstance(data,bytes):
            for text,final in [('左',False),('左手训练',True)]:
                await self.queue.put(json.dumps({'header':{'event':'result-generated'},'payload':{'output':{'sentence':{'sentence_id':1,'begin_time':0,'text':text,'sentence_end':final}}}}))
            return
        action=json.loads(data)['header']['action']
        kind='task-started' if action=='run-task' else 'task-finished'
        await self.queue.put(json.dumps({'header':{'event':'task-failed' if self.fail else kind,'error_message':'test-secret-do-not-return'}}))
    async def recv(self):return await self.queue.get()


def test_provider_protocol_final_results_and_cleanup(app_client,staff_user,monkeypatch):
    configured(monkeypatch)
    from app.services import asr_stream
    fake=FakeProvider();monkeypatch.setattr(asr_stream,'open_provider',lambda:fake)
    ticket=app_client.post('/api/asr/tickets',headers=headers(staff_user)).json()['ticket']
    with app_client.websocket_connect('/api/asr/stream',headers={'origin':'http://testserver'}) as ws:
        ws.send_json({'type':'auth','ticket':ticket});assert ws.receive_json()=={'type':'ready'}
        ws.send_bytes(bytes(3200))
        assert ws.receive_json()['text']=='左'
        assert ws.receive_json()['text']=='左手训练'
        ws.send_json({'type':'stop'});assert ws.receive_json()=={'type':'done'}
    assert fake.closed
    run=json.loads(fake.sent[0]);assert run['payload']['parameters']=={'format':'pcm','sample_rate':16000}
    assert json.loads(fake.sent[-1])['header']['action']=='finish-task'
    assert run['header']['task_id']==json.loads(fake.sent[-1])['header']['task_id']


@pytest.mark.parametrize('action',['cancel','disconnect','invalid_audio','provider_fail'])
def test_abort_and_failure_release_slot_without_secret(app_client,staff_user,monkeypatch,action):
    configured(monkeypatch)
    from app.api import asr
    from app.services import asr_stream
    fake=FakeProvider(fail=action=='provider_fail');monkeypatch.setattr(asr_stream,'open_provider',lambda:fake)
    ticket=app_client.post('/api/asr/tickets',headers=headers(staff_user)).json()['ticket']
    with app_client.websocket_connect('/api/asr/stream',headers={'origin':'http://testserver'}) as ws:
        ws.send_json({'type':'auth','ticket':ticket})
        message=ws.receive_json()
        if action=='provider_fail':assert message=={'type':'error','code':'STREAM_FAILED'}
        else:
            assert message=={'type':'ready'}
            if action=='cancel':ws.send_json({'type':'cancel'});assert ws.receive()['type']=='websocket.close'
            elif action=='invalid_audio':ws.send_bytes(b'odd');assert ws.receive_json()=={'type':'error','code':'STREAM_FAILED'}
    assert fake.closed and not asr._active


def test_ticket_expiry_rate_and_per_user_connection_limit(app_client,staff_user,monkeypatch):
    configured(monkeypatch)
    from app.api import asr
    from app.services import asr_stream
    fake=FakeProvider();monkeypatch.setattr(asr_stream,'open_provider',lambda:fake)
    auth=headers(staff_user)
    first=app_client.post('/api/asr/tickets',headers=auth).json()['ticket']
    second=app_client.post('/api/asr/tickets',headers=auth).json()['ticket']
    with app_client.websocket_connect('/api/asr/stream',headers={'origin':'http://testserver'}) as ws:
        ws.send_json({'type':'auth','ticket':first});assert ws.receive_json()['type']=='ready'
        with app_client.websocket_connect('/api/asr/stream',headers={'origin':'http://testserver'}) as duplicate:
            duplicate.send_json({'type':'auth','ticket':second});assert duplicate.receive_json()['code']=='BUSY'
        assert staff_user.id in asr._active
        ws.send_json({'type':'cancel'});ws.receive()
    expired=app_client.post('/api/asr/tickets',headers=auth).json()['ticket']
    asr._tickets[expired]=(staff_user.id,0)
    with app_client.websocket_connect('/api/asr/stream',headers={'origin':'http://testserver'}) as ws:
        ws.send_json({'type':'auth','ticket':expired});assert ws.receive_json()['code']=='AUTH_REQUIRED'
    for _ in range(3):assert app_client.post('/api/asr/tickets',headers=auth).status_code==200
    assert app_client.post('/api/asr/tickets',headers=auth).status_code==429


def test_id_survives_revised_timestamp_and_final_cannot_regress():
    from app.services.asr_stream import Transcript
    t=Transcript()
    t.apply({'sentence_id':1,'begin_time':0,'text':'我','sentence_end':False})
    assert t.apply({'sentence_id':1,'begin_time':170,'text':'我想训练','sentence_end':True})=='我想训练'
    assert t.apply({'sentence_id':1,'begin_time':0,'text':'我','sentence_end':False})=='我想训练'
    assert t.apply({'sentence_id':0,'heartbeat':True})=='我想训练'


def test_secure_config_probe_failure_never_replaces_existing_key(tmp_path,monkeypatch,capsys):
    import importlib.util,sys
    from pathlib import Path
    spec=importlib.util.spec_from_file_location('configure_asr_test',Path(__file__).parents[2]/'scripts/configure_asr.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    monkeypatch.setattr(module,'settings',settings.model_copy())
    output=tmp_path/'.asr.env';output.write_text('old configuration')
    monkeypatch.setattr(sys.stdin,'isatty',lambda:True)
    monkeypatch.setattr(sys,'argv',['configure_asr.py','--output',str(output)])
    monkeypatch.setattr('builtins.input',lambda _: '')
    monkeypatch.setattr(module.getpass,'getpass',lambda _: 'test-key-never-print-12345')
    async def fail():raise ValueError('test-key-never-print-12345')
    monkeypatch.setattr(module,'probe',fail)
    with pytest.raises(SystemExit) as error:module.main()
    assert output.read_text()=='old configuration'
    assert 'test-key-never-print' not in str(error.value)+capsys.readouterr().out


def test_active_account_revocation_stops_stream_and_frees_connection(app_client,staff_user,db,monkeypatch):
    configured(monkeypatch)
    from app.api import asr
    from app.services import asr_stream
    fake=FakeProvider();monkeypatch.setattr(asr_stream,'open_provider',lambda:fake)
    ticket=app_client.post('/api/asr/tickets',headers=headers(staff_user)).json()['ticket']
    with app_client.websocket_connect('/api/asr/stream',headers={'origin':'http://testserver'}) as ws:
        ws.send_json({'type':'auth','ticket':ticket});assert ws.receive_json()['type']=='ready'
        staff_user.is_active=False;db.commit()
        ws.send_bytes(bytes(3200));assert ws.receive_json()=={'type':'error','code':'AUTH_REQUIRED'}
    assert fake.closed and not asr._active


def test_secure_config_success_is_ignored_and_never_prints_key(tmp_path,monkeypatch,capsys):
    import importlib.util,sys,subprocess
    from pathlib import Path
    root=Path(__file__).parents[2]
    spec=importlib.util.spec_from_file_location('asr_config_success',root/'scripts/configure_asr.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    monkeypatch.setattr(module,'settings',settings.model_copy())
    output=tmp_path/'.asr.env'
    monkeypatch.setattr(sys.stdin,'isatty',lambda:True)
    monkeypatch.setattr(sys,'argv',['configure_asr.py','--output',str(output)])
    monkeypatch.setattr('builtins.input',lambda _: '')
    monkeypatch.setattr(module.getpass,'getpass',lambda _: 'test-key-never-print-12345')
    async def probe():pass
    monkeypatch.setattr(module,'probe',probe)
    module.main()
    assert 'ASR_API_KEY=test-key-never-print-12345' in output.read_text()
    assert 'test-key-never-print' not in capsys.readouterr().out
    assert subprocess.run(['git','check-ignore','-q','backend/.asr.env'],cwd=root).returncode==0


def test_config_probe_accepts_startup_without_requiring_an_empty_audio_result(monkeypatch):
    import asyncio,importlib.util
    from pathlib import Path
    spec=importlib.util.spec_from_file_location('asr_probe_test',Path(__file__).parents[2]/'scripts/configure_asr.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    fake=FakeProvider()
    async def only_startup():
        if len(fake.sent)>1:raise ValueError('Provider may reject zero audio finish')
        return await fake.queue.get()
    fake.recv=only_startup
    monkeypatch.setattr(module,'open_provider',lambda:fake)
    asyncio.run(module.probe())
    assert fake.closed and len(fake.sent)==1
