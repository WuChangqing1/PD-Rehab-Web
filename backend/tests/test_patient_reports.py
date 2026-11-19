from app.services.patient_report import report_sections, render_patient_pdf, report_filename


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
