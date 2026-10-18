def test_stale_patient_patch_is_rejected_and_unrelated_fields_survive(app_client,auth_headers,patient_payload):
    first=app_client.post('/api/patients',headers=auth_headers,json={**patient_payload,'last_medication_time':'2026-10-17T09:30:00+08:00'}).json()
    url='/api/patients/'+first['id']
    saved=app_client.patch(url,headers=auth_headers,json={'doctor_notes':'另一位医生已更新','expected_updated_at':first['updated_at']})
    assert saved.status_code==200
    stale=app_client.patch(url,headers=auth_headers,json={'phone':'000','expected_updated_at':first['updated_at']})
    assert stale.status_code==409
    latest=app_client.get(url,headers=auth_headers).json()
    assert latest['doctor_notes']=='另一位医生已更新' and latest['phone']==patient_payload['phone']
    assert latest['last_medication_time'].startswith('2026-10-17T01:30:00')


def test_required_patient_fields_cannot_be_cleared_by_patch(app_client,auth_headers,patient_payload):
    row=app_client.post('/api/patients',headers=auth_headers,json=patient_payload).json()
    for key in ['name','sex','dominant_hand','affected_side','medication_state']:
        response=app_client.patch('/api/patients/'+row['id'],headers=auth_headers,json={key:None})
        assert response.status_code==422
