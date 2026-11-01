from sqlalchemy import select,func
from app.db.models import AssessmentSession,Patient,MicroExpressionResult
from app.services import assessment_service

def records(db,staff_user):
    p=Patient(hospital_number='exit-qa',name='Exit test')
    db.add(p);db.flush()
    rows=[AssessmentSession(patient_id=p.id,session_type='MICRO_EXPRESSION_ONLY',status=status,created_by=staff_user.id) for status in ['IN_PROGRESS','COMPLETED']]
    db.add_all(rows);db.commit()
    return p,rows

def test_exit_is_idempotent_and_preserves_completed_results(app_client,auth_headers,db,staff_user):
    p,rows=records(db,staff_user)
    db.add(MicroExpressionResult(assessment_session_id=rows[1].id,model_name='TEST_ONLY'));db.commit()
    for _ in range(2):
        assert app_client.post(f'/api/assessment-sessions/{rows[0].id}/discard',headers=auth_headers).status_code==200
    reply=app_client.post(f'/api/assessment-sessions/{rows[1].id}/discard',headers=auth_headers)
    assert reply.status_code==200 and reply.json()['deleted'] is False
    assert db.scalar(select(func.count()).select_from(MicroExpressionResult))==1

def test_discard_requires_auth(app_client,db,staff_user):
    _,rows=records(db,staff_user)
    assert app_client.post(f'/api/assessment-sessions/{rows[0].id}/discard').status_code==401

def test_history_opens_without_patient_and_contains_completed_results(app_client,auth_headers,db,staff_user):
    p,rows=records(db,staff_user)
    reply=app_client.get('/api/assessment-sessions/history',headers=auth_headers)
    assert reply.status_code==200
    data=reply.json()
    assert data['total']==1 and data['items'][0]['id']==rows[1].id
    assert data['items'][0]['patient_name']==p.name
    assert app_client.get('/api/assessment-sessions/history').status_code==401
    assert app_client.get('/api/assessment-sessions/history?patient_id=missing',headers=auth_headers).json()['total']==0

def test_single_face_completion_requires_result_and_does_not_complete_comprehensive(db,staff_user):
    p,rows=records(db,staff_user)
    assessment_service.complete_single_module(db,rows[0])
    assert rows[0].status=='IN_PROGRESS'
    db.add(MicroExpressionResult(assessment_session_id=rows[0].id,model_name='TEST_ONLY'));db.flush()
    assessment_service.complete_single_module(db,rows[0])
    assert rows[0].status=='COMPLETED'
    comprehensive=AssessmentSession(patient_id=p.id,session_type='COMPREHENSIVE',status='IN_PROGRESS')
    db.add(comprehensive);db.flush()
    db.add(MicroExpressionResult(assessment_session_id=comprehensive.id,model_name='TEST_ONLY'));db.flush()
    assessment_service.complete_single_module(db,comprehensive)
    assert comprehensive.status=='IN_PROGRESS'

def test_heartbeat_refreshes_only_unfinished_assessments(app_client,auth_headers,db,staff_user):
    from datetime import timedelta
    from app.db.base import utcnow
    _,rows=records(db,staff_user)
    old=utcnow()-timedelta(minutes=3)
    for row in rows:row.updated_at=old
    db.commit()
    assert app_client.post(f'/api/assessment-sessions/{rows[0].id}/heartbeat').status_code==401
    reply=app_client.post(f'/api/assessment-sessions/{rows[0].id}/heartbeat',headers=auth_headers)
    assert reply.status_code==200 and reply.json()['active']
    db.expire_all();assert db.get(AssessmentSession,rows[0].id).updated_at>old
    app_client.post(f'/api/assessment-sessions/{rows[1].id}/heartbeat',headers=auth_headers)
    db.expire_all();assert db.get(AssessmentSession,rows[1].id).updated_at==old

def test_stale_cleanup_preserves_heartbeat_and_completed_results(db,staff_user):
    from datetime import timedelta
    from app.db.base import utcnow
    from app.services.assessment_lifecycle import expire_abandoned
    p,rows=records(db,staff_user)
    old=utcnow()-timedelta(minutes=3)
    for row in rows:row.updated_at=old
    fresh=AssessmentSession(patient_id=p.id,session_type='COMPREHENSIVE',status='IN_PROGRESS')
    db.add(fresh);db.commit()
    ids=[r.id for r in rows];fresh_id=fresh.id
    assert expire_abandoned(db,utcnow()-timedelta(seconds=90))==1
    db.expire_all()
    assert db.get(AssessmentSession,ids[0]) is None
    assert db.get(AssessmentSession,ids[1]) is not None
    assert db.get(AssessmentSession,fresh_id) is not None
