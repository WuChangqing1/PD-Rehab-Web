from sqlalchemy import select

from app.db.models import ExternalPracticeRecord, Patient


def test_feed_cursor_binding_and_tombstone(app_client, auth_headers, staff_user, db, engine):
    from app.services.sync_changes import install
    with engine.begin() as connection:
        install(connection)
    staff_user.role = 'ADMIN'
    patient = Patient(hospital_number='sync-qa', name='QA', sex='UNKNOWN')
    db.add(patient)
    db.commit()
    context = dict(patient_id=patient.id, device_id='device-sync-1', local_profile_id='profile-sync-1')
    base = '/api/integration/v1'
    bind = app_client.post(base+'/bindings', json=context, headers=auth_headers)
    assert bind.status_code == 200
    path = base+'/changes'
    empty = app_client.get(path, params=context, headers=auth_headers)
    assert empty.status_code == 200 and empty.json()['items'] == []
    cursor = empty.json()['next_cursor']
    for i in range(3):
        assert app_client.post(base+'/records', headers=auth_headers, json={
            **context, 'source_record_id':f'qa-{i}', 'record_type':'PIANO_SESSION',
            'schema_version':'test', 'payload':{'metric':i},
        }).status_code == 201
    first = app_client.get(path, params={**context,'cursor':cursor,'limit':2}, headers=auth_headers).json()
    assert app_client.post(base+'/records', headers=auth_headers, json={
        **context, 'source_record_id':'qa-during-pagination', 'record_type':'PIANO_SESSION',
        'schema_version':'test', 'payload':{'metric':3},
    }).status_code == 201
    second = app_client.get(path, params={**context,'cursor':first['next_cursor'],'limit':2}, headers=auth_headers).json()
    assert first['has_more'] and not second['has_more']
    items = first['items'] + second['items']
    assert len({item['id'] for item in items}) == 4
    cursor = second['next_cursor']
    row = db.scalar(select(ExternalPracticeRecord).where(ExternalPracticeRecord.id==items[0]['id']))
    db.delete(row); db.commit()
    gone = app_client.get(path, params={**context,'cursor':cursor}, headers=auth_headers).json()
    assert gone['items'] == [{'kind':'external_practice_records','id':items[0]['id'],'deleted':True}]
    assert app_client.get(path, params={**context,'cursor':cursor+'x'}, headers=auth_headers).status_code == 409
    second_patient = Patient(hospital_number='sync-qa-other', name='QA Other', sex='UNKNOWN')
    db.add(second_patient); db.commit()
    other = {**context, 'patient_id':second_patient.id, 'local_profile_id':'other-profile'}
    assert app_client.post(base+'/bindings', json=other, headers=auth_headers).status_code == 200
    assert app_client.get(path, params={**other,'cursor':gone['next_cursor']}, headers=auth_headers).status_code == 409
    assert app_client.delete(base+'/bindings/'+bind.json()['binding_id'], headers=auth_headers).status_code == 200
    assert app_client.get(path, params={**context,'cursor':gone['next_cursor']}, headers=auth_headers).status_code == 403
