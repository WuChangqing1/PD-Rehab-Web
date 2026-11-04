"""Contract tests for Flutter/Web reconciliation using isolated test DB."""
from __future__ import annotations

import pytest
from app.db.models import Patient

@pytest.fixture(autouse=True)
def integration_admin(staff_user,db):
    staff_user.role="ADMIN";db.commit()


def _patient(db):
    row = Patient(hospital_number='P900001', name='Integration Patient',
                  sex='UNKNOWN', medication_state='UNKNOWN')
    db.add(row); db.commit(); db.refresh(row)
    return row


def test_bootstrap_auth_and_no_secrets(app_client, auth_headers, staff_user, db):
    patient = _patient(db)
    assert app_client.get('/api/integration/v1/bootstrap').status_code == 401
    result = app_client.get('/api/integration/v1/bootstrap', headers=auth_headers)
    assert result.status_code == 200, result.text
    body = result.json()
    assert any(item['id'] == patient.id for item in body['patients'])
    assert any(item['id'] == staff_user.id for item in body['staff'])
    assert 'password_hash' not in str(body)


def test_binding_and_idempotent_sync(app_client, auth_headers, db):
    patient = _patient(db)
    base = {'device_id':'device-abcdefghij', 'local_profile_id':'local-profile-abcdefgh',
            'patient_id':patient.id}
    unbound = app_client.post('/api/integration/v1/records', headers=auth_headers, json={
        **base, 'source_record_id':'session-1', 'record_type':'PIANO_SESSION',
        'schema_version':'flutter-v4', 'payload':{'status':'COMPLETED','accuracy':0.0}})
    assert unbound.status_code == 403, unbound.text
    link = app_client.post('/api/integration/v1/bindings', headers=auth_headers, json=base)
    assert link.status_code == 200, link.text
    payload = {**base,'source_record_id':'session-1','record_type':'PIANO_SESSION',
               'schema_version':'flutter-v4','payload':{'status':'COMPLETED','accuracy':0.0}}
    first = app_client.post('/api/integration/v1/records', headers=auth_headers, json=payload)
    assert first.status_code == 201, first.text
    assert first.json()['already_synced'] is False
    retry = app_client.post('/api/integration/v1/records', headers=auth_headers, json=payload)
    assert retry.status_code == 201 and retry.json()['already_synced'] is True
    assert retry.json()['id'] == first.json()['id']
    modified = app_client.post('/api/integration/v1/records', headers=auth_headers,
                               json={**payload,'payload':{'status':'COMPLETED','accuracy':1.0}})
    assert modified.status_code == 409
    rows = app_client.get('/api/integration/v1/records', headers=auth_headers,
                          params={'patient_id':patient.id,'include_payload':'true'}).json()['items']
    assert len(rows) == 1
    assert rows[0]['payload']['accuracy'] == 0.0
    snapshot = app_client.get('/api/integration/v1/patient-data', headers=auth_headers,
                              params={'patient_id':patient.id})
    assert snapshot.status_code == 200, snapshot.text
    assert len(snapshot.json()['categories']['external_practice_records']) == 1


def test_binding_cannot_reassign_patient(app_client, auth_headers, db):
    first = _patient(db)
    second = Patient(hospital_number='P900002', name='Another Patient', sex='UNKNOWN')
    db.add(second); db.commit();db.refresh(second)
    base = {'device_id':'device-abcdefghij','local_profile_id':'local-profile-abcdefgh'}
    assert app_client.post('/api/integration/v1/bindings', headers=auth_headers,
                           json={**base,'patient_id':first.id}).status_code == 200
    assert app_client.post('/api/integration/v1/bindings', headers=auth_headers,
                           json={**base,'patient_id':second.id}).status_code == 409


def test_face_model_cannot_fabricate_results(app_client, auth_headers, db):
    patient = _patient(db)
    link = {'device_id':'device-abcdefghij','local_profile_id':'local-profile-abcdefgh',
            'patient_id':patient.id}
    app_client.post('/api/integration/v1/bindings', headers=auth_headers, json=link)
    capabilities = app_client.get('/api/integration/v1/capabilities', headers=auth_headers)
    assert capabilities.status_code == 200
    if not capabilities.json()['face_model_ready']:
        response = app_client.post('/api/integration/v1/face/jobs',headers=auth_headers,
            data=link, files={'video':('face.mp4',b'not-real-video','video/mp4')})
        assert response.status_code == 503, response.text


def test_ai_without_provider_fails_transparently(app_client, auth_headers):
    from app.core.config import settings
    if not settings.expert_llm_api_key:
        response = app_client.post('/api/integration/v1/expert/chat',
            headers=auth_headers, json={'question':'这个无法匹配的查询是什么？'})
        assert response.status_code == 503
        assert response.json()['error']['code'] == 'MODEL_NOT_CONFIGURED'

def test_plan_snapshots_group_progress_and_keep_raw_history(app_client, auth_headers, db):
    patient = _patient(db)
    root = '/api/integration/v1'
    scope = {'patient_id': patient.id, 'device_id': 'device-plan-test', 'local_profile_id': 'profile-plan-test'}
    assert app_client.post(root+'/bindings', headers=auth_headers, json=scope).status_code == 200
    def upload(units, revision):
        body = {**scope, 'record_type': 'TRAINING_PLAN', 'source_record_id': f'plan-123:{revision}',
                'schema_version': 'flutter-v4', 'payload': {
                    'record': {'plan_id': 'plan-123', 'plan_json': '{"title":"123","start":"2026-11-03"}'},
                    'daily_progress': [{'local_date':'2026-11-03','completed_units':units,'target':2,'target_type':'count'}],
                    'snapshot_revision': revision}}
        r = app_client.post(root+'/records', headers=auth_headers, json=body)
        assert r.status_code == 201, r.text
        return r.json()
    first = upload(1, 1)
    params = {'patient_id':patient.id,'on_date':'2026-11-03','limit':1}
    def plans(**extra):
        r = app_client.get(root+'/plans', headers=auth_headers, params={**params, **extra})
        assert r.status_code == 200, r.text
        return r.json()
    assert plans()['items'][0]['progress']['completed_units'] == 1
    second = upload(2, 3)
    assert upload(2, 3)['already_synced']
    upload(1, 2)  # Offline, older revision arrives last.
    result = plans()
    assert result['next_offset'] is None
    row = result['items'][0]
    assert row['id'] == second['id'] and row['version_count'] == 3
    assert row['progress']['completed_units'] == 2 and row['plan_start'] == '2026-11-03'
    assert plans(on_date='2026-11-04')['items'][0]['progress'] is None
    history = plans(snapshot_id=second['id'],limit=10)
    assert len(history['items']) == 3
    raw = app_client.get(root+'/records/'+first['id'], headers=auth_headers, params={'patient_id':patient.id})
    assert raw.json()['payload']['daily_progress'][0]['completed_units'] == 1
