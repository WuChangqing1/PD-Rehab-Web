from app.services.patient_report import report_sections, render_patient_pdf, report_filename, metric_trends


def payload(records=None):
    return {'patient': {'id': 'patient-1', 'name': '张三（测试）', 'hospital_number': 'P-001'},
            'date_range': {'start_date': '2025-12-31', 'end_date': '2026-01-01', 'timezone': 'Asia/Shanghai'},
            'records': records or {}, 'integrity': {'sha256': 'abc'}}


def test_separates_native_mobile_versions_and_excludes_private_domains():
    data = payload({'piano_sessions': [
        {'id': '1', 'metrics_version': 'v1', 'input_source': 'HUMAN_KEYBOARD', 'accuracy': 10},
        {'id': '2', 'metrics_version': 'v2', 'input_source': 'HUMAN_KEYBOARD', 'accuracy': 90}],
        'external_practice_records': [{'id': '3', 'metric_version': 'app-v3', 'record_type': 'dance', 'origin': 'PianoForParkinson'}],
        'expert_chat_turns': [{'question': 'private question'}]})
    sections = report_sections(data)
    assert len(sections) == 3
    assert {s['version'] for s in sections} == {'v1', 'v2', 'app-v3'}
    assert 'private question' not in str(sections)


def test_pdf_empty_and_large_are_a4_multipage():
    empty = render_patient_pdf(payload())
    assert empty.startswith(b'%PDF-')
    data = payload({'piano_sessions': [{'id': str(n), 'metrics_version': 'v1', 'completed_at': '2026-01-01T01:00:00', 'accuracy': n} for n in range(300)]})
    large = render_patient_pdf(data)
    assert large.count(b'/Type /Page\n') > 1
    assert b'595.2756 841.8898' in large
    assert report_filename(data) == 'patient-P-001-2025-12-31_2026-01-01.pdf'
    assert render_patient_pdf(payload({'external_practice_records':[{'id':'long','payload_json':{'notes':'中文长字段测试'*1800}}]})).startswith(b'%PDF-')


def test_filename_cannot_inject_headers_or_paths():
    data = payload(); data['patient']['hospital_number'] = '../../bad\r\nname'
    assert '/' not in report_filename(data)
    assert '\r' not in report_filename(data)


def test_report_date_boundaries_share_inclusive_business_filter():
    from datetime import date, datetime
    from app.services.business_export import date_bounds
    assert date_bounds(date(2025,12,31),date(2026,1,1)) == (datetime(2025,12,30,16),datetime(2026,1,1,16))
    assert date_bounds(date(2026,2,28),date(2026,2,28)) == (datetime(2026,2,27,16),datetime(2026,2,28,16))
    assert date_bounds(None,None) == (None,None)


def metric_row(identifier, value, at, **changes):
    return {'id':identifier,'accuracy':value,'completed_at':at,'mode':'SINGLE_KEY_RHYTHM',
            'metrics_version':'v1','input_source':'HUMAN_KEYBOARD','bpm':60,
            'judgement_window_ms':300,'sequence_length':4,'note_density':1,'hand_mode':'SINGLE',
            'weak_side_ratio':0.5,'finger_complexity':1,'session_duration_sec':60,
            'difficulty_before_json':{'cue_lead_ms':700}, **changes}


def test_trends_separate_config_version_source_and_sort_actual_chronology():
    rows=[metric_row('late',0.9,'2026-01-03T00:00:00'), metric_row('early',0.2,'2026-01-01T00:00:00'),
          metric_row('fast',0.8,'2026-01-02T00:00:00',bpm=90),
          metric_row('other-version',0.7,'2026-01-02T00:00:00',metrics_version='v2'),
          metric_row('seed',0.99,'2026-01-02T00:00:00',input_source='SEED_DEMO'),
          metric_row('other-recipe',0.5,'2026-01-02T00:00:00',recipe_id='OTHER')]
    trends=metric_trends(payload({'piano_sessions':rows}))
    assert len(trends)==4
    main=next(t for t in trends if len(t['points'])==2)
    assert [p['id'] for p in main['points']]==['early','late']
    assert main['latest']==0.9 and main['previous']==0.2
    assert round(main['delta'],5)==0.7
    assert main['unit']=='比例 (0-1)'
    assert all(p['id']!='seed' for t in trends for p in t['points'])
    assert render_patient_pdf(payload({'piano_sessions':rows})).startswith(b'%PDF-')


def test_missing_nonfinite_boolean_interrupted_and_unknown_version_do_not_become_zero_trend():
    rows=[metric_row('null',None,'2026-01-01T00:00:00'),
          metric_row('nan',float('nan'),'2026-01-01T00:00:00'),
          metric_row('bool',False,'2026-01-01T00:00:00'),
          metric_row('unfinished',0.5,None),
          metric_row('interrupted',0.5,'2026-01-01T00:00:00',difficulty_before_json={'completion_status':'INTERRUPTED'}),
          metric_row('unknown',0.7,'2026-01-01T00:00:00',metrics_version=None),
          metric_row('zero',0,'2026-01-02T00:00:00')]
    trends=metric_trends(payload({'piano_sessions':rows}))
    assert len(trends)==1
    assert trends[0]['latest']==0 and trends[0]['previous'] is None
    assert trends[0]['delta'] is None
    assert [p['id'] for p in trends[0]['points']]==['zero']


def test_incomplete_configuration_is_never_assumed_compatible_and_server_metric_is_authoritative():
    rows=[metric_row('a',0.8,'2026-01-01T00:00:00',difficulty_before_json={}),
          metric_row('b',0.9,'2026-01-02T00:00:00',difficulty_before_json={}),
          metric_row('server',0.6,'2026-01-03T00:00:00',difficulty_before_json={'cue_lead_ms':700,'server_metrics':{'accuracy':0}})]
    trends=metric_trends(payload({'piano_sessions':rows}))
    assert len(trends)==3
    assert all(len(t['points'])==1 and t['delta'] is None for t in trends)
    assert next(t for t in trends if t['points'][0]['id']=='server')['latest']==0


def test_face_result_requires_completed_authorized_assessment():
    sections = report_sections(payload({'assessment_sessions': [
        {'id':'done','status':'COMPLETED'}, {'id':'pending','status':'PROCESSING'}],
        'micro_expression_results': [{'id':'1','assessment_session_id':'done'},
                                     {'id':'2','assessment_session_id':'pending'}]}))
    face = [s for s in sections if s['title']=='已完成面部分析结果']
    assert [r['id'] for s in face for r in s['rows']] == ['1']


def test_report_api_denies_revoked_and_patient_role_and_downloads(db, staff_user):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.api.patient_reports import router
    from app.api.deps import get_current_user
    from app.db.session import get_db
    from app.db.models import Patient, PatientAccessGrant
    patient = Patient(name='测试患者',hospital_number='PDF-001')
    db.add(patient);db.commit()
    app = FastAPI();app.include_router(router,prefix='/api')
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: staff_user
    with TestClient(app) as client:
        url=f'/api/patients/{patient.id}/report.pdf'
        response=client.get(url)
        assert response.status_code == 200, response.text
        assert response.content.startswith(b'%PDF-')
        assert response.headers['cache-control']=='no-store'
        grant=PatientAccessGrant(patient_id=patient.id,staff_user_id=staff_user.id,active=False)
        db.add(grant);db.commit()
        assert client.get(url).status_code==403
        staff_user.role='PATIENT';db.commit()
        assert client.get(url).status_code==403
